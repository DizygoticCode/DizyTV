import shutil
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from dizytv.recorder import record_stream, due_jobs
from dizytv.storage import Store, file_lock
from dizytv.core import make_job

PACKETS = (b'\x47' + bytes(187)) * 20


class Source(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        self.send_response(200); self.send_header('Content-Type','video/mp2t'); self.end_headers()
        try:
            count = 1 if self.path == '/short' else 100
            for _ in range(count):
                self.wfile.write(PACKETS); self.wfile.flush(); time.sleep(.03)
        except (BrokenPipeError, ConnectionResetError):
            pass


class RecorderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1',0), Source)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def test_completed_stream_saved_in_chosen_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            result = record_stream(self.url+'/live', folder, '../News', time.time()+.15, reserve=0)
            self.assertEqual('completed', result['status'])
            self.assertEqual(Path(folder), Path(result['path']).parent)
            self.assertGreater(result['bytes'], 0)
            self.assertEqual(0, Path(result['path']).stat().st_size % 188)

    def test_eof_preserves_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            result = record_stream(self.url+'/short', folder, 'News', time.time()+3, reserve=0)
            self.assertEqual('partial', result['status'])
            self.assertTrue(Path(result['path']).is_file())
            self.assertIn('ended', result['error'])

    def test_low_space_does_not_write_and_destination_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('dizytv.recorder.shutil.disk_usage', return_value=shutil._ntuple_diskusage(100,99,1)):
                result = record_stream(self.url+'/live', folder, 'News', time.time()+1, reserve=2)
            self.assertEqual('failed', result['status'])
            self.assertEqual([], list(Path(folder).glob('*.ts')))
            result = record_stream(self.url+'/live', Path(folder)/'missing', 'News', time.time()+1, reserve=0)
            self.assertEqual('failed', result['status'])
            self.assertFalse((Path(folder)/'missing').exists())

    def test_cancel_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            count = [0]
            def cancel():
                count[0] += 1
                return count[0] > 2
            result = record_stream(self.url+'/live', folder, 'News', time.time()+5, reserve=0, cancel=cancel)
            self.assertEqual('partial', result['status'])
            self.assertGreater(result['bytes'], 0)

    def test_late_and_missed_jobs_and_worker_exclusion(self):
        now = 2000000000
        missed = make_job('a'*40, 'Missed', now-3600, now-10, 0,0)
        late = make_job('a'*40, 'Late', now-60, now+60, 0,0)
        future = make_job('a'*40, 'Future', now+3600, now+7200, 0,0)
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            store.update(lambda s: s.update(jobs=[missed,late,future]))
            self.assertEqual([late['id']], [j['id'] for j in due_jobs(store, now)])
            self.assertEqual('missed', store.read()['jobs'][0]['status'])
            with file_lock(Path(folder)/'worker.lock', blocking=False):
                with self.assertRaises(OSError):
                    with file_lock(Path(folder)/'worker.lock', blocking=False):
                        self.fail('A second worker acquired the lock')


if __name__ == '__main__':
    unittest.main()
