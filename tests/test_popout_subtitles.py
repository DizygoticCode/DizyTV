"""Subtitle state and Qt overlay regressions; real broadcast rendering needs a display."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QApplication, QDialog

from dizytv.auto_captions import LocalCaptionWorker
from dizytv.desktop import MainWindow
from dizytv.storage import Store


class SubtitlePlayer:
    """A decoder whose output replacement can lose the active SPU selection."""
    def __init__(self):
        self.track = -1
        self.tracks = [(2, 'English'), (8, 'French')]
    def video_get_spu_description(self): return self.tracks
    def video_get_spu(self): return self.track
    def video_set_spu(self, track):
        self.track = track
        return 0
    def video_set_subtitle_file(self, path):
        self.track = 12
        self.tracks.append((12, 'External'))
        return True
    def get_state(self): return 'State.Playing'
    def stop(self): pass
    def release(self): pass


class PopoutSubtitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.window = MainWindow(Store(self.folder.name), start_worker=False)
        self.window.timer.stop()
        self.window.player = SubtitlePlayer()
        self.window.playback_started = 1
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window._auto_caption_worker = None
        self.window.player = None
        self.window.close()
        self.app.processEvents()
        self.folder.cleanup()

    def test_manual_broadcast_selection_returns_after_output_recreation(self):
        window = self.window
        window.choose_subtitle_track(8)
        window.player.track = -1  # VLC lost its SPU while creating another output.
        window.sync_subtitles()
        self.assertEqual(8, window.player.track)
        self.assertEqual(8, window._subtitle_manual_track)

    def test_auto_broadcast_selection_is_restored_when_video_moves(self):
        window = self.window
        window.sync_subtitles()
        self.assertEqual(2, window.player.track)
        # Model the native output replacement; this is independent of Vosk.
        def output_changed(): window.player.track = -1
        with patch.object(window, '_rebind_video', side_effect=output_changed):
            window.open_popout()
            window.sync_subtitles()
            self.assertEqual(2, window.player.track)
            window.exit_screen_fullscreen()
            window.sync_subtitles()
            self.assertEqual(2, window.player.track)

    def test_visible_vosk_caption_is_not_delayed_again_on_popout_or_dock(self):
        window = self.window
        window.state['settings']['auto_caption_delay_ms'] = 5000
        window._auto_caption_worker = Mock()
        window.show_auto_caption_text('Already visible dialogue')
        updated = window._auto_caption_updated
        window.open_popout()
        self.assertIsNotNone(window._auto_caption_overlay)
        self.assertEqual('Already visible dialogue', window._auto_caption_label.text())
        self.assertEqual(updated, window._auto_caption_updated)
        self.assertEqual(0, len(window._auto_caption_queue))
        window.exit_screen_fullscreen()
        self.assertEqual('Already visible dialogue', window._auto_caption_label.text())
        self.assertEqual(updated, window._auto_caption_updated)
        self.assertEqual(0, len(window._auto_caption_queue))

    def test_off_cancels_restart_already_queued_by_worker_completion(self):
        window = self.window
        window._auto_caption_worker = Mock()
        window._auto_caption_worker_serial = 4
        window._auto_caption_seq = 4
        window.stop_auto_captions()
        window._auto_caption_restart_requested = True
        callbacks = []
        with patch('dizytv.desktop.QTimer.singleShot', side_effect=lambda delay, callback: callbacks.append(callback)):
            window.auto_caption_finished(4, '')
        self.assertEqual(1, len(callbacks))
        window.disable_all_subtitles()
        with patch.object(window, 'toggle_auto_captions') as restart:
            callbacks[0]()
            restart.assert_not_called()
        self.assertIsNone(window._auto_caption_overlay)
        self.assertEqual(-1, window.player.track)

    def test_external_file_explicitly_reenables_subtitles_after_all_off(self):
        window = self.window
        path = Path(self.folder.name) / 'captions.srt'
        path.write_text('1\n00:00:00,000 --> 00:00:02,000\nHello\n')
        window.disable_all_subtitles()
        with patch('dizytv.desktop.QFileDialog.getOpenFileName', return_value=(str(path), '')):
            window.load_subtitle_file()
        window.sync_subtitles()
        self.assertFalse(window._subtitle_session_all_off)
        self.assertEqual(12, window.player.track)

    def test_native_caption_geometry_follows_popout_move_and_screen_change(self):
        window = self.window
        window.open_popout()
        window._auto_caption_overlay = QDialog(window.screen_dialog, Qt.Tool | Qt.FramelessWindowHint)
        window.position_auto_caption_overlay()
        before = window._auto_caption_overlay.pos()
        window.screen_dialog.move(window.screen_dialog.pos() + QPoint(40, 30))
        self.app.processEvents()
        self.assertEqual(before + QPoint(40, 30), window._auto_caption_overlay.pos())
        with patch.object(window, 'position_auto_caption_overlay') as reposition:
            self.app.sendEvent(window.screen_dialog, QEvent(QEvent.ScreenChangeInternal))
            self.assertTrue(reposition.called)


class CaptionStopTests(unittest.TestCase):
    def test_stop_returns_without_waiting_for_ffmpeg_process_management(self):
        entered = threading.Event()
        release = threading.Event()
        worker = LocalCaptionWorker('ffmpeg', 'https://example.com/live', 'model', lambda _: None, lambda _: None)
        class Process:
            def poll(self):
                entered.set()
                release.wait(2)
                return None
            def kill(self): pass
        worker._process = Process()
        begin = time.monotonic()
        try:
            worker.stop()
            elapsed = time.monotonic() - begin
            self.assertLess(elapsed, .2)
            self.assertTrue(worker._stop.is_set())
            self.assertTrue(entered.wait(1))
        finally:
            release.set()

    def test_caption_decoded_after_stop_is_never_delivered(self):
        captions = []
        finished = []
        worker = LocalCaptionWorker('ffmpeg', 'https://example.com/live', 'model', captions.append, finished.append)
        class Recognizer:
            def AcceptWaveform(self, block):
                worker.stop()
                return True
            def Result(self): return '{"text":"stale dialogue"}'
        process = Mock()
        process.stdout.read.side_effect = [b'pcm', b'']
        process.poll.return_value = 0
        fake_vosk = SimpleNamespace(Model=lambda _: object(), KaldiRecognizer=lambda *_: Recognizer(), SetLogLevel=lambda _: None)
        with patch.dict('sys.modules', vosk=fake_vosk), patch('dizytv.auto_captions.subprocess.Popen', return_value=process):
            worker._run()
        self.assertEqual([], captions)
        self.assertEqual([''], finished)


if __name__ == '__main__':
    unittest.main()
