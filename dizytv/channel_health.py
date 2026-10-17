"""Opt-in, bounded channel reachability snapshots for large IPTV catalogues.

These are safe lightweight GET samples, not VLC playback, licence or DRM tests.
Never auto-hide a channel from the user's catalogue based on a one-off failure.
No URLs (including query tokens) or IP addresses are saved in reports.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import http.client
import ipaddress
import queue
import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request

from .core import ace_request_params, http_url

CONCLUSIVE_MISSING = frozenset({'missing'})


def confirmed_missing_ids(results):
    """Require *two consecutive* explicit HTTP 404/410 observations per ID.

    A timeout, 403, transient provider fault or a newly restored manifest
    resets the streak; the status is endpoint-missing rather than conclusive
    information about a broadcaster or another feed with the same name.
    """
    consecutive = {}
    for entry in results:
        cid = entry.get('id', '')
        if not cid:continue
        consecutive[cid] = consecutive.get(cid,0)+1 if entry.get('status') in CONCLUSIVE_MISSING else 0
    return {cid for cid,misses in consecutive.items() if misses>=2}


BATCH_SIZE = 40
MAX_WORKERS = 4
TIMEOUT = 4
MAX_RESPONSE = 2048


def _public_endpoint(url):
    """Resolve once and pin the actual connection to a verified public IP.

    Never do DNS validation with one lookup and then let the HTTP library do
    a second, potentially private, lookup when opening the socket.
    """
    url = http_url(url)
    parsed = urlsplit(url)
    hostname = (parsed.hostname or '').lower().rstrip('.')
    if parsed.username or parsed.password:
        raise ValueError('Embedded URL credentials are not accepted')
    if hostname in ('localhost', 'localhost.localdomain') or hostname.endswith(
            ('.localhost', '.local', '.internal')):
        raise ValueError('Local or private endpoints are not scanned')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        if not addresses:
            raise ValueError('Unable to resolve host')
        ips = [ipaddress.ip_address(entry[4][0]) for entry in addresses]
    else:
        ips = [literal]
    if any(not ip.is_global for ip in ips):
        raise ValueError('Local or private endpoints are not scanned')
    return url, parsed, str(ips[0]), port


def public_stream_url(url):
    """Validate an HTTP stream URL against local/private network access."""
    return _public_endpoint(url)[0]


def _probe_public(url, timeout):
    """Direct public-IP-only HTTP probe; TLS still verifies the real hostname."""
    deadline = time.monotonic() + timeout
    current = url
    for hop in range(4):
        clean, parsed, pinned_ip, port = _public_endpoint(current)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Stream probe deadline exceeded')
        host = parsed.hostname
        connection_type = (http.client.HTTPSConnection if parsed.scheme == 'https'
                           else http.client.HTTPConnection)
        conn = connection_type(host, port, timeout=remaining)

        def create_pinned_connection(_target, connect_timeout=None, source_address=None):
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError('Stream probe deadline exceeded')
            return socket.create_connection((pinned_ip, port), timeout=left,
                                            source_address=source_address)

        # http.client calls this for the actual socket. For HTTPS it retains
        # the original host for SNI and certificate hostname verification.
        conn._create_connection = create_pinned_connection
        try:
            target = parsed.path or '/'
            if parsed.query:
                target += '?' + parsed.query
            conn.request('GET', target, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; DizyTV/0.1)',
                'Range': 'bytes=0-2047', 'Accept': '*/*',
            })
            response = conn.getresponse()
            status = response.status
            if status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location:
                    return 'unverified', 'Redirect response has no destination'
                if hop == 3:
                    return 'unverified', 'Too many stream redirects'
                # The next iteration revalidates and pins every redirect hop.
                current = urljoin(clean, location)
                continue
            # Error status is already conclusive at the headers. Waiting for
            # a slow error body could lose a 429 and keep scanning its provider.
            if status >= 400:
                return interpret_http(status)
            # read1 samples only the first available chunk: read(2048) could
            # otherwise wait forever for a slow trickle to fill the buffer.
            data = response.read1(MAX_RESPONSE)
            return interpret_http(status, response.getheader('Content-Type', ''), data)
        finally:
            conn.close()
    return 'unverified', 'Too many stream redirects'


# A per-channel daemon enforces an actual UI deadline even for a hostile slow
# DNS resolver or HTTP headers trickling below a socket-level timeout. Limit
# outstanding probes so timed-out daemon threads cannot create unbounded sockets.
_PROBE_SLOTS = threading.BoundedSemaphore(MAX_WORKERS)


def _bounded_probe(url, timeout):
    result = queue.Queue(maxsize=1)

    def worker():
        if not _PROBE_SLOTS.acquire(blocking=False):
            result.put(('checker-busy', 'Stream checker is busy; not probed, retry later'))
            return
        try:
            try:
                result.put(_probe_public(url, timeout))
            except ValueError:
                result.put(('skipped', 'Private/untrusted stream or invalid address; not probed'))
            except (URLError, TimeoutError, socket.timeout, OSError, http.client.HTTPException):
                result.put(('unreachable', 'Stream connection failed or timed out from this network'))
            except Exception:
                result.put(('unreachable', 'Unexpected stream probe failure'))
        finally:
            _PROBE_SLOTS.release()

    threading.Thread(target=worker, daemon=True, name='dizytv-health-probe').start()
    try:
        return result.get(timeout=timeout)
    except queue.Empty:
        return 'unreachable', 'Stream check exceeded the overall time limit'


def interpret_http(code, content_type='', body=b''):
    if code in (401,403):
        return ('access-limited', 'Access denied; token, account, provider or region may restrict this stream')
    if code in (404,410):
        return ('missing', 'Stream endpoint missing / expired')
    if code == 429:
        return ('rate-limited', 'Provider rate-limited this check; retry later')
    if code == 451:
        return ('access-limited', 'HTTP 451: provider reports a legal access restriction; check official availability')
    if code >= 500:
        return ('provider-error', 'Stream provider returned HTTP '+str(code))
    if code >= 400:
        return ('rejected', 'Stream host returned HTTP '+str(code))
    if content_type.lower().split(';')[0].strip() in ('text/html', 'application/xhtml+xml') or body.lstrip().lower().startswith((b'<!doctype html',b'<html')):
        return ('not-a-stream', 'Stream URL returned a web page, not a video playlist')
    if body.lstrip().startswith(b'#EXTM3U'):
        if b'#EXT-X-' in body:
            return ('manifest-only','HLS manifest reachable; media segments and VLC decode NOT verified')
        return ('playlist-only','Playlist reachable; playable media NOT verified')
    if content_type.lower().startswith(('video/','audio/')) or body.startswith((b'G',b'\x47')):
        return ('data-response','Media endpoint responds; picture/audio still not verified')
    return ('unverified','HTTP '+str(code)+' response; media format and playback not verified')


def check_channel(channel, timeout=TIMEOUT, opener=None):
    """Classify one channel without reading whole streams or exposing its URL."""
    if ace_request_params(channel.get('stream', '')) is not None:
        return {'status': 'engine-required',
                'detail': 'Ace peer/session playback must be checked manually (not HTTP scanned)'}
    try:
        if opener is None:
            # Production uses pinned sockets rather than urllib's second DNS
            # lookup, and a strict overall deadline even for slow responders.
            status, detail = _bounded_probe(channel['stream'], timeout)
        else:
            # Optional test-injected opener; never used for live network I/O.
            stream = public_stream_url(channel['stream'])
            request = Request(stream, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; DizyTV/0.1)',
                'Range': 'bytes=0-2047', 'Accept': '*/*',
            })
            with opener(request, timeout=timeout) as response:
                public_stream_url(response.geturl())
                data = response.read1(MAX_RESPONSE) if hasattr(response, 'read1') else response.read(MAX_RESPONSE)
                status, detail = interpret_http(
                    response.status, response.headers.get('Content-Type', ''), data)
    except HTTPError as exc:
        status, detail = interpret_http(exc.code)
    except (ValueError, KeyError):
        status, detail = 'skipped', 'Private/untrusted stream or invalid address; not probed'
    except (URLError, TimeoutError, socket.timeout, OSError, http.client.HTTPException):
        status, detail = 'unreachable', 'Stream connection failed or timed out from this network'
    return {'status': status, 'detail': detail}


def check_batch(channels, start=0, batch_size=BATCH_SIZE, workers=MAX_WORKERS, checker=check_channel):
    """Check a contiguous prefix, pausing on HTTP 429 or exhausted capacity.

    At most four probes are in flight. Those already started may finish after
    a pause; the returned offset resumes at the first unchecked channel. A
    trailing checker-busy entry signals a pause, not a completed observation.
    """
    if not isinstance(start,int) or start<0:
        raise ValueError('Invalid batch offset')
    if not isinstance(batch_size,int) or not 1<=batch_size<=BATCH_SIZE:
        raise ValueError('Invalid batch size')
    if not isinstance(workers,int) or not 1<=workers<=MAX_WORKERS:
        raise ValueError('Invalid worker count')
    portion=list(channels[start:start+batch_size])
    results=[None]*len(portion)
    paused=threading.Event()

    def check_one(channel):
        result=checker(channel)
        if result['status'] in ('rate-limited','checker-busy'):
            # Publish from the worker before the coordinator can refill slots.
            paused.set()
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        next_index=0
        tasks={}
        while tasks or (next_index<len(portion) and not paused.is_set()):
            while not paused.is_set() and len(tasks)<workers and next_index<len(portion):
                tasks[pool.submit(check_one,portion[next_index])]=next_index
                next_index+=1
            completed,_=wait(tasks,return_when=FIRST_COMPLETED)
            # Inspect all ready results before scheduling any more requests.
            for future in completed:
                i=tasks.pop(future)
                try:result=future.result()
                except Exception:result={'status':'unreachable','detail':'Unexpected stream probe failure'}
                results[i]={'id':portion[i].get('id',''),'name':str(portion[i].get('name',''))[:150],
                            'status':result['status'],'detail':result['detail']}
    for i,result in enumerate(results[:next_index]):
        if result['status']=='checker-busy':
            # Do not skip or cache channels for which no probe could start.
            # Already-running results after this gap are retried only manually.
            return results[:i+1],start+i
    return results[:next_index],start+next_index
