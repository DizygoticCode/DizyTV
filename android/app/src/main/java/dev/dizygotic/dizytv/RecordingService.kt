package dev.dizygotic.dizytv

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.system.Os
import androidx.documentfile.provider.DocumentFile
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import org.json.JSONObject

class RecordingService:Service() {
    private val running=AtomicBoolean(false); private val stopping=AtomicBoolean(false)
    private val executor=Executors.newSingleThreadExecutor(); private var current:String?=null
    private var wake:PowerManager.WakeLock?=null
    override fun onBind(intent:Intent?):IBinder?=null
    override fun onCreate() {
        super.onCreate()
        getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("recording","DizyTV recordings",NotificationManager.IMPORTANCE_LOW))
    }
    private fun notification(title:String):Notification {
        val stop=PendingIntent.getService(this,1,Intent(this,RecordingService::class.java).setAction("stop"),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this,"recording").setSmallIcon(R.drawable.ic_record).setContentTitle("DizyTV is recording").setContentText(title).setOngoing(true).setContentIntent(open).addAction(Notification.Action.Builder(null,"Stop",stop).build()).build()
    }
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        if(intent?.action=="stop") { stopping.set(true); return START_NOT_STICKY }
        val id=intent?.getStringExtra("job_id")?:run { stopSelf(); return START_NOT_STICKY }
        if(!running.compareAndSet(false,true)) {
            if(current!=id) DeviceStore(this).job(id) { it.put("status","failed").put("error","Another recording is already running") }
            return START_NOT_STICKY
        }
        current=id; stopping.set(false)
        if(Build.VERSION.SDK_INT>=34) startForeground(1,notification("Starting…"),ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE) else startForeground(1,notification("Starting…"))
        wake=getSystemService(PowerManager::class.java).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"DizyTV:recording").also { it.acquire(24*60*60*1000L) }
        executor.execute { try { record(id) } finally { if(wake?.isHeld==true) wake?.release(); running.set(false); current=null; stopForeground(STOP_FOREGROUND_REMOVE); stopSelf() } }
        return START_NOT_STICKY
    }
    private fun record(id:String) {
        val store=DeviceStore(this); var bytes=0L; var document:DocumentFile?=null; var status="failed"; var error=""; var connection:HttpURLConnection?=null; var accepted=false
        try {
            val state=store.read(); val job=Domain.objects(state.getJSONArray("jobs")).firstOrNull { it.getString("id")==id }?:return
            if(job.getString("status") !in Domain.active) return
            accepted=true
            val now=Instant.now().epochSecond
            if(job.getLong("end")<=now) { status="missed"; error="Timer already expired"; return }
            val late=now-job.getLong("start")>5 || job.getString("status")=="recording"
            val settings=state.getJSONObject("settings"); val uri=Uri.parse(settings.getString("recording_dir"))
            require(uri.scheme=="content" && contentResolver.persistedUriPermissions.any { it.uri==uri && it.isWritePermission }) { "Choose a recording folder again; storage permission is unavailable" }
            val folder=DocumentFile.fromTreeUri(this,uri)?:throw IllegalArgumentException("Recording folder unavailable")
            require(folder.canWrite()) { "Recording folder is not writable" }
            val channel=Domain.objects(state.getJSONArray("channels")).firstOrNull { it.getString("id")==job.getString("channel_id") }?:throw IllegalArgumentException("Channel missing")
            store.job(id) { it.put("status","recording").put("bytes",0).put("error","") }
            getSystemService(NotificationManager::class.java).notify(1,notification(job.getString("title")))
            document=folder.createFile("video/mp2t",Domain.filename(job.getString("title"),now))?:throw IllegalArgumentException("Could not create recording file")
            store.job(id) { it.put("uri",document.uri.toString()) }
            val url=Domain.stream(channel,settings)
            connection=URL(url).openConnection() as HttpURLConnection; connection.connectTimeout=10000; connection.readTimeout=10000
            require(connection.responseCode==200) { "Engine returned HTTP ${connection.responseCode}" }
            val type=connection.contentType.orEmpty().lowercase(); require(!listOf("mpegurl","text/","json","html").any { type.contains(it) }) { "Recording requires direct MPEG-TS output" }
            val descriptor=contentResolver.openFileDescriptor(document.uri,"w")?:throw IllegalArgumentException("Storage permission denied")
            descriptor.use { fd->
                fun free():Long?=runCatching { val stat=Os.fstatvfs(fd.fileDescriptor); stat.f_bavail*stat.f_frsize }.getOrNull()
                val reserve=settings.getLong("reserve_bytes"); require(free()?.let { it>reserve }!=false) { "Free space is below reserve" }
                java.io.FileOutputStream(fd.fileDescriptor).use { output->
                    connection.inputStream.use { input->
                        val buffer=ByteArray(65536); var first=true; var last=0L
                        while(Instant.now().epochSecond<job.getLong("end")) {
                            if(stopping.get() || Domain.objects(store.read().getJSONArray("jobs")).none { it.getString("id")==id && it.getString("status")=="recording" }) throw IllegalArgumentException("Recording stopped by user")
                            require(free()?.let { it>reserve }!=false) { "Recording stopped at the storage reserve" }
                            val n=input.read(buffer); require(n>0) { "Stream ended before timer" }
                            if(first) { require(buffer[0]==0x47.toByte()) { "Engine did not return MPEG-TS" }; first=false }
                            output.write(buffer,0,n); bytes+=n
                            if(Instant.now().epochSecond-last>=2) { store.job(id) { it.put("bytes",bytes) }; last=Instant.now().epochSecond }
                        }
                        output.flush()
                    }
                }
            }
            status=if(bytes>0 && !late) "completed" else if(bytes>0) "partial" else "failed"
            if(late) error="Recording started late or resumed after interruption"
        } catch(e:Exception) { status=if(bytes>0) "partial" else "failed"; error=e.message.orEmpty().take(1024) }
        finally {
            connection?.disconnect()
            if(bytes==0L) document?.delete()
            if(accepted) store.job(id) { it.put("status",status).put("bytes",bytes).put("error",error); if(bytes==0L) it.remove("uri") }
            sendBroadcast(Intent("dev.dizygotic.dizytv.STATE_CHANGED").setPackage(packageName))
        }
    }
    override fun onDestroy() { stopping.set(true); executor.shutdown(); super.onDestroy() }
}
