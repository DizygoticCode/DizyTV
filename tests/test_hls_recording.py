"""Local HTTP fixtures for detached clear-HLS recording, without broadcast access."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from dizytv.recorder import record_stream

PACKETS = (b'\x47' + bytes(187)) * 20
OTHER_PACKETS = (b'\x47' + bytes([1]) * 187) * 20


class HLSSource(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *_):
        pass

    def do_GET(self):
        type(self).requests.append(self.path)
        route = self.path.split('?', 1)[0]
        content = 'application/vnd.apple.mpegurl'
        if route == '/redirect':
            self.send_response(302)
            self.send_header('Location', '/hls/live.m3u8')
            self.end_headers()
            return
        if route in ('/hls/live.m3u8', '/mislabeled'):
            body = '#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXT-X-MEDIA-SEQUENCE:4\n#EXTINF:1,\n/hls/one.ts\n#EXT-X-DISCONTINUITY\n#EXTINF:1,\n/hls/two.ts\n'
            if route == '/mislabeled':
                content = 'application/octet-stream'
        elif route == '/master.m3u8':
            body = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1280000\nhls/live.m3u8\n'
        elif route == '/encrypted.m3u8':
            body = '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key?METHOD=NONE"\n#EXTINF:1,\nhls/one.ts\n'
        elif route == '/session-key.m3u8':
            body = '#EXTM3U\n#EXT-X-SESSION-KEY:METHOD=SAMPLE-AES,URI="key"\n#EXT-X-STREAM-INF:BANDWIDTH=1\nhls/live.m3u8\n'
        elif route == '/clear.m3u8':
            body = '#EXTM3U\n#EXT-X-KEY:METHOD=NONE\n#EXTINF:1,\nhls/one.ts\n'
        elif route == '/fmp4.m3u8':
            body = '#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:1,\nsegment.m4s\n'
        elif route == '/range.m3u8':
            body = '#EXTM3U\n#EXTINF:1,\n#EXT-X-BYTERANGE:188@0\nhls/one.ts\n'
        elif route == '/loop.m3u8':
            body = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nloop.m3u8\n'
        elif route == '/badsegment.m3u8':
            body = '#EXTM3U\n#EXTINF:1,\nhls/one.ts\n#EXTINF:1,\ninvalid.ts\n'
        elif route == '/oversized.m3u8':
            body = '#EXTM3U\n#EXTINF:1,\nhuge.ts\n'
        elif route == '/ended.m3u8':
            body = '#EXTM3U\n#EXTINF:1,\nhls/one.ts\n#EXT-X-ENDLIST\n'
        elif route == '/forbidden.m3u8':
            self.send_error(403)
            return
        elif route == '/invalid.ts':
            body = b'not a transport stream'
            content = 'video/mp2t'
        elif route == '/huge.ts':
            body = PACKETS * 8
            content = 'video/mp2t'
        elif route in ('/hls/one.ts', '/hls/two.ts'):
            body = OTHER_PACKETS if 'two' in route else PACKETS
            content = 'video/mp2t'
        elif route == '/slow.ts':
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp2t')
            self.end_headers()
            self.wfile.flush()
            time.sleep(4)
            return
        elif route == '/direct.ts':
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp2t')
            self.end_headers()
            try:
                for _ in range(150):
                    self.wfile.write(PACKETS)
                    self.wfile.flush()
                    time.sleep(.02)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        else:
            self.send_error(404)
            return
        body = body.encode() if isinstance(body, str) else body
        self.send_response(200)
        self.send_header('Content-Type', content)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class HLSRecordingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), HLSSource)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def record(self, route, folder, seconds=.4, **kwargs):
        return record_stream(self.url + route, folder, '../GB News',
                             time.time() + seconds, reserve=0, **kwargs)

    def test_master_redirect_and_mislabeled_hls_record_exact_ts_once(self):
        for route in ('/master.m3u8', '/redirect', '/mislabeled'):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as folder:
                result = self.record(route, folder)
                self.assertEqual('completed', result['status'], result)
                self.assertEqual(PACKETS + OTHER_PACKETS, Path(result['path']).read_bytes())
                self.assertEqual(Path(folder), Path(result['path']).parent)
                self.assertEqual([], list(Path(folder).glob('*.part')))

    def test_protection_and_unsupported_formats_are_rejected_before_segments(self):
        for route, message in (('/encrypted.m3u8', 'encrypted'),
                               ('/session-key.m3u8', 'encrypted'),
                               ('/fmp4.m3u8', 'Fragmented'),
                               ('/range.m3u8', 'byte-range')):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as folder:
                HLSSource.requests.clear()
                result = self.record(route, folder)
                self.assertEqual('failed', result['status'], result)
                self.assertIn(message, result['error'])
                self.assertEqual([route], HLSSource.requests)
                self.assertEqual([], list(Path(folder).iterdir()))

    def test_clear_none_key_is_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.record('/clear.m3u8', folder)
            self.assertEqual('completed', result['status'], result)
            self.assertEqual(PACKETS, Path(result['path']).read_bytes())

    def test_master_cycle_fails_promptly(self):
        with tempfile.TemporaryDirectory() as folder:
            began = time.monotonic()
            result = self.record('/loop.m3u8', folder, seconds=10)
            self.assertEqual('failed', result['status'], result)
            self.assertIn('loop', result['error'].lower())
            self.assertLess(time.monotonic() - began, 1)

    def test_bad_segment_and_endlist_keep_prior_footage(self):
        for route, error in (('/badsegment.m3u8', 'MPEG-TS'), ('/ended.m3u8', 'ended')):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as folder:
                result = self.record(route, folder, seconds=2)
                self.assertEqual('partial', result['status'], result)
                self.assertIn(error, result['error'])
                self.assertEqual(PACKETS, Path(result['path']).read_bytes())

    def test_cancel_after_first_segment_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            stop = threading.Event()
            result = self.record('/hls/live.m3u8', folder, seconds=10,
                                 cancel=stop.is_set,
                                 progress=lambda *_: stop.set())
            self.assertEqual('partial', result['status'], result)
            self.assertIn('stopped by user', result['error'])
            self.assertEqual(PACKETS, Path(result['path']).read_bytes())

    def test_recording_quota_preserves_complete_packets(self):
        for route in ('/hls/live.m3u8', '/direct.ts'):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as folder:
                result = self.record(route, folder, seconds=2, max_bytes=len(PACKETS))
                self.assertEqual('partial', result['status'], result)
                self.assertIn('limit', result['error'])
                self.assertEqual(PACKETS, Path(result['path']).read_bytes())

    def test_free_space_reserve_includes_next_write(self):
        with tempfile.TemporaryDirectory() as folder:
            free = shutil._ntuple_diskusage(100000, 99000, 1000)
            with patch('dizytv.recorder.shutil.disk_usage', return_value=free):
                result = self.record('/direct.ts', folder, seconds=2)
            self.assertEqual('failed', result['status'], result)
            self.assertIn('reserve', result['error'])
            self.assertEqual([], list(Path(folder).iterdir()))

    def test_http_error_is_actionable_without_exposing_query_tokens(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.record('/forbidden.m3u8?token=secret', folder)
            self.assertEqual('failed', result['status'], result)
            self.assertIn('403', result['error'])
            self.assertNotIn('secret', result['error'])

    def test_same_title_never_overwrites_existing_footage(self):
        with tempfile.TemporaryDirectory() as folder:
            first = self.record('/hls/live.m3u8', folder)
            second = self.record('/hls/live.m3u8', folder)
            self.assertEqual('completed', first['status'], first)
            self.assertEqual('completed', second['status'], second)
            self.assertNotEqual(first['path'], second['path'])
            self.assertEqual(2, len(list(Path(folder).glob('*.ts'))))

    def test_cancel_stalled_source_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            stop = threading.Event()
            timer = threading.Timer(.15, stop.set)
            timer.start()
            try:
                began = time.monotonic()
                result = self.record('/slow.ts', folder, seconds=30, cancel=stop.is_set)
                self.assertLess(time.monotonic() - began, 3.5)
                self.assertEqual('cancelled', result['status'], result)
            finally:
                timer.cancel()


if __name__ == '__main__':
    unittest.main()
