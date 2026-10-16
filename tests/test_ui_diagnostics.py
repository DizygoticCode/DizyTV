"""Contract tests for optional local UI-hang diagnosis and nonblocking state IO."""
import tempfile
import threading
import unittest
from pathlib import Path

from dizytv.ui_diagnostics import UiHangMonitor
from dizytv.storage import Store, _mutex


class UiHangDiagnosticsTests(unittest.TestCase):
    def test_only_detects_missing_ui_heartbeat_after_threshold(self):
        with tempfile.TemporaryDirectory() as folder:
            now=[100.0]
            monitor=UiHangMonitor(folder,threshold=8,clock=lambda:now[0])
            self.assertFalse(monitor.poll_once())
            self.assertFalse(monitor.path.exists())
            now[0]=107.0
            self.assertFalse(monitor.poll_once())
            now[0]=109.0
            self.assertTrue(monitor.poll_once())
            self.assertIn('Qt UI no heartbeat',monitor.path.read_text(encoding='utf-8'))
            self.assertFalse(monitor.poll_once())  # no unbounded repeated logs
            monitor.heartbeat()
            now[0]=120.0
            self.assertTrue(monitor.poll_once())

    def test_gui_state_poll_does_not_wait_on_recorder_mutex(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            locked=threading.Event()
            release=threading.Event()
            def hold_recorder_lock():
                with _mutex:
                    locked.set()
                    release.wait(3)
            worker=threading.Thread(target=hold_recorder_lock,daemon=True)
            worker.start()
            self.assertTrue(locked.wait(1))
            try:
                # No Qt 5-second tick may wait for a simultaneous state write.
                self.assertIsNone(store.try_read())
            finally:
                release.set()
                worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.assertIsNotNone(store.try_read())


if __name__=='__main__':
    unittest.main()
