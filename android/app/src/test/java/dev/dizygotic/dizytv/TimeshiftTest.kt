package dev.dizygotic.dizytv

import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files
import java.net.InetSocketAddress
import java.net.URL
import java.net.URI
import com.sun.net.httpserver.HttpServer

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
    private fun tsPackets(count:Int):ByteArray=ByteArray(count*188) { offset->
        if(offset%188==0)0x47.toByte() else ((offset/188+offset%188)%255).toByte()
    }

    private fun respond(exchange:com.sun.net.httpserver.HttpExchange,body:ByteArray,
                        type:String="video/mp2t") {
        exchange.responseHeaders.set("Content-Type",type)
        exchange.sendResponseHeaders(200,body.size.toLong())
        exchange.responseBody.use { it.write(body) }
        exchange.close()
    }

    @Test fun clearHlsCanBeCapturedServedReplayedAndRemoved() {
        val root=Files.createTempDirectory("dizytv-live-hls").toFile()
        val server=HttpServer.create(InetSocketAddress("127.0.0.1",0),0)
        val first=tsPackets(8)
        val second=tsPackets(9)
        val manifest="#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n"+
            "#EXTINF:4.0,\nseg0.ts\n#EXTINF:4.0,\nseg1.ts\n"
        server.createContext("/live.m3u8") { respond(it,manifest.toByteArray(),"application/vnd.apple.mpegurl") }
        server.createContext("/seg0.ts") { respond(it,first) }
        server.createContext("/seg1.ts") { respond(it,second) }
        server.start()
        val relay=DeviceTimeshift("http://127.0.0.1:"+server.address.port+"/live.m3u8",
            root,30,256L*1024*1024,1024L*1024*1024)
        try {
            val live=relay.start()
            assertTrue(live.startsWith("http://127.0.0.1:"))
            // The local replay URL never requires seeking the remote live feed.
            val playlist=URL(live).readText()
            assertTrue(playlist.contains("#EXTM3U"))
            val seq=Regex("s/(\\d+)\\.ts").find(playlist)!!.groupValues[1]
            assertArrayEquals(first,URL(URI(live).resolve("s/$seq.ts").toString()).readBytes())
            for(tries in 1..20) {
                if(relay.ring.snapshot().size>=2)break
                Thread.sleep(50)
            }
            assertEquals(2,relay.ring.snapshot().size)
            assertTrue(URL(relay.replayUrl(7.0)).readText().contains("#EXT-X-START"))
            assertTrue(relay.ring.currentBytes()>0)
        } finally {
            relay.close()
            server.stop(0)
        }
        assertEquals(0,root.listFiles()?.sumOf { it.listFiles()?.size?:0 }?:0)
        root.deleteRecursively()
    }

    @Test fun nonseekableHttpTsCanBeCapturedAndPlayedFromLocalFragments() {
        val root=Files.createTempDirectory("dizytv-live-ts").toFile()
        val server=HttpServer.create(InetSocketAddress("127.0.0.1",0),0)
        val payload=tsPackets(50)
        server.createContext("/stream.ts") { respond(it,payload) }
        server.start()
        val relay=DeviceTimeshift("http://127.0.0.1:"+server.address.port+"/stream.ts",
            root,30,256L*1024*1024,1024L*1024*1024)
        try {
            val live=relay.start()
            val playlist=URL(live).readText()
            assertTrue(playlist.contains("#EXT-X-MEDIA-SEQUENCE:"))
            val fragment=Regex("s/(\\d+)\\.ts").find(playlist)!!.value
            val cached=URL(URI(live).resolve(fragment).toString()).readBytes()
            assertArrayEquals(payload,cached)
            assertTrue(relay.ring.availableSeconds()>=0.1)
        } finally {
            relay.close()
            server.stop(0)
        }
        root.deleteRecursively()
    }

    @Test fun encryptedHlsFailsSafelyWithoutLeavingDiskSegments() {
        val root=Files.createTempDirectory("dizytv-blocked-hls").toFile()
        val server=HttpServer.create(InetSocketAddress("127.0.0.1",0),0)
        server.createContext("/protected.m3u8") {
            respond(it,("#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI=\"key\"\n"+
                "#EXTINF:4.0,\nseg.ts\n").toByteArray(),"application/vnd.apple.mpegurl")
        }
        server.start()
        val relay=DeviceTimeshift("http://127.0.0.1:"+server.address.port+"/protected.m3u8",
            root,30,256L*1024*1024,1024L*1024*1024)
        try {
            try {
                relay.start()
                fail("Encrypted HLS must never be added to the local buffer")
            } catch(e:IllegalArgumentException) {
                assertTrue(e.message.orEmpty().contains("Encrypted HLS"))
            }
            assertTrue(relay.ring.snapshot().isEmpty())
        } finally {
            relay.close()
            server.stop(0)
        }
        root.deleteRecursively()
    }

    @Test fun localManifestKeepsSeveralSegmentsForSlowerMediaPlayers() {
        val dir=Files.createTempDirectory("dizytv-hls-window").toFile()
        val ring=TimeshiftRing(dir,30,256L*1024*1024,1024L*1024*1024,
            free={Long.MAX_VALUE})
        try {
            for(n in 1..8)ring.append(tsPackets(1),4.0)
            assertEquals(8,Regex("#EXTINF:").findAll(ring.manifest()).count())
            assertTrue(ring.manifest().contains("#EXT-X-MEDIA-SEQUENCE:0"))
        } finally { ring.close() }
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
