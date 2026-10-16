"""Short, non-invasive HTTP stream checks. No VPN/DRM bypass or secret URL logs."""
import errno
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

def explain_connection_failure(exc):
    """Classify standard exception *types*, never interpolate raw provider strings.

    URLError.reason may contain a credential-bearing URL, private hostname,
    proxy address or local path. Only stable built-in error classes/codes are
    allowed in the user-facing message.
    """
    reason=exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, ssl.SSLCertVerificationError):
        return 'Stream TLS certificate verification failed. Check device time and the source provider certificate.'
    if isinstance(reason, (TimeoutError, socket.timeout)) or (
            isinstance(reason, OSError) and reason.errno==errno.ETIMEDOUT):
        return 'Stream connection timed out. The provider or network may be slow or unreachable.'
    if isinstance(reason, socket.gaierror):
        return 'Stream DNS lookup failed. Check the network or try another authorised source.'
    if isinstance(reason, ConnectionRefusedError) or (
            isinstance(reason, OSError) and reason.errno==errno.ECONNREFUSED):
        return 'Stream connection was refused by the host. The service may be offline.'
    if isinstance(reason, ConnectionResetError) or (
            isinstance(reason, OSError) and reason.errno in (errno.ECONNRESET,errno.ECONNABORTED)):
        return 'Stream connection was reset or aborted. The provider may have disconnected.'
    if isinstance(reason, ssl.SSLError):
        return 'Stream TLS negotiation failed. Check the source and device certificate configuration.'
    if isinstance(reason, ValueError):
        return 'Stream URL is invalid or redirects to an unsupported address.'
    return 'Stream connection failed (network or provider). Check the source and try another authorised stream.'


def probe_stream(url,timeout=5):
    """Bounded GET rather than HEAD: many free streaming origins reject HEAD."""
    try:
        request=Request(http_url(url),headers={
            'User-Agent':'Mozilla/5.0 (compatible; DizyTV/0.1)',
            'Range':'bytes=0-1023','Accept':'*/*'})
        with build_opener(SafeRedirect).open(request,timeout=timeout) as response:
            snippet=response.read(1024)
            content_type=response.headers.get('Content-Type','').lower()
            if snippet.lstrip(b'\xef\xbb\xbf \t\r\n').startswith(b'#EXTM3U'):
                return 'HTTP reachable (HLS playlist). VLC failure may be caused by unavailable segments, format or stream restrictions.'
            if content_type.startswith('text/html') or snippet.lstrip().lower().startswith((b'<!doctype html',b'<html')):
                return 'The URL returns an HTML page rather than a direct stream. EPG listings may still appear without playable video; try another authorised source or the official player.'
            return explain_status(response.status)
    except HTTPError as exc:
        return explain_status(exc.code)
    except (URLError,TimeoutError,socket.timeout,ssl.SSLError,OSError,ValueError) as exc:
        # Never include the raw URL or its possibly private authorization tokens.
        return explain_connection_failure(exc)
