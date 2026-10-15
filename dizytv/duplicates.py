"""Conservative, read-only candidate grouping for the duplicate channel viewer.

Only normalized display names within the SAME stated country and TV/radio type
are grouped. Never discard a channel, merge regional services, or assume the
same channel name means identical video/rights/quality.
"""
from __future__ import annotations
import re
import unicodedata
from .core import display_channel_name, channel_kind


def duplicate_key(channel):
    display=display_channel_name(channel.get('name',''))
    name=unicodedata.normalize('NFKC',display).casefold()
    name=re.sub(r'\s+',' ',name).strip()
    country=str(channel.get('country') or 'Unspecified').strip().casefold()
    kind=channel_kind(channel)
    return (name,country,kind) if name and name!='unnamed channel' else None


def duplicate_groups(channels):
    """Return name/country groups with 2+ different saved channel IDs.

    Distinct URLs under the same name remain separately selectable; +1 and
    HD regions with distinct names are not silently conflated.
    """
    groups={}
    seen={}
    for ch in channels:
        key=duplicate_key(ch)
        if key is None:continue
        cid=ch.get('id','')
        if not cid or cid in seen.setdefault(key,set()):continue
        seen[key].add(cid)
        groups.setdefault(key,[]).append(ch)
    return [(key,rows) for key,rows in sorted(groups.items())
            if len(rows)>1]
