package dev.dizygotic.dizytv

import org.junit.Assert.*
import org.junit.Test

class MatchdayLinkPolicyTest {
    @Test fun acceptsPublicUserSubmittedLinks() {
        assertEquals("https://example.org/watch",MatchdayLinkPolicy.validateSource(" https://example.org/watch "))
        assertEquals("https://example.org/caf%C3%A9",MatchdayLinkPolicy.validateSource("https://example.org/caf%C3%A9"))
        assertTrue(MatchdayLinkPolicy.allowResource("https://cdn.example.org/assets/player.js?version=42"))
        assertTrue(MatchdayLinkPolicy.sameSiteNavigation("https://example.org/watch","https://example.org/other"))
        assertFalse(MatchdayLinkPolicy.sameSiteNavigation("https://example.org/watch","https://different.org/watch"))
    }
    @Test fun rejectsUntrustedSchemesPrivateHostsCredentialsAndEscapedAuthority() {
        val bad=listOf("http://example.org/watch","https://localhost/watch",
            "https://foo.local/watch","https://127.0.0.1/watch","https://127.1/watch",
            "https://0177.0.0.1/watch","https://0x7f.0.0.1/watch",
            "https://%31%32%37.0.0.1/watch","https://１２７.０.０.１/watch",
            "https://example.org:8080/watch","https://user:pass@example.org/watch",
            "https://[::1]/watch","file:///tmp/media.html","javascript:alert(1)",
            "https://example.org/watch?token=secret","https://example.org/watch#secret")
        bad.forEach { value ->
            try { MatchdayLinkPolicy.validateSource(value);fail("accepted "+value) }
            catch (_:IllegalArgumentException) {}
        }
    }
    @Test fun blocksPrivateOrCleartextSubresourcesAndCrossHostNavigation() {
        for(value in listOf("http://cdn.example.org/script.js","https://192.168.1.1/data",
                "https://example.local/file","file:///sdcard/secret",
                "content://media/external","https://%31%32%37.0.0.1/test"))
            assertFalse(value,MatchdayLinkPolicy.allowResource(value))
        assertFalse(MatchdayLinkPolicy.sameSiteNavigation(
            "https://example.org/watch","https://private.internal/watch"))
        assertFalse(MatchdayLinkPolicy.sameSiteNavigation(
            "https://example.org/watch","intent://other"))
    }
}
