package dev.dizygotic.dizytv

import org.junit.Assert.*
import org.junit.Test

class StreamAccessHelpTest {
    @Test fun warnsWithoutClaimingGeoDetectionOrVpnAutomation() {
        val message=StreamAccessHelp.unconfirmedPlayback
        assertTrue(message.contains("may be offline"))
        assertTrue(message.contains("restricted by country"))
        assertTrue(message.contains("VPN"))
        assertTrue(message.contains("does not change your location"))
        assertFalse(message.contains("Geo-blocked"))
    }
}
