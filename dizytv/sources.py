"""User-editable, public-source catalogue presets and fault-tolerant per-source refresh.

These are *indexes of links*, not bundled streams or proof of rights/availability.
Use only streams the viewer is authorised to access; geoblocking and DRM are not bypassed.
"""
from __future__ import annotations

from .core import http_url, parse_playlist

LEGACY_URL = "https://search-ace.stream/playlist"
FREE_PLAYLISTS = (
    ("Ace Stream public directory", LEGACY_URL, ""),
    ("UK free television", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_uk.m3u8", "United Kingdom"),
    ("IPTV-org United Kingdom", "https://iptv-org.github.io/iptv/countries/uk.m3u", "United Kingdom"),
    ("IPTV-org United States", "https://iptv-org.github.io/iptv/countries/us.m3u", "United States"),
    ("Free-TV curated international", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8", ""),
    ("IPTV-org worldwide", "https://iptv-org.github.io/iptv/index.m3u", ""),
)
# These guide URLs are opt-in download links; their contents are never redistributed.
FREE_GUIDES = (
    ("UK Freeview (seven days)", "https://raw.githubusercontent.com/dp247/Freeview-EPG/master/epg.xml"),
    ("US lightweight XMLTV", "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_lite.xml.gz"),
)
DEFAULT_PLAYLIST_URLS = [row[1] for row in FREE_PLAYLISTS[:-1]]  # Worldwide mega-index optional on low-memory phones
DEFAULT_GUIDE_URLS = [row[1] for row in FREE_GUIDES]
COUNTRY_HINTS = {row[1]: row[2] for row in FREE_PLAYLISTS if row[2]}


def configured_playlists(settings):
    """Older installations transparently gain free presets, keeping custom URL first."""
    urls = settings.get("playlist_urls")
    if urls is None:
        urls = [settings.get("playlist_url", LEGACY_URL)] + DEFAULT_PLAYLIST_URLS
    return list(dict.fromkeys(http_url(str(u).strip()) for u in urls if str(u).strip()))


def refresh_catalogue(settings, old_channels, fetch):
    """One source failing must not remove its last working channels or other feeds.

    Return (channels, successes, errors). Throw if every source failed and there is
    no cached catalogue. Never store a zero-channel successful refresh.
    """
    urls = configured_playlists(settings)
    if not urls:
        raise ValueError("Add at least one channel playlist in Settings")
    if len(urls) > 16:
        raise ValueError("Use at most 16 channel playlists")
    existing = {}
    for ch in old_channels:
        source = ch.get("source", LEGACY_URL)
        existing.setdefault(source, []).append(ch)
    seen = set()
    combined, errors, success = [], [], 0

    def append(items):
        for ch in items:
            if ch["id"] not in seen:
                seen.add(ch["id"])
                combined.append(ch)

    for url in urls:
        try:
            channels = parse_playlist(fetch(url))
            for ch in channels:
                ch["source"] = url
                if ch.get("country") == "Unspecified" and COUNTRY_HINTS.get(url):
                    ch["country"] = COUNTRY_HINTS[url]
            success += 1
            append(channels)
        except Exception as exc:
            errors.append(url + ": " + str(exc))
            append(existing.get(url, []))
    if not success:
        if old_channels:
            return old_channels, 0, errors
        raise ValueError("No playlist could be imported: " + "; ".join(errors[:2]))
    if not combined:
        raise ValueError("No playable URLs were present; saved channels retained")
    return combined, success, errors
