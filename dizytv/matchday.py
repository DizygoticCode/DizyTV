"""Free-tier football fixture discovery and permission-based local viewing links.

TheSportsDB v1/123 is a documented, rate-limited public API. Its free plan
returns only some fixtures: NEVER imply comprehensive league or live coverage.
Fixtures are metadata, not authorisation to retransmit a stream.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
import json
import re
import time

from .storage import atomic_json

API = 'https://www.thesportsdb.com/api/v1/json/123/'
LEAGUES = (
    ('4328', 'Premier League'),
    ('4329', 'Championship'),
    ('4396', 'League One'),
    ('4397', 'League Two'),
    ('4482', 'FA Cup'),
    ('4570', 'EFL Cup'),
    ('4480', 'Champions League'),
    ('4481', 'Europa League'),
    ('5071', 'Conference League'),
)
LEAGUE_NAMES = dict(LEAGUES)
CACHE_AGE = 30 * 60
MAX_BODY = 1_048_576
MAX_LOCAL_SOURCES = 100


def _utc_timestamp(row):
    value = str(row.get('strTimestamp') or '')
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return int(parsed.replace(tzinfo=timezone.utc).timestamp()) if parsed.tzinfo is None else int(parsed.timestamp())
        except (ValueError, OverflowError):
            pass
    date = str(row.get('dateEvent') or '')
    clock = str(row.get('strTime') or '')
    if not re.fullmatch(r'\d{4}-\d\d-\d\d', date) or not re.fullmatch(r'\d\d:\d\d(?::\d\d)?', clock):
        return None
    try:
        return int(datetime.fromisoformat(date+'T'+clock).replace(tzinfo=timezone.utc).timestamp())
    except (ValueError, OverflowError):
        return None


def parse_fixtures(payload, league_id):
    """Only accept matches in the requested league; never guess team mappings."""
    if not isinstance(payload, dict):
        raise ValueError('Invalid fixture response')
    rows = payload.get('events')
    if rows is None:
        return []
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError('Invalid fixture event list')
    result = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get('idLeague')) != str(league_id):
            continue
        home = str(row.get('strHomeTeam') or '').strip()[:100]
        away = str(row.get('strAwayTeam') or '').strip()[:100]
        event_id = str(row.get('idEvent') or '')
        if not (home and away and event_id.isdecimal() and len(event_id) <= 16):
            continue
        kickoff = _utc_timestamp(row)
        if kickoff is None:
            continue  # Never fabricate a kickoff time.
        result.append(dict(id=event_id, competition=LEAGUE_NAMES[str(league_id)],
                           league_id=str(league_id), home=home, away=away,
                           kickoff=kickoff, status=str(row.get('strStatus') or '')[:36],
                           provider='TheSportsDB (free tier, incomplete)'))
    return result


def _fetch(endpoint, params):
    if endpoint not in ('eventsnextleague.php', 'eventsday.php'):
        raise ValueError('Unsupported fixture API endpoint')
    url = API + endpoint + '?' + urlencode(params)
    request = Request(url, headers={'User-Agent': 'DizyTV/0.1 (fixtures)',
                                    'Accept': 'application/json'})
    with urlopen(request, timeout=7) as response:
        if urlsplit(response.geturl()).hostname not in ('www.thesportsdb.com', 'thesportsdb.com'):
            raise ValueError('Fixture provider redirected to an unexpected host')
        data = response.read(MAX_BODY + 1)
    if len(data) > MAX_BODY:
        raise ValueError('Fixture response too large')
    return json.loads(data.decode('utf-8'))


def collect_fixtures(today=None, fetch=None):
    """Bound to 11 API calls/refresh and show missing-coverage warning in UI.

    All nine leagues supply the nearest *single* event. Two additional
    Championship date queries support today's and tomorrow's favourite club.
    No inference of live status or viewing rights is made.
    """
    today = today or datetime.now(timezone.utc).date()
    fetch = fetch or _fetch
    matches = {}
    errors = []
    for league_id, _name in LEAGUES:
        try:
            payload = fetch('eventsnextleague.php', {'id': league_id})
            for event in parse_fixtures(payload, league_id):
                matches[event['id']] = event
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f'{_name}: {type(exc).__name__}')
    for day in (today, today + timedelta(days=1)):
        try:
            payload = fetch('eventsday.php', {'d': day.isoformat(), 'l': '4329'})
            for event in parse_fixtures(payload, '4329'):
                matches[event['id']] = event
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f'Championship {day}: {type(exc).__name__}')
    return sorted(matches.values(), key=lambda event: (event['kickoff'], event['id'])), errors


def cached_fixtures(folder, fetch=None, refresh=False, now=None, offline=False):
    """Cache separately from state.json: never erase recordings or settings."""
    path = Path(folder) / 'matchday-fixtures.json'
    now = time.time() if now is None else now
    prior = None
    try:
        if path.is_file() and path.stat().st_size <= MAX_BODY:
            candidate = json.loads(path.read_text('utf-8'))
            if isinstance(candidate, dict) and isinstance(candidate.get('fixtures'), list):
                prior = candidate
                if not refresh and 0 <= now - candidate.get('fetched_at', 0) < CACHE_AGE:
                    return prior['fixtures'], [], True
    except (OSError, ValueError, TypeError):
        pass
    if offline:
        return (prior['fixtures'] if prior else []), [], bool(prior)
    try:
        fixtures, errors = collect_fixtures(fetch=fetch)
        if errors and prior and not fixtures:
            return prior['fixtures'], errors, True
        if fixtures:
            atomic_json(path, {'fetched_at': now, 'fixtures': fixtures}, max_bytes=MAX_BODY)
        return fixtures, errors, False
    except (OSError, ValueError, TypeError):
        if prior:
            return prior['fixtures'], ['Fixture provider unavailable'], True
        raise


def safe_public_url(url):
    """User-entered sources never become network fetch targets in DizyTV.

    Do not accept passwords, tokens/query strings, localhost, IP literals or
    private naming conventions. This is not proof of legality or playability.
    """
    url = str(url).strip()
    if not 10 <= len(url) <= 1500:
        raise ValueError('Source URL length is invalid')
    parts = urlsplit(url)
    host = (parts.hostname or '').lower().rstrip('.')
    if (parts.scheme != 'https' or not host or parts.username or parts.password
            or parts.query or parts.fragment or '\\' in url or parts.port not in (None, 443)
            or host.endswith(('.localhost', '.local', '.internal', '.test'))
            or '.' not in host or '..' in host):
        raise ValueError('Only plain public HTTPS URLs without tokens are accepted')
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('IP-address sources are not accepted')
    if any(ord(c) < 32 for c in url):
        raise ValueError('Invalid characters in source URL')
    return url


def validate_source(source):
    if not isinstance(source, dict):
        raise ValueError('Invalid Matchday source')
    event_id = str(source.get('event_id', ''))
    label = str(source.get('label') or '').strip()
    kind = source.get('kind')
    if not event_id.isdecimal() or len(event_id) > 16 or not 1 <= len(label) <= 80:
        raise ValueError('Invalid event or source label')
    if kind not in ('web', 'hls'):
        raise ValueError('Choose a browser link or direct HLS source')
    url = safe_public_url(source.get('url', ''))
    if kind == 'hls' and not urlsplit(url).path.lower().endswith('.m3u8'):
        raise ValueError('Direct playback requires an HLS .m3u8 URL')
    if source.get('permission_confirmed') is not True:
        raise ValueError('Confirm your permission to view this source')
    return {'event_id': event_id, 'label': label, 'url': url, 'kind': kind,
            'permission_confirmed': True, 'verified': False}


def load_sources(folder):
    path = Path(folder) / 'matchday-sources.json'
    if not path.is_file():
        return []
    if path.stat().st_size > 256_000:
        raise ValueError('Matchday source list is too large')
    rows = json.loads(path.read_text('utf-8'))
    if not isinstance(rows, list) or len(rows) > MAX_LOCAL_SOURCES:
        raise ValueError('Invalid Matchday source list')
    return [validate_source(row) for row in rows]


def add_source(folder, source):
    item = validate_source(source)
    records = load_sources(folder)
    if len(records) >= MAX_LOCAL_SOURCES:
        raise ValueError('Matchday source limit reached')
    if not any(x['event_id'] == item['event_id'] and x['url'] == item['url'] for x in records):
        records.append(item)
        atomic_json(Path(folder) / 'matchday-sources.json', records, max_bytes=256_000)
    return records


def is_favourite(fixture, team='Southampton'):
    tokens = (fixture.get('home', ''), fixture.get('away', ''))
    return any(team.strip().casefold() in value.casefold() for value in tokens)
