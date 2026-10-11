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
            # Right-click opens menu; choosing Record must not play the stream.
            with patch('dizytv.desktop.QMenu.exec',lambda menu,*args:menu.actions()[-1].trigger()):
                QTest.mouseClick(window.grid,Qt.RightButton,Qt.NoModifier,QPoint(230,75))
            self.assertEqual([(ch['id'],'Current show')],scheduled)
            self.assertEqual([ch['id']],watched)
            # Right-click on a channel with no current programme can record now.
            window.guide={'names':{},'programmes':[]}
            window.render_channels()
            recorded_now=[]; window.record_now=lambda:recorded_now.append(window.selected['id'])
            with patch('dizytv.desktop.QMenu.exec',lambda menu,*args:menu.actions()[-1].trigger()):
                QTest.mouseClick(window.grid,Qt.RightButton,Qt.NoModifier,QPoint(25,75))
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
