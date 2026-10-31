"""Dashboard regression contract: presentation must never replace old features."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import time
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from dizytv.desktop import MainWindow, desktop_style
from dizytv.desktop_dashboard import navigate
from dizytv.storage import Store


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_every_existing_tab_and_tool_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Store(directory), start_worker=False)
            try:
                self.assertEqual(
                    [window.tabs.tabText(i) for i in range(window.tabs.count())],
                    ['Live TV', 'TV Guide', 'Recordings'])
                self.assertEqual(window.header_logo.objectName(), 'dizytvLogo')
                self.assertIsNotNone(window.tools_button.menu())
                menu = window.tools_button.menu()
                text = ' '.join(a.text() for a in menu.actions())
                for action in (
                    'Save local backup', 'Restore local backup',
                    'Set up Ace Stream', 'Check channel health',
                    'Find duplicate channels', 'System usage',
                    'Selected channel source', 'Try another saved source',
                ):
                    with self.subTest(action=action):
                        self.assertIn(action, text)
                for action in ('Live TV', 'TV Guide', 'Movies', 'Series',
                               'Sports', 'DVR', 'Search'):
                    self.assertTrue(
                        any(b.text() == action
                            for b in window.dashboard_navigation_buttons.values()))
                self.assertIs(window.video.parentWidget(),
                              window.dashboard_hero.widget(0))
                self.assertTrue(window.seek_slider is not None)
                self.assertTrue(window.subtitle_button is not None)
                self.assertTrue(window.controls_scroll.widget() is not None)
                self.assertEqual(window.channels.objectName(), '')
            finally:
                window.close()

    def test_timeline_reuses_full_epg_model_without_channel_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Store(directory), start_worker=False)
            try:
                self.assertIsNot(window.dashboard_grid, window.grid)
                self.assertEqual(len(window.dashboard_grid.rows), len(window.grid.rows))
                # Retain the original full guide and recorder route.
                navigate(window, 'guide')
                self.assertEqual(1, window.tabs.currentIndex())
                navigate(window, 'dvr')
                self.assertEqual(2, window.tabs.currentIndex())
                navigate(window, 'live')
                self.assertEqual(0, window.tabs.currentIndex())
            finally:
                window.close()

    def test_sports_shortcut_filters_canonical_sport_channel(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            channel = dict(
                id='a'*40, name='Local Football', stream='https://example.com/clear.m3u8',
                group='Sport', genre='Sport', country='United Kingdom',
                source='https://iptv-org.github.io/iptv/countries/uk.m3u',
                transport='HTTP', tvg_id='football-uk', kind='TV')
            store.update(lambda state: state.update(channels=[channel]))
            window = MainWindow(store, start_worker=False)
            try:
                navigate(window, 'Sports')
                self.assertEqual('Sport', window.section_filter.currentData())
                self.assertEqual(1, window.channels.count())
                self.assertEqual('Local Football', window.channels.item(0).data(Qt.UserRole)['name'])
            finally:
                window.close()

    def test_navigation_buttons_are_not_clipped_at_saved_80_percent_scale(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            store.update(lambda state: state['settings'].update(
                ui_scale=80, button_size='Compact'))
            window = MainWindow(store, start_worker=False)
            try:
                window.resize(640, 460)
                window.show()
                for _ in range(3):
                    self.app.processEvents()
                nav = window.dashboard_nav_scroll
                self.assertGreaterEqual(
                    nav.height(), nav.widget().sizeHint().height())
                self.assertEqual(80, store.read()['settings']['ui_scale'])
                bar = nav.horizontalScrollBar()
                if bar.maximum() > bar.minimum():
                    self.assertTrue(window.dashboard_nav_more.isVisible())
            finally:
                window.close()

    def test_collapsed_timeline_releases_space_and_restores_same_guide(self):
        from PySide6.QtWidgets import QPushButton
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Store(directory), start_worker=False)
            try:
                window.resize(1150, 730)
                window.show()
                self.app.processEvents()
                timeline = window.dashboard_timeline
                grid = window.dashboard_grid
                initial = window.live_layout.stretch(window.live_layout.indexOf(timeline))
                button = next(b for b in timeline.findChildren(QPushButton)
                              if b.text() == 'Hide timeline')
                button.click()
                self.app.processEvents()
                self.assertFalse(window.dashboard_grid.isVisible())
                self.assertEqual(0, window.live_layout.stretch(
                    window.live_layout.indexOf(timeline)))
                self.assertLess(timeline.maximumHeight(), 100)
                self.assertEqual('Show timeline', button.text())
                button.click()
                self.app.processEvents()
                self.assertTrue(window.dashboard_grid.isVisible())
                self.assertEqual(initial, window.live_layout.stretch(
                    window.live_layout.indexOf(timeline)))
                self.assertIs(grid, window.dashboard_grid)
            finally:
                window.close()

    def test_real_programme_detail_and_theme_and_scale(self):
        from dizytv.desktop_dashboard import update_dashboard_details
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Store(directory), start_worker=False)
            try:
                window.selected = dict(name='Demo', country='United Kingdom',
                                       genre='News')
                now = int(time.time())
                update_dashboard_details(window, [
                    dict(title='Actual XMLTV title', start=now-20, end=now+400,
                         description='Real description')])
                self.assertEqual('Actual XMLTV title',
                                 window.dashboard_programme_title.text())
                self.assertIn('Real description',
                              window.dashboard_programme_description.text())
                update_dashboard_details(window, [])
                self.assertEqual('No guide match',
                                 window.dashboard_programme_title.text())
                for theme in ('Green', 'Dark', 'Light'):
                    css = desktop_style(80, 'Compact', theme)
                    self.assertIn('QWidget#dashboardNavigation', css)
                    self.assertIn('QFrame#dashboardTimeline', css)
                    self.assertIn('QLabel#dashboardProgrammeTitle', css)
            finally:
                window.close()


if __name__ == '__main__':
    unittest.main()
