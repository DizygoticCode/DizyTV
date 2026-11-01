package dev.dizygotic.dizytv

import java.time.DayOfWeek
import java.time.Instant
import java.time.ZoneId

/** Matchday filters always use the viewer's configured IANA display timezone. */
object MatchdayWindow {
    fun visible(kickoff:Long, zone:ZoneId, now:Instant, mode:String):Boolean {
        val today=now.atZone(zone).toLocalDate()
        val day=Instant.ofEpochSecond(kickoff).atZone(zone).toLocalDate()
        if (day.isBefore(today)) return false
        return when(mode) {
            "Today" -> day==today
            "Tomorrow" -> day==today.plusDays(1)
            "Weekend" -> !day.isAfter(today.plusDays(7)) &&
                day.dayOfWeek in listOf(DayOfWeek.SATURDAY,DayOfWeek.SUNDAY)
            else -> !day.isAfter(today.plusDays(14))
        }
    }
}
