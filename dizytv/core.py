"""Portable catalogue, XMLTV, scheduling and backup contracts (no UI dependencies)."""
from __future__ import annotations

import copy
from difflib import SequenceMatcher
import hashlib
import json
import re
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_BACKUP = 16 * 1024 * 1024
MAX_FEED = 32 * 1024 * 1024
TERMINAL = {'completed', 'partial', 'failed', 'cancelled', 'missed'}
ACTIVE = {'queued', 'starting', 'recording'}
STATUSES = ACTIVE | TERMINAL | {'paused'}
COUNTRIES = {'GB':'United Kingdom','UK':'United Kingdom','US':'United States','USA':'United States',
             'CA':'Canada','AU':'Australia','NZ':'New Zealand','IE':'Ireland','FR':'France',
             'DE':'Germany','ES':'Spain','IT':'Italy','PT':'Portugal','NL':'Netherlands',
             'BE':'Belgium','CH':'Switzerland','AT':'Austria','PL':'Poland','CZ':'Czechia',
             'SE':'Sweden','NO':'Norway','DK':'Denmark','FI':'Finland','GR':'Greece',
             'TR':'Turkey','UA':'Ukraine','RU':'Russia','IN':'India','PK':'Pakistan',
             'BR':'Brazil','MX':'Mexico','AR':'Argentina','JP':'Japan','CN':'China',
             'KR':'South Korea','ZA':'South Africa','IL':'Israel','AE':'United Arab Emirates'}
GENRES = [('Sport',r'sports?'),('News',r'news|current affairs'),('Movies',r'movies?|films?|cinema'),
          ('Kids',r'kids|children|cartoons?'),('Music',r'music'),('Documentary',r'documentar(?:y|ies)|factual'),
          ('Entertainment',r'entertainment'),('Education',r'education'),('General',r'general')]


def normalise_genre(value):
    for genre, pattern in GENRES:
        if re.search(r'\b(?:'+pattern+r')\b',value,re.I):
            return genre
    return value.strip()[:512] or 'Unspecified'


def channel_kind(channel):
    """Recognize unmistakable audio stations without rewriting saved identities."""
    if channel.get('kind') == 'Radio':
        return 'Radio'
    name = str(channel.get('name',''))
    tvg = str(channel.get('tvg_id',''))
    group = str(channel.get('group',''))
    if re.search(r'(?i)(?:^|[._-])radio\w*',tvg):
        return 'Radio'
    if re.search(r'(?i)\b(?:radio|fm station)\b',group):
        return 'Radio'
    if re.search(r'(?i)\b(?:radio|fm radio)\b',name):
        return 'Radio'
    if re.match(r'(?i)^BBC (?:Asian Network|World Service)\b',name) and tvg.lower().startswith('bbcradio'):
        return 'Radio'
    return 'TV'


def channel_categories(attrs, stream, name=''):
    group = attrs.get('group-title','')
    explicit = attrs.get('tvg-country',attrs.get('country','')).strip()
    country = COUNTRIES.get(explicit.upper(), explicit) if explicit else 'Unspecified'
    if not explicit:
        aliases = {**COUNTRIES, **{name:name for name in COUNTRIES.values()}}
        for alias, country_name in sorted(aliases.items(),key=lambda pair:-len(pair[0])):
            if re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',group,re.I):
                country = country_name; break
        if country == 'Unspecified':
            # Only recognised source tags, not guesses from words in a channel name.
            country = next((COUNTRIES[tag.upper()] for tag in re.findall(r'\[([A-Za-z]{2,3})\]', name or attrs.get('tvg-name','')) if tag.upper() in COUNTRIES), 'Unspecified')
    genre = attrs.get('tvg-genre',attrs.get('genre','')).strip()
    if not genre:
        candidate = normalise_genre(group)
        genre = candidate if candidate in {g for g,_ in GENRES} else 'Unspecified'
    else:
        genre = normalise_genre(genre)
    kind = 'Radio' if attrs.get('radio','').lower() in ('true','1','yes') else 'TV'
    kind = channel_kind({'kind':kind,'name':name or attrs.get('tvg-name',''),
                         'tvg_id':attrs.get('tvg-id',''),'group':group})
    return {'country':country,'genre':genre,'kind':kind,
            'transport':'Ace Stream' if ace_id(stream) else 'HTTP'}



def display_channel_name(name):
    """Display-only cleanup: never rewrite playlist, programme or stream metadata."""
    value=re.sub(r'[\u200b-\u200d\ufeff\x00-\x1f\x7f]', '', str(name))
    value=re.sub(r'[ⒼⓈⓎⓐ-ⓩ]', '', value).strip()
    annotation=re.compile(
        r'(?:\s*[@#]\s*(?:HD|SD|FHD|UHD|4K|2160P|1080P|720P|480P|50FPS|60FPS|UK|GB|US|USA|LIVE)'
        r'|\s*[@#]\s*'
        r'|\s*[\[(](?:HD|SD|FHD|UHD|4K|2160P|1080P|720P)[\])])\Z',
        re.I
    )
    for _ in range(8):
        cleaned=annotation.sub('',value).strip()
        if cleaned==value:
            break
        value=cleaned
    return re.sub(r'\s+', ' ', value).strip() or 'Unnamed channel'


def channel_section(channel):
    """Country/category navigator: keep original group-title and IDs intact."""
    if channel_kind(channel)=='Radio':
        return 'Radio'
    genre=normalise_genre(str(channel.get('genre') or ''))
    sections={'Sport','News','Movies','Kids','Music','Documentary','Entertainment','Education'}
    if genre in sections:
        return genre
    label=' '.join((display_channel_name(channel.get('name','')),str(channel.get('group') or '')))
    patterns=[
        ('News',r'\b(?:news|headlines?|weather)\b'),
        ('Sport',r'\b(?:sports?|football|cricket|racing|nba|nfl|golf)\b'),
        ('Movies',r'\b(?:movies?|cinema|films?)\b'),
        ('Kids',r'\b(?:kids|children|cartoons?|junior)\b'),
        ('Music',r'\b(?:music|concert)\b'),
        ('Documentary',r'\b(?:documentar(?:y|ies)|factual|history|nature)\b'),
        ('Education',r'\b(?:education|learning)\b'),
        ('Entertainment',r'\b(?:entertainment|comedy|drama)\b'),
    ]
    for section,pattern in patterns:
        if re.search(pattern,label,re.I):
            return section
    return 'General TV'


def catalogue(state):
    overrides = state.get('category_overrides', {})
    return [{**ch, **overrides.get(ch['id'], {})} for ch in state['channels']]


def default_state():
    from .sources import DEFAULT_PLAYLIST_URLS, DEFAULT_GUIDE_URLS
    return {'settings': {'playlist_url': 'https://search-ace.stream/playlist',
                         'playlist_urls': list(DEFAULT_PLAYLIST_URLS),
                         'xmltv_urls': list(DEFAULT_GUIDE_URLS), 'engine_url': 'http://127.0.0.1:6878',
                         'timezone': 'auto', 'epg_offset_minutes': 0,
                         'padding_before': 2, 'padding_after': 5,
                         'reserve_bytes': 1073741824, 'recording_dir': '',
                         'timeshift_enabled': False, 'timeshift_minutes': 30,
                         'timeshift_max_bytes': 4*1024**3, 'timeshift_dir': '',
                         'ui_scale': 100, 'button_size': 'Normal', 'engine_executable': ''},
            'channels': [], 'favourites': [], 'mappings': {}, 'jobs': []}


def http_url(value):
    if not isinstance(value, str) or len(value) > 8192:
        raise ValueError('Invalid URL')
    p = urlparse(value)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Use an HTTP(S) URL without embedded credentials')
    if any(ord(c) < 32 for c in value):
        raise ValueError('Invalid URL characters')
    return value


def ace_id(stream):
    p = urlparse(stream)
    if p.scheme == 'acestream':
        candidate = p.netloc or p.path.lstrip('/')
    else:
        q = parse_qs(p.query)
        candidate = next((q[k][0] for k in ('id', 'content_id', 'infohash') if k in q), '')
    return candidate.lower() if re.fullmatch('[a-fA-F0-9]{40}', candidate) else None


def stream_url(stream, engine):
    identifier = ace_id(stream)
    if identifier:
        return http_url(engine).rstrip('/') + '/ace/getstream?' + urlencode({'id': identifier})
    return http_url(stream)


def parse_playlist(text):
    if len(text.encode('utf-8')) > MAX_FEED:
        raise ValueError('Playlist is too large')
    channels, seen, attrs, name = [], set(), {}, ''
    for line in text.lstrip('\ufeff').splitlines():
        line = line.strip()
        if line.startswith('#EXTINF:'):
            header, _, name = line.partition(',')
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', header))
        elif line and not line.startswith('#'):
            aid = ace_id(line)
            if not aid:
                try:
                    http_url(line)
                except ValueError:
                    attrs, name = {}, ''
                    continue
            cid = aid or hashlib.sha256(line.encode()).hexdigest()[:40]
            if cid not in seen:
                seen.add(cid)
                channels.append({'id': cid, 'name': (name or attrs.get('tvg-name') or cid)[:512],
                                 'group': attrs.get('group-title', '')[:512],
                                 'tvg_id': attrs.get('tvg-id', '')[:512],
                                 'stream': 'acestream://' + aid if aid else line,
                                 **channel_categories(attrs,line,name)})
            attrs, name = {}, ''
    if not channels:
        raise ValueError('No supported channels found; cached catalogue was retained')
    if len(channels) > 100000:
        raise ValueError('Too many channels')
    return channels


def xmltv_time(value):
    match = re.fullmatch(r'(\d{14})(?:\s+([+-]\d{4}|Z|UTC|GMT))?', value.strip())
    if not match:
        raise ValueError('XMLTV time must include full date and seconds')
    date, offset = match.groups()
    if not offset or offset in ('Z', 'UTC', 'GMT'):
        offset = '+0000'
    return int(datetime.strptime(date + offset, '%Y%m%d%H%M%S%z').timestamp())


def parse_xmltv(text, offset_minutes=0):
    raw = text.encode('utf-8') if isinstance(text, str) else text
    if len(raw) > MAX_FEED:
        raise ValueError('XMLTV is too large')
    if b'<!ENTITY' in raw.upper():
        raise ValueError('XML entities are not permitted')
    # XMLTV commonly includes a harmless external DTD. ElementTree does not load it.
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError('Invalid XMLTV document') from exc
    if root.tag != 'tv':
        raise ValueError('Expected an XMLTV <tv> document')
    names = {c.get('id'): c.findtext('display-name', '')[:512] for c in root.findall('channel') if c.get('id')}
    programmes = []
    correction = int(offset_minutes) * 60
    for node in root.iter('programme'):
        try:
            start, end = xmltv_time(node.attrib['start']) + correction, xmltv_time(node.attrib['stop']) + correction
            if end <= start or not node.get('channel'):
                continue
            programmes.append({'channel': node.get('channel'), 'start': start, 'end': end,
                               'title': node.findtext('title', 'Untitled')[:1024],
                               'description': node.findtext('desc', '')[:8192],
                               'categories':[c.text[:512] for c in node.findall('category') if c.text][:32]})
        except (KeyError, ValueError):
            continue
        if len(programmes) > 200000:
            raise ValueError('Too many guide programmes')
    programmes.sort(key=lambda p: (p['channel'], p['start']))
    return names, programmes


def display_zone(selected='auto', detected=None):
    if selected != 'auto':
        return ZoneInfo(selected)
    if detected:
        return ZoneInfo(detected)
    return datetime.now().astimezone().tzinfo


def format_time(utc_seconds, selected='auto', day=True, detected=None):
    value = datetime.fromtimestamp(utc_seconds, timezone.utc).astimezone(display_zone(selected, detected))
    return value.strftime('%a %d %b %H:%M %Z' if day else '%H:%M %Z')


# Use only unambiguous aliases between the published UK playlist and Freeview EPG.
# BBC One/ITV1 regional listings deliberately require explicit user selection.
UK_EPG_ALIASES = {
    'bbctwo.uk': 'BBCTwoHD.uk',
    'bbcfour.uk': 'BBCFourHD.uk',
    'channel5.uk': '5.uk',
}


def _guide_name(value):
    value = re.sub(r'[ⒼⓈⓎⓐ-ⓩ]', '', value)
    value = re.sub(r'\s*\((?:\d{3,4}p|HD|SD|FHD|4K)\)', '', value, flags=re.I)
    value = re.sub(r'\s*\[(?:\d{3,4}p|HD|SD|FHD|4K)\]', '', value, flags=re.I)
    value = re.sub(r'\s+(?:HD|SD|FHD|4K)$', '', value, flags=re.I)
    return re.sub(r'\s+', ' ', value).strip().casefold()


def _guide_compact(value):
    """Normalise presentation differences without dropping regional identities."""
    text = _guide_name(display_channel_name(value)).replace('&', ' and ')
    numbers = {'one':'1', 'two':'2', 'three':'3', 'four':'4', 'five':'5',
               'six':'6', 'seven':'7', 'eight':'8', 'nine':'9', 'ten':'10'}
    text = re.sub(r'\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b',
                  lambda m:numbers[m.group()], text)
    return ''.join(char for char in text if char.isalnum())


def guide_suggestions(channel, guide_names, limit=8):
    """Rank fuzzy candidates for *manual* confirmation, never automatic assignment."""
    if limit<=0:return []
    name = _guide_compact(channel.get('name',''))
    tvg = _guide_compact(channel.get('tvg_id',''))
    if not name and not tvg:return []
    candidates=[]
    for key,label in guide_names.items():
        label_name=_guide_compact(label)
        key_name=_guide_compact(key)
        score=max(
            SequenceMatcher(None,name,label_name).ratio() if name and label_name else 0,
            SequenceMatcher(None,tvg,key_name).ratio() if tvg and key_name else 0,
        )
        if score>=0.5:
            candidates.append((score,key,label))
    candidates.sort(key=lambda entry:(-entry[0],str(entry[2]).casefold(),str(entry[1]).casefold()))
    return [(key,label) for _,key,label in candidates[:limit]]


def guide_lookup(guide_names):
    """Pre-index names once: thousands of channel filters remain O(1) each."""
    ids, labels = {}, {}
    for key, name in guide_names.items():
        # Compact labels recover safe spacing, punctuation and numeral variants.
        # A separate namespace prevents them from shadowing exact labels.
        alternatives=((ids, key.casefold()), (labels, _guide_name(name)),
                      (labels, '\\0'+_guide_compact(name)))
        for table, normalized in alternatives:
            if normalized in table:
                table[normalized] = None  # Ambiguous; require explicit mapping.
            else:
                table[normalized] = key
    return ids, labels


def match_guide(channel, mappings, guide_names, lookup=None):
    if channel['id'] in mappings:
        return mappings[channel['id']]
    cid = channel.get('tvg_id', '')
    if cid in guide_names:
        return cid
    ids, labels = lookup if lookup is not None else guide_lookup(guide_names)
    if cid:
        match = ids.get(cid.casefold())
        if match:
            return match
        base = cid.partition('@')[0]
        if base != cid:
            match = ids.get(base.casefold())
            if match:
                return match
        alias = UK_EPG_ALIASES.get(base.casefold())
        if alias:
            match = ids.get(alias.casefold())
            if match:
                return match
    exact = labels.get(_guide_name(channel['name']))
    if exact:return exact
    return labels.get('\\0'+_guide_compact(channel['name'])) or cid


def make_job(channel_id, title, start, end, before=2, after=5):
    if end <= start or before < 0 or after < 0:
        raise ValueError('A recording must end after its start')
    return {'id': str(uuid.uuid4()), 'channel_id': channel_id, 'title': title[:1024],
            'start': int(start) - int(before)*60, 'end': int(end) + int(after)*60,
            'status': 'queued', 'bytes': 0}


def check_conflicts(jobs, candidate):
    return [j for j in jobs if j['id'] != candidate['id'] and j['status'] in ACTIVE
            and j['start'] < candidate['end'] and candidate['start'] < j['end']]


def safe_filename(title, timestamp):
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip(' .')[:90] or 'Recording'
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y%m%d-%H%M%S')
    return f'{date}_{title}.ts'


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid ' + label)


def validate_state(state):
    if not isinstance(state, dict) or set(default_state()) - set(state):
        raise ValueError('Backup is missing required data')
    if not isinstance(state['settings'], dict):
        raise ValueError('Invalid settings')
    settings = state['settings']
    if set(default_state()['settings']) - {'playlist_urls','timeshift_enabled','timeshift_minutes','timeshift_max_bytes','timeshift_dir','ui_scale','button_size','engine_executable'} - set(settings):
        raise ValueError('Backup is missing required settings')
    for key in ('playlist_url', 'engine_url'):
        http_url(settings[key])
    if not isinstance(settings['xmltv_urls'], list) or len(settings['xmltv_urls']) > 20:
        raise ValueError('Use at most 20 guide sources')
    for url in settings['xmltv_urls']:
        http_url(url)
    if 'playlist_urls' in settings:
        if not isinstance(settings['playlist_urls'], list) or not 1 <= len(settings['playlist_urls']) <= 16:
            raise ValueError('Use 1 to 16 playlist URLs')
        for url in settings['playlist_urls']:
            http_url(url)
    try:
        if settings['timezone'] != 'auto':
            ZoneInfo(settings['timezone'])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError('Unknown timezone') from exc
    for key in ('padding_before', 'padding_after'):
        _integer(settings[key], 0, 240, key)
    _integer(settings['epg_offset_minutes'], -1440, 1440, 'guide offset')
    _integer(settings['reserve_bytes'], 0, 1024**5, 'storage reserve')
    if 'ui_scale' in settings:
        _integer(settings['ui_scale'],75,150,'interface scale')
    if 'button_size' in settings and settings['button_size'] not in ('Compact','Normal','Large'):
        raise ValueError('Invalid button size')
    if 'engine_executable' in settings and (not isinstance(settings['engine_executable'],str) or len(settings['engine_executable'])>4096):
        raise ValueError('Invalid engine executable path')
    if not isinstance(settings['recording_dir'], str) or len(settings['recording_dir']) > 4096:
        raise ValueError('Invalid destination')
    # Optional for old 0.1.x settings and portable backups.
    if 'timeshift_enabled' in settings and type(settings['timeshift_enabled']) is not bool:
        raise ValueError('Timeshift enabled must be boolean')
    if 'timeshift_minutes' in settings:
        _integer(settings['timeshift_minutes'], 1, 240, 'timeshift minutes')
    if 'timeshift_max_bytes' in settings:
        _integer(settings['timeshift_max_bytes'], 256*1024**2, 32*1024**3, 'timeshift disk quota')
    if 'timeshift_dir' in settings and (not isinstance(settings['timeshift_dir'],str) or
                                     len(settings['timeshift_dir'])>4096):
        raise ValueError('Invalid timeshift folder')
    for key, limit in (('channels', 100000), ('favourites', 100000), ('jobs', 10000)):
        if not isinstance(state[key], list) or len(state[key]) > limit:
            raise ValueError('Invalid ' + key)
    ids = set()
    for ch in state['channels']:
        if not isinstance(ch, dict) or any(not isinstance(ch.get(k), str) for k in ('id','name','stream','group','tvg_id')):
            raise ValueError('Invalid channel')
        if not re.fullmatch('[a-f0-9]{40}', ch['id']) or ch['id'] in ids:
            raise ValueError('Duplicate or invalid channel identifier')
        ids.add(ch['id'])
        if 'source' in ch:
            http_url(ch['source'])
        for key in ('country','genre','kind','transport'):
            if key in ch and (not isinstance(ch[key],str) or len(ch[key])>512):
                raise ValueError('Invalid channel category')
        if not ace_id(ch['stream']):
            http_url(ch['stream'])
    if any(not isinstance(f, str) or not re.fullmatch('[a-f0-9]{40}', f) for f in state['favourites']):
        raise ValueError('Invalid favourites')
    if not isinstance(state['mappings'], dict) or len(state['mappings']) > 100000 or any(not isinstance(k,str) or not isinstance(v,str) or len(v)>512 for k,v in state['mappings'].items()):
        raise ValueError('Invalid guide mappings')
    overrides = state.get('category_overrides', {})
    if not isinstance(overrides, dict) or len(overrides) > 100000:
        raise ValueError('Invalid saved categories')
    for cid, values in overrides.items():
        if not isinstance(cid,str) or not re.fullmatch('[a-f0-9]{40}',cid) or not isinstance(values,dict) or set(values)-{'country','genre','kind'}:
            raise ValueError('Invalid saved categories')
        if any(not isinstance(v,str) or not v.strip() or len(v)>512 for v in values.values()) or values.get('kind','TV') not in ('TV','Radio'):
            raise ValueError('Invalid saved categories')
    job_ids = set()
    for job in state['jobs']:
        if not isinstance(job, dict) or not isinstance(job.get('id'), str) or job['id'] in job_ids or len(job['id']) > 100:
            raise ValueError('Invalid job identifier')
        job_ids.add(job['id'])
        if job.get('status') not in STATUSES or not isinstance(job.get('title'), str) or len(job['title']) > 1024:
            raise ValueError('Invalid job')
        if not isinstance(job.get('channel_id'), str) or not re.fullmatch('[a-f0-9]{40}', job['channel_id']):
            raise ValueError('Invalid job channel')
        _integer(job.get('start'), 0, 253402300799, 'start time')
        _integer(job.get('end'), 1, 253402300799, 'end time')
        if job['end'] <= job['start']:
            raise ValueError('Invalid recording interval')
    return state


def export_backup(state):
    data = copy.deepcopy(validate_state(state))
    data['settings']['recording_dir'] = ''
    # Keep only the portable recording contract, not paths or device grants.
    data['jobs'] = [{k:j[k] for k in ('id','channel_id','title','start','end','status')} for j in data['jobs']]
    for key in ('playlist_url', 'engine_url'):
        data['settings'][key] = _redact_url(data['settings'][key])
    data['settings']['xmltv_urls'] = [_redact_url(u) for u in data['settings']['xmltv_urls']]
    if 'playlist_urls' in data['settings']:
        data['settings']['playlist_urls'] = [_redact_url(u) for u in data['settings']['playlist_urls']]
    for ch in data['channels']:
        ch['stream'] = _redact_url(ch['stream'])
        if 'source' in ch:
            ch['source'] = _redact_url(ch['source'])
    payload = json.dumps({'app':'DizyTV', 'version':1, 'data':data}, ensure_ascii=False, indent=2)
    if len(payload.encode('utf-8')) > MAX_BACKUP:
        raise ValueError('Backup is too large')
    return payload


def _redact_url(url):
    p = urlparse(url)
    query = parse_qs(p.query)
    safe = {k:v for k,v in query.items() if not re.search('token|key|pass|secret|auth|signature', k, re.I)}
    return p._replace(query=urlencode(safe, doseq=True)).geturl()


def restore_backup(payload, now=None):
    if len(payload.encode('utf-8')) > MAX_BACKUP:
        raise ValueError('Backup is too large')
    try:
        backup = json.loads(payload)
    except (ValueError, RecursionError) as exc:
        raise ValueError('Invalid backup JSON') from exc
    if not isinstance(backup, dict) or backup.get('app') != 'DizyTV' or type(backup.get('version')) is not int or backup['version'] != 1:
        raise ValueError('Unsupported DizyTV backup version')
    state = copy.deepcopy(validate_state(backup.get('data')))
    state['settings']['recording_dir'] = ''
    state['settings']['timeshift_dir'] = ''
    state['settings']['timeshift_enabled'] = False
    state['settings']['engine_executable'] = ''
    now = int(time.time()) if now is None else now
    state['jobs']=[{k:j[k] for k in ('id','channel_id','title','start','end','status')} for j in state['jobs']]
    for job in state['jobs']:
        if job['status'] not in TERMINAL:
            job['status'] = 'missed' if job['end'] <= now else 'paused'
    return state
