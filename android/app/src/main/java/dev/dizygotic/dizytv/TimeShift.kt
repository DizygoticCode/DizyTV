package dev.dizygotic.dizytv

import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URI
import java.net.URL
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min

/** Temporary, quota-bounded MPEG-TS segments. No permanent files are written. */
internal class TimeshiftRing(
    val directory:File,
    val minutes:Int,
    val quota:Long,
    private val reserve:Long,
    private val clock:()->Long={System.currentTimeMillis()},
    private val free:()->Long={directory.usableSpace}
) {
    data class Part(val seq:Long,val created:Long,val duration:Double,val size:Long,val path:File)
    private val parts=ArrayDeque<Part>()
    private var nextSeq=0L
    private var bytes=0L
    private var closed=false

    init {
        require(minutes in 1..240) { "Timeshift length must be 1–240 minutes" }
        require(quota in 256L*1024*1024..32L*1024*1024*1024) { "Timeshift quota must be 256 MiB–32 GiB" }
        require(directory.isDirectory || directory.mkdirs()) { "Cannot create local timeshift directory" }
    }

    @Synchronized fun append(data:ByteArray,duration:Double):Part {
        check(!closed) { "Timeshift has stopped" }
        require(data.isNotEmpty() && data.size<=16*1024*1024) { "Invalid segment size" }
        require(duration>=0.1 && duration<=30.0) { "Invalid segment duration" }
        prune()
        require(free()>max(reserve,1024L*1024*1024)+data.size+32L*1024*1024) {
            "Not enough free device space for timeshift"
        }
        val id=nextSeq++
        val temp=File(directory,id.toString()+".part")
        val file=File(directory,id.toString()+".ts")
        temp.writeBytes(data)
        require(temp.renameTo(file)) { "Unable to save timeshift segment" }
        val segment=Part(id,clock(),duration,data.size.toLong(),file)
        parts.addLast(segment)
        bytes+=segment.size
        prune()
        return segment
    }

    @Synchronized private fun prune() {
        while(parts.isNotEmpty() && (bytes>quota || clock()-parts.first().created>minutes*60000L ||
               free()<max(reserve,1024L*1024*1024)+32L*1024*1024)) {
            val expired=parts.removeFirst()
            bytes-=expired.size
            expired.path.delete()
        }
    }

    @Synchronized fun snapshot():List<Part> { prune();return parts.toList() }
    @Synchronized fun availableSeconds():Double=parts.sumOf { it.duration }
    @Synchronized fun currentBytes():Long=bytes
    @Synchronized fun seqAgo(seconds:Double):Long? {
        var remaining=max(0.0,seconds)
        for(segment in parts.toList().asReversed()) {
            remaining-=segment.duration
            if(remaining<=0) return segment.seq
        }
        return parts.firstOrNull()?.seq
    }
    @Synchronized fun manifest(start:Long?=null):String {
        val selected=if(start==null) parts.takeLast(3) else parts.filter { it.seq>=start }
        if(selected.isEmpty()) return ""
        val result=StringBuilder("#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:")
        result.append(ceil(selected.maxOf { it.duration }).toInt().coerceAtLeast(1))
        result.append("\n#EXT-X-MEDIA-SEQUENCE:").append(selected.first().seq).append('\n')
        if(start!=null) result.append("#EXT-X-START:TIME-OFFSET=0,PRECISE=YES\n")
        selected.forEach { part ->
            result.append("#EXTINF:").append(String.format(java.util.Locale.ROOT,"%.3f",part.duration))
                .append(",\ns/").append(part.seq).append(".ts\n")
        }
        return result.toString()
    }
    @Synchronized fun find(seq:Long):File?=parts.firstOrNull { it.seq==seq }?.path
    @Synchronized fun close() {
        if(closed)return
        closed=true
        parts.forEach { it.path.delete() }
        parts.clear()
        bytes=0
        directory.listFiles()?.filter { it.name.endsWith(".part") }?.forEach { it.delete() }
        directory.delete()
    }
}

/** One-user, one-channel loopback HLS relay for clear MPEG-TS / HLS-TS. */
internal class DeviceTimeshift(
    private val origin:String,cacheRoot:File,minutes:Int,quota:Long,reserve:Long
) {
    private val token=UUID.randomUUID().toString()
    val ring=TimeshiftRing(File(cacheRoot,"session-"+token),minutes,quota,reserve)
    private val stopped=AtomicBoolean(false)
    private val ready=CountDownLatch(1)
    @Volatile private var error:String?=null
    @Volatile private var active:HttpURLConnection?=null
    private var listener:ServerSocket?=null
    val liveUrl:String get()=url("live.m3u8")
    private fun url(path:String):String {
        val port=listener?.localPort?:throw IllegalStateException("Timeshift not started")
        return "http://127.0.0.1:"+port+"/"+token+"/"+path
    }
    fun replayUrl(secondsAgo:Double):String {
        val seq=ring.seqAgo(secondsAgo)?:throw IllegalStateException("Buffer is not ready")
        return url("replay.m3u8?seq="+seq)
    }

    private fun open(url:String):HttpURLConnection {
        val p=URI(url)
        require(p.scheme in listOf("http","https") && p.host!=null) { "Timeshift supports HTTP(S) only" }
        return (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout=10000;readTimeout=10000
            setRequestProperty("User-Agent","DizyTV/0.1")
        }
    }
    private fun smallDownload(url:String,maxSize:Int):Pair<String,ByteArray> {
        val conn=open(url);active=conn
        try {
            conn.inputStream.use { input->
                val result=ByteArrayOutputStream()
                val buf=ByteArray(65536)
                while(!stopped.get()) {
                    val count=input.read(buf)
                    if(count<0)break
                    result.write(buf,0,count)
                    require(result.size()<=maxSize) { "Segment exceeds 16 MiB" }
                }
                return conn.url.toString() to result.toByteArray()
            }
        } finally { conn.disconnect();active=null }
    }
    private fun hlsFeed(initial:String) {
        var source=initial
        val downloaded=LinkedHashSet<String>()
        while(!stopped.get()) {
            try {
                val (playlistUrl,bytes)=smallDownload(source,2*1024*1024)
                val lines=bytes.toString(Charsets.UTF_8).trimStart('\uFEFF')
                    .lineSequence().map { it.trim() }.filter { it.isNotEmpty() }.toList()
                require(lines.firstOrNull()=="#EXTM3U") { "Invalid HLS source" }
                require(lines.none { it.startsWith("#EXT-X-KEY:") && !it.contains("METHOD=NONE") }) {
                    "Encrypted HLS isn't supported by local timeshift"
                }
                require(lines.none { it.startsWith("#EXT-X-MAP:") }) {
                    "Fragmented-MP4 HLS isn't supported by local timeshift"
                }
                val variant=lines.indexOfFirst { it.startsWith("#EXT-X-STREAM-INF:") }
                if(variant>=0) {
                    val target=lines.getOrNull(variant+1)?:throw IllegalArgumentException("HLS variant missing")
                    source=URI(playlistUrl).resolve(target).toString()
                    continue
                }
                var duration=4.0
                for(line in lines) {
                    if(stopped.get())break
                    if(line.startsWith("#EXTINF:")) {
                        duration=(line.substringAfter(':').substringBefore(',').toDoubleOrNull()?:4.0)
                            .coerceIn(0.1,30.0)
                    } else if(!line.startsWith('#')) {
                        val segment=URI(playlistUrl).resolve(line).toString()
                        if(segment in downloaded)continue
                        val data=smallDownload(segment,16*1024*1024).second
                        require(data.isNotEmpty() && data[0]==0x47.toByte()) {
                            "Only HLS with MPEG-TS segments is supported"
                        }
                        ring.append(data,duration)
                        downloaded.add(segment)
                        if(downloaded.size>10000) downloaded.remove(downloaded.first())
                        ready.countDown()
                    }
                }
                if(!stopped.get())Thread.sleep(1500)
            } catch(e:Exception) {
                error=e.message
                if(ring.snapshot().isEmpty()){ready.countDown();return}
                if(!stopped.get())Thread.sleep(2000)
            }
        }
    }
    private fun tsFeed() {
        while(!stopped.get()) {
            val conn=open(origin);active=conn
            try {
                conn.inputStream.use { input->
                    if(conn.contentType.orEmpty().contains("mpegurl") ||
                        conn.url.path.lowercase().endsWith(".m3u8")) {
                        val source=conn.url.toString()
                        conn.disconnect();active=null
                        hlsFeed(source);return
                    }
                    val data=ByteArrayOutputStream()
                    val block=ByteArray(188*1024)
                    var started=System.nanoTime()
                    while(!stopped.get()) {
                        val n=input.read(block)
                        if(n<0)break
                        if(n==0)continue
                        if(data.size()==0) require(block[0]==0x47.toByte()) { "Not a direct MPEG-TS stream" }
                        data.write(block,0,n)
                        val duration=(System.nanoTime()-started)/1e9
                        if(duration>=4.0 || data.size()>=8*1024*1024) {
                            ring.append(data.toByteArray(),max(0.1,duration))
                            ready.countDown()
                            data.reset();started=System.nanoTime()
                        }
                    }
                }
            } catch(e:Exception) {
                error=e.message
                if(ring.snapshot().isEmpty()){ready.countDown();return}
                if(!stopped.get())Thread.sleep(2000)
            } finally { conn.disconnect();active=null }
        }
    }

    private fun ingest() {
        try {
            if(URI(origin).path.lowercase().endsWith(".m3u8"))hlsFeed(origin) else tsFeed()
        } catch(e:Exception){error=e.message;ready.countDown()}
    }

    private fun serve(socket:Socket) {
        socket.use { client ->
            client.soTimeout=4000
            val reader=client.getInputStream().bufferedReader(Charsets.US_ASCII)
            val request=reader.readLine()?.split(' ')?:return
            var line=reader.readLine()
            var count=0
            while(line!=null && line.isNotEmpty() && count++<60)line=reader.readLine()
            val route=request.getOrNull(1)?:return
            val prefix="/"+token+"/"
            if(request.firstOrNull()!="GET" || !route.startsWith(prefix))return
            val path=route.removePrefix(prefix).substringBefore('?')
            val payload:ByteArray
            val mime:String
            if(path=="live.m3u8" || path=="replay.m3u8") {
                val seq=if(path=="replay.m3u8")route.substringAfter("seq=","").toLongOrNull() else null
                if(path=="replay.m3u8" && seq==null)return
                val manifest=ring.manifest(seq)
                if(manifest.isEmpty())return
                payload=manifest.toByteArray(Charsets.US_ASCII)
                mime="application/vnd.apple.mpegurl"
            } else if(path.startsWith("s/") && path.endsWith(".ts")) {
                val seq=path.removePrefix("s/").removeSuffix(".ts").toLongOrNull()?:return
                val file=ring.find(seq)?:return
                if(!file.isFile)return
                payload=file.readBytes()
                mime="video/mp2t"
            } else return
            val header="HTTP/1.1 200 OK\r\nContent-Type: "+mime+"\r\nContent-Length: "+
                payload.size+"\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n"
            val out=client.getOutputStream()
            out.write(header.toByteArray(Charsets.US_ASCII))
            out.write(payload)
            out.flush()
        }
    }

    fun start():String {
        try {
            listener=ServerSocket(0,30,InetAddress.getByName("127.0.0.1"))
            Thread({
                while(!stopped.get()) {
                    try {
                        val client=listener?.accept()?:break
                        Thread({runCatching { serve(client) }},"timeshift-client").apply { isDaemon=true;start() }
                    } catch(_:Exception) { if(stopped.get())break }
                }
            },"timeshift-loopback").apply { isDaemon=true;start() }
            Thread({ingest()},"timeshift-capture").apply { isDaemon=true;start() }
            require(ready.await(18,TimeUnit.SECONDS) && ring.snapshot().isNotEmpty()) {
                error?:"No usable live segments were received"
            }
            return liveUrl
        } catch(e:Exception) { close();throw e }
    }

    fun close() {
        stopped.set(true)
        active?.disconnect()
        runCatching { listener?.close() }
        listener=null
        ring.close()
    }
}
