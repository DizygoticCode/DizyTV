package dev.dizygotic.dizytv

import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files
import java.net.ServerSocket
import java.net.InetAddress
import java.net.URL
import java.net.URI

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

    /** Pure JVM deterministic live source, independent of Android SDK stubs. */
    private class FixtureServer(private val routes:Map<String,Pair<ByteArray,String>>):AutoCloseable {
        private val socket=ServerSocket(0,16,InetAddress.getByName("127.0.0.1"))
        val port:Int get()=socket.localPort
        private val worker=Thread({
            while(!socket.isClosed) {
                val client=try { socket.accept() } catch(_:java.io.IOException) { break }
                runCatching {
                    client.use {
                        it.soTimeout=3000
                        val reader=it.getInputStream().bufferedReader(Charsets.US_ASCII)
                        val route=reader.readLine()?.split(' ')?.getOrNull(1)?.substringBefore('?')?:""
                        var line=reader.readLine()
                        while(!line.isNullOrBlank())line=reader.readLine()
                        val result=routes[route]
                        val content=result?.first?:ByteArray(0)
                        val mime=result?.second?:"text/plain"
                        val code=if(result==null)"404 Not Found" else "200 OK"
                        val headers="HTTP/1.1 $code\r\nContent-Type: $mime\r\n"+
                            "Content-Length: "+content.size+"\r\nConnection: close\r\n\r\n"
                        it.getOutputStream().use { out->
                            out.write(headers.toByteArray(Charsets.US_ASCII))
                            out.write(content)
                            out.flush()
                        }
                    }
                }
            }
        },"dizytv-test-http").apply { isDaemon=true;start() }
        override fun close() { socket.close();worker.join(3000) }
    }

    @Test fun clearHlsCanBeCapturedServedReplayedAndRemoved() {
        val root=Files.createTempDirectory("dizytv-live-hls").toFile()
        val first=tsPackets(8)
        val second=tsPackets(9)
        val manifest="#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n"+
            "#EXTINF:4.0,\nseg0.ts\n#EXTINF:4.0,\nseg1.ts\n"
        val server=FixtureServer(mapOf(
            "/live.m3u8" to (manifest.toByteArray() to "application/vnd.apple.mpegurl"),
            "/seg0.ts" to (first to "video/mp2t"),
            "/seg1.ts" to (second to "video/mp2t")))
        val relay=DeviceTimeshift("http://127.0.0.1:"+server.port+"/live.m3u8",
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
            server.close()
        }
        assertEquals(0,root.listFiles()?.sumOf { it.listFiles()?.size?:0 }?:0)
        root.deleteRecursively()
    }

    @Test fun nonseekableHttpTsCanBeCapturedAndPlayedFromLocalFragments() {
        val root=Files.createTempDirectory("dizytv-live-ts").toFile()
        val payload=tsPackets(50)
        val server=FixtureServer(mapOf("/stream.ts" to (payload to "video/mp2t")))
        val relay=DeviceTimeshift("http://127.0.0.1:"+server.port+"/stream.ts",
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
            server.close()
        }
        root.deleteRecursively()
    }

    @Test fun encryptedHlsFailsSafelyWithoutLeavingDiskSegments() {
        val root=Files.createTempDirectory("dizytv-blocked-hls").toFile()
        val encrypted="#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI=\"key\"\n"+
            "#EXTINF:4.0,\nseg.ts\n"
        val server=FixtureServer(mapOf(
            "/protected.m3u8" to (encrypted.toByteArray() to "application/vnd.apple.mpegurl")))
        val relay=DeviceTimeshift("http://127.0.0.1:"+server.port+"/protected.m3u8",
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
            server.close()
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
