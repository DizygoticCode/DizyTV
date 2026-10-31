"""Headless Matchday UI regressions: no network on startup, old tabs retained."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication

from dizytv.desktop import MainWindow
from dizytv.storage import Store


class MatchdayUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_live_guide_recordings_still_first_and_matchday_does_not_fetch_at_start(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('dizytv.matchday._fetch',side_effect=AssertionError('network on UI init')):
                window=MainWindow(Store(folder), start_worker=False)
            try:
                self.assertEqual(['Live TV','TV Guide','Recordings'],
                                 [window.tabs.tabText(i) for i in range(3)])
                self.assertIn('Matchday',window.tabs.tabText(3))
                self.assertEqual(0, window.matchday_page.fixtures_table.rowCount())
            finally:
                window.close()

    def test_favourite_filter_only_uses_provider_fixtures(self):
        with tempfile.TemporaryDirectory() as folder:
            window=MainWindow(Store(folder),start_worker=False)
            try:
                page=window.matchday_page
                from time import time
                now=int(time())+3600
                page.fixtures=[
                    dict(id='4',kickoff=now,home='Southampton',away='Queens Park Rangers',competition='Championship'),
                    dict(id='5',kickoff=now,home='Leeds',away='Norwich',competition='Championship')
                ]
                page.fav_only.setChecked(True)
                self.assertEqual(1,page.fixtures_table.rowCount())
                self.assertEqual('4',page.visible[0]['id'])
            finally:
                window.close()

    def test_direct_hls_uses_existing_native_player_without_fake_channel(self):
        with tempfile.TemporaryDirectory() as folder:
            window=MainWindow(Store(folder),start_worker=False)
            try:
                with patch.object(window,'stop_playback') as stop,patch.object(window,'play_url') as play:
                    window.play_matchday_hls('https://example.org/football/live.m3u8')
                    stop.assert_called_once_with()
                    play.assert_called_once_with('https://example.org/football/live.m3u8')
                    self.assertIsNone(window.selected)
                with patch.object(window,'play_url') as play:
                    window.play_matchday_hls('https://127.0.0.1/private.m3u8')
                    play.assert_not_called()
            finally:
                window.close()


if __name__=='__main__':
    unittest.main()
