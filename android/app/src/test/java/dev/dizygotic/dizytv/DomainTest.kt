package dev.dizygotic.dizytv

import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject

class DomainTest {
    @Test fun countryGenreAndTypeCategories() {
        val text="#EXTM3U\n#EXTINF:-1 tvg-country=\"GB\" group-title=\"Sports\",Sport\nacestream://"+"a".repeat(40)+"\n#EXTINF:-1 tvg-country=\"US\" radio=\"true\" group-title=\"Music\",Radio\nhttps://example.com/live.ts"
        val channels=Domain.playlist(text)
        assertEquals("United Kingdom",channels.getJSONObject(0).getString("country"))
        assertEquals("Sport",channels.getJSONObject(0).getString("genre"))
        assertEquals("Ace Stream",channels.getJSONObject(0).getString("transport"))
        assertEquals("Radio",channels.getJSONObject(1).getString("kind"))
    }
    @Test fun offsetsAndDstPreserveUtc() {
        val a = Domain.xmlTime("20261025013000 +0100")
        val b = Domain.xmlTime("20261025013000 +0000")
        assertEquals(3600L, b-a)
        assertTrue(Domain.time(a,"Europe/London").contains("BST"))
        assertTrue(Domain.time(b,"Europe/London").contains("GMT"))
        assertEquals(a, Domain.xmlTime("20261025003000"))
    }
    @Test fun playlistIdsMatchDesktopAndDeduplicate() {
        val hash = "a".repeat(40)
        val input = "#EXTM3U\n#EXTINF:-1 tvg-id=\"bbc.one\" group-title=\"UK\",BBC One\nacestream://$hash\n#EXTINF:-1,Duplicate\nhttp://localhost:6878/ace/getstream?id=$hash"
        val channels = Domain.playlist(input)
        assertEquals(1,channels.length())
        assertEquals(hash,channels.getJSONObject(0).getString("id"))
        assertEquals("bbc.one",channels.getJSONObject(0).getString("tvg_id"))
    }
    @Test fun backupRestorePausesAndResetsPermissions() {
        val s = Domain.defaults()
        s.getJSONObject("settings").put("recording_dir","content://other-device/tree")
        s.getJSONArray("jobs").put(Domain.job("a".repeat(40),"News",2000000000,2000003600,0,0))
        val backup = Domain.backup(s)
        assertFalse(backup.contains("content://other-device"))
        val restored = Domain.restore(backup,1900000000)
        assertEquals("",restored.getJSONObject("settings").getString("recording_dir"))
        assertEquals("paused",restored.getJSONArray("jobs").getJSONObject(0).getString("status"))
        assertEquals(2000000000L,restored.getJSONArray("jobs").getJSONObject(0).getLong("start"))
    }
    @Test fun malformedBackupRejectedAndTimersConflictWithPadding() {
        for (input in listOf("{}","{\"app\":\"DizyTV\",\"version\":9,\"data\":{}}")) {
            try { Domain.restore(input); fail("Invalid backup accepted") } catch (_:IllegalArgumentException) {}
        }
        val a=Domain.job("a".repeat(40),"A",2000000000,2000003600,2,5)
        val b=Domain.job("a".repeat(40),"B",2000003600,2000007200,0,0)
        assertTrue(Domain.overlap(a,b))
        assertEquals(1999999880L,a.getLong("start"))
    }
    @Test fun filenameCannotEscapeFolder() {
        val name=Domain.filename("../News\\x:*?",2000000000)
        assertFalse(name.contains('/')); assertFalse(name.contains('\\')); assertTrue(name.endsWith(".ts"))
    }
}
