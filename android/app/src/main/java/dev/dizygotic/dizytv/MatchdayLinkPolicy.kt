package dev.dizygotic.dizytv

import java.net.URI
import java.util.Locale

/**
 * Matchday links are explicitly user-submitted, authorised public HTTPS only.
 * No IP literals, encoded/unicode authorities, local domains, credentials
 * or nonstandard ports. This is not a viewing-rights or video-quality check.
 */
object MatchdayLinkPolicy {
    private val numericHost = Regex("(?i)(?:0x[0-9a-f]+|[0-9]+)(?:\\.(?:0x[0-9a-f]+|[0-9]+))*")
    private val numericLabels = Regex("(?i)(?:0x[0-9a-f]+|[0-9]+)")
    private val badSuffixes = listOf(".localhost", ".local", ".internal", ".test", ".onion", ".invalid")

    private fun checked(value:String, allowQuery:Boolean):URI {
        require(value.length in 10..4096 && !value.contains('\\') && value.none { it.code < 32 }) {
            "Invalid Matchday link"
        }
        val uri=URI(value)
        val authority=uri.rawAuthority ?: throw IllegalArgumentException("Missing HTTPS host")
        require(authority.all { it.code in 33..126 } && '%' !in authority) {
            "Only ordinary ASCII website names are supported"
        }
        val host=(uri.host ?: "").lowercase(Locale.ROOT).trimEnd('.')
        require(uri.scheme?.lowercase(Locale.ROOT)=="https" && uri.userInfo==null &&
            uri.port in listOf(-1,443) && host.length in 4..253 &&
            host.contains('.') && !host.contains("..") &&
            !host.endsWith('.') && !host.startsWith('.') &&
            host.all { it in 'a'..'z' || it in '0'..'9' || it=='.' || it=='-' } &&
            host !in listOf("localhost","localdomain") &&
            badSuffixes.none { host.endsWith(it) } &&
            !numericHost.matches(host) && !host.split('.').all(numericLabels::matches) &&
            !host.contains(':')) { "Only public HTTPS sites are permitted" }
        if (!allowQuery) {
            require(uri.rawQuery==null && uri.rawFragment==null) {
                "Links with tokens, queries or fragments cannot be saved"
            }
        }
        return uri
    }

    fun validateSource(raw:String):String {
        val value=raw.trim()
        require(value.length <= 1500) { "Matchday URL is too long" }
        checked(value,false)
        return value
    }

    /** Subresources may have CDN cache parameters; never expose them in logs. */
    fun allowResource(url:String):Boolean =
        runCatching { checked(url,true); true }.getOrDefault(false)

    /** Top-level web navigation stays on the original website. */
    fun sameSiteNavigation(original:String, next:String):Boolean =
        runCatching {
            val start=checked(original,false)
            val destination=checked(next,true)
            start.host.equals(destination.host,ignoreCase=true) &&
                (start.port==-1 || start.port==443) &&
                destination.port in listOf(-1,443)
        }.getOrDefault(false)
}
