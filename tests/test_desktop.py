import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimeZone

from dizytv.desktop import MainWindow, GuideGrid
from dizytv.storage import Store


class DesktopTests(unittest.TestCase):
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
