package dev.dizygotic.dizytv

import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files

class TimeshiftTest {
    @Test fun fourHourUpperBoundAndTemporaryCleanup() {
        val dir=Files.createTempDirectory("dizytv-ring").toFile()
        var now=1000000L
        val ring=TimeshiftRing(dir,1,256L*1024*1024,1024L*1024*1024,
                                clock={now},free={Long.MAX_VALUE})
        val first=ring.append(byteArrayOf(0x47,0x00),4.0)
        now+=61000
        val second=ring.append(byteArrayOf(0x47,0x01),4.0)
        assertFalse(first.path.exists())
        assertTrue(second.path.exists())
        assertEquals(second.seq,ring.seqAgo(999.0))
        assertTrue(ring.manifest(second.seq).contains("EXT-X-START"))
        ring.close()
        assertFalse(dir.exists())
    }
    @Test fun rejectsOversizedQuotaOrDuration() {
        val dir=Files.createTempDirectory("dizytv-ring-bounds").toFile()
        try {
            try { TimeshiftRing(dir,241,256L*1024*1024,1024L*1024*1024);fail("Missing time bound") }
            catch(_:IllegalArgumentException) {}
            try { TimeshiftRing(dir,240,33L*1024*1024*1024,1024L*1024*1024);fail("Missing quota bound") }
            catch(_:IllegalArgumentException) {}
        } finally { dir.deleteRecursively() }
    }
}
