import unittest
from unittest.mock import patch
from io import BytesIO
import socket
import ssl
from urllib.error import HTTPError, URLError

from dizytv.stream_diagnostics import probe_stream,explain_status,explain_connection_failure,regional_access_notice
from dizytv.sources import safe_source_label

class DiagnosticsTests(unittest.TestCase):
    def test_http_errors_are_precise_not_assumed_geoblocking(self):
        self.assertIn('access denied',explain_status(403))
        self.assertIn('missing',explain_status(404))
        self.assertIn('rate-limiting',explain_status(429))
        self.assertIn('server error',explain_status(503))
    def test_regional_hint_is_qualified_and_never_leaks_provider_text(self):
        for code in (403,451):
            hint=regional_access_notice(explain_status(code))
            self.assertIn('regional',hint.lower())
            self.assertIn('DizyTV does not change your location',hint)
            self.assertNotIn('definitely',hint)
        for code in (200,401,404,410,429,500):
            self.assertEqual('',regional_access_notice(explain_status(code)))
        self.assertEqual('',regional_access_notice('Stream not started'))
        self.assertNotIn('SECRET',regional_access_notice('HTTP 403: token=SECRET'))

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

    def test_distinct_safe_network_failure_reasons(self):
        cases=[
            (URLError(socket.gaierror(-2,'private.example.org?token=SECRET')), 'DNS lookup'),
            (URLError(TimeoutError('https://hidden.example/?token=SECRET')), 'timed out'),
            (URLError(ConnectionRefusedError('https://hidden.example/?token=SECRET')), 'refused'),
            (URLError(ConnectionResetError('https://hidden.example/?token=SECRET')), 'reset'),
            (URLError(ssl.SSLCertVerificationError('cert for secret.local invalid')), 'certificate verification'),
            (URLError(ssl.SSLError('https://secret.local')), 'TLS negotiation'),
            (URLError(ValueError('http://private-host/SECRET')), 'invalid'),
            (URLError(OSError('credential=SECRET')), 'network or provider'),
        ]
        for err,expected in cases:
            with self.subTest(expected=expected):
                result=explain_connection_failure(err)
                self.assertIn(expected,result)
                self.assertNotIn('SECRET',result)
                self.assertNotIn('private',result.lower())
                self.assertNotIn('secret.local',result)

    def test_urllib_probe_classification_never_includes_provider_secrets(self):
        class Bad:
            def open(self,request,timeout):
                raise URLError(socket.gaierror(-2,'private.origin?token=DO_NOT_ECHO'))
        with patch('dizytv.stream_diagnostics.build_opener',return_value=Bad()):
            message=probe_stream('https://secret.example/live?token=DO_NOT_ECHO')
            self.assertIn('DNS lookup',message)
            self.assertNotIn('DO_NOT_ECHO',message)
            self.assertNotIn('private.origin',message)

    def test_custom_source_provenance_hides_host_and_authentication(self):
        label=safe_source_label('https://user:password@home.lan:8443/live.m3u8?key=SECRET')
        self.assertEqual('Custom playlist',label)
        self.assertNotIn('home.lan',label)
        self.assertIn('IPTV-org',safe_source_label('https://iptv-org.github.io/iptv/countries/uk.m3u'))

    def test_html_body_detected_without_reliable_content_type(self):
        class Res:
            status=200
            headers={'Content-Type':'application/octet-stream'}
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return b'<!doctype HTML><html><title>Sign in</title>'
        with patch('dizytv.stream_diagnostics.build_opener') as opener:
            opener.return_value.open.return_value=Res()
            result=probe_stream('https://example.org/live')
        self.assertIn('HTML page',result)
        self.assertIn('EPG',result)

    def test_hls_bom_whitespace_is_detected(self):
        class Res:
            status=200
            headers={'Content-Type':'text/plain'}
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return b'\xef\xbb\xbf\n#EXTM3U\n#EXT-X-VERSION:3'
        with patch('dizytv.stream_diagnostics.build_opener') as opener:
            opener.return_value.open.return_value=Res()
            self.assertIn('HLS playlist',probe_stream('https://example.org/a.m3u8'))
