package dev.dizygotic.dizytv

import org.json.JSONArray
import org.json.JSONObject

/** Public link indexes only. Stream availability, rights and regional access are not guaranteed. */
object Sources {
    const val legacy="https://search-ace.stream/playlist"
    val presets=listOf(
        legacy,
        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_uk.m3u8",
        "https://iptv-org.github.io/iptv/countries/uk.m3u",
        "https://iptv-org.github.io/iptv/countries/us.m3u",
        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
    )
    const val optionalWorld="https://iptv-org.github.io/iptv/index.m3u"
    val guides=listOf(
        "https://raw.githubusercontent.com/dp247/Freeview-EPG/master/epg.xml",
        "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_lite.xml.gz"
    )
    private val countryHints=mapOf(presets[1] to "United Kingdom",presets[2] to "United Kingdom",presets[3] to "United States")
    fun label(url:String):String = when(url) {
        presets[0]->"Ace Stream public directory"
        presets[1]->"UK free television"
        presets[2]->"IPTV-org United Kingdom"
        presets[3]->"IPTV-org United States"
        presets[4]->"Free-TV international"
        optionalWorld->"IPTV-org worldwide"
        else->runCatching { java.net.URI(url).host }.getOrNull()?:"Custom source"
    }

    fun urls(settings:JSONObject):List<String> {
        val source=if(settings.has("playlist_urls")) Domain.strings(settings.getJSONArray("playlist_urls"))
                   else listOf(settings.optString("playlist_url",legacy))+presets
        return source.map { Domain.http(it.trim()) }.filter { it.isNotBlank() }.distinct().also {
            require(it.isNotEmpty() && it.size<=16) { "Configure between 1 and 16 playlist URLs" }
        }
    }

    data class Result(val channels:JSONArray,val succeeded:Int,val errors:List<String>)

    fun refresh(settings:JSONObject,previous:JSONArray,fetch:(String)->String):Result {
        val old=Domain.objects(previous).groupBy { it.optString("source",legacy) }
        val merged=JSONArray(); val seen=mutableSetOf<String>()
        var success=0; val errors=mutableListOf<String>()
        fun append(rows:List<JSONObject>) {
            for(ch in rows) if(seen.add(ch.getString("id"))) merged.put(ch)
        }
        for(url in urls(settings)) {
            try {
                val rows=Domain.objects(Domain.playlist(fetch(url)))
                for(ch in rows) {
                    ch.put("source",url)
                    if(ch.optString("country")=="Unspecified") countryHints[url]?.let { ch.put("country",it) }
                }
                append(rows); success++
            } catch(e:Exception) {
                errors.add("${label(url)}: ${e.javaClass.simpleName}")
                append(old[url].orEmpty())
            }
        }
        if(success==0) {
            require(previous.length()>0) { "All playlist sources failed; no previous catalogue available" }
            return Result(previous,0,errors)
        }
        require(merged.length()>0) { "No supported channels found; cached catalogue retained" }
        return Result(merged,success,errors)
    }
}
