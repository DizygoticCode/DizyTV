package dev.dizygotic.dizytv

import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject
import java.io.File
import java.io.IOException

class RecoveryTest {
    @Test fun cancellationAndExpiredJobsCannotBeClaimed() {
        val job=Domain.job("a".repeat(40),"News",2000000000,2000000060,0,0)
        job.put("status","cancelled")
        assertFalse(Domain.claim(job,2000000001)); assertEquals("cancelled",job.getString("status"))
        job.put("status","paused"); assertFalse(Domain.claim(job,2000000001))
        job.put("status","queued"); assertFalse(Domain.claim(job,2000000070)); assertEquals("missed",job.getString("status"))
    }
    @Test fun recoveryKeepsFootageOnFailureAndNewSegment() {
        val job=Domain.job("a".repeat(40),"News",2000000000,2000000060,0,0)
        job.put("status","recording").put("uri","content://recordings/old").put("bytes",188)
        assertTrue(Domain.claim(job,2000000001))
        Domain.finish(job,JSONObject().put("status","failed").put("bytes",0).put("error","Engine unavailable"))
        assertEquals("partial",job.getString("status")); assertEquals(188,job.getLong("bytes")); assertEquals("content://recordings/old",job.getJSONArray("segments").getJSONObject(0).getString("uri"))
        assertEquals(listOf("content://recordings/old"),Domain.recordingUris(job))
        job.put("status","queued"); assertTrue(Domain.claim(job,2000000002))
        Domain.finish(job,JSONObject().put("status","completed").put("bytes",188).put("uri","content://recordings/new").put("error",""))
        assertEquals(376,job.getLong("bytes")); assertEquals("content://recordings/new",job.getString("uri")); assertEquals(1,job.getJSONArray("segments").length())
        assertEquals(listOf("content://recordings/old","content://recordings/new"),Domain.recordingUris(job))
    }
    @Test fun adjacentJobsWaitAndOldCompletionCannotStopSuccessor() {
        val q=RecordingQueue(); assertTrue(q.enqueue("A",1)); assertTrue(q.enqueue("B",2)); assertFalse(q.enqueue("B",3))
        assertFalse(q.finish("A")); assertEquals(1,q.size()); assertEquals(3,q.latestStartId)
        assertTrue(q.finish("B")); assertEquals(0,q.size())
    }
    @Test fun successorExpiredWhileWaitingIsMissed() {
        val job=Domain.job("b".repeat(40),"Next",2000000000,2000000002,0,0)
        assertFalse(Domain.claim(job,2000000003)); assertEquals("missed",job.getString("status"))
    }
    @Test fun atomicGuideFailureKeepsPreviousCache() {
        val folder=kotlin.io.path.createTempDirectory("dizytv-cache").toFile()
        try {
            val target=File(folder,"guide.json"); target.writeText("previous guide")
            try { JsonCache.write(target,"new guide") { _,_->throw IOException("Simulated provider failure") }; fail("Write should fail") } catch (_:IOException) {}
            assertEquals("previous guide",target.readText()); assertEquals(1,folder.listFiles()!!.size)
        } finally { folder.deleteRecursively() }
    }
}
