"""Opt-in, bounded channel reachability snapshots for large IPTV catalogues.

These are safe lightweight GET samples, not VLC playback, licence or DRM tests.
Never auto-hide a channel from the user's catalogue based on a one-off failure.
No URLs (including query tokens) or IP addresses are saved in reports.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .core import ace_request_params, http_url

BATCH_SIZE = 40
MAX_WORKERS = 4
TIMEOUT = 4
MAX_RESPONSE = 2048


def public_stream_url(url):
    """Do not use an untrusted playlist to probe the user's LAN or loopback."""
    url = http_url(url)
    parsed = urlsplit(url)
    hostname = (parsed.hostname or '').lower().rstrip('.')
    if hostname in ('localhost', 'localhost.localdomain') or hostname.endswith(('.localhost','.local','.internal')):
        raise ValueError('Local or private endpoints are not scanned')
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        # Reject domain names that currently resolve to local/private networks.
        # Revalidation also applies to all redirects below.
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme=='https' else 80),
                                        type=socket.SOCK_STREAM)
        if not addresses:
            raise ValueError('Unable to resolve host')
        for record in addresses:
            address = ipaddress.ip_address(record[4][0])
            if not address.is_global:
                raise ValueError('Local or private endpoints are not scanned')
    else:
        if not address.is_global:
            raise ValueError('Local or private endpoints are not scanned')
    return url


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return super().redirect_request(req,fp,code,msg,headers,public_stream_url(newurl))


def interpret_http(code, content_type='', body=b''):
    if code in (401,403):
        return ('access-limited', 'Access denied; token, account, provider or region may restrict this stream')
    if code in (404,410):
        return ('missing', 'Stream endpoint missing / expired')
    if code == 429:
        return ('rate-limited', 'Provider rate-limited this check; retry later')
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
    if ace_request_params(channel.get('stream','')) is not None:
        return {'status':'engine-required','detail':'Ace peer/session playback must be checked manually (not HTTP scanned)'}
    try:
        stream=public_stream_url(channel['stream'])
        client=opener if opener is not None else build_opener(PublicRedirect()).open
        request=Request(stream,headers={'User-Agent':'Mozilla/5.0 (compatible; DizyTV/0.1)',
                                      'Range':'bytes=0-2047','Accept':'*/*'})
        with client(request,timeout=timeout) as response:
            # Some providers redirect to an unrelated private address.
            public_stream_url(response.geturl())
            data=response.read(MAX_RESPONSE)
            status,detail=interpret_http(response.status,response.headers.get('Content-Type',''),data)
            return {'status':status,'detail':detail}
    except HTTPError as exc:
        status,detail=interpret_http(exc.code)
    except (ValueError,KeyError) as exc:
        status,detail='skipped','Private/untrusted stream or invalid address; not probed'
    except (URLError,TimeoutError,socket.timeout,OSError):
        status,detail='unreachable','Stream connection failed or timed out from this network'
    return {'status':status,'detail':detail}


def check_batch(channels, start=0, batch_size=BATCH_SIZE, workers=MAX_WORKERS, checker=check_channel):
    """40 max / four parallel requests; no persistent background polling."""
    if not isinstance(start,int) or start<0:
        raise ValueError('Invalid batch offset')
    if not isinstance(batch_size,int) or not 1<=batch_size<=BATCH_SIZE:
        raise ValueError('Invalid batch size')
    if not isinstance(workers,int) or not 1<=workers<=MAX_WORKERS:
        raise ValueError('Invalid worker count')
    portion=list(channels[start:start+batch_size])
    results=[None]*len(portion)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(checker,ch):i for i,ch in enumerate(portion)}
        for future in as_completed(tasks):
            i=tasks[future]
            try:result=future.result()
            except Exception:result={'status':'unreachable','detail':'Unexpected stream probe failure'}
            results[i]={'id':portion[i].get('id',''),'name':str(portion[i].get('name',''))[:150],
                        'status':result['status'],'detail':result['detail']}
    return results,start+len(portion)
