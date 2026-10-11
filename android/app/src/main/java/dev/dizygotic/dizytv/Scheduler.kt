package dev.dizygotic.dizytv

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.net.Uri
import org.json.JSONObject
import java.time.Instant

object Scheduler {
    private fun alarm(context:Context)=context.getSystemService(AlarmManager::class.java)
    fun exactAllowed(context:Context)=Build.VERSION.SDK_INT<31 || alarm(context).canScheduleExactAlarms()
    private fun pending(context:Context,id:String):PendingIntent {
        val intent=Intent(context,TimerReceiver::class.java).setData(Uri.parse("dizytv://timer/$id")).putExtra("job_id",id)
        return PendingIntent.getBroadcast(context,0,intent,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }
    fun arm(context:Context,job:JSONObject) {
        require(exactAllowed(context)) { "Grant exact-alarm access, then try scheduling again" }
        alarm(context).setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,maxOf(System.currentTimeMillis()+1000,job.getLong("start")*1000),pending(context,job.getString("id")))
    }
    fun cancel(context:Context,id:String)=alarm(context).cancel(pending(context,id))
    fun recover(context:Context) {
        val store=DeviceStore(context); val now=Instant.now().epochSecond
        val state=store.update { s->Domain.objects(s.getJSONArray("jobs")).forEach { j->
            if(j.getString("status") in Domain.active && j.getLong("end")<=now) j.put("status",if(j.optLong("bytes")>0) "partial" else "missed").put("error","Timer expired while recorder was unavailable")
        } }
        for(j in Domain.objects(state.getJSONArray("jobs"))) if(j.getString("status") in Domain.active) {
            runCatching { arm(context,j) }.onFailure { e->store.job(j.getString("id")) { it.put("status","paused").put("error",e.message) } }
        }
    }
}

class TimerReceiver:BroadcastReceiver() {
    override fun onReceive(context:Context,intent:Intent) {
        val id=intent.getStringExtra("job_id")?:return
        try { context.startForegroundService(Intent(context,RecordingService::class.java).putExtra("job_id",id)) }
        catch(e:Exception) { DeviceStore(context).job(id) { it.put("status","failed").put("error",e.message) } }
    }
}

class BootReceiver:BroadcastReceiver() {
    override fun onReceive(context:Context,intent:Intent) {
        if(intent.action==Intent.ACTION_BOOT_COMPLETED || intent.action==Intent.ACTION_MY_PACKAGE_REPLACED) runCatching { Scheduler.recover(context) }
    }
}
