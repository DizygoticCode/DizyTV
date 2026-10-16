"""Deterministic rolling buffer tests: bounded storage, playlists and local serving."""
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from dizytv.timeshift import MAX_SEGMENT_BYTES, RollingWindow, RollingTimeshift, parse_hls

PACKET = bytes([0x47]) + bytes(187)


class TestTimeshift(unittest.TestCase):
    def test_buffer_eviction_by_time_and_size(self):
        now=[1000.]
        with tempfile.TemporaryDirectory() as path:
            w=RollingWindow(path, minutes=1,max_bytes=256*1024**2,
                            clock=lambda:now[0],free=lambda:1024**4)
            a=w.append(PACKET*10,4)
            now[0]+=30
            b=w.append(PACKET*10,4)
            now[0]+=31
            c=w.append(PACKET*10,4)
            self.assertEqual([b.seq,c.seq],[x.seq for x in w.snapshot()])
            self.assertFalse(a.path.exists())
            self.assertIn('#EXT-X-MEDIA-SEQUENCE:1',w.playlist(from_seq=b.seq))
            self.assertNotIn('#EXT-X-ENDLIST',w.playlist())
            self.assertIn('s/2.ts',w.playlist())
            w.close()
            self.assertFalse(c.path.exists())

    def test_live_playlist_keeps_multiple_segments_for_vlc_buffering(self):
        with tempfile.TemporaryDirectory() as root:
            w=RollingWindow(root,free=lambda:1024**4)
            for i in range(15):
                w.append(PACKET*100,4)
            manifest=w.playlist()
            self.assertIn('#EXT-X-MEDIA-SEQUENCE:3',manifest)
            self.assertEqual(12,manifest.count('#EXTINF:'))
            w.close()

    def test_moving_holdback_excludes_new_segments_and_catches_up_continuously(self):
        with tempfile.TemporaryDirectory() as root:
            window=RollingWindow(root,free=lambda:1024**4)
            for _ in range(5):
                window.append(PACKET*10,4)
            held=window.playlist(holdback_seconds=5)
            self.assertIn('s/2.ts',held)
            self.assertNotIn('s/3.ts',held)
            self.assertNotIn('s/4.ts',held)
            self.assertEqual(3,held.count('#EXTINF:'))
            window.append(PACKET*10,4)
            # A new cached segment advances the held-back edge by one piece:
            # it doesn't accidentally rewind from an old fixed seq.
            later=window.playlist(holdback_seconds=5)
            self.assertIn('s/3.ts',later)
            self.assertNotIn('s/4.ts',later)
            self.assertNotIn('s/5.ts',later)
            self.assertEqual('',window.playlist(holdback_seconds=30))
            with self.assertRaises(ValueError):
                window.playlist(holdback_seconds=-1)
            window.close()

    def test_holdback_has_stable_playable_segments_during_short_origin_stall(self):
        # Broadcaster temporarily stops publishing new HLS segments. The local
        # playlist must keep advertising already-cached ones, not expose the
        # still-newest (possibly unavailable) source edge or become empty.
        with tempfile.TemporaryDirectory() as root:
            window=RollingWindow(root,free=lambda:1024**4)
            for _ in range(6):
                window.append(PACKET*10,4)
            initial=window.playlist(holdback_seconds=8)
            self.assertEqual(4,initial.count('#EXTINF:'))
            self.assertNotIn('s/4.ts',initial)
            self.assertNotIn('s/5.ts',initial)
            self.assertEqual(initial,window.playlist(holdback_seconds=8))
            window.append(PACKET*10,4)  # Origin resumes after short stall.
            resumed=window.playlist(holdback_seconds=8)
            self.assertIn('s/4.ts',resumed)
            self.assertNotIn('s/5.ts',resumed)
            self.assertNotIn('s/6.ts',resumed)
            window.close()

    def test_holdback_loopback_url_enforces_bounded_delay_and_no_public_access(self):
        from http.server import ThreadingHTTPServer
        from threading import Thread
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/channel.ts',root,
                                     session_id='holdback-token')
            for _ in range(6):
                session.window.append(PACKET*10,4)
            session._server=ThreadingHTTPServer(('127.0.0.1',0),session._handler())
            Thread(target=session._server.serve_forever,daemon=True).start()
            try:
                with urlopen(session.holdback_url(5)) as response:
                    manifest=response.read().decode()
                self.assertIn('s/3.ts',manifest)
                self.assertNotIn('s/4.ts',manifest)
                with self.assertRaises(Exception):
                    urlopen(session.base_url+'holdback.m3u8?ms=50001')
                with self.assertRaises(ValueError):
                    session.holdback_url(31)
            finally:
                session.close()

    def test_start_delayed_uses_reused_buffer_not_second_capture_engine(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/channel.ts',root,
                                     session_id='holdback-start')
            try:
                with patch.object(session,'start',return_value='http://127.0.0.1/live.m3u8') as start, \
                     patch.object(session.window,'holdback_entries',return_value=[object()]*3), \
                     patch.object(session,'holdback_url',return_value='http://127.0.0.1/holdback.m3u8') as held:
                    self.assertEqual('http://127.0.0.1/holdback.m3u8',session.start_delayed(5))
                    start.assert_called_once()
                    held.assert_called_once_with(5)
            finally:
                session.close()

    def test_holdback_requires_real_playable_fragments_for_long_segments(self):
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/channel.ts',root,
                                     session_id='long-segment-holdback')
            # One 10s segment is > 1s desired holdback, but it is removed
            # wholesale from the live edge: there is NO playable video yet.
            session.window.append(PACKET*10,10)
            self.assertEqual([],session.window.holdback_entries(1))
            session.window.append(PACKET*10,10)
            self.assertEqual(1,len(session.window.holdback_entries(1)))
            session.window.append(PACKET*10,10)
            self.assertEqual(2,len(session.window.holdback_entries(1)))
            session.window.append(PACKET*10,10)
            self.assertEqual(3,len(session.window.holdback_entries(1)))
            try:
                with patch.object(session,'start',return_value='http://127.0.0.1/live.m3u8'), \
                     patch.object(session,'holdback_url',
                                  return_value='http://127.0.0.1/holdback.m3u8?ms=1000') as holdback:
                    self.assertIn('holdback.m3u8',session.start_delayed(1))
                    holdback.assert_called_once_with(1)
            finally:
                session.close()

    def test_timeshift_cleanup_does_not_wait_on_gui_thread(self):
        from threading import Event
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/channel.ts',root,
                                     session_id='async-shutdown')
            cleanup_entered=Event()
            allow_cleanup=Event()
            cleanup_finished=Event()
            original_close=session.close
            def slow_cleanup():
                cleanup_entered.set()
                allow_cleanup.wait(2)
                try:
                    original_close()
                finally:
                    cleanup_finished.set()
            with patch.object(session,'close',side_effect=slow_cleanup):
                try:
                    session.close_async()  # Must return before background IO ends.
                    self.assertTrue(session.stop_event.is_set())
                    self.assertTrue(session.ready.is_set())
                    self.assertTrue(cleanup_entered.wait(1))
                    self.assertFalse(allow_cleanup.is_set())
                finally:
                    allow_cleanup.set()
            self.assertTrue(cleanup_finished.wait(3))
            # The normal cleanup entry point remains safe/idempotent.
            original_close()
            self.assertFalse(session.window.directory.exists())

    def test_closing_server_before_serving_never_calls_shutdown_deadlock(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/channel.ts',root,
                                     session_id='pre-server-thread')
            server=Mock()
            session._server=server
            session._server_thread=None  # Startup interrupted pre-serve_forever.
            session.close()
            server.server_close.assert_called_once()
            server.shutdown.assert_not_called()
            session.close()  # Concurrent/late cleanup is harmless.
            self.assertTrue(session.stop_event.is_set())

    def test_socket_created_during_close_is_not_leaked(self):
        """A rapid channel switch can cancel HTTP server construction itself."""
        from threading import Event, Thread
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/live.ts',root,
                                     session_id='concurrent-socket-close')
            creating=Event()
            allow_create=Event()
            server=Mock()
            errors=[]
            def slow_server(*args,**kwargs):
                creating.set()
                if not allow_create.wait(3):
                    raise RuntimeError('socket creation test timed out')
                return server
            def start():
                try:session.start(timeout=0.1)
                except RuntimeError as exc:errors.append(str(exc))
            try:
                with patch('dizytv.timeshift.ThreadingHTTPServer',side_effect=slow_server):
                    starter=Thread(target=start,daemon=True)
                    starter.start()
                    self.assertTrue(creating.wait(2))
                    session.close_async()
                    self.assertTrue(session.stop_event.is_set())
                    allow_create.set()
                    starter.join(timeout=3)
                    self.assertFalse(starter.is_alive())
                # Cleanup runs on a separate thread, but is guaranteed to
                # close the socket created after cancellation, never leak it.
                limit=time.monotonic()+3
                while server.server_close.call_count==0 and time.monotonic()<limit:
                    time.sleep(.02)
                server.server_close.assert_called_once_with()
                self.assertTrue(errors)
                self.assertFalse(session._capture_thread is not None and
                                 session._capture_thread.is_alive())
            finally:
                allow_create.set()
                session.close()

    def test_closed_timeshift_rejects_late_capture_start(self):
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/channel.ts',root,
                                     session_id='preclosed')
            session.close()
            with self.assertRaisesRegex(RuntimeError,'already closed'):
                session.start(timeout=0.1)

    def test_free_space_reserve_blocks_more_data(self):
        with tempfile.TemporaryDirectory() as path:
            w=RollingWindow(path, free=lambda:1024, reserve_bytes=1024**3)
            with self.assertRaisesRegex(OSError,'reserve'):
                w.append(PACKET,1)
            w.close()

    def test_size_duration_boundaries(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(ValueError):
                RollingWindow(path,minutes=241)
            with self.assertRaises(ValueError):
                RollingWindow(path,max_bytes=33*1024**3)
            w=RollingWindow(path,free=lambda:1024**4)
            with self.assertRaises(ValueError):
                w.append(b'',4)
            with self.assertRaises(ValueError):
                w.append(b'x'*(MAX_SEGMENT_BYTES+1),4)
            w.close()

    def test_manifest_and_segments_reachable_only_with_token(self):
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/channel.ts',root,session_id='test-token')
            session.window.append(PACKET*10,4)
            session._server=__import__('http.server',fromlist=['ThreadingHTTPServer']).ThreadingHTTPServer(('127.0.0.1',0),session._handler())
            try:
                worker=__import__('threading').Thread(target=session._server.serve_forever,daemon=True)
                worker.start()
                with urlopen(session.live_url()) as res:
                    manifest=res.read().decode()
                self.assertIn('#EXTM3U',manifest)
                with urlopen(session.base_url+'s/0.ts') as res:
                    self.assertEqual(PACKET*10,res.read())
                with self.assertRaises(Exception):
                    urlopen(session.base_url.replace('/test-token/','/wrong-token/')+'live.m3u8')
                with urlopen(session.replay_url(30)) as res:
                    self.assertIn('EXT-X-START',res.read().decode())
            finally:
                session.close()

    def test_hls_parser_rejects_encryption_and_fmp4(self):
        kind,urls=parse_hls('#EXTM3U\n#EXTINF:4,\na.ts\n', 'https://example.com/live/playlist.m3u8')
        self.assertEqual('segments',kind)
        self.assertEqual('https://example.com/live/a.ts',urls[0][0])
        with self.assertRaisesRegex(ValueError,'encrypted'):
            parse_hls('#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key"\n#EXTINF:4,\na.ts','https://example.com')
        with self.assertRaisesRegex(ValueError,'Fragmented'):
            parse_hls('#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:4,\na.m4s','https://example.com')

    def test_actual_clear_hls_ingest_replay_and_local_cleanup(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        class Origin(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path=='/live.m3u8':
                    payload=b'#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:1\n#EXTINF:4,\n/one.ts\n'
                    mime='application/vnd.apple.mpegurl'
                elif self.path=='/one.ts':
                    payload=PACKET*100
                    mime='video/mp2t'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type',mime)
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self,*_):
                pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Origin)
        Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as root:
                session=RollingTimeshift('http://127.0.0.1:'+str(server.server_port)+'/live.m3u8',
                                         root,session_id='hls-test')
                live=session.start(timeout=5)
                with urlopen(live) as response:
                    self.assertIn('s/0.ts',response.read().decode())
                self.assertGreater(session.window.latest_seconds(),0)
                with urlopen(session.replay_url(30)) as response:
                    self.assertIn('EXT-X-START',response.read().decode())
                session.close()
                self.assertFalse((Path(root)/'session-hls-test').exists())
        finally:
            server.shutdown()
            server.server_close()

    def test_real_direct_ts_short_http_response_still_enters_buffer(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        class Origin(BaseHTTPRequestHandler):
            def do_GET(self):
                payload=PACKET*100
                self.send_response(200)
                self.send_header('Content-Type','video/mp2t')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self,*_):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Origin)
        Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as root:
                session=RollingTimeshift('http://127.0.0.1:'+str(server.server_port)+'/live.ts',
                                         root,session_id='ts-test')
                self.assertIn('/live.m3u8',session.start(timeout=5))
                self.assertTrue(session.window.snapshot())
                session.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_quota_evicts_oldest_without_touching_unrelated_files(self):
        with tempfile.TemporaryDirectory() as root:
            other=Path(root)/'keep-me.txt'
            other.write_text('user file',encoding='utf-8')
            w=RollingWindow(Path(root)/'session',free=lambda:1024**4)
            w.max_bytes=len(PACKET)*12
            a=w.append(PACKET*10,4)
            b=w.append(PACKET*10,4)
            self.assertFalse(a.path.exists())
            self.assertEqual([b.seq],[p.seq for p in w.snapshot()])
            w.close()
            self.assertEqual('user file',other.read_text(encoding='utf-8'))

    def test_crash_cleanup_only_removes_older_timeshift_segments(self):
        import os
        import time
        with tempfile.TemporaryDirectory() as root:
            cache=Path(root)/'cache'
            stale=cache/'session-old'
            stale.mkdir(parents=True)
            orphan=stale/'000000000000.ts'
            orphan.write_bytes(PACKET)
            os.utime(stale,(time.time()-90000,time.time()-90000))
            unrelated=cache/'my-recording.ts'
            unrelated.write_bytes(PACKET)
            session=RollingTimeshift('https://example.com/a.ts',cache,session_id='new-session')
            self.assertFalse(orphan.exists())
            self.assertTrue(unrelated.exists())
            session.close()

    def test_on_device_only_no_persistent_recordings(self):
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/video.ts',root,session_id='bounded')
            session.window.append(PACKET*20,4)
            self.assertEqual(1,len(session.window.snapshot()))
            session.close()
            self.assertFalse((Path(root)/'session-bounded').exists())
