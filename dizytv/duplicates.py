"""Conservative candidate grouping for same-name channels.

Keep regions, +1 variants, television/radio separate and never delete channels.
Different network URLs and video quality are selectable within each group.
"""
from __future__ import annotations

import re
import unicodedata

from .core import channel_kind, display_channel_name


def duplicate_key(channel):
    name = unicodedata.normalize(
        'NFKC', display_channel_name(channel.get('name', ''))
    ).casefold()
    name = re.sub(r'\s+', ' ', name).strip()
    # Quality tags can indicate alternate encodes. They are only candidates.
    # Preserve +1 timeshift variants and distinctive regional station names.
    name = re.sub(r'\s+(?:sd|hd|fhd|uhd|4k|720p|1080p|2160p)$', '', name)
    country = str(channel.get('country') or 'Unspecified').strip().casefold()
    kind = channel_kind(channel)
    return (name, country, kind) if name and name != 'unnamed channel' else None


def duplicate_groups(channels):
    """Group distinct saved channel IDs with same normalized name/country/type."""
    groups = {}
    seen = {}
    for channel in channels:
        key = duplicate_key(channel)
        if key is None:
            continue
        cid = channel.get('id', '')
        if not cid or cid in seen.setdefault(key, set()):
            continue
        seen[key].add(cid)
        groups.setdefault(key, []).append(channel)
    return [
        (key, rows) for key, rows in sorted(groups.items())
        if len(rows) > 1
    ]
