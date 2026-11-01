package dev.dizygotic.dizytv

import org.junit.Assert.*
import org.junit.Test
import java.time.Instant
import java.time.ZoneId

class MatchdayWindowTest {
    private val now=Instant.parse("2026-11-01T00:30:00Z")
    @Test fun usesViewerTimezoneForTodayTomorrowAndWeekend() {
        val la=ZoneId.of("America/Los_Angeles") // Saturday 31 October
        val uk=ZoneId.of("Europe/London") // Sunday 1 November
        val fixture=Instant.parse("2026-10-31T23:00:00Z").epochSecond
        assertTrue(MatchdayWindow.visible(fixture,la,now,"Today"))
        assertFalse(MatchdayWindow.visible(fixture,uk,now,"Today"))
        assertTrue(MatchdayWindow.visible(fixture,la,now,"Weekend"))
        val sunday=Instant.parse("2026-11-01T19:00:00Z").epochSecond
        assertTrue(MatchdayWindow.visible(sunday,la,now,"Tomorrow"))
        assertTrue(MatchdayWindow.visible(sunday,uk,now,"Today"))
    }
    @Test fun rejectsPastAndOutOfRangeFixtures() {
        val zone=ZoneId.of("Europe/London")
        val past=Instant.parse("2026-10-30T15:00:00Z").epochSecond
        val future=Instant.parse("2026-11-20T15:00:00Z").epochSecond
        assertFalse(MatchdayWindow.visible(past,zone,now,"Upcoming"))
        assertFalse(MatchdayWindow.visible(future,zone,now,"Upcoming"))
        assertFalse(MatchdayWindow.visible(future,zone,now,"Weekend"))
        assertTrue(MatchdayWindow.visible(Instant.parse("2026-11-07T15:00:00Z").epochSecond,zone,now,"Weekend"))
    }
}
