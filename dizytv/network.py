"""Bounded feed downloads with independently validated HTTP redirects."""
import gzip
import io
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .core import http_url, MAX_FEED


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url):
    request = Request(http_url(url), headers={'User-Agent':'DizyTV/0.1', 'Accept-Encoding':'identity'})
    with build_opener(SafeRedirect).open(request, timeout=20) as response:
        data = response.read(MAX_FEED+1)
        if len(data) > MAX_FEED:
            raise ValueError('Feed exceeds 32 MiB')
    if data.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as archive:
            data = archive.read(MAX_FEED+1)
        if len(data) > MAX_FEED:
            raise ValueError('Expanded feed exceeds 32 MiB')
    return data.decode('utf-8-sig')
