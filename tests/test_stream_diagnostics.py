import unittest
from unittest.mock import patch
from io import BytesIO
from urllib.error import HTTPError, URLError

from dizytv.stream_diagnostics import probe_stream,explain_status

class DiagnosticsTests(unittest.TestCase):
    def test_http_errors_are_precise_not_assumed_geoblocking(self):
        self.assertIn('access denied',explain_status(403))
        self.assertIn('missing',explain_status(404))
        self.assertIn('rate-limiting',explain_status(429))
        self.assertIn('server error',explain_status(503))
    def test_rejected_stream_does_not_echo_sensitive_url_tokens(self):
        class FakeOpener:
            def open(self,request,timeout):
                raise HTTPError(request.full_url,403,'Access denied',None,None)
        with patch('dizytv.stream_diagnostics.build_opener',return_value=FakeOpener()):
            message=probe_stream('https://example.com/playlist.m3u8?secret=sensitive')
            self.assertIn('HTTP 403',message)
            self.assertNotIn('sensitive',message)
    def test_hls_manifest_vs_html_landing(self):
        class Res:
            status=200
            def __init__(self,payload,ctype):self.payload=payload;self.headers={'Content-Type':ctype}
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return self.payload[:n]
        with patch('dizytv.stream_diagnostics.build_opener') as build:
            build.return_value.open.return_value=Res(b'#EXTM3U\n','application/vnd.apple.mpegurl')
            self.assertIn('HLS playlist',probe_stream('https://example.com/live.m3u8'))
            build.return_value.open.return_value=Res(b'<html></html>','text/html')
            self.assertIn('HTML page',probe_stream('https://example.com/live'))
