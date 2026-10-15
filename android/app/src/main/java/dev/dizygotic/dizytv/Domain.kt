package dev.dizygotic.dizytv

import org.json.JSONArray
import org.json.JSONObject
import java.net.URI
import java.net.URLDecoder
import java.net.URLEncoder
import java.security.MessageDigest
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.ResolverStyle
import java.util.Locale
import java.util.UUID

object Domain {
    const val MAX_BACKUP=16*1024*1024
    val terminal=setOf("completed","partial","failed","cancelled","missed")
    val active=setOf("queued","starting","recording")
    private val countries=mapOf("GB" to "United Kingdom","UK" to "United Kingdom","US" to "United States","USA" to "United States","CA" to "Canada","AU" to "Australia","NZ" to "New Zealand","IE" to "Ireland","FR" to "France","DE" to "Germany","ES" to "Spain","IT" to "Italy","PT" to "Portugal","NL" to "Netherlands","BE" to "Belgium","CH" to "Switzerland","AT" to "Austria","PL" to "Poland","CZ" to "Czechia","SE" to "Sweden","NO" to "Norway","DK" to "Denmark","FI" to "Finland","GR" to "Greece","TR" to "Turkey","UA" to "Ukraine","RU" to "Russia","IN" to "India","PK" to "Pakistan","BR" to "Brazil","MX" to "Mexico","AR" to "Argentina","JP" to "Japan","CN" to "China","KR" to "South Korea","ZA" to "South Africa","IL" to "Israel","AE" to "United Arab Emirates")
    private val genres=listOf("Sport" to "sports?","News" to "news|current affairs","Movies" to "movies?|films?|cinema","Kids" to "kids|children|cartoons?","Music" to "music","Documentary" to "documentar(?:y|ies)|factual","Entertainment" to "entertainment","Education" to "education","General" to "general")
    fun normaliseGenre(value:String)=genres.firstOrNull { Regex("\\b(?:${it.second})\\b",RegexOption.IGNORE_CASE).containsMatchIn(value) }?.first?:value.trim().take(512).ifEmpty { "Unspecified" }

    /** Display-only labels; IDs, original names and streams are never edited. */
    fun displayName(raw:String):String {
        var value=raw.replace(Regex("[\\u200B-\\u200D\\uFEFF\\x00-\\x1F\\x7F]"),"").trim()
            .replace(Regex("[ⒼⓈⓎⓐ-ⓩ]"),"").trim()
        val marker=Regex("(?:\\s*[@#]\\s*(?:HD|SD|FHD|UHD|4K|2160P|1080P|720P|480P|50FPS|60FPS|UK|GB|US|USA|LIVE)\\b|\\s*[@#]\\s*$|\\s*[\\[(](?:HD|SD|FHD|UHD|4K|2160P|1080P|720P)[\\])])+$",RegexOption.IGNORE_CASE)
        repeat(8) {
            val cleaned=value.replace(marker,"").trim()
            if(cleaned==value) return@repeat
            value=cleaned
        }
        return value.replace(Regex("\\s+")," ").ifEmpty { "Unnamed channel" }
    }

    fun isShowLoop(ch:JSONObject):Boolean {
        if(ch.optString("kind")=="Radio") return false
        val name=displayName(ch.optString("name")).lowercase()
        val group=ch.optString("group").lowercase()
        if(Regex("""\b(?:news|sport|sports|football|cricket|radio|music|weather|racing)\b""",RegexOption.IGNORE_CASE).containsMatchIn(name+" "+group)) return false
        val shows=listOf("south park","rick and morty","family guy","simpsons","futurama",
            "brooklyn 99","brooklyn nine nine","goldbergs","big bang theory",
            "young sheldon","frasier","cheers","mr bean","friends","midsomer murders",
            "only fools and horses","pluto tv sitcoms","comedy movies","comedy series",
            "drama series","classic tv comedy")
        val normal=name.replace(Regex("""[^a-z0-9 ]""")," ").replace(Regex("""\s+""")," ").trim()
        val named=shows.any { show ->
            if(show=="friends") normal=="friends" || normal.contains("247 friends") || normal.contains("24 7 friends")
            else Regex("""(?<!\w)"""+Regex.escape(show)+"""(?!\w)""").containsMatchIn(normal)
        }
        val tagged=Regex("""(?i)\b(?:24\s*/\s*7|247|24[- ]hour|marathon|non[- ]stop|binge[- ]?watch|loops?)\b""")
            .containsMatchIn(name+" "+group)
        return named || tagged
    }

    fun section(ch:JSONObject):String {
        if(ch.optString("kind")=="Radio") return "Radio"
        if(isShowLoop(ch)) return "24/7 Shows & Loops"
        val genre=normaliseGenre(ch.optString("genre"))
        if(genre in setOf("Sport","News","Movies","Kids","Music","Documentary","Entertainment","Education")) return genre
        val label=displayName(ch.optString("name"))+" "+ch.optString("group")
        val patterns=listOf(
            "News" to "\\b(?:news|headlines?|weather)\\b",
            "Sport" to "\\b(?:sports?|football|cricket|racing|nba|nfl|golf)\\b",
            "Movies" to "\\b(?:movies?|cinema|films?)\\b",
            "Kids" to "\\b(?:kids|children|cartoons?|junior)\\b",
            "Music" to "\\b(?:music|concert)\\b",
            "Documentary" to "\\b(?:documentar(?:y|ies)|factual|history|nature)\\b",
            "Education" to "\\b(?:education|learning)\\b",
            "Entertainment" to "\\b(?:entertainment|comedy|drama)\\b"
        )
        return patterns.firstOrNull { Regex(it.second,RegexOption.IGNORE_CASE).containsMatchIn(label) }?.first?:"General TV"
    }

    private fun categories(attrs:Map<String,String>,stream:String,name:String):JSONObject {
        val group=attrs["group-title"].orEmpty(); val explicit=(attrs["tvg-country"]?:attrs["country"]).orEmpty().trim()
        val aliases=countries+countries.values.associateWith { it }
        val country=if(explicit.isNotEmpty()) countries[explicit.uppercase()]?:explicit else aliases.entries.sortedByDescending { it.key.length }.firstOrNull { Regex("(?<!\\w)"+Regex.escape(it.key)+"(?!\\w)",RegexOption.IGNORE_CASE).containsMatchIn(group) }?.value?:Regex("\\[([A-Za-z]{2,3})\\]").findAll(name.ifEmpty { attrs["tvg-name"].orEmpty() }).firstNotNullOfOrNull { countries[it.groupValues[1].uppercase()] }?:"Unspecified"
        val explicitGenre=(attrs["tvg-genre"]?:attrs["genre"]).orEmpty(); val genre=if(explicitGenre.isNotEmpty()) normaliseGenre(explicitGenre) else normaliseGenre(group).takeIf { g->genres.any { it.first==g } }?:"Unspecified"
        return JSONObject().put("country",country).put("genre",genre).put("kind",if(attrs["radio"].orEmpty().lowercase() in listOf("true","1","yes")) "Radio" else "TV").put("transport",if(aceId(stream)!=null) "Ace Stream" else "HTTP")
    }
    fun defaults()=JSONObject("""{"settings":{"playlist_url":"https://search-ace.stream/playlist","xmltv_urls":[],"engine_url":"http://127.0.0.1:6878","timezone":"auto","epg_offset_minutes":0,"padding_before":2,"padding_after":5,"reserve_bytes":1073741824,"recording_dir":"","timeshift_enabled":false,"timeshift_minutes":30,"timeshift_max_bytes":4294967296},"channels":[],"favourites":[],"mappings":{},"jobs":[]}""").apply {
        getJSONObject("settings").put("playlist_urls",JSONArray(Sources.presets)).put("xmltv_urls",JSONArray(Sources.guides))
    }
    fun catalogue(state:JSONObject)=objects(state.getJSONArray("channels")).map { original->
        val channel=JSONObject(original.toString()); val saved=state.optJSONObject("category_overrides")?.optJSONObject(channel.getString("id"))
        saved?.keys()?.forEach { channel.put(it,saved.get(it)) }; channel
    }
    fun objects(array:JSONArray)=(0 until array.length()).map { array.getJSONObject(it) }
    fun strings(array:JSONArray)=(0 until array.length()).map { array.getString(it) }
    fun http(value:String):String {
        require(value.length<=8192 && value.none { it.code<32 }) { "Invalid URL" }
        val u=URI(value)
        require(u.scheme in listOf("http","https") && !u.host.isNullOrEmpty() && u.userInfo==null) { "Use an HTTP(S) URL without credentials" }
        return value
    }
    fun aceId(value:String):String? {
        val uri=URI(value)
        val candidate=if(uri.scheme=="acestream") uri.host?:uri.path.trimStart('/') else {
            uri.rawQuery.orEmpty().split('&').map { it.split('=',limit=2) }.firstOrNull { it.size==2 && it[0] in listOf("id","infohash","content_id") }?.get(1).orEmpty()
        }
        return candidate.lowercase().takeIf { it.matches(Regex("[a-f0-9]{40}")) }
    }
    fun stream(channel:JSONObject,settings:JSONObject):String {
        val value=channel.getString("stream"); val id=aceId(value)
        return if(id!=null) http(settings.getString("engine_url")).trimEnd('/')+"/ace/getstream?id=$id" else http(value)
    }
    fun playlist(text:String):JSONArray {
        require(text.toByteArray().size<=32*1024*1024) { "Playlist exceeds 32 MiB" }
        val result=JSONArray(); val seen=mutableSetOf<String>(); var name=""; var attrs=mapOf<String,String>()
        for(raw in text.trimStart('\uFEFF').lineSequence()) {
            val line=raw.trim()
            if(line.startsWith("#EXTINF:")) {
                name=line.substringAfter(',',"")
                attrs=Regex("""([\w-]+)="([^"]*)"""").findAll(line.substringBefore(',')).associate { it.groupValues[1] to it.groupValues[2] }
            } else if(line.isNotEmpty() && !line.startsWith('#')) {
                val aid=runCatching { aceId(line) }.getOrNull()
                if(aid==null && runCatching { http(line) }.isFailure) { attrs=emptyMap(); name=""; continue }
                val id=aid?:MessageDigest.getInstance("SHA-256").digest(line.toByteArray()).joinToString("") { "%02x".format(it) }.take(40)
                if(seen.add(id)) {
                    val ch=JSONObject().put("id",id).put("name",name.ifEmpty { attrs["tvg-name"]?:id }.take(512)).put("group",attrs["group-title"].orEmpty().take(512)).put("tvg_id",attrs["tvg-id"].orEmpty().take(512)).put("stream",if(aid!=null) "acestream://$aid" else line)
                    val c=categories(attrs,line,name); c.keys().forEach { ch.put(it,c.get(it)) }; result.put(ch)
                }
                attrs=emptyMap(); name=""
            }
        }
        require(result.length() in 1..100000) { "No supported channels found; cached catalogue retained" }
        return result
    }
    fun xmlTime(value:String):Long {
        val m=Regex("(\\d{14})(?:\\s+([+-]\\d{4}|Z|UTC|GMT))?").matchEntire(value.trim())?:throw IllegalArgumentException("Invalid XMLTV time")
        val offset=m.groupValues[2].takeIf { it.isNotEmpty() && it !in listOf("Z","UTC","GMT") }?:"+0000"
        return OffsetDateTime.parse(m.groupValues[1]+" "+offset,DateTimeFormatter.ofPattern("uuuuMMddHHmmss XX").withResolverStyle(ResolverStyle.STRICT)).toEpochSecond()
    }
    private fun guideName(raw:String):String = raw
        .replace(Regex("[ⒼⓈⓎⓐ-ⓩ]"),"")
        .replace(Regex("\\s*\\((?:\\d{3,4}p|HD|SD|FHD|4K)\\)",RegexOption.IGNORE_CASE),"")
        .replace(Regex("\\s+(?:HD|SD|FHD|4K)$",RegexOption.IGNORE_CASE),"")
        .trim().replace(Regex("\\s+")," ").lowercase(Locale.ROOT)

    fun matchGuide(ch:JSONObject,mappings:JSONObject,names:JSONObject):String {
        val id=ch.getString("id")
        if(mappings.has(id)) return mappings.getString(id) // Respect explicit No mapping.
        val tvg=ch.optString("tvg_id")
        if(names.has(tvg)) return tvg
        val keys=names.keys().asSequence().toList()
        if(tvg.isNotEmpty()) keys.filter { it.equals(tvg,true) }.singleOrNull()?.let { return it }
        val base=tvg.substringBefore('@')
        if(base!=tvg) keys.filter { it.equals(base,true) }.singleOrNull()?.let { return it }
        // Only aliases with one correct guide target. BBC One / ITV1 are regional.
        val aliases=mapOf("bbctwo.uk" to "BBCTwoHD.uk","bbcfour.uk" to "BBCFourHD.uk","channel5.uk" to "5.uk")
        aliases[base.lowercase()]?.let { alias->
            keys.filter { it.equals(alias,true) }.singleOrNull()?.let { return it }
        }
        val normalized=guideName(ch.getString("name"))
        return keys.filter { guideName(names.optString(it))==normalized }.singleOrNull()?:tvg
    }

    fun zone(value:String)=if(value=="auto") ZoneId.systemDefault() else ZoneId.of(value)
    fun time(seconds:Long,timezone:String,short:Boolean=false)=DateTimeFormatter.ofPattern(if(short) "HH:mm z" else "EEE dd MMM HH:mm z",Locale.UK).withZone(zone(timezone)).format(Instant.ofEpochSecond(seconds))
    fun job(channel:String,title:String,start:Long,end:Long,before:Int=2,after:Int=5):JSONObject {
        require(end>start && before>=0 && after>=0)
        return JSONObject().put("id",UUID.randomUUID().toString()).put("channel_id",channel).put("title",title.take(1024)).put("start",start-before*60).put("end",end+after*60).put("status","queued").put("bytes",0)
    }
    fun overlap(a:JSONObject,b:JSONObject)=a.getString("id")!=b.getString("id") && a.getString("status") in active && a.getLong("start")<b.getLong("end") && b.getLong("start")<a.getLong("end")
    fun segmentBytes(job:JSONObject)=objects(job.optJSONArray("segments")?:JSONArray()).sumOf { it.optLong("bytes") }
    fun recordingUris(job:JSONObject)=(objects(job.optJSONArray("segments")?:JSONArray()).map { it.optString("uri") }+job.optString("uri")).filter { it.isNotEmpty() }.distinct()
    fun claim(job:JSONObject,now:Long):Boolean {
        if(job.getString("status") !in active) return false
        if(job.getLong("end")<=now) { job.put("status",if(job.optLong("bytes")>0) "partial" else "missed").put("error","Timer expired while waiting for recorder"); return false }
        if(job.getLong("start")>now) return false
        job.put("resume_late",now-job.getLong("start")>5 || job.getString("status") in listOf("starting","recording"))
        val segments=job.optJSONArray("segments")?:JSONArray()
        for(key in listOf("uri","path")) {
            val previous=job.optString(key)
            if(previous.isNotEmpty() && objects(segments).none { it.optString(key)==previous }) segments.put(JSONObject().put(key,previous).put("bytes",maxOf(0,job.optLong("bytes")-segmentBytes(job))).put("status","partial"))
            job.remove(key)
        }
        job.put("segments",segments).put("status","recording").put("bytes",segmentBytes(job)).put("error","")
        return true
    }
    fun finish(job:JSONObject,result:JSONObject) {
        val previous=segmentBytes(job); val newBytes=result.optLong("bytes"); val bytes=previous+newBytes
        var status=result.getString("status"); var error=result.optString("error")
        if(previous>0 || job.optBoolean("resume_late") && status=="completed") { if(bytes>0) status="partial"; if(error.isEmpty()) error="Recording resumed after interruption or started late" }
        if(job.getString("status")=="cancelled" && bytes==0L) { status="cancelled"; error="Recording stopped by user" }
        job.put("status",status).put("bytes",bytes).put("error",error)
        if(newBytes>0 && result.has("uri")) job.put("uri",result.getString("uri")) else job.remove("uri")
    }
    fun filename(title:String,now:Long)=DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").withZone(ZoneId.of("UTC")).format(Instant.ofEpochSecond(now))+"_"+title.replace(Regex("[<>:\"/\\\\|?*\\x00-\\x1f]"),"_").trim(' ','.').take(90).ifEmpty { "Recording" }+".ts"
    private fun number(o:JSONObject,key:String,min:Long,max:Long) {
        val n=o.get(key); require((n is Int || n is Long) && o.getLong(key) in min..max) { "Invalid $key" }
    }
    fun validate(s:JSONObject):JSONObject {
        try {
            val settings=s.getJSONObject("settings")
            http(settings.getString("playlist_url")); http(settings.getString("engine_url"))
            val urls=settings.getJSONArray("xmltv_urls"); require(urls.length()<=20); strings(urls).forEach { http(it) }
            if(settings.has("playlist_urls")) {
                val playlistUrls=settings.getJSONArray("playlist_urls")
                require(playlistUrls.length() in 1..16) { "Configure between 1 and 16 playlist URLs" }
                strings(playlistUrls).forEach { http(it) }
            }
            zone(settings.getString("timezone")); number(settings,"epg_offset_minutes",-1440,1440)
            number(settings,"padding_before",0,240); number(settings,"padding_after",0,240); number(settings,"reserve_bytes",0,1125899906842624)
            require(settings.getString("recording_dir").length<=4096)
            if(settings.has("timeshift_enabled")) require(settings.get("timeshift_enabled") is Boolean)
            if(settings.has("timeshift_minutes")) number(settings,"timeshift_minutes",1,240)
            if(settings.has("timeshift_max_bytes")) number(settings,"timeshift_max_bytes",256L*1024*1024,32L*1024*1024*1024)
            val channels=s.getJSONArray("channels"); require(channels.length()<=100000); val ids=mutableSetOf<String>()
            for(ch in objects(channels)) {
                require(ch.getString("id").matches(Regex("[a-f0-9]{40}")) && ids.add(ch.getString("id")))
                for(k in listOf("name","group","tvg_id","stream")) require(ch.get(k) is String)
                if(ch.has("source")) http(ch.getString("source"))
                for(k in listOf("country","genre","kind","transport")) if(ch.has(k)) require(ch.get(k) is String && ch.getString(k).length<=512)
                if(aceId(ch.getString("stream"))==null) http(ch.getString("stream"))
            }
            val favourites=s.getJSONArray("favourites"); require(favourites.length()<=100000); strings(favourites).forEach { require(it.matches(Regex("[a-f0-9]{40}"))) }
            val maps=s.getJSONObject("mappings"); require(maps.length()<=100000); maps.keys().forEach { require(maps.get(it) is String && maps.getString(it).length<=512) }
            if(s.has("category_overrides")) {
                val overrides=s.getJSONObject("category_overrides"); require(overrides.length()<=100000)
                overrides.keys().forEach { cid->
                    require(cid.matches(Regex("[a-f0-9]{40}"))); val values=overrides.getJSONObject(cid)
                    values.keys().forEach { key->require(key in listOf("country","genre","kind") && values.get(key) is String && values.getString(key).isNotBlank() && values.getString(key).length<=512) }
                    require(values.optString("kind","TV") in listOf("TV","Radio"))
                }
            }
            val jobs=s.getJSONArray("jobs"); require(jobs.length()<=10000); val jobIds=mutableSetOf<String>()
            for(j in objects(jobs)) {
                require(j.get("id") is String && j.getString("id").length<=100 && jobIds.add(j.getString("id")))
                require(j.getString("status") in active+terminal+"paused" && j.get("title") is String && j.getString("title").length<=1024)
                require(j.getString("channel_id").matches(Regex("[a-f0-9]{40}")))
                number(j,"start",0,253402300799); number(j,"end",1,253402300799); require(j.getLong("end")>j.getLong("start"))
            }
            return s
        } catch(e:Exception) { throw IllegalArgumentException("Invalid DizyTV data: ${e.message}",e) }
    }
    private fun redact(url:String):String {
        val u=URI(url); val query=u.rawQuery?:return url
        val safe=query.split('&').filterNot { Regex("token|key|pass|secret|auth|signature",RegexOption.IGNORE_CASE).containsMatchIn(URLDecoder.decode(it.substringBefore('='),"UTF-8")) }
        return url.substringBefore('?')+(if(safe.isEmpty()) "" else "?"+safe.joinToString("&"))
    }
    fun backup(state:JSONObject):String {
        val data=JSONObject(validate(state).toString()); val settings=data.getJSONObject("settings"); settings.put("recording_dir","")
        for(k in listOf("playlist_url","engine_url")) settings.put(k,redact(settings.getString(k)))
        settings.put("xmltv_urls",JSONArray(strings(settings.getJSONArray("xmltv_urls")).map { redact(it) }))
        if(settings.has("playlist_urls")) settings.put("playlist_urls",JSONArray(strings(settings.getJSONArray("playlist_urls")).map { redact(it) }))
        objects(data.getJSONArray("channels")).forEach { it.put("stream",redact(it.getString("stream"))); if(it.has("source")) it.put("source",redact(it.getString("source"))) }
        val jobs=JSONArray(); for(j in objects(data.getJSONArray("jobs"))) { val clean=JSONObject(); for(k in listOf("id","channel_id","title","start","end","status")) clean.put(k,j.get(k)); jobs.put(clean) }
        data.put("jobs",jobs)
        val text=JSONObject().put("app","DizyTV").put("version",1).put("data",data).toString(2)
        require(text.toByteArray().size<=MAX_BACKUP) { "Backup exceeds 16 MiB" }; return text
    }
    fun restore(text:String,now:Long=Instant.now().epochSecond):JSONObject {
        try {
            require(text.toByteArray().size<=MAX_BACKUP) { "Backup exceeds 16 MiB" }; val backup=JSONObject(text)
            require(backup.getString("app")=="DizyTV" && backup.get("version") is Int && backup.getInt("version")==1) { "Unsupported backup version" }
            val s=validate(backup.getJSONObject("data")); s.getJSONObject("settings").put("recording_dir","").put("timeshift_enabled",false)
            val jobs=JSONArray()
            for(original in objects(s.getJSONArray("jobs"))) {
                val j=JSONObject(); for(k in listOf("id","channel_id","title","start","end","status")) j.put(k,original.get(k))
                if(j.getString("status") !in terminal) j.put("status",if(j.getLong("end")<=now) "missed" else "paused")
                jobs.put(j)
            }
            s.put("jobs",jobs)
            return s
        } catch(e:Exception) { throw IllegalArgumentException("Cannot restore backup: ${e.message}",e) }
    }
}
