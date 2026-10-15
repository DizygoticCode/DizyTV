"""User-editable, public-source catalogue presets and fault-tolerant per-source refresh.

These are *indexes of links*, not bundled streams or proof of rights/availability.
Use only streams the viewer is authorised to access; geoblocking and DRM are not bypassed.
"""
from __future__ import annotations

from .core import http_url, parse_playlist
from .iptv_directory_data import DIRECTORY_ROWS
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
    ("Free public sports channels", "https://iptv-org.github.io/iptv/categories/sports.m3u", ""),
    ("Free-TV curated international", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8", ""),
    # UK FAST services: published generated channel lists, not guarantees of playback.
    # 24/7 programme-themed stations typically originate from FAST providers.
    ("Plex FAST UK · series/24-7", "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/plex_gb.m3u", "United Kingdom"),
    ("Samsung TV Plus FAST UK", "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/samsungtvplus_gb.m3u", "United Kingdom"),
    ("Pluto TV FAST UK", "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/plutotv_gb.m3u", "United Kingdom"),
    ("IPTV-org worldwide", "https://iptv-org.github.io/iptv/index.m3u", ""),
)
# These optional US FAST feeds may be region-restricted and are never
# enabled automatically on British devices.
OPTIONAL_FAST_PLAYLISTS = (
    ("Roku FAST US", "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/roku_all.m3u", "United States"),
    ("Tubi FAST US", "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/tubi_all.m3u", "United States"),
)
# Third-party UK retransmission candidates requested by users. These are
# separate, opt-in sources because they may include short-lived/session-bound
# links, unsupported DRM or streams requiring regional broadcast rights.
# A matching channel name / EPG ID is NOT proof of playable video.
OPTIONAL_UK_RETRANSMISSIONS = (
    ("UK retransmissions (+1 / STV+1 candidate)", "https://raw.githubusercontent.com/ExperiencersInternational/tvsetup/main/config.m3u", "United Kingdom"),
    ("UK alternatives (E4 candidate)", "https://raw.githubusercontent.com/dp247/IPTV/master/playlists/playlist_uk.m3u8", "United Kingdom"),
)
# Matching FAST XMLTV listings use the same opaque channel IDs in their M3U
# tvg-id attributes. Guide files are opt-in URLs; contents are not redistributed.
# UK Freeview listings and FAST listings are different catalogues.
UK_FAST_GUIDES = (
    ("Plex UK FAST EPG", "https://i.mjh.nz/Plex/gb.xml.gz"),
    ("Samsung TV Plus UK FAST EPG", "https://i.mjh.nz/SamsungTVPlus/gb.xml.gz"),
    ("Pluto TV UK FAST EPG", "https://i.mjh.nz/PlutoTV/gb.xml.gz"),
)
FREE_GUIDES = (
    ("UK Freeview (seven days)", "https://raw.githubusercontent.com/dp247/Freeview-EPG/master/epg.xml"),
    ("US lightweight XMLTV", "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_lite.xml.gz"),
    *UK_FAST_GUIDES,
)
FAST_GUIDE_BY_PLAYLIST = dict(zip(
    (row[1] for row in FREE_PLAYLISTS if row[0] in (
        "Plex FAST UK · series/24-7", "Samsung TV Plus FAST UK", "Pluto TV FAST UK")),
    (url for _,url in UK_FAST_GUIDES),
))
# Keep source count bounded; the worldwide mega-index stays opt-in.
DEFAULT_PLAYLIST_URLS = [row[1] for row in FREE_PLAYLISTS[:-1]]
DEFAULT_GUIDE_URLS = [row[1] for row in FREE_GUIDES]
COUNTRY_HINTS = {row[1]: row[2] for row in FREE_PLAYLISTS if row[2]}
# Directory entries carry a country hint for country/subdivision/city feeds.
# No country is guessed for region, language or grouped worldwide indexes.
DIRECTORY_META = {url:(kind,name,parent) for kind,name,url,parent in DIRECTORY_ROWS}
DIRECTORY_COUNTRIES = {url:(name if kind=='Countries' else parent)
                       for kind,name,url,parent in DIRECTORY_ROWS
                       if kind in ('Countries','States & provinces','Cities')}
DIRECTORY_CATEGORIES = {url:name for kind,name,url,parent in DIRECTORY_ROWS
                        if kind=='Categories' and name not in ('Undefined','XXX')}
CATEGORY_HINTS = {
    'https://iptv-org.github.io/iptv/categories/classic.m3u': 'Classic',
    'https://iptv-org.github.io/iptv/categories/series.m3u': 'Series',
    'https://iptv-org.github.io/iptv/categories/movies.m3u': 'Movies',
    'https://iptv-org.github.io/iptv/categories/comedy.m3u': 'Comedy',
    'https://iptv-org.github.io/iptv/categories/sports.m3u': 'Sport',
}

def source_label(url):
    """Human-readable source name without exposing playlist credentials or query tokens."""
    for label, preset, _ in (*FREE_PLAYLISTS, *OPTIONAL_FAST_PLAYLISTS, *OPTIONAL_UK_RETRANSMISSIONS):
        if preset == url:
            return label
    if url in DIRECTORY_META:
        kind,name,parent=DIRECTORY_META[url]
        location=(name+', '+parent) if parent else name
        return 'IPTV-org '+kind+' · '+location
    parsed=urlparse(url)
    if parsed.hostname=='iptv-org.github.io' and parsed.path.startswith('/iptv/'):
        return 'IPTV-org · '+parsed.path.removeprefix('/iptv/')
    return parsed.hostname or "Custom playlist"


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
        # A stream found in two directories must remain cached independently
        # if either feed later fails.
        for source in ch.get("sources") or [ch.get("source", LEGACY_URL)]:
            existing.setdefault(source, []).append(ch)
    seen = {}
    combined, errors, success = [], [], 0

    def append(items,origin):
        for channel in items:
            ch={**channel,'source':origin,'sources':[origin]}
            if ch["id"] in seen:
                saved=combined[seen[ch["id"]]]
                sources=saved.setdefault('sources',[saved.get('source',LEGACY_URL)])
                if origin not in sources:sources.append(origin)
                for key in ('country','genre'):
                    if saved.get(key,'Unspecified')=='Unspecified' and ch.get(key)!='Unspecified':
                        saved[key]=ch[key]
            else:
                seen[ch["id"]]=len(combined)
                combined.append(ch)

    for url in urls:
        try:
            channels = parse_playlist(fetch(url))
            for ch in channels:
                ch["source"] = url
                if ch.get("country") == "Unspecified":
                    hint=COUNTRY_HINTS.get(url) or DIRECTORY_COUNTRIES.get(url)
                    if hint:ch["country"]=hint
                if ch.get("genre") == "Unspecified":
                    hint=CATEGORY_HINTS.get(url) or DIRECTORY_CATEGORIES.get(url)
                    if hint:ch["genre"]=hint
            success += 1
            append(channels,url)
        except Exception as exc:
            errors.append(source_label(url) + ": " + type(exc).__name__)
            append(existing.get(url, []),url)
    if not success:
        if old_channels:
            return old_channels, 0, errors
        raise ValueError("No playlist could be imported: " + "; ".join(errors[:2]))
    if not combined:
        raise ValueError("No playable URLs were present; saved channels retained")
    return combined, success, errors
