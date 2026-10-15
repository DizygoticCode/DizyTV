"""Playback configuration regressions; no provider or engine connections."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from dizytv.desktop import MainWindow, SystemUsageDialog, diagnose_video_output
from dizytv.storage import Store


class PlaybackConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_one_decoder_event_does_not_prove_a_usable_frame_or_keyframe(self):
        warning = diagnose_video_output(1407, 1, 0, 1, (0, 0))
        self.assertIn('keyframe', warning)
        self.assertIn('segment', warning)

    def test_http_ace_entries_keep_existing_engine_cache_policy(self):
        identifier = 'a' * 40
        streams = [
            'acestream://' + identifier,
            'http://example.com/ace/getstream?id=' + identifier,
            'https://example.com/ace/manifest.m3u8?infohash=' + identifier,
        ]
        with tempfile.TemporaryDirectory() as folder:
            window = MainWindow(Store(folder), start_worker=False)
            window.player = Mock()
            window.player.play.return_value = 0
            window.vlc_instance = Mock()
            media = window.vlc_instance.media_new.return_value
            with patch.object(window, 'init_player'):
                for stream in streams:
                    with self.subTest(stream=stream.split('?')[0]):
                        media.reset_mock()
                        window.selected = dict(id=identifier, name='Fixture', stream=stream)
                        window.play_url('http://127.0.0.1:6878/fixture')
                        options = [call.args[0] for call in media.add_option.call_args_list]
                        self.assertFalse(any(option.startswith(':network-caching=') for option in options))
                media.reset_mock()
                window.selected['stream'] = 'https://example.com/test.m3u8'
                window.state['settings']['http_buffer_ms'] = 8000
                window.play_url('https://example.com/test.m3u8')
                media.add_option.assert_any_call(':network-caching=8000')
            window.close()

    def test_startup_callbacks_do_not_access_destroyed_window_widgets(self):
        self.app.processEvents()
        with tempfile.TemporaryDirectory() as folder:
            window = MainWindow(Store(folder), start_worker=False)
            errors = []
            with patch('sys.excepthook', side_effect=lambda *exc: errors.append(exc)):
                window.close()
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                self.app.processEvents()
            self.assertEqual([], errors)

    def test_pending_ace_session_cannot_restart_after_stop_or_close(self):
        for action in ('stop_playback', 'close'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as folder:
                window = MainWindow(Store(folder), start_worker=False)
                window.pool = Mock()
                window.selected = dict(id='a'*40, name='Fixture',
                                       stream='acestream://'+'a'*40)
                window.play()
                pending = window.engine_task
                getattr(window, action)()
                with patch.object(window, 'play_stream') as start:
                    pending.signals.success.emit('http://127.0.0.1:6878/fixture')
                    start.assert_not_called()
                window.close()

    def test_current_ace_session_still_starts_normally(self):
        with tempfile.TemporaryDirectory() as folder:
            window = MainWindow(Store(folder), start_worker=False)
            window.pool = Mock()
            window.selected = dict(id='a'*40, name='Fixture',
                                   stream='acestream://'+'a'*40)
            window.play()
            pending = window.engine_task
            with patch.object(window, 'play_stream') as start:
                pending.signals.success.emit('http://127.0.0.1:6878/fixture')
                start.assert_called_once_with('http://127.0.0.1:6878/fixture')
            window.close()

    def test_switching_to_http_does_not_leave_ace_startup_permanently_busy(self):
        with tempfile.TemporaryDirectory() as folder:
            window = MainWindow(Store(folder), start_worker=False)
            window.pool = Mock()
            ace = dict(id='a'*40, name='Ace fixture', stream='acestream://'+'a'*40)
            window.selected = ace
            window.play()
            old = window.engine_task
            with patch.object(window, 'play_stream'):
                window.selected = dict(id='b'*40, name='HTTP fixture', stream='https://example.com/test.m3u8')
                window.play()
                old.signals.success.emit('http://127.0.0.1:6878/old')
                window.selected = ace
                window.play()
                current = window.engine_task
                self.assertIsNotNone(current)
                self.assertIsNot(old, current)
                old.signals.failure.emit('Fixture late failure')
                self.assertIs(current, window.engine_task)
            window.close()

    def test_opening_recording_stops_live_capture_and_pending_engine_request(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = Path(folder) / 'recording.ts'
            fixture.write_bytes(b'fixture')
            window = MainWindow(Store(folder), start_worker=False)
            window.pool = Mock()
            window.selected = dict(id='a'*40, name='Fixture', stream='acestream://'+'a'*40)
            window.play()
            pending = window.engine_task
            session = Mock()
            window.timeshift = session
            with patch.object(window, 'selected_job', return_value={'path': str(fixture)}), \
                    patch.object(window, 'play_url') as play, \
                    patch.object(window, 'play_stream') as live:
                window.play_file()
                self.assertIsNone(window.timeshift)
                session.close.assert_called_once()
                play.assert_called_once_with(str(fixture.resolve()))
                pending.signals.success.emit('http://127.0.0.1:6878/fixture')
                live.assert_not_called()
            window.close()

    def test_direct_video_freeze_is_detected_even_while_audio_keeps_playing(self):
        with tempfile.TemporaryDirectory() as folder:
            window = MainWindow(Store(folder), start_worker=False)
            window.player = Mock()
            window.player.get_state.return_value = 'State.Playing'
            window.playback_started = 1
            window._active_direct_video = True
            window._playback_url = 'https://example.com/test.m3u8'
            window.selected = dict(id='a'*40, name='Fixture', kind='TV',
                                   stream=window._playback_url)
            with patch.object(window, 'media_activity', return_value=120):
                window.check_direct_playback(now=10)
                window.check_direct_playback(now=29)
                self.assertEqual('buffering', window.playback_light_state())
                self.assertIn('stopped advancing', window.status.text())
                # A user pause/resume starts a fresh observation window.
                window.player.get_state.return_value = 'State.Paused'
                window.check_direct_playback(now=100)
                window.player.get_state.return_value = 'State.Playing'
                window.check_direct_playback(now=101)
                self.assertEqual('live', window.playback_light_state())
            with patch.object(window, 'media_activity', return_value=121):
                window.check_direct_playback(now=102)
                self.assertEqual('live', window.playback_light_state())
            window.close()

    def test_watchdog_tracks_playing_media_when_browsing_another_channel(self):
        with tempfile.TemporaryDirectory() as folder:
            window = MainWindow(Store(folder), start_worker=False)
            window.player = Mock()
            window.player.play.return_value = 0
            window.player.get_state.return_value = 'State.Playing'
            window.vlc_instance = Mock()
            ace = dict(id='a'*40, name='Ace fixture', stream='acestream://'+'a'*40)
            tv = dict(id='b'*40, name='TV fixture', stream='https://example.com/test.m3u8')
            radio = dict(id='c'*40, name='Radio fixture', kind='Radio', stream='https://example.com/radio')
            with patch.object(window, 'init_player'), \
                    patch.object(window, 'media_activity', return_value=120) as activity:
                window.selected = ace
                window.play_url('http://127.0.0.1:6878/fixture')
                window.selected = tv
                window.check_direct_playback(now=10)
                window.check_direct_playback(now=30)
                self.assertEqual('live', window.playback_light_state())
                activity.assert_not_called()
                window.play_url(tv['stream'])
                window.selected = radio
                window.check_direct_playback(now=40)
                window.check_direct_playback(now=60)
                self.assertEqual('buffering', window.playback_light_state())
            window.close()

    def test_stats_readers_release_retained_media_on_all_paths(self):
        # Exercise ownership without importing an optional native VLC runtime.
        # Real libVLC refcount checks are a separate playback integration test.
        binding = SimpleNamespace(MediaStats=lambda: SimpleNamespace(
            decoded_audio=0, decoded_video=0, displayed_pictures=0,
            played_abuffers=0, lost_pictures=0, demux_bitrate=0.0, input_bitrate=0.0))
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {'vlc': binding}):
            window = MainWindow(Store(folder), start_worker=False)
            usage = SystemUsageDialog(window)
            window.player = Mock()
            window.player.video_get_track_count.return_value = 1
            window.player.video_get_size.return_value = (160, 90)
            window.playback_started = 1
            media = window.player.get_media.return_value
            for reader in (window.media_activity, window.video_output_warning, usage.refresh_snapshot):
                for outcome in (True, False, RuntimeError('Fixture unavailable')):
                    with self.subTest(reader=reader.__name__, outcome=type(outcome).__name__):
                        media.release.reset_mock()
                        media.get_stats.side_effect = outcome if isinstance(outcome, Exception) else None
                        media.get_stats.return_value = outcome
                        reader()
                        media.release.assert_called_once_with()
            usage.close()
            window.close()

    def test_system_usage_samples_only_while_visible_including_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            window = MainWindow(Store(folder), start_worker=False)
            window.open_system_usage()
            dialog = window.usage_dialog
            self.assertTrue(dialog.timer.isActive())
            QTest.keyClick(dialog, Qt.Key_Escape)
            self.assertFalse(dialog.isVisible())
            self.assertFalse(dialog.timer.isActive())
            dialog.show()
            self.assertTrue(dialog.timer.isActive())
            window.close()
            self.assertFalse(dialog.timer.isActive())

    def test_direct_watchdog_never_interferes_with_ace_radio_or_missing_stats(self):
        with tempfile.TemporaryDirectory() as folder:
            window = MainWindow(Store(folder), start_worker=False)
            window.player = Mock()
            window.player.get_state.return_value = 'State.Playing'
            window.playback_started = 1
            window._playback_url = 'http://127.0.0.1:6878/fixture'
            for stream, kind, frames in [('acestream://'+'a'*40, 'TV', 50),
                                         ('https://example.com/radio', 'Radio', 50),
                                         ('https://example.com/video', 'TV', None)]:
                with self.subTest(kind=kind, frames=frames), \
                        patch.object(window, 'media_activity', return_value=frames):
                    window.selected = dict(id='a'*40, name='Fixture', kind=kind, stream=stream)
                    window.check_direct_playback(now=10)
                    window.check_direct_playback(now=100)
                    self.assertEqual('live', window.playback_light_state())
            window.close()


class DesktopEnvironmentTests(unittest.TestCase):
    def test_linux_entrypoint_selects_x11_for_vlc3_embedding(self):
        from dizytv.__main__ import configure_desktop_environment
        for platform in ('', 'wayland', 'wayland-egl'):
            with self.subTest(platform=platform), patch('sys.platform', 'linux'), \
                    patch.dict(os.environ, {'QT_QPA_PLATFORM': platform}, clear=False):
                configure_desktop_environment()
                self.assertEqual('xcb', os.environ['QT_QPA_PLATFORM'])

    def test_offscreen_and_other_platforms_keep_their_backend(self):
        from dizytv.__main__ import configure_desktop_environment
        for system, platform in (('linux', 'offscreen'), ('linux', 'minimal'),
                                 ('win32', ''), ('darwin', 'cocoa')):
            with self.subTest(system=system, platform=platform), patch('sys.platform', system), \
                    patch.dict(os.environ, {'QT_QPA_PLATFORM': platform}, clear=False):
                configure_desktop_environment()
                self.assertEqual(platform, os.environ['QT_QPA_PLATFORM'])
