package dev.dizygotic.dizytv

import android.util.Xml
import org.json.JSONArray
import org.json.JSONObject
import org.xmlpull.v1.XmlPullParser
import java.net.HttpURLConnection
import java.net.URL
import java.io.ByteArrayInputStream
import java.util.zip.GZIPInputStream
import java.io.InputStream
import java.io.ByteArrayOutputStream

object Feeds {
    private const val LIMIT=32*1024*1024
    private fun bounded(input:InputStream):ByteArray {
        val out=ByteArrayOutputStream(); val buffer=ByteArray(8192)
        while(true) { val n=input.read(buffer); if(n<0) break; require(out.size()+n<=LIMIT) { "Feed exceeds 32 MiB" }; out.write(buffer,0,n) }
        return out.toByteArray()
    }
    fun download(url:String):String {
        var next=Domain.http(url)
        repeat(6) {
            val connection=URL(next).openConnection() as HttpURLConnection
            connection.instanceFollowRedirects=false; connection.connectTimeout=15000; connection.readTimeout=20000
            connection.setRequestProperty("User-Agent","DizyTV/0.1"); connection.setRequestProperty("Accept-Encoding","identity")
            try {
                if(connection.responseCode in 300..399) {
                    next=Domain.http(URL(URL(next),connection.getHeaderField("Location")?:throw IllegalArgumentException("Missing redirect URL")).toString())
                } else {
                    require(connection.responseCode==200) { "Feed returned HTTP ${connection.responseCode}" }
                    val bytes=connection.inputStream.use { bounded(it) }
                    val expanded=if(bytes.size>=2 && bytes[0]==0x1f.toByte() && bytes[1]==0x8b.toByte()) GZIPInputStream(ByteArrayInputStream(bytes)).use { bounded(it) } else bytes
                    require(expanded.size<=LIMIT); return expanded.toString(Charsets.UTF_8).trimStart('\uFEFF')
                }
            } finally { connection.disconnect() }
        }
        throw IllegalArgumentException("Too many feed redirects")
    }
    fun xmltv(text:String,offset:Int):JSONObject {
        require(text.toByteArray().size<=LIMIT && !text.uppercase().contains("<!ENTITY")) { "XML entities or oversized guide are not allowed" }
        val names=JSONObject(); val programmes=JSONArray(); val parser=Xml.newPullParser(); parser.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES,false); parser.setInput(text.reader())
        var channel:String?=null; var programme:JSONObject?=null; var rootSeen=false
        while(parser.eventType!=XmlPullParser.END_DOCUMENT) {
            if(parser.eventType==XmlPullParser.START_TAG && !rootSeen) { require(parser.name=="tv") { "Expected an XMLTV document" }; rootSeen=true }
            if(parser.eventType==XmlPullParser.START_TAG) when(parser.name) {
                "tv" -> Unit
                "channel" -> channel=parser.getAttributeValue(null,"id")
                "display-name" -> { val value=parser.nextText(); channel?.let { names.put(it,value.take(512)) } }
                "programme" -> programme=runCatching {
                    val start=Domain.xmlTime(parser.getAttributeValue(null,"start"))+offset*60; val end=Domain.xmlTime(parser.getAttributeValue(null,"stop"))+offset*60
                    require(end>start)
                    val id=parser.getAttributeValue(null,"channel"); require(!id.isNullOrBlank())
                    JSONObject().put("channel",id).put("start",start).put("end",end).put("title","Untitled").put("description","").put("categories",JSONArray())
                }.getOrNull()
                "title" -> { val value=parser.nextText(); programme?.put("title",value.take(1024)) }
                "desc" -> { val value=parser.nextText(); programme?.put("description",value.take(8192)) }
                "category" -> { val value=parser.nextText(); programme?.getJSONArray("categories")?.let { if(it.length()<32) it.put(value.take(512)) } }
            }
            if(parser.eventType==XmlPullParser.END_TAG) when(parser.name) {
                "channel" -> channel=null
                "programme" -> { programme?.let { programmes.put(it) }; programme=null; require(programmes.length()<=200000) { "Too many guide programmes" } }
            }
            parser.next()
        }
        require(rootSeen) { "Empty XMLTV document" }; return JSONObject().put("names",names).put("programmes",programmes)
    }
}
