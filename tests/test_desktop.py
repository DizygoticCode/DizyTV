import time
import hashlib
import sys
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QDialog
from PySide6.QtCore import QTimeZone

from dizytv.desktop import MainWindow, GuideGrid, Settings, TimeSeekSlider
from dizytv.storage import Store


class DesktopTests(unittest.TestCase):
    def test_guide_keeps_all_ace_and_category_filtered_channels(self):
        # Regression: two independent 250-row caps used to truncate 2k+ feeds.
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            channels=[
                dict(id=hashlib.sha1(f'ace-{i}'.encode()).hexdigest(),name=f'Ace Stream {i:04d}',stream=f'acestream://{i:040x}',
                     group='Sport',genre='Sport',country='United Kingdom',
                     transport='Ace Stream',source='https://search-ace.stream/playlist',
                     tvg_id=f'ace-{i}',kind='TV')
                for i in range(2300)
            ]
            channels += [
                dict(id=hashlib.sha1(f'news-{i}'.encode()).hexdigest(),name=f'News {i:04d}',stream=f'https://example.com/{i}.m3u8',
                     group='News',genre='News',country='United Kingdom',
                     transport='HTTP',source='https://iptv-org.github.io/iptv/countries/uk.m3u',
                     tvg_id=f'news-{i}',kind='TV')
                for i in range(65)
            ]
            store.update(lambda state:state.update(channels=channels))
            w=MainWindow(store,start_worker=False)
            w.source_filter.setCurrentIndex(w.source_filter.findData('<ace>'))
            w.render_channels()
            self.assertEqual(2300,w.channels.count())
            self.assertEqual(2300,len(w.grid.rows))
            self.assertEqual(hashlib.sha1(b'ace-2299').hexdigest(),w.grid.rows[-1]['id'])
            h,_,_,_=w.grid.geometry_units()
            self.assertGreater(w.grid.minimumHeight(),2300*h)
            begin,end=w.grid.visible_row_range(__import__('PySide6.QtCore',fromlist=['QRect']).QRect(0,48+2200*h,900,600))
            self.assertGreater(begin,2100)
            self.assertLess(end-begin,20)
            w.section_filter.setCurrentIndex(w.section_filter.findData('Sport'))
            w.render_channels()
            self.assertEqual(2300,len(w.grid.rows))
            w.source_filter.setCurrentIndex(w.source_filter.findData('<http>'))
            w.section_filter.setCurrentIndex(w.section_filter.findData('News'))
            w.render_channels()
            self.assertEqual(65,len(w.grid.rows))
            w.close()

    def test_popout_quick_guide_pages_every_channel_and_searches_final_page(self):
        from dizytv.core import parse_playlist
        from PySide6.QtWidgets import QListWidget, QPushButton, QLineEdit
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            playlist='#EXTM3U\n'+''.join(
                f'#EXTINF:-1,Quick Channel {i:04d}\nhttps://example.com/{i}.m3u8\n'
                for i in range(321))
            store.update(lambda s:s.update(channels=parse_playlist(playlist)))
            window=MainWindow(store,start_worker=False)
            window.show_tv_guide()
            dialog=window.guide_popup
            results=dialog.findChild(QListWidget)
            more=next(b for b in dialog.findChildren(QPushButton) if 'next 150' in b.text())
            self.assertEqual(150,results.count())
            more.click()
            self.assertEqual(300,results.count())
            more.click()
            self.assertEqual(321,results.count())
            self.assertFalse(more.isEnabled())
            query=dialog.findChild(QLineEdit)
            query.setText('Quick Channel 0320')
            self.assertEqual(1,results.count())
            self.assertEqual('Quick Channel 0320',results.item(0).data(Qt.UserRole)['name'])
            self.assertFalse(more.isEnabled())
            query.clear()
            self.assertEqual(150,results.count())
            dialog.close()
            window.close()

    @unittest.skipIf(sys.platform=='darwin', 'Qt offscreen native-window reparenting not validated on macOS')
    def test_global_search_finds_programme_hidden_by_source_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            now=int(time.time())
            ch={'id':hashlib.sha1(b'global-ace').hexdigest(),'name':'Global Science News','stream':'acestream://'+('a'*40),
                'tvg_id':'global-science','group':'Ace News','country':'United Kingdom',
                'genre':'News','kind':'TV','transport':'Ace Stream'}
            store.update(lambda state:state.update(channels=[ch]))
            w=MainWindow(store,start_worker=False)
            w.guide={'names':{'global-science':'Global Science News'},
                     'programmes':[{'channel':'global-science','title':'Solar Observatory Report',
                                    'start':now+3600,'end':now+5400}]}
            w._indexed_guide=None
            w.source_filter.setCurrentIndex(w.source_filter.findData('<http>'))
            self.assertEqual(0,w.channels.count())
            w.open_global_search()
            dlg=w.global_search_dialog
            dlg.query.setText('solar')
            dlg.debounce.stop() if hasattr(dlg,'debounce') else dlg.timer.stop()
            dlg.search()
            self.assertEqual(1,dlg.results.count())
            self.assertEqual('programme',dlg.results.item(0).data(Qt.UserRole)[0])
            dlg.results.setCurrentRow(0)
            dlg.show_in_guide() if hasattr(dlg,'show_in_guide') else dlg.show_hit()
            self.assertEqual(1,w.channels.count())
            self.assertEqual(hashlib.sha1(b'global-ace').hexdigest(),w.grid.rows[0]['id'])
            self.assertEqual(1,w.tabs.currentIndex())
            w.close()

    def test_guide_scale_reduces_geometry(self):
        grid=GuideGrid()
        grid.set_data([{'id':'a','name':'BBC One','tvg_id':'bbc'}],[],{},'auto',0)
        default=grid.minimumWidth()
        grid.set_guide_scale(60)
        self.assertLess(grid.minimumWidth(),default)
        self.assertLess(grid.geometry_units()[0],58)

    def test_complete_iptv_directory_picker_filters_cities_and_imports_only_selected(self):
        from dizytv.desktop import IPTVDirectoryDialog
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            w=MainWindow(store,start_worker=False)
            settings=Settings(store.read(),w)
            self.assertIsNotNone(settings.findChild(QPushButton,'browseIPTVDirectory'))
            active=settings.values()['playlist_urls']
            dialog=IPTVDirectoryDialog(active,settings)
            self.assertGreaterEqual(dialog.results.count(),1200)
            dialog.kind_filter.setCurrentText('Cities')
            dialog.query.setText('sydney australia')
            self.assertEqual(1,dialog.results.count())
            item=dialog.results.item(0)
            self.assertEqual('https://iptv-org.github.io/iptv/cities/ausyd.m3u',
                             item.data(Qt.UserRole))
            item.setSelected(True)
            dialog.add_selected()
            self.assertEqual(QDialog.Accepted,dialog.result())
            self.assertEqual(['https://iptv-org.github.io/iptv/cities/ausyd.m3u'],
                             dialog.added_urls)
            self.assertEqual(active,settings.values()['playlist_urls'])
            with patch.object(IPTVDirectoryDialog,'exec',lambda d:(
                    setattr(d,'added_urls',dialog.added_urls) or QDialog.Accepted)):
                settings.browse_iptv_directory()
            self.assertEqual(len(active)+1,len(settings.values()['playlist_urls']))
            self.assertIn(dialog.added_urls[0],settings.values()['playlist_urls'])
            world=IPTVDirectoryDialog(active,settings)
            world.add_worldwide()
            self.assertEqual(QDialog.Accepted,world.result())
            self.assertEqual(['https://iptv-org.github.io/iptv/index.m3u'],world.added_urls)
            crowded=['https://example.com/'+str(i)+'.m3u' for i in range(24)]
            limited=IPTVDirectoryDialog(crowded,settings)
            limited.add_worldwide()
            self.assertEqual(QDialog.Rejected,limited.result())
            self.assertIn('Remove an active feed',limited.status_label.text())
            limited.close();world.close();dialog.close();settings.close();w.close()

    def test_appearance_picker_and_settings_restyle_guide_without_losing_channels(self):
        from dizytv.desktop import desktop_style,overlay_theme_style
        from dizytv.core import parse_playlist
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            channel=parse_playlist('#EXTM3U\n#EXTINF:-1,BBC One\nhttps://example.com/bbc.m3u8')[0]
            store.update(lambda s:s.update(channels=[channel]))
            w=MainWindow(store,start_worker=False)
            self.assertEqual('Green',w.theme_picker.currentText())
            self.assertEqual(3,w.tabs.count())
            self.assertEqual(['Live TV','TV Guide','Recordings'],
                             [w.tabs.tabText(i) for i in range(w.tabs.count())])
            self.assertFalse(w.tabs.tabBar().expanding())
            self.assertTrue(w.tabs.tabBar().usesScrollButtons())
            self.assertTrue(w.tools_button.menu().actions())
            w.channels.setCurrentRow(0)
            w.theme_picker.setCurrentText('Dark')
            self.assertEqual('Dark',store.read()['settings']['theme'])
            self.assertEqual('Dark',w.grid.theme)
            self.assertIn('#17191f',QApplication.instance().styleSheet())
            self.assertEqual(channel['id'],w.selected['id'])
            self.assertNotIn('#151e19',desktop_style(theme='Light'))
            self.assertIn('#f7f9fc',desktop_style(theme='Light'))
            self.assertEqual('#f1f5fb',__import__('dizytv.desktop',fromlist=['theme_color']).theme_color('#15221a','Light'))
            self.assertIn('#17263b',overlay_theme_style('color:#edfff0;', 'Light'))
            settings=Settings(w.store.read(),w)
            self.assertEqual('Dark',settings.theme.currentText())
            settings.theme.setCurrentText('Light')
            self.assertEqual('Light',settings.values()['theme'])
            settings.close()
            w.theme_picker.setCurrentText('Light')
            self.assertEqual('Light',store.read()['settings']['theme'])
            self.assertEqual('Light',w.grid.theme)
            w.close()
            again=MainWindow(store,start_worker=False)
            self.assertEqual('Light',again.theme_picker.currentText())
            self.assertEqual(1,again.channels.count())
            again.close()

    def test_compact_scaling_and_smaller_resizable_window(self):
        from dizytv.desktop import desktop_style
        with tempfile.TemporaryDirectory() as folder:
            window=MainWindow(Store(folder),start_worker=False)
            s=Settings(window.state,window)
            s.ui_scale.setValue(80)
            s.button_size.setCurrentText('Compact')
            self.assertEqual(80,s.values()['ui_scale'])
            self.assertEqual('Compact',s.values()['button_size'])
            s.guide_scale.setValue(65)
            self.assertEqual(65,s.values()['guide_scale'])
            self.assertIn('font-size:11px;',desktop_style(80,'Compact'))
            window.resize(710,480)
            window.show()
            self.app.processEvents()
            self.assertLessEqual(window.minimumWidth(),480)
            self.assertLessEqual(window.width(),720)
            self.assertIsNotNone(window.controls_scroll.horizontalScrollBar())
            s.close();window.close()

    def test_live_light_reports_green_amber_red_and_follows_rewind(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            w=MainWindow(Store(folder),start_worker=False)
            self.assertEqual('stopped',w.playback_light_state())
            w.player=Mock()
            w.playback_started=1
            w.player.get_state.return_value='State.Playing'
            w.last_good_video=time.monotonic()
            self.assertEqual('live',w.playback_light_state())
            # Direct streams must not turn amber after 18 seconds solely
            # because there is no local timeshift capture to refresh stats.
            w.last_good_video=time.monotonic()-30
            self.assertEqual('live',w.playback_light_state())
            w.timeshift=Mock()
            self.assertEqual('buffering',w.playback_light_state())
            w.timeshift=None
            w.pulse_live_light()
            self.assertIn('3cdb80',w.live_button.styleSheet())
            w.timeshift_lag=30
            self.assertEqual('buffering',w.playback_light_state())
            w.player.get_state.return_value='State.Error'
            self.assertEqual('stopped',w.playback_light_state())
            w.player=None
            w.close()

    def test_vlc_reports_playing_but_picture_counters_frozen_auto_recovers(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            w=MainWindow(Store(folder),start_worker=False)
            w.timeshift=Mock()
            w.timeshift.window.snapshot.return_value=[Mock(seq=7)]
            w.timeshift.live_url.return_value='http://127.0.0.1:99/token/live.m3u8'
            w.player=Mock()
            w.player.get_state.return_value='State.Playing'
            w.playback_started=1
            w.last_capture_seq=7
            w.last_capture_progress=100
            w.last_good_video=70
            w.last_live_recovery=0
            w._last_media_activity=2000
            with patch.object(w,'media_activity',return_value=2000),patch.object(w,'play_url') as recover:
                w.check_live_timeshift(now=110)
                recover.assert_called_once()
            w.timeshift=None;w.player=None;w.close()

    def test_stalled_local_timeshift_recovers_only_when_unpaused(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            w=MainWindow(Store(folder),start_worker=False)
            ring=Mock()
            ring.snapshot.return_value=[Mock(seq=20)]
            w.timeshift=Mock(window=ring)
            w.timeshift.live_url.return_value='http://127.0.0.1:3333/token/live.m3u8'
            w.player=Mock()
            w.player.get_state.return_value='State.Buffering'
            w.playback_started=1
            w.last_good_video=10;w.last_live_recovery=10
            w.last_capture_progress=40;w.last_capture_seq=20
            with patch.object(w,'play_url') as play:
                w.check_live_timeshift(now=60)
                play.assert_called_once()
                play.reset_mock()
                w.player.get_state.return_value='State.Paused'
                w.check_live_timeshift(now=120)
                play.assert_not_called()
            w.timeshift=None;w.player=None;w.close()

    def test_wheel_seek_notches_and_forward_rewind_with_seekable_stream(self):
        from unittest.mock import Mock
        slider=TimeSeekSlider(Qt.Horizontal)
        slider.setEnabled(True)
        events=[]
        slider.seek_requested.connect(events.append)
        slider.seek_wheel_delta(120)
        slider.seek_wheel_delta(-240)
        self.assertEqual([30000,-60000],events)
        with tempfile.TemporaryDirectory() as folder:
            w=MainWindow(Store(folder),start_worker=False)
            w.player=Mock()
            w.player.is_seekable.return_value=True
            w.player.get_time.return_value=120000
            w.player.get_length.return_value=300000
            w.playback_started=1
            w.seek_relative(30000)
            w.player.set_time.assert_called_with(150000)
            w.seek_relative(-30000)
            w.player.set_time.assert_called_with(90000)
            w.player=None
            w.close()

    def test_cached_forward_button_uses_relative_lag_and_returns_to_live(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            w=MainWindow(Store(folder),start_worker=False)
            w.player=Mock()
            w.playback_started=1
            w.timeshift=Mock()
            w.timeshift.window.latest_seconds.return_value=180
            w.timeshift.replay_url.return_value='http://127.0.0.1:6789/test/replay.m3u8'
            w.timeshift.live_url.return_value='http://127.0.0.1:6789/test/live.m3u8'
            w.timeshift_lag=90
            with patch.object(w,'play_url') as player:
                w.seek_relative(30000)
                self.assertEqual(60,w.timeshift_lag)
                w.timeshift.replay_url.assert_called_with(60)
                player.assert_called_with('http://127.0.0.1:6789/test/replay.m3u8')
                w.seek_relative(-30000)
                self.assertEqual(90,w.timeshift_lag)
                w.seek_relative(120000)
                self.assertEqual(0,w.timeshift_lag)
                player.assert_called_with('http://127.0.0.1:6789/test/live.m3u8')
            w.timeshift=None;w.player=None
            w.close()

    def test_opt_in_offline_caption_window_and_worker_are_stopped_on_channel_change(self):
        from unittest.mock import Mock, patch
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            w=MainWindow(store,start_worker=False)
            w.show()
            settings=Settings(store.read(),w)
            self.assertIsNotNone(settings.auto_model_path)
            self.assertIsNotNone(settings.auto_ffmpeg_path)
            w.player=Mock()
            w.playback_started=1
            w._playback_url='https://example.com/authorized-live.m3u8'
            fake=Mock()
            with patch('dizytv.desktop.verify_caption_engine',
                       return_value=('ffmpeg','C:/models/vosk')), \
                 patch('dizytv.desktop.LocalCaptionWorker',return_value=fake):
                w.toggle_auto_captions()
                fake.start.assert_called_once()
                self.assertIs(w._auto_caption_worker,fake)
                serial=w._auto_caption_seq
                w.receive_auto_caption(serial,'Some example spoken words')
                self.assertEqual('Some example spoken words',w._auto_caption_label.text())
                self.assertEqual(Qt.PlainText,w._auto_caption_label.textFormat())
                self.assertEqual('autoCaptionOverlay',w._auto_caption_overlay.objectName())
                w.toggle_auto_captions()
                fake.stop.assert_called_once()
                self.assertIsNone(w._auto_caption_overlay)
                self.assertIsNone(w._auto_caption_worker)
            # Late transcription messages cannot resurrect an overlay.
            w.receive_auto_caption(serial,'stale result')
            self.assertIsNone(w._auto_caption_overlay)
            w.player=None
            settings.close();w.close()

    def test_explicit_srt_file_is_not_replaced_by_next_broadcast_subtitle_tick(self):
        from unittest.mock import Mock, patch
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'own-caption.srt'
            path.write_text('1\n00:00:01,000 --> 00:00:04,000\nTest\n',encoding='utf-8')
            store=Store(folder)
            store.update(lambda s:s['settings'].update(subtitles_enabled=False))
            w=MainWindow(store,start_worker=False)
            w.player=Mock()
            w.player.get_length.return_value=0
            w.player.get_time.return_value=0
            w.player.is_seekable.return_value=False
            w.playback_started=1
            w.player.video_set_subtitle_file.return_value=True
            w.player.video_get_spu_description.return_value=[(1,'English'),(2,'French')]
            w.player.video_set_spu.return_value=0
            w._subtitle_auto_applied=True
            with patch('dizytv.desktop.QFileDialog.getOpenFileName',
                       return_value=(str(path),'')):
                w.load_subtitle_file()
            self.assertEqual('external',w._subtitle_manual_track)
            self.assertTrue(store.read()['settings']['subtitles_enabled'])
            w.player.video_set_spu.reset_mock()
            w.sync_subtitles()
            w.player.video_set_spu.assert_not_called()
            # A pure appearance edit must not remove a manual subtitle file.
            with patch.object(Settings,'exec',lambda d: QDialog.Accepted), \
                 patch.object(Settings,'values',
                              lambda d:dict(d.original,subtitle_colour='Yellow')):
                w.settings()
            self.assertEqual('external',w._subtitle_manual_track)
            w.player=None;w.close()

    def test_global_subtitle_toggle_restores_a_valid_track_when_reenabled(self):
        from unittest.mock import Mock, patch
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            store.update(lambda s:s['settings'].update(subtitles_enabled=False))
            w=MainWindow(store,start_worker=False)
            w.player=Mock()
            w.player.get_length.return_value=0
            w.player.get_time.return_value=0
            w.player.is_seekable.return_value=False
            w.playback_started=1
            w.player.video_get_spu_description.return_value=[(3,'English')]
            w.player.video_get_spu.return_value=-1
            w.player.video_set_spu.return_value=0
            w._subtitle_manual_track=3
            w._subtitle_auto_applied=True
            with patch.object(Settings,'exec',lambda d: QDialog.Accepted), \
                 patch.object(Settings,'values',
                              lambda d:dict(d.original,subtitles_enabled=True)):
                w.settings()
            self.assertIsNone(w._subtitle_manual_track)
            w.player.video_set_spu.assert_called_with(3)
            w.player=None;w.close()

    def test_backup_restore_applies_subtitles_off_to_active_player(self):
        from unittest.mock import Mock, patch
        from pathlib import Path
        from PySide6.QtWidgets import QMessageBox
        from dizytv.core import export_backup
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            state=store.read()
            state['settings']['subtitles_enabled']=False
            backup=Path(folder)/'subtitle-backup.json'
            backup.write_text(export_backup(state),encoding='utf-8')
            w=MainWindow(store,start_worker=False)
            w.player=Mock()
            w.player.get_length.return_value=0
            w.player.get_time.return_value=0
            w.player.is_seekable.return_value=False
            w.player.video_set_spu.return_value=0
            w.player.video_get_spu_description.return_value=[(3,'English')]
            w.playback_started=1
            w._subtitle_auto_applied=True
            w._subtitle_manual_track=3
            with patch('dizytv.desktop.QFileDialog.getOpenFileName',
                       return_value=(str(backup),'')), \
                 patch('dizytv.desktop.QMessageBox.question',
                       return_value=QMessageBox.Yes):
                w.restore()
            self.assertFalse(store.read()['settings']['subtitles_enabled'])
            self.assertIsNone(w._subtitle_manual_track)
            w.player.video_set_spu.assert_called_with(-1)
            self.assertTrue(w._subtitle_auto_applied)
            w.player=None;w.close()

    def test_disable_subtitles_retries_after_vlc_initially_rejects_off(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            store.update(lambda s:s['settings'].update(subtitles_enabled=False))
            w=MainWindow(store,start_worker=False)
            w.player=Mock()
            w.playback_started=1
            w.player.video_set_spu.side_effect=[-1,0]
            w.sync_subtitles()
            self.assertFalse(w._subtitle_auto_applied)
            w.sync_subtitles()
            self.assertTrue(w._subtitle_auto_applied)
            w.sync_subtitles()
            self.assertEqual(2,w.player.video_set_spu.call_count)
            w.player.video_set_spu.assert_called_with(-1)
            w.player=None;w.close()

    def test_automatic_subtitles_retry_track_until_vlc_accepts_selection(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            w=MainWindow(Store(folder),start_worker=False)
            w.player=Mock()
            w.playback_started=1
            w.player.video_get_spu_description.return_value=[(3,'English')]
            w.player.video_get_spu.return_value=-1
            w.player.video_set_spu.side_effect=[-1,0]
            w.sync_subtitles()
            self.assertFalse(w._subtitle_auto_applied)
            self.assertEqual((),w._subtitle_track_signature)
            w.sync_subtitles()
            self.assertTrue(w._subtitle_auto_applied)
            self.assertEqual(2,w.player.video_set_spu.call_count)
            w.sync_subtitles()
            self.assertEqual(2,w.player.video_set_spu.call_count)
            w.player=None;w.close()

    def test_caption_overlay_repositions_when_main_window_moves(self):
        from PySide6.QtWidgets import QFrame
        with tempfile.TemporaryDirectory() as folder:
            w=MainWindow(Store(folder),start_worker=False)
            w.show()
            QApplication.processEvents()
            w._auto_caption_overlay=QFrame(w.video)
            with patch.object(w,'position_auto_caption_overlay') as reposition:
                w.move(w.x()+40,w.y()+32)
                QApplication.processEvents()
                self.assertGreater(reposition.call_count,0)
            w.destroy_auto_caption_overlay()
            w.close()

    def test_vlc_closed_captions_track_lifecycle_and_preferences(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            w=MainWindow(store,start_worker=False)
            self.assertEqual('CC Subtitles',w.subtitle_button.text())
            settings=Settings(store.read(),w)
            self.assertTrue(settings.cc_enabled.isChecked())
            settings.cc_font.setCurrentText('Monospace')
            settings.cc_position.setCurrentText('Raised')
            settings.cc_colour.setCurrentText('Cyan')
            settings.cc_size.setValue(38)
            self.assertEqual('Cyan',settings.values()['subtitle_colour'])
            self.assertEqual(38,settings.values()['subtitle_size'])
            w.player=Mock()
            w.player.get_state.return_value='State.Playing'
            w.player.video_get_spu_description.return_value=[(-1,'Disable'),(1,'French'),(3,'English')]
            w.player.video_get_spu.return_value=-1
            w.player.video_set_spu.return_value=0
            w.playback_started=1
            w.state['settings']['subtitle_language']='English'
            w.sync_subtitles()
            w.player.video_set_spu.assert_called_with(3)
            self.assertTrue(w._subtitle_auto_applied)
            w.choose_subtitle_track(1)
            w.player.video_set_spu.assert_called_with(1)
            self.assertEqual(1,w._subtitle_manual_track)
            w.state['settings']['subtitles_enabled']=False
            w._subtitle_auto_applied=False
            w.sync_subtitles()
            w.player.video_set_spu.assert_called_with(-1)
            w.player=None
            settings.close();w.close()

    def test_subtitle_style_saved_without_restart_or_active_recording_changes(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            w=MainWindow(store,start_worker=False)
            initial=store.read()['settings']
            modified=dict(initial,subtitle_colour='Yellow',subtitle_position='High',
                          subtitle_size=50,subtitle_font='Serif')
            w.store.update(lambda s:s.update(settings=modified))
            w.state=w.store.read()
            w.apply_interface_scale()
            self.assertEqual('Yellow',w.state['settings']['subtitle_colour'])
            from dizytv.subtitles import vlc_subtitle_options
            opts=vlc_subtitle_options(w.state['settings'])
            self.assertIn('--sub-margin=135',opts)
            self.assertIn('--freetype-fontsize=50',opts)
            self.assertIsNone(w.player)
            self.assertEqual([],store.read()['jobs'])
            w.close()

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

    @unittest.skipIf(sys.platform=='darwin', 'Qt offscreen native-window reparenting not validated on macOS')
    def test_transparent_popout_controls_overlay_video_without_resizing_window(self):
        with tempfile.TemporaryDirectory() as folder:
            w=MainWindow(Store(folder),start_worker=False)
            w.show()
            self.app.processEvents()
            w.open_popout()
            self.app.processEvents()
            dialog=w.screen_dialog
            before_window=dialog.size()
            before_video=w.video.size()
            self.assertNotIn(w.detached_controls,[dialog.layout().itemAt(i).widget() for i in range(dialog.layout().count())])
            self.assertEqual(w.detached_controls.testAttribute(Qt.WA_TranslucentBackground),
                             os.name=='nt' and os.environ.get('QT_QPA_PLATFORM')!='offscreen')
            self.assertIn('#playerControls {background:transparent;',w.detached_controls.styleSheet())
            w.hide_detached_controls()
            self.app.processEvents()
            self.assertEqual(before_window,dialog.size())
            self.assertEqual(before_video,w.video.size())
            w.show_detached_controls()
            self.app.processEvents()
            self.assertEqual(before_window,dialog.size())
            self.assertEqual(before_video,w.video.size())
            w.exit_screen_fullscreen()
            w.close()

    @unittest.skipIf(sys.platform=='darwin', 'Qt offscreen native-window reparenting not validated on macOS')
    @unittest.skipIf(sys.platform=='darwin', 'Qt offscreen native-window reparenting not validated on macOS')
    def test_popout_cursor_uses_global_to_panel_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            w=MainWindow(Store(folder),start_worker=False)
            w.show()
            w.open_popout()
            self.app.processEvents()
            panel=w.detached_controls
            w.screen_dialog.move(480,260)
            w.position_detached_overlay()
            self.app.processEvents()
            point=panel.mapToGlobal(panel.rect().center())
            self.assertTrue(w.cursor_over_detached_controls(point))
            # The inactivity timeout must never hide controls while the
            # cursor is inside them, even when the TV is off the origin.
            with patch('dizytv.desktop.QCursor.pos',return_value=point):
                w.hide_detached_controls()
                self.assertTrue(panel.isVisible())
            w.exit_screen_fullscreen()
            w.close()

    def test_resizable_popout_keeps_player_and_guide_available(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            window=MainWindow(Store(folder),start_worker=False)
            window.show()
            self.app.processEvents()
            window.player=Mock()
            window.open_popout()
            self.assertIsNotNone(window.screen_dialog)
            self.assertFalse(window.screen_dialog.isFullScreen())
            self.assertGreaterEqual(window.screen_dialog.minimumWidth(),360)
            self.assertIs(window.video.parentWidget(),window.screen_dialog)
            self.assertTrue(window.tabs.isVisible())
            window.hide_detached_controls()
            window.show_detached_controls()
            self.assertTrue(window.detached_controls.isVisible())
            window.toggle_screen_fullscreen()
            self.assertTrue(window.screen_dialog.isFullScreen())
            window.open_popout()
            self.assertFalse(window.screen_dialog.isFullScreen())
            window.exit_screen_fullscreen()
            self.assertIsNone(window.screen_dialog)
            self.assertIs(window.video.parentWidget(),window.tabs.widget(0))
            window.player=None
            window.close()

    @unittest.skipIf(sys.platform=='darwin', 'Qt offscreen native-window reparenting not validated on macOS')
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

    def test_cached_radio_under_separate_uk_radio_section(self):
        from dizytv.core import parse_playlist
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            src=('#EXTM3U\n#EXTINF:-1 tvg-id="BBCRadio2.uk" tvg-country="GB" group-title="UK",BBC Radio 2\nhttps://example.com/r.m3u8\n'
                 '#EXTINF:-1 tvg-country="GB" group-title="UK",BBC One\nhttps://example.com/tv.m3u8')
            channels=parse_playlist(src)
            channels[0]['kind']='TV'  # pre-fix cached data
            store.update(lambda s:s.update(channels=channels))
            w=MainWindow(store,start_worker=False)
            uk=next(w.country_tree.topLevelItem(i) for i in range(w.country_tree.topLevelItemCount()) if 'United Kingdom' in w.country_tree.topLevelItem(i).text(0))
            names=[uk.child(i).text(0) for i in range(uk.childCount())]
            self.assertTrue(any('Radio' in name for name in names),names)
            w.close()

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

    def test_same_channel_remains_available_from_multiple_playlist_filters(self):
        from dizytv.core import parse_playlist
        from dizytv.sources import FREE_PLAYLISTS
        presets={label:url for label,url,_ in FREE_PLAYLISTS}
        canada=presets['IPTV-org Canada']
        series=presets['Free television series channels']
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory)
            ch=parse_playlist('#EXTM3U\n#EXTINF:-1,24-7 Comedy\nhttps://example.com/show.m3u8')[0]
            ch.update(source=canada,sources=[canada,series],country='Canada',genre='Series')
            store.update(lambda s:s.update(channels=[ch]))
            w=MainWindow(store,start_worker=False)
            for source in (canada,series):
                idx=w.source_filter.findData(source)
                self.assertGreaterEqual(idx,0)
                w.source_filter.setCurrentIndex(idx)
                self.assertEqual(1,w.channels.count())
                self.assertEqual(ch['id'],w.grid.rows[0]['id'])
            w.close()

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
            self.assertEqual(3, window.tabs.count())
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
