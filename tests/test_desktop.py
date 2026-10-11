import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimeZone

from dizytv.desktop import MainWindow, GuideGrid, Settings
from dizytv.storage import Store


class DesktopTests(unittest.TestCase):
    def test_tv_player_modes_and_seekable_dvr_controls(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            window=MainWindow(Store(folder),start_worker=False)
            window.player=Mock()
            window.player.is_seekable.return_value=True
            window.player.get_length.return_value=300000
            window.player.get_time.return_value=120000
            window.player.get_state.return_value=Mock()
            window.playback_started=1
            window.seek_relative(-30000)
            window.player.set_time.assert_called_with(90000)
            window.seek_slider.setValue(500)
            window.seek_from_slider()
            window.player.set_time.assert_called_with(150000)
            window.player.is_seekable.return_value=False
            window.player.set_time.reset_mock()
            window.seek_relative(-30000)
            window.player.set_time.assert_not_called()
            window.toggle_cinema()
            self.assertTrue(window.cinema_mode)
            self.assertFalse(window.sidebar.isVisible())
            window.toggle_cinema()
            self.assertFalse(window.cinema_mode)
            window.player=None
            window.close()

    def test_fullscreen_restores_embedded_video_without_discarding_player(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            window=MainWindow(Store(folder),start_worker=False)
            window.show()
            self.app.processEvents()
            fake=Mock()
            window.player=fake
            window.toggle_screen_fullscreen()
            self.assertIsNotNone(window.screen_dialog)
            self.assertIs(window.video.parentWidget(),window.screen_dialog)
            window.exit_screen_fullscreen()
            self.assertIsNone(window.screen_dialog)
            self.assertIs(window.video.parentWidget(),window.tabs.widget(0))
            self.assertIs(window.player,fake)
            window.player=None
            window.close()

    def test_default_no_implicit_timeshift_and_settings_max_four_hours(self):
        with tempfile.TemporaryDirectory() as folder:
            window=MainWindow(Store(folder),start_worker=False)
            self.assertFalse(window.state['settings']['timeshift_enabled'])
            dialog=Settings(window.state,window)
            dialog.timeshift_enabled.setChecked(True)
            dialog.timeshift_minutes.setValue(240)
            dialog.timeshift_limit.setValue(8)
            values=dialog.values()
            self.assertTrue(values['timeshift_enabled'])
            self.assertEqual(240,values['timeshift_minutes'])
            self.assertEqual(8*1024**3,values['timeshift_max_bytes'])
            dialog.close()
            window.close()

    def test_ace_setup_opens_verified_official_provider_without_download(self):
        with tempfile.TemporaryDirectory() as folder:
            window=MainWindow(Store(folder),start_worker=False)
            with patch('dizytv.desktop.QDesktopServices.openUrl',return_value=True) as open_url:
                window.open_ace_stream_setup()
                self.assertEqual('https://docs.acestream.net/products/',open_url.call_args.args[0].toString())
            window.close()

    def test_guide_index_reuses_programmes_and_limits_painting_to_visible_window(self):
        from dizytv.core import parse_playlist
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            ch=parse_playlist('#EXTM3U\n#EXTINF:-1 tvg-id="bbc",BBC\nhttps://example.com/bbc.m3u8')[0]
            store.update(lambda s:s.update(channels=[ch]))
            window=MainWindow(store,start_worker=False)
            start=window.guide_start
            window.guide={'names':{'bbc':'BBC'},
                'programmes':[
                    {'channel':'bbc','start':start,'end':start+3600,'title':'On now','categories':['News']},
                    *[{'channel':'other','start':start,'end':start+3600,'title':'Not in grid','categories':['Sports']}
                        for _ in range(3000)],
                    {'channel':'bbc','start':start+86400,'end':start+90000,'title':'Tomorrow','categories':['News']}]}
            by_channel,genres=window.guide_index()
            self.assertIs(window.guide_index()[0],by_channel)
            self.assertEqual({'News'},genres['bbc'])
            window.render_channels()
            self.assertEqual(['On now'],[p['title'] for p in window.grid.programmes])
            window.close()

    def test_non_ace_playback_bypasses_engine_check(self):
        from dizytv.core import parse_playlist
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            store.update(lambda s:s.update(channels=parse_playlist('#EXTM3U\n#EXTINF:-1,Free news\nhttps://example.com/live.m3u8')))
            window=MainWindow(store,start_worker=False)
            window.selected=store.read()['channels'][0]
            shown=[]; window.play_url=shown.append
            window.play()
            self.assertEqual(['https://example.com/live.m3u8'],shown)
            self.assertIsNone(window.engine_task)
            window.close()

    def test_epg_left_click_watches_and_right_click_offers_recording(self):
        from dizytv.core import parse_playlist
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            ch=parse_playlist('#EXTM3U\n#EXTINF:-1 tvg-id="itv1",ITV1\nhttps://example.com/live.m3u8')[0]
            store.update(lambda s:s.update(channels=[ch]))
            window=MainWindow(store,start_worker=False)
            start=window.guide_start
            programme={'channel':'itv1','start':start,'end':start+3600,'title':'Current show','categories':[]}
            window.guide={'names':{'itv1':'ITV1'},'programmes':[programme]}
            window.render_channels()
            window.resize(1100,750)
            window.show()
            window.tabs.setCurrentIndex(1)
            self.app.processEvents()
            window.grid.repaint()
            self.app.processEvents()
            self.assertGreater(len(window.grid.hitboxes),0)
            watched=[]; scheduled=[]
            window.play=lambda:watched.append(window.selected['id'])
            window.schedule_programme=lambda ch,p:scheduled.append((ch['id'],p['title']))
            # A simple left-click on the EPG or its channel name watches live TV.
            QTest.mouseClick(window.grid,Qt.LeftButton,Qt.NoModifier,QPoint(230,75))
            self.assertEqual([ch['id']],watched)
            self.assertEqual([],scheduled)
            self.assertEqual(0,window.tabs.currentIndex())
            # Left-click switched to Live TV; return to the guide before
            # exercising its right-click context menu.
            window.tabs.setCurrentIndex(1)
            self.app.processEvents()
            window.grid.repaint()
            # Right-click opens menu; choosing Record must not play the stream.
            QTest.mouseClick(window.grid,Qt.RightButton,Qt.NoModifier,QPoint(230,75))
            actions=window.grid.context_menu.actions()
            self.assertEqual('● Record programme…',actions[-1].text())
            actions[-1].trigger()
            self.assertEqual([(ch['id'],'Current show')],scheduled)
            self.assertEqual([ch['id']],watched)
            # Right-click on a channel with no current programme can record now.
            window.guide={'names':{},'programmes':[]}
            window.render_channels()
            recorded_now=[]; window.record_now=lambda:recorded_now.append(window.selected['id'])
            QTest.mouseClick(window.grid,Qt.RightButton,Qt.NoModifier,QPoint(25,75))
            actions=window.grid.context_menu.actions()
            self.assertEqual('● Record now…',actions[-1].text())
            actions[-1].trigger()
            self.assertEqual([ch['id']],recorded_now)
            window.close()

    def test_saved_category_edit_filters_channels_and_guide(self):
        from dizytv.core import parse_playlist
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory)
            store.update(lambda s:s.update(channels=parse_playlist('#EXTM3U\n#EXTINF:-1,Uncategorised\nacestream://'+'a'*40),category_overrides={'a'*40:{'country':'Ireland','genre':'News'}}))
            window=MainWindow(store,start_worker=False)
            self.assertGreater(window.country_filter.findData('Ireland'),0)
            window.country_filter.setCurrentIndex(window.country_filter.findData('Ireland'))
            window.genre_filter.setCurrentIndex(window.genre_filter.findData('News'))
            self.assertEqual(['Uncategorised'],[c['name'] for c in window.grid.rows]); window.close()

    def test_preserved_segment_is_playable_after_failed_resume(self):
        from pathlib import Path
        from dizytv.core import make_job
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory); path=Path(directory)/'earlier.ts'; path.write_bytes(b'\x47'+bytes(187))
            job=make_job('a'*40,'News',2000000000,2000000060,0,0); job.update(status='partial',path='',segments=[{'path':str(path),'bytes':188,'status':'partial'}])
            store.update(lambda s:s.update(jobs=[job])); window=MainWindow(store,start_worker=False); window.jobs.selectRow(0)
            played=[]; window.play_url=played.append; window.play_file()
            self.assertEqual([str(path.resolve())],played); window.close()

    def test_country_genre_filter_also_filters_epg_rows(self):
        from dizytv.core import parse_playlist
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory)
            source='#EXTM3U\n#EXTINF:-1 tvg-country="GB" group-title="Sports",Sport\nacestream://'+'a'*40+'\n#EXTINF:-1 tvg-country="US" group-title="News",News\nacestream://'+'b'*40
            store.update(lambda s:s.update(channels=parse_playlist(source)))
            window=MainWindow(store,start_worker=False)
            window.country_filter.setCurrentIndex(window.country_filter.findData('United Kingdom'))
            window.genre_filter.setCurrentIndex(window.genre_filter.findData('Sport'))
            self.assertEqual(1,window.channels.count())
            self.assertEqual('Sport',window.grid.rows[0]['name'])
            window.close()

    def test_country_tree_and_category_navigation_keeps_source_values(self):
        from dizytv.core import parse_playlist
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            source='#EXTM3U\n#EXTINF:-1 tvg-id="BBCOne.uk" tvg-country="GB" group-title="News",BBC One @ HD Ⓖ\nhttps://example.com/one.m3u8\n#EXTINF:-1 tvg-country="US" group-title="Sports",AT&T SportsNet\nhttps://example.com/two.m3u8'
            store.update(lambda s:s.update(channels=parse_playlist(source)))
            window=MainWindow(store,start_worker=False)
            self.assertEqual(2,window.country_tree.topLevelItemCount())
            uk=next(window.country_tree.topLevelItem(i) for i in range(2) if 'United Kingdom' in window.country_tree.topLevelItem(i).text(0))
            self.assertEqual(('country','United Kingdom','',''),uk.data(0,Qt.UserRole))
            news=uk.child(0)
            self.assertIn('News',news.text(0))
            leaf=news.child(0)
            self.assertEqual('BBC One',leaf.text(0))
            window.country_tree_clicked(news)
            self.assertEqual(['BBC One'],[window.channels.item(i).text() for i in range(window.channels.count())])
            window.country_tree_clicked(leaf)
            self.assertEqual('BBC One @ HD Ⓖ',window.selected['name'])
            self.assertEqual('BBCOne.uk',window.selected['tvg_id'])
            self.assertEqual('https://example.com/one.m3u8',window.selected['stream'])
            window.close()

    def test_source_filter_separates_free_http_from_ace_and_preserves_all(self):
        from dizytv.core import parse_playlist
        from dizytv.sources import DEFAULT_PLAYLIST_URLS
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            ace=parse_playlist('#EXTM3U\n#EXTINF:-1,Old sports\nacestream://'+'a'*40)[0]
            ace['source']=DEFAULT_PLAYLIST_URLS[0]
            uk=parse_playlist('#EXTM3U\n#EXTINF:-1 tvg-country="GB",BBC News\nhttps://example.com/live.m3u8')[0]
            uk['source']=DEFAULT_PLAYLIST_URLS[1]
            store.update(lambda s:s.update(channels=[ace,uk]))
            window=MainWindow(store,start_worker=False)
            self.assertEqual(2,window.channels.count())
            self.assertEqual('BBC News',window.channels.item(0).text())
            window.source_filter.setCurrentIndex(window.source_filter.findData('<http>'))
            self.assertEqual(['BBC News'],[window.channels.item(i).text() for i in range(window.channels.count())])
            window.country_filter.setCurrentIndex(window.country_filter.findData('United Kingdom'))
            self.assertEqual(1,len(window.grid.rows))
            window.source_filter.setCurrentIndex(window.source_filter.findData(DEFAULT_PLAYLIST_URLS[0]))
            self.assertEqual(0,window.channels.count())
            window.country_filter.setCurrentIndex(0)
            self.assertEqual(1,window.channels.count())
            window.close()

    def test_add_free_presets_keeps_custom_playlist(self):
        from dizytv.sources import DEFAULT_PLAYLIST_URLS
        with tempfile.TemporaryDirectory() as folder:
            state=Store(folder).read()
            state['settings']['playlist_urls']=['https://example.com/private.m3u']
            dialog=Settings(state,None)
            dialog.add_free_playlists()
            urls=dialog.values()['playlist_urls']
            self.assertEqual('https://example.com/private.m3u',urls[0])
            self.assertIn(DEFAULT_PLAYLIST_URLS[1],urls)
            self.assertEqual(len(urls),len(set(urls)))
            dialog.close()

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_first_launch_and_timezone_guide_without_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Store(directory), start_worker=False)
            window.show(); self.app.processEvents()
            self.assertEqual('DizyTV', window.windowTitle())
            self.assertIn('auto', window.timezone_label.text().lower())
            self.assertEqual(4, window.tabs.count())
            self.assertEqual(0, window.channels.count())
            window.close()

    def test_favourites_filter_does_not_remove_catalogue(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            catalogue = [{'id':'a'*40,'name':'News','group':'UK','tvg_id':'n','stream':'acestream://'+'a'*40},
                         {'id':'b'*40,'name':'Sport','group':'UK','tvg_id':'s','stream':'acestream://'+'b'*40}]
            store.update(lambda s:s.update(channels=catalogue,favourites=['b'*40]))
            window = MainWindow(store,start_worker=False)
            window.favourites_only.setChecked(True)
            self.app.processEvents()
            self.assertEqual(1,window.channels.count())
            self.assertIn('Sport',window.channels.item(0).text())
            self.assertEqual(2,len(store.read()['channels']))
            window.close()


if __name__ == '__main__':
    unittest.main()
