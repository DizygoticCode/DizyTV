package dev.dizygotic.dizytv

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/** Deliberately limited free fixture metadata; NOT a feed of authorised streams. */
object MatchdayFixtures {
    val leagues = linkedMapOf(
        "4328" to "Premier League", "4329" to "Championship",
        "4396" to "League One", "4397" to "League Two",
        "4482" to "FA Cup", "4570" to "EFL Cup",
        "4480" to "Champions League", "4481" to "Europa League",
        "5071" to "Conference League"
    )

    private const val prefix = "https://www.thesportsdb.com/api/v1/json/123/"

    fun parse(payload:JSONObject, leagueId:String):List<JSONObject> {
        val events=payload.optJSONArray("events")?:return emptyList()
        val results=ArrayList<JSONObject>()
        for(i in 0 until minOf(events.length(),1000)) {
            val raw=events.optJSONObject(i)?:continue
            if(raw.optString("idLeague")!=leagueId) continue
            val id=raw.optString("idEvent")
            val home=raw.optString("strHomeTeam").trim().take(100)
            val away=raw.optString("strAwayTeam").trim().take(100)
            if(!id.matches(Regex("[0-9]{1,16}")) || home.isEmpty() || away.isEmpty()) continue
            val stamp=raw.optString("strTimestamp").trim()
            val kickoff=runCatching {
                // Offset timestamps must preserve the supplied instant.
                if(stamp.endsWith("Z")) Instant.parse(stamp).epochSecond
                else if(Regex("[+-][0-9]{2}:[0-9]{2}$").containsMatchIn(stamp))
                    java.time.OffsetDateTime.parse(stamp).toInstant().epochSecond
                else java.time.LocalDateTime.parse(stamp)
                    .toEpochSecond(ZoneOffset.UTC)
            }.getOrNull()?:continue
            results.add(JSONObject().put("id",id).put("competition",leagues[leagueId])
                .put("home",home).put("away",away).put("kickoff",kickoff))
        }
        return results
    }

    private fun request(path:String):JSONObject {
        // Fixed endpoint and generated numeric/date params only. No user-controlled hosts.
        require(path.matches(Regex("(eventsnextleague\\.php\\?id=[0-9]{4}|eventsday\\.php\\?d=[0-9]{4}-[0-9]{2}-[0-9]{2}&l=4329)")))
        val connection=(URL(prefix+path).openConnection() as HttpURLConnection)
        try {
            connection.connectTimeout=7000
            connection.readTimeout=7000
            connection.instanceFollowRedirects=false
            connection.setRequestProperty("Accept","application/json")
            connection.setRequestProperty("User-Agent","DizyTV/0.1 (Matchday fixtures)")
            if(connection.responseCode!=200) throw IllegalStateException("Fixture API unavailable")
            val data=connection.inputStream.use { input->
                val output=java.io.ByteArrayOutputStream()
                val buffer=ByteArray(8192)
                while(true) {
                    val size=input.read(buffer)
                    if(size<0) break
                    if(output.size()+size>1048576) throw IllegalStateException("Fixture payload too large")
                    output.write(buffer,0,size)
                }
                output.toString("UTF-8")
            }
            return JSONObject(data)
        } finally {
            connection.disconnect()
        }
    }

    /** 9 next-league + 2 Championship day queries, below 30/min free limit. */
    fun refresh():Pair<List<JSONObject>,Int> {
        val unique=linkedMapOf<String,JSONObject>()
        var unavailable=0
        for(id in leagues.keys) {
            runCatching { parse(request("eventsnextleague.php?id="+id),id) }
                .onSuccess { matches->matches.forEach { unique[it.getString("id")]=it } }
                .onFailure { unavailable++ }
        }
        val today=LocalDate.now(ZoneOffset.UTC)
        for(day in listOf(today,today.plusDays(1))) {
            runCatching { parse(request("eventsday.php?d="+day+"&l=4329"),"4329") }
                .onSuccess { matches->matches.forEach { unique[it.getString("id")]=it } }
                .onFailure { unavailable++ }
        }
        return unique.values.sortedBy { it.optLong("kickoff") } to unavailable
    }
}
