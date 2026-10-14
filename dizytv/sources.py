"""User-editable, public-source catalogue presets and fault-tolerant per-source refresh.

These are *indexes of links*, not bundled streams or proof of rights/availability.
Use only streams the viewer is authorised to access; geoblocking and DRM are not bypassed.
"""
from __future__ import annotations

from .core import http_url, parse_playlist
from urllib.parse import urlparse

LEGACY_URL = "https://search-ace.stream/playlist"
FREE_PLAYLISTS = (
    ("Ace Stream public directory", LEGACY_URL, ""),
    ("UK free television", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_uk.m3u8", "United Kingdom"),
    ("IPTV-org United Kingdom", "https://iptv-org.github.io/iptv/countries/uk.m3u", "United Kingdom"),
    ("IPTV-org United States", "https://iptv-org.github.io/iptv/countries/us.m3u", "United States"),
    ("IPTV-org Canada", "https://iptv-org.github.io/iptv/countries/ca.m3u", "Canada"),
    ("IPTV-org Australia", "https://iptv-org.github.io/iptv/countries/au.m3u", "Australia"),
    ("IPTV-org New Zealand", "https://iptv-org.github.io/iptv/countries/nz.m3u", "New Zealand"),
    ("IPTV-org South Africa", "https://iptv-org.github.io/iptv/countries/za.m3u", "South Africa"),
    ("IPTV-org Singapore", "https://iptv-org.github.io/iptv/countries/sg.m3u", "Singapore"),
    ("IPTV-org Hong Kong", "https://iptv-org.github.io/iptv/countries/hk.m3u", "Hong Kong"),
    ("Free classic TV and movies", "https://iptv-org.github.io/iptv/categories/classic.m3u", ""),
    ("Free television series channels", "https://iptv-org.github.io/iptv/categories/series.m3u", ""),
    ("Free movie channels", "https://iptv-org.github.io/iptv/categories/movies.m3u", ""),
    ("Free comedy / sitcom channels", "https://iptv-org.github.io/iptv/categories/comedy.m3u", ""),
    ("Free-TV curated international", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8", ""),
    ("IPTV-org worldwide", "https://iptv-org.github.io/iptv/index.m3u", ""),
)
# These guide URLs are opt-in download links; their contents are never redistributed.
FREE_GUIDES = (
    ("UK Freeview (seven days)", "https://raw.githubusercontent.com/dp247/Freeview-EPG/master/epg.xml"),
    ("US lightweight XMLTV", "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_lite.xml.gz"),
)
# Fifteen bounded free HTTP/Ace/category sources; the worldwide mega-index stays opt-in.
DEFAULT_PLAYLIST_URLS = [row[1] for row in FREE_PLAYLISTS[:-1]]
DEFAULT_GUIDE_URLS = [row[1] for row in FREE_GUIDES]
COUNTRY_HINTS = {row[1]: row[2] for row in FREE_PLAYLISTS if row[2]}
CATEGORY_HINTS = {
    'https://iptv-org.github.io/iptv/categories/classic.m3u': 'Classic',
    'https://iptv-org.github.io/iptv/categories/series.m3u': 'Series',
    'https://iptv-org.github.io/iptv/categories/movies.m3u': 'Movies',
    'https://iptv-org.github.io/iptv/categories/comedy.m3u': 'Comedy',
}

def source_label(url):
    """Human-readable source name without exposing playlist credentials or query tokens."""
    for label, preset, _ in FREE_PLAYLISTS:
        if preset == url:
            return label
    return urlparse(url).hostname or "Custom playlist"


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
    if len(urls) > 24:
        raise ValueError("Use at most 24 channel playlists")
    existing = {}
    for ch in old_channels:
        source = ch.get("source", LEGACY_URL)
        existing.setdefault(source, []).append(ch)
    seen = {}
    combined, errors, success = [], [], 0

    def append(items):
        for ch in items:
            # One stable identity, but retain every category/region playlist
            # in which it appears. Source filtering must not hide duplicates.
            origins=list(dict.fromkeys(ch.get('sources',[]) or
                                       [ch.get('source',LEGACY_URL)]))
            if ch["id"] in seen:
                saved=combined[seen[ch["id"]]]
                sources=saved.setdefault('sources',[saved.get('source',LEGACY_URL)])
                for origin in origins:
                    if origin not in sources:sources.append(origin)
                # Enrich missing metadata; never overwrite a known category.
                for key in ('country','genre'):
                    if saved.get(key,'Unspecified')=='Unspecified' and ch.get(key)!='Unspecified':
                        saved[key]=ch[key]
            else:
                entry={**ch,'sources':origins}
                seen[ch["id"]]=len(combined)
                combined.append(entry)

    for url in urls:
        try:
            channels = parse_playlist(fetch(url))
            for ch in channels:
                ch["source"] = url
                if ch.get("country") == "Unspecified" and COUNTRY_HINTS.get(url):
                    ch["country"] = COUNTRY_HINTS[url]
                if ch.get("genre") == "Unspecified" and CATEGORY_HINTS.get(url):
                    ch["genre"] = CATEGORY_HINTS[url]
            success += 1
            append(channels)
        except Exception as exc:
            errors.append(source_label(url) + ": " + type(exc).__name__)
            append(existing.get(url, []))
    if not success:
        if old_channels:
            return old_channels, 0, errors
        raise ValueError("No playlist could be imported: " + "; ".join(errors[:2]))
    if not combined:
        raise ValueError("No playable URLs were present; saved channels retained")
    return combined, success, errors
