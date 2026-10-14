"""Short, non-invasive HTTP stream checks. No VPN/DRM bypass or secret URL logs."""
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from .network import SafeRedirect
from .core import http_url

def explain_status(code):
    if code in (401,403):
        return f'HTTP {code}: stream access denied (possible geo restriction, expired token or authentication). Check official availability.'
    if code in (404,410):
        return f'HTTP {code}: the playlist or stream endpoint is missing or no longer available.'
    if code==429:
        return 'HTTP 429: the stream host is rate-limiting requests; try again later.'
    if code>=500:
        return f'HTTP {code}: the stream provider is currently reporting a server error.'
    if code>=400:
        return f'HTTP {code}: the host rejected playback.'
    return f'HTTP {code}: the address responds, but this does not guarantee VLC can decode the stream.'

def probe_stream(url,timeout=5):
    """Bounded GET rather than HEAD: many free streaming origins reject HEAD."""
    try:
        request=Request(http_url(url),headers={
            'User-Agent':'Mozilla/5.0 (compatible; DizyTV/0.1)',
            'Range':'bytes=0-1023','Accept':'*/*'})
        with build_opener(SafeRedirect).open(request,timeout=timeout) as response:
            snippet=response.read(1024)
            content_type=response.headers.get('Content-Type','').lower()
            if snippet.startswith(b'#EXTM3U'):
                return 'HTTP reachable (HLS playlist). VLC failure may be caused by unavailable segments, format or stream restrictions.'
            if content_type.startswith('text/html'):
                return 'The URL returns an HTML page rather than a direct stream. This playlist entry may be expired or require a supported official player.'
            return explain_status(response.status)
    except HTTPError as exc:
        return explain_status(exc.code)
    except (URLError,TimeoutError,socket.timeout,ssl.SSLError,OSError,ValueError) as exc:
        # Never include the raw URL or its possibly private authorization tokens.
        return 'Stream connection failed ('+type(exc).__name__+'). Check network/DNS/TLS, provider availability and local firewall.'
