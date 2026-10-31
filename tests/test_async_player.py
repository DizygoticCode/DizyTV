"""Native-call isolation regressions, using a slow local libVLC substitute."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from dizytv.desktop import MainWindow
from dizytv.storage import Store


class NativeFixture:
    def __init__(self):
        self.calls = []
        self.delays = {}
        self.blockers = {}
        self.entered = {}
        self.media = None
        self.state = 'State.Stopped'
        self.spu = -1
        self.volume = 100
        self.released = threading.Event()

    def call(self, name, *args):
        self.calls.append((name, args, threading.get_ident()))
        self.entered.setdefault(name, threading.Event()).set()
        time.sleep(self.delays.get(name, 0))
        if name in self.blockers:
            self.blockers[name].wait(3)

    def instance(self, *options):
        self.call('instance', *options)
        return self

    def media_player_new(self):
        self.call('media_player_new')
        return self

    def media_new(self, url):
        self.call('media_new', url)
        fixture = self

        class Media:
            def add_option(self, option): fixture.call('add_option', option)
            def release(self): fixture.call('media_release')
            def get_stats(self, stats):
                fixture.call('get_stats')
                stats.displayed_pictures = 12
                stats.played_abuffers = 8
                return True
        media = Media()
        media.url = url
        return media

    def set_media(self, media):
        self.call('set_media', media.url)
        self.media = media

    def get_media(self):
        self.call('get_media')
        return self.media

    def stop(self):
        self.call('stop')
        self.state = 'State.Stopped'

    def play(self):
        self.call('play', self.media.url)
        self.state = 'State.Playing'
        return 0

    def get_state(self):
        self.call('get_state')
        return self.state

    def get_time(self): self.call('get_time'); return 2000
    def get_length(self): self.call('get_length'); return 9000
    def is_seekable(self): self.call('is_seekable'); return True
    def video_get_spu(self): self.call('video_get_spu'); return self.spu
    def video_get_spu_description(self): self.call('video_get_spu_description'); return [(1, b'English')]
    def video_get_track_count(self): self.call('video_get_track_count'); return 1
    def video_get_size(self, _): self.call('video_get_size'); return (160, 90)
    def video_set_spu(self, value): self.call('video_set_spu', value); self.spu = value; return 0
    def video_set_subtitle_file(self, value): self.call('video_set_subtitle_file', value); return True
    def audio_set_volume(self, value): self.call('audio_set_volume', value); self.volume = value; return 0
    def set_pause(self, value): self.call('set_pause', value); self.state = 'State.Paused' if value else 'State.Playing'
    def set_time(self, value): self.call('set_time', value); return 0
    def set_xwindow(self, value): self.call('set_xwindow', value)
    def set_hwnd(self, value): self.call('set_hwnd', value)
    def set_nsobject(self, value): self.call('set_nsobject', value)
    def release(self): self.call('release'); self.released.set()

    def binding(self):
        return SimpleNamespace(Instance=self.instance, MediaStats=lambda: SimpleNamespace(
            decoded_audio=10, decoded_video=12, displayed_pictures=0,
            played_abuffers=0, lost_pictures=0, demux_bitrate=0.0, input_bitrate=0.0))


class AsyncPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_until(self, condition, timeout=2):
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(.002)
        self.assertTrue(condition(), 'Timed out waiting for player work')

    def test_slow_native_start_keeps_qt_heartbeat_live(self):
        native = NativeFixture()
        native.delays['stop'] = .25
        with tempfile.TemporaryDirectory() as folder, \
                patch('dizytv.media_runtime.configure_private_vlc'), \
                patch.dict(sys.modules, {'vlc': native.binding()}):
            window = MainWindow(Store(folder), start_worker=False)
            beats = []
            timer = QTimer()
            timer.setInterval(5)
            timer.timeout.connect(lambda: beats.append(time.monotonic()))
            timer.start()
            try:
                started = time.monotonic()
                window.play_url('https://example.invalid/video.m3u8')
                elapsed = time.monotonic() - started
                self.assertLess(elapsed, .1, 'Native startup blocked the Qt caller')
                self.wait_until(lambda: native.state == 'State.Playing')
                self.assertGreaterEqual(len(beats), 8)
                self.assertNotIn(threading.get_ident(), [call[2] for call in native.calls])
            finally:
                timer.stop()
                window.close()
                self.wait_until(native.released.is_set)

