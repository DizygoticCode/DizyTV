package dev.dizygotic.dizytv

/** A failed playback attempt is not proof of geographic blocking. */
internal object StreamAccessHelp {
    const val unconfirmedPlayback =
        "Playback not confirmed. This channel may be offline, require an account, " +
        "use DRM or be restricted by country. Check the broadcaster's authorised " +
        "viewing areas and your existing network/VPN settings. DizyTV does not " +
        "change your location or bypass access rules."
}
