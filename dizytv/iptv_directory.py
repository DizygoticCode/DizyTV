"""Complete browseable IPTV-org playlist directory.

Use the shipped PLAYLISTS.md snapshot without touching the network during
startup. Refresh online only on explicit request; selected feed URLs alone
enter Settings, so 1,200+ overlapping playlists are not bulk downloaded.
"""
from __future__ import annotations

import html
import re

from .iptv_directory_data import DIRECTORY_ROWS

DIRECTORY_URL = "https://raw.githubusercontent.com/iptv-org/iptv/master/PLAYLISTS.md"
DIRECTORY_TYPES = ("All", "Indexes", "Countries", "States & provinces", "Cities",
                   "Regions", "Categories", "Languages")
WORLDWIDE_URL = "https://iptv-org.github.io/iptv/index.m3u"
BASE = "https://iptv-org.github.io/iptv/"
_TABLE = re.compile(
    r"<tr>\s*<td[^>]*>(.*?)</td>.*?<code>("
    r"https://iptv-org\.github\.io/iptv/(?:categories|languages)/[a-z0-9-]+\.m3u"
    r")</code>", re.I)
_PLACE = re.compile(
    r"^(\s*)-\s+(.+?)\s+<code>("
    r"https://iptv-org\.github\.io/iptv/(?:countries|subdivisions|cities|regions)/[a-z0-9-]+\.m3u"
    r")</code>")
_INDEXES = (
    ("All categories",BASE+"index.category.m3u"),
    ("All languages",BASE+"index.language.m3u"),
    ("All countries",BASE+"index.country.m3u"),
    ("Worldwide (all channels)",WORLDWIDE_URL),
)


def _label(value):
    name=html.unescape(re.sub(r"<[^>]+>", "", value))
    return re.sub(r"\s+", " ", re.sub(r"^[^\w]+", "", name)).strip()


def parse_directory(markdown):
    """Parse all *published* group playlists, including country subdivisions.

    The source-based template is intentionally excluded: it has <FILENAME>
    rather than concrete, listed URLs in PLAYLISTS.md.
    """
    if not isinstance(markdown,str) or len(markdown)>2_000_000:
        raise ValueError("Invalid IPTV-org source directory")
    result=[]; seen=set(); country=""
    def append(kind,name,url,parent=""):
        if url not in seen:
            seen.add(url);result.append((kind,name,url,parent))
    for name,url in _INDEXES:
        append("Indexes",name,url)
    for line in markdown.splitlines():
        tr=_TABLE.search(line)
        if tr:
            url=tr[2]
            kind="Categories" if "/categories/" in url else "Languages"
            append(kind,_label(tr[1]),url)
            continue
        bullet=_PLACE.search(line)
        if not bullet:continue
        url=bullet[3]
        label=_label(bullet[2])
        if "/countries/" in url:
            country=label;append("Countries",label,url)
        elif "/subdivisions/" in url:
            append("States & provinces",label,url,country)
        elif "/cities/" in url:
            append("Cities",label,url,country)
        elif "/regions/" in url:
            append("Regions",label,url)
    if len(result)<100:
        raise ValueError("Published IPTV-org directory could not be parsed; using bundled snapshot")
    return result


def directory_search(rows,kind="All",query=""):
    needle=query.casefold().strip()
    return [row for row in rows
            if (kind=="All" or row[0]==kind)
            and all(token in " ".join((row[1],row[2],row[3])).casefold()
                    for token in needle.split())]
