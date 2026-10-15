"""Catalogue semantics affected by the large-catalogue performance fixes."""
import hashlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from dizytv.channel_browser import channel_sort_key, is_show_loop_channel
from dizytv.desktop import MainWindow
from dizytv.storage import Store


def channel(name, genre='Series', tvg_id='shared'):
    return dict(id=hashlib.sha1(name.encode()).hexdigest(), name=name, group=genre,
                genre=genre, country='United Kingdom', kind='TV', transport='HTTP',
                tvg_id=tvg_id, stream='https://example.com/' + name.replace(' ', '-'))


class CatalogueRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_alternate_streams_share_one_copy_of_each_guide_programme(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            store.update(lambda state: state.update(channels=[
                channel('World Channel primary'), channel('World Channel backup')]))
            window = MainWindow(store, start_worker=False)
            try:
                start = window.guide_start
                programme = dict(channel='shared', start=start, end=start+3600,
                                 title='Shared programme', categories=['Series'])
                window.guide = dict(names={'shared': 'World Channel'}, programmes=[programme])
                window.render_channels()
                self.assertEqual(2, len(window.grid.rows))
                self.assertEqual([programme], window.grid.programmes)
            finally:
                window.close()

    def test_shared_guide_retains_genre_union_when_only_later_channel_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            store.update(lambda state: state.update(channels=[
                channel('A primary', 'Series'), channel('Z backup', 'News')]))
            window = MainWindow(store, start_worker=False)
            try:
                start = window.guide_start
                programmes = [dict(channel='shared', start=start+i*3600,
                                   end=start+(i+1)*3600, title=title, categories=[genre])
                              for i, (title, genre) in enumerate([
                                  ('Bulletin', 'News'), ('Drama', 'Series')])]
                window.guide = dict(names={'shared': 'World Channel'}, programmes=programmes)
                window.render_channels()
                window.genre_filter.setCurrentIndex(window.genre_filter.findData('News'))
                self.assertEqual(2, len(window.grid.rows))
                self.assertEqual(programmes, window.grid.programmes)
            finally:
                window.close()

    def test_pending_tree_batches_are_cancelled_when_window_is_destroyed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            store.update(lambda state: state.update(channels=[
                channel(f'World Channel {i:04d}') for i in range(3001)]))
            window = MainWindow(store, start_worker=False)
            self.app.processEvents()
            section = window.country_tree.topLevelItem(0).child(0)
            window.populate_expanded_section(section)
            self.assertEqual(250, section.childCount())
            self.app.processEvents()
            self.assertGreater(section.childCount(), 250)
            self.assertLess(section.childCount(), 3001)
            window.close()
            errors = []
            with patch.object(sys, 'excepthook', lambda *args: errors.append(args)):
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                self.app.processEvents()
            self.assertEqual([], errors)

    def test_show_name_boundaries_and_existing_friends_rules_are_preserved(self):
        for name in ('The Simpsons HD', '247 Friends', 'Friends TV', '1247 Friends',
                     'Friends TVshow', 'Énergie South Park', 'South Park +1'):
            with self.subTest(name=name):
                self.assertTrue(is_show_loop_channel(channel(name)))
        for name in ('South Parkway', 'Notfriends', 'Garfield and Friends',
                     'Friends comedy', 'Rick and Mortyville', 'South Park News'):
            with self.subTest(name=name):
                self.assertFalse(is_show_loop_channel(channel(name)))
        self.assertFalse(is_show_loop_channel(channel('South Park Radio')))

    def test_sort_preserves_unicode_plus_one_and_playlist_positions(self):
        rows = [channel(name) for name in ('E4 +1', '中国电视', 'E4', 'E4 Extra', 'Énergie')]
        for mode in ('Name A–Z', 'Similar names / +1', 'Country → category', 'Category → name'):
            with self.subTest(mode=mode):
                ordered = sorted(enumerate(rows), key=lambda pair: channel_sort_key(pair[1], mode, pair[0]))
                self.assertEqual(['E4', 'E4 +1', 'E4 Extra', 'Énergie', '中国电视'],
                                 [ch['name'] for _, ch in ordered])
        ordered = sorted(enumerate(rows), key=lambda pair: channel_sort_key(pair[1], 'Playlist order', pair[0]))
        self.assertEqual(rows, [ch for _, ch in ordered])
        for name, expected in (('A ++1', 'a +'), ('+1', ''), ('E4 + 1', 'e4')):
            with self.subTest(name=name):
                self.assertEqual(expected, channel_sort_key(channel(name), 'Similar names / +1')[0])


if __name__ == '__main__':
    unittest.main()
