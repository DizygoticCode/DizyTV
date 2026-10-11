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

    def test_on_device_only_no_persistent_recordings(self):
        with tempfile.TemporaryDirectory() as root:
            session=RollingTimeshift('https://example.com/video.ts',root,session_id='bounded')
            session.window.append(PACKET*20,4)
            self.assertEqual(1,len(session.window.snapshot()))
            session.close()
            self.assertFalse((Path(root)/'session-bounded').exists())
