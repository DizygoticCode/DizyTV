package dev.dizygotic.dizytv

import org.junit.Assert.*
import org.junit.Test
import org.json.JSONArray
import org.json.JSONObject

class SourcesTest {
    @Test fun freePresetsAndLegacyUpgrade() {
        val defaults=Domain.defaults().getJSONObject("settings")
        assertTrue(Sources.urls(defaults).any { it.contains("countries/us.m3u") })
        assertTrue(Sources.urls(defaults).any { it.contains("playlist_uk.m3u8") })
        assertTrue(Domain.strings(defaults.getJSONArray("xmltv_urls")).any { it.contains("Freeview-EPG") })
        val legacy=JSONObject().put("playlist_url",Sources.legacy)
        assertTrue(Sources.urls(legacy).size>1)
    }

    @Test fun perSourceOutageRetainsPreviouslySavedChannels() {
        val a="https://example.com/a.m3u"; val b="https://example.com/b.m3u"
        val old=Domain.playlist("#EXTM3U\n#EXTINF:-1,Archived\nhttps://example.com/archived.ts")
        old.getJSONObject(0).put("source",b)
        val settings=JSONObject().put("playlist_url",a).put("playlist_urls",JSONArray(listOf(a,b)))
        val result=Sources.refresh(settings,old) { u ->
            if(u==b) throw IllegalArgumentException("offline")
            "#EXTM3U\n#EXTINF:-1,Online\nhttps://example.com/live.m3u8"
        }
        assertEquals(1,result.succeeded)
        assertEquals(2,result.channels.length())
        assertEquals(1,result.errors.size)
        val state=Domain.defaults().put("channels",result.channels)
        Domain.validate(state)
        assertEquals(2,Domain.restore(Domain.backup(state)).getJSONArray("channels").length())
    }

    @Test fun exactGuideMatchPreservesManualOverride() {
        val ch=JSONObject().put("id","a".repeat(40)).put("name","BBC News HD").put("tvg_id","")
        val names=JSONObject().put("bbc-news","BBC News")
        assertEquals("bbc-news",Domain.matchGuide(ch,JSONObject(),names))
        assertEquals("",Domain.matchGuide(ch,JSONObject().put(ch.getString("id"),""),names))
        assertEquals("",Domain.matchGuide(ch,JSONObject(),JSONObject().put("a","BBC News").put("b","BBC News")))
    }
}
