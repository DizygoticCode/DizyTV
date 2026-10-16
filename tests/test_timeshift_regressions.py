"""Regression coverage for rolling replay, media clocks, and cancellation."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
import tempfile
import time
import unittest
from urllib.request import urlopen

from dizytv.timeshift import RollingTimeshift, RollingWindow, parse_hls

PACKET = b'\x47' + bytes(187)


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError('Timed out waiting for local capture')
        Event().wait(.01)


@contextmanager
def origin(route):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload, content_type = route(self.path)
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = Thread(target=server.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
    worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def pcr_packet(seconds):
    """One adaptation-only TS packet, PID 256, with an encoded 90 kHz PCR."""
    base = round(seconds * 90000) % (1 << 33)
    clock = bytes((base >> 25, (base >> 17) & 255, (base >> 9) & 255,
                   (base >> 1) & 255, ((base & 1) << 7) | 0x7e, 0))
    return b'\x47\x01\x00\x20\xb7\x10' + clock + bytes(176)


class TestTimeshiftRegressions(unittest.TestCase):
    def test_starting_sequence_uses_variable_media_durations(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RollingWindow(directory, free=lambda: 1 << 40)
            for duration in (2, 7, 3, 5):
                window.append(PACKET, duration)
            self.assertEqual(3, window.starting_seq(0))
            self.assertEqual(3, window.starting_seq(5))
            self.assertEqual(2, window.starting_seq(5.1))
            self.assertEqual(1, window.starting_seq(15))
            self.assertEqual(0, window.starting_seq(500))
            window.close()

    def test_fast_hls_backfill_respects_media_duration_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RollingWindow(directory, minutes=1, free=lambda: 1 << 40)
            for _ in range(8):
                window.append(PACKET, 10)
            self.assertEqual(60, window.latest_seconds())
            self.assertEqual(6, len(list(Path(directory).glob('*.ts'))))
            window.close()

    def test_closed_window_never_accepts_a_late_capture_write(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RollingWindow(directory, free=lambda: 1 << 40)
            sentinel = Path(directory) / 'unrelated.txt'
            sentinel.write_text('keep')
            window.append(PACKET, 4)
            window.close()
            with self.assertRaisesRegex(OSError, 'closed'):
                window.append(PACKET, 4)
            self.assertEqual([], window.snapshot())
            self.assertEqual('keep', sentinel.read_text())
            self.assertEqual([], list(Path(directory).glob('*.ts')))

    def test_hls_sequence_identity_survives_changed_signed_urls(self):
        manifests = []

        def route(path):
            if path.startswith('/live.m3u8'):
                manifests.append(path)
                return (f'#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:42\n#EXTINF:4,\n'
                        f'/segment.ts?token={len(manifests)}\n').encode(), 'application/vnd.apple.mpegurl'
            return PACKET * 10, 'video/mp2t'

        with tempfile.TemporaryDirectory() as directory, origin(route) as base:
            session = RollingTimeshift(base + '/live.m3u8', directory)
            try:
                session.start(timeout=3)
                wait_until(lambda: len(manifests) >= 2)
                # Wait for the second fetch to finish, not merely for its header.
                wait_until(lambda: session.window.counter >= 2 or len(manifests) >= 3)
                self.assertEqual(4, session.window.latest_seconds())
            finally:
                session.close()

    def test_hls_reused_uri_with_new_sequence_is_new_media(self):
        state = {'sequence': 1}
        second_request = Event()

        def route(path):
            if path == '/live.m3u8':
                sequence = state['sequence']
                return (f'#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:{sequence}\n'
                        '#EXTINF:4,\n/segment.ts\n').encode(), 'application/vnd.apple.mpegurl'
            if state['sequence'] == 2:
                second_request.set()
            return PACKET * 10, 'video/mp2t'

        with tempfile.TemporaryDirectory() as directory, origin(route) as base:
            session = RollingTimeshift(base + '/live.m3u8', directory)
            try:
                session.start(timeout=3)
                state['sequence'] = 2
                self.assertTrue(second_request.wait(4), 'New HLS sequence was skipped because its URI was reused')
                wait_until(lambda: len(session.window.snapshot()) == 2)
                self.assertEqual(8, session.window.latest_seconds())
            finally:
                session.close()

    def test_direct_ts_uses_media_pcr_instead_of_download_speed(self):
        # An HTTP buffer can deliver four media seconds in a few milliseconds.
        payload = pcr_packet(900) + PACKET * 10 + pcr_packet(904)
        fetched = Event()
        release = Event()

        def route(path):
            if fetched.is_set():
                release.wait(5)
            fetched.set()
            return payload, 'video/mp2t'

        with tempfile.TemporaryDirectory() as directory, origin(route) as base:
            session = RollingTimeshift(base + '/live.ts', directory)
            try:
                session.start(timeout=3)
                self.assertAlmostEqual(4, session.window.snapshot()[0].duration, places=2)
            finally:
                session.close_async()
                release.set()
                session.close()

    def test_cancel_during_slow_hls_read_does_not_write_or_report_error(self):
        reading = Event()
        release = Event()

        def route(path):
            if path == '/live.m3u8':
                return b'#EXTM3U\n#EXTINF:4,\n/slow.ts\n', 'application/vnd.apple.mpegurl'
            reading.set()
            release.wait(5)
            return PACKET * 10, 'video/mp2t'

        with tempfile.TemporaryDirectory() as directory, origin(route) as base:
            session = RollingTimeshift(base + '/live.m3u8', directory)
            session._capture_thread = Thread(target=session._capture, daemon=True)
            session._capture_thread.start()
            try:
                self.assertTrue(reading.wait(2))
                session.close()
                release.set()
                session._capture_thread.join(timeout=3)
                self.assertFalse(session._capture_thread.is_alive())
                self.assertEqual('', session.error)
                self.assertEqual([], session.window.snapshot())
                self.assertFalse(session.window.directory.exists())
            finally:
                release.set()
                session.close()

    def test_unsupported_hls_byte_ranges_are_rejected_before_capture(self):
        with self.assertRaisesRegex(ValueError, 'range'):
            parse_hls('#EXTM3U\n#EXTINF:4,\n#EXT-X-BYTERANGE:188@0\nall.ts\n',
                      'https://example.test/live.m3u8')

    def test_invalid_hls_duration_is_rejected_instead_of_clamped(self):
        for duration in ('NaN', 'inf', '-4'):
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, 'duration'):
                parse_hls(f'#EXTM3U\n#EXTINF:{duration},\nsegment.ts\n',
                          'https://example.test/live.m3u8')
