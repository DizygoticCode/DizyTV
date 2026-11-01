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

    def test_saved_timezone_survives_qt_reparent_without_per_fixture_disk_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            store.update(lambda state: state['settings'].update(timezone='America/Los_Angeles'))
            window=MainWindow(store,start_worker=False)
            try:
                page=window.matchday_page
                # QTabWidget reparents pages to an internal QStackedWidget.
                self.assertIsNot(page.parentWidget(),window)
                with patch.object(store,'try_read',side_effect=AssertionError('read in render')):
                    self.assertEqual('America/Los_Angeles',page._display_zone().key)
                    page.fixtures=[dict(id='37',kickoff=1793491200,
                        home='Southampton',away='QPR',competition='Championship')]
                    page.render()
            finally:
                window.close()

    def test_auto_timezone_tracks_dst_changes_across_fixture_dates(self):
        with tempfile.TemporaryDirectory() as folder:
            window=MainWindow(Store(folder),start_worker=False)
            try:
                page=window.matchday_page
                with patch('dizytv.desktop.detected_zone',
                           return_value='America/New_York'):
                    zone=page._display_zone()
                    self.assertEqual('America/New_York',zone.key)
                    # US DST ends 1 November 2026: 12:00 UTC is 08:00
                    # local on October 31, but 07:00 on November 3.
                    from datetime import datetime, timezone
                    before=int(datetime(2026,10,31,12,tzinfo=timezone.utc).timestamp())
                    after=int(datetime(2026,11,3,12,tzinfo=timezone.utc).timestamp())
                    self.assertEqual(8,page._day({'kickoff':before},zone).hour)
                    self.assertEqual(7,page._day({'kickoff':after},zone).hour)
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
