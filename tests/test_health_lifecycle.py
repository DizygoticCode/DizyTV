"""Health scan controls with deterministic completions and no network access."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from dizytv.desktop import ChannelHealthDialog
from dizytv.health_history import HealthHistory
from dizytv.storage import Store


class CapturingPool:
    def __init__(self):
        self.tasks=[]

    def start(self,task):
        self.tasks.append(task)


class HealthLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store=Store(self.folder.name)
        self.pool=CapturingPool()
        self.dialog=ChannelHealthDialog(self.store,None,self.pool)
        self.dialog.rows=[{
            'id':f'{i+1:040x}','name':f'Channel {i}',
            'stream':f'https://example.com/{i}',
        } for i in range(90)]
        self.dialog.reset_filter()
        self.dialog.show()
        self.app.processEvents()
        self.addCleanup(self.dialog.close)

    def finish_batch(self,status='unverified',count=40,start=0):
        entries=[{
            'id':row['id'],'name':row['name'],'status':status,'detail':'Fixture result',
        } for row in self.dialog.rows[start:start+count]]
        self.pool.tasks[-1].signals.success.emit((entries,start+count))

    def test_close_stops_automatic_continuation_and_retains_completed_results(self):
        self.dialog.start_progressive_scan()
        self.dialog.close()
        self.finish_batch()
        self.app.processEvents()
        self.assertEqual(1,len(self.pool.tasks))
        self.assertFalse(self.dialog.scan_all)
        self.assertEqual(40,len(self.dialog.results))
        self.assertEqual(40,len(HealthHistory(self.store).read()))

    def test_escape_stops_automatic_continuation(self):
        self.dialog.start_progressive_scan()
        QTest.keyClick(self.dialog,Qt.Key_Escape)
        self.finish_batch()
        self.app.processEvents()
        self.assertFalse(self.dialog.isVisible())
        self.assertEqual(1,len(self.pool.tasks))
        self.assertFalse(self.dialog.scan_all)

    def test_stop_cancels_continuation_already_queued_by_a_completed_batch(self):
        self.dialog.start_progressive_scan()
        self.finish_batch()
        self.dialog.stop_progressive_scan()
        self.app.processEvents()
        self.assertEqual(1,len(self.pool.tasks))
        self.assertFalse(self.dialog.running)
        self.assertEqual(40,self.dialog.progress.value())
        self.assertTrue(self.dialog.batch_button.isEnabled())

    def test_rate_limit_pause_allows_manual_resume_at_first_unchecked_channel(self):
        self.dialog.start_progressive_scan()
        self.finish_batch('rate-limited',count=4)
        self.app.processEvents()
        self.assertEqual(1,len(self.pool.tasks))
        self.assertFalse(self.dialog.scan_all)
        self.assertEqual(4,self.dialog.offset)
        self.assertEqual(4,self.dialog.progress.value())
        self.assertEqual(90,self.dialog.progress.maximum())
        self.assertTrue(self.dialog.batch_button.isEnabled())
        self.assertTrue(self.dialog.scan_button.isEnabled())
        self.assertIn('429',self.dialog.summary.text())

    def test_recheck_partial_rate_limited_batch_keeps_progress_at_checked_prefix(self):
        self.dialog.start_progressive_scan()
        self.finish_batch('rate-limited',count=4)
        self.dialog.recheck_last()
        self.finish_batch(count=40)
        self.app.processEvents()
        self.assertEqual(40,self.dialog.offset)
        self.assertEqual(40,self.dialog.progress.value())
        self.assertEqual(44,len(self.dialog.results))
        self.assertEqual(40,len(HealthHistory(self.store).read()))

    def test_selected_check_keeps_scan_cursor_and_saves_its_result(self):
        self.dialog.selected=self.dialog.rows[0]
        self.dialog.check_selected()
        self.finish_batch(count=1)
        self.app.processEvents()
        self.assertEqual(0,self.dialog.offset)
        self.assertEqual(0,self.dialog.progress.value())
        self.assertEqual(1,len(self.dialog.results))
        self.assertEqual(1,len(HealthHistory(self.store).read()))

    def test_closing_main_window_stops_its_modeless_health_dialog(self):
        from dizytv.desktop import MainWindow
        window=MainWindow(self.store,start_worker=False)
        self.addCleanup(window.close)
        pool=CapturingPool()
        window.pool=pool
        window.show()
        window.open_channel_health()
        dialog=window.health_dialog
        self.addCleanup(dialog.close)
        dialog.rows=list(self.dialog.rows)
        dialog.reset_filter()
        dialog.start_progressive_scan()
        window.close()
        entries=[dict(id=row['id'],name=row['name'],status='unverified',detail='Fixture')
                 for row in dialog.rows[:40]]
        pool.tasks[0].signals.success.emit((entries,40))
        self.app.processEvents()
        self.assertFalse(dialog.isVisible())
        self.assertFalse(dialog.scan_all)
        self.assertEqual(1,len(pool.tasks))

    def test_task_failure_does_not_echo_provider_credentials_or_signed_urls(self):
        self.dialog.start_progressive_scan()
        self.pool.tasks[-1].signals.failure.emit(
            'https://user:password@provider.example/live?token=secret')
        self.app.processEvents()
        self.assertNotIn('password',self.dialog.summary.text())
        self.assertNotIn('secret',self.dialog.summary.text())
        self.assertFalse(self.dialog.running)
        self.assertFalse(self.dialog.scan_all)
        self.assertTrue(self.dialog.batch_button.isEnabled())

    def test_empty_selection_has_no_busy_progress_or_active_scan(self):
        self.dialog.rows=[]
        self.dialog.reset_filter()
        self.dialog.start_progressive_scan()
        self.assertFalse(self.dialog.scan_all)
        self.assertFalse(self.dialog.running)
        self.assertFalse(self.dialog.scan_button.isEnabled())
        self.assertFalse(self.dialog.stop_button.isEnabled())
        self.assertGreater(self.dialog.progress.maximum(),0)
        self.assertEqual(0,self.dialog.progress.value())
        self.assertEqual(0,len(self.pool.tasks))

    def test_busy_capacity_pauses_without_saving_false_failure_or_advancing_cursor(self):
        blocked=self.dialog.rows[2]
        history=HealthHistory(self.store)
        history.record([dict(id=blocked['id'],status='manifest-only')])
        self.dialog.start_progressive_scan()
        entries=[dict(id=row['id'],name=row['name'],status='unverified',detail='Fixture')
                 for row in self.dialog.rows[:2]]
        entries.append(dict(id=blocked['id'],name=blocked['name'],
                            status='checker-busy',detail='Checker busy; not probed'))
        self.pool.tasks[-1].signals.success.emit((entries,2))
        self.app.processEvents()
        self.assertFalse(self.dialog.scan_all)
        self.assertEqual(1,len(self.pool.tasks))
        self.assertEqual(2,self.dialog.offset)
        self.assertEqual(2,self.dialog.progress.value())
        self.assertEqual(2,len(self.dialog.results))
        self.assertIn('busy',self.dialog.summary.text().lower())
        self.assertEqual('manifest-only',history.read()[blocked['id']]['status'])
        self.assertTrue(self.dialog.batch_button.isEnabled())
        self.dialog.batch_button.click()
        self.assertEqual(2,self.dialog.last_batch_start)
        self.finish_batch(count=40,start=2)
        self.assertEqual(42,self.dialog.offset)
        self.assertEqual(42,len(self.dialog.results))

    def test_fully_busy_batch_does_not_advance_or_replace_saved_results(self):
        self.dialog.start_progressive_scan()
        row=self.dialog.rows[0]
        self.pool.tasks[-1].signals.success.emit(([
            dict(id=row['id'],name=row['name'],status='checker-busy',detail='Not probed')],0))
        self.app.processEvents()
        self.assertFalse(self.dialog.scan_all)
        self.assertEqual(1,len(self.pool.tasks))
        self.assertEqual(0,self.dialog.offset)
        self.assertEqual([],self.dialog.results)
        self.assertEqual({},HealthHistory(self.store).read())


if __name__=='__main__':
    unittest.main()
