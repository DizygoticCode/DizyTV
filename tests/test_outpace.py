"""Native Outpace integration tests without requiring a Mac, swarm or network."""
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dizytv import engine, outpace, core  # Load zoneinfo/sysconfig before mocked OS platform


CID = '0123456789abcdef0123456789abcdef01234567'


class OutpaceTests(unittest.TestCase):
    def setUp(self):
        self.previous_owned=outpace._OWNED_PROCESS
        self.previous_shutdown=outpace._SHUTTING_DOWN
        self.previous_identity=outpace._OWNED_IDENTITY
        self.previous_binary=outpace._OWNED_BINARY
        outpace._OWNED_PROCESS=None
        outpace._SHUTTING_DOWN=False
        outpace._OWNED_IDENTITY=None
        outpace._OWNED_BINARY=None

    def tearDown(self):
        outpace._OWNED_PROCESS=self.previous_owned
        outpace._SHUTTING_DOWN=self.previous_shutdown
        outpace._OWNED_IDENTITY=self.previous_identity
        outpace._OWNED_BINARY=self.previous_binary

    def test_close_does_not_touch_external_engine_or_active_recording(self):
        self.assertFalse(outpace.stop_owned_daemon())
        # Re-enable the test fixture after the first shutdown.
        outpace._SHUTTING_DOWN=False
        owned=Mock()
        owned.poll.return_value=None
        outpace._OWNED_PROCESS=owned
        self.assertFalse(outpace.stop_owned_daemon(preserve_recordings=True))
        owned.terminate.assert_not_called()
        self.assertIs(outpace._OWNED_PROCESS,owned)
        outpace._SHUTTING_DOWN=False
        self.assertTrue(outpace.stop_owned_daemon())
        owned.terminate.assert_called_once()
        self.assertIsNone(outpace._OWNED_PROCESS)
        with self.assertRaisesRegex(RuntimeError,'closing'):
            outpace.ensure_ready('http://127.0.0.1:6878')

    def test_recorder_can_stop_owned_helper_and_start_later_timers(self):
        owned=Mock()
        owned.poll.return_value=None
        outpace._OWNED_PROCESS=owned
        outpace._SHUTTING_DOWN=False
        self.assertTrue(outpace.stop_owned_daemon(allow_restart=True))
        owned.terminate.assert_called_once()
        self.assertFalse(outpace._SHUTTING_DOWN)
        self.assertIsNone(outpace._OWNED_PROCESS)

    def test_native_sessions_prevent_killing_worker_owned_helper(self):
        class Response:
            status=200
            def __init__(self,body):
                self.content=io.BytesIO(body)
            def __enter__(self): return self
            def __exit__(self,*args): return None
            def read(self,n): return self.content.read(n)
        process=Mock()
        process.poll.return_value=None
        outpace._OWNED_PROCESS=process
        # A currently playing user/recording means the helper stays alive.
        with patch.object(outpace,'urlopen',return_value=Response(
                b'{"streams":[{"network":"ace","id":"cid:abc","clients":1}]}')):
            self.assertFalse(outpace.stop_idle_owned_daemon())
            process.terminate.assert_not_called()
        # An unavailable API is not proof it is safe to kill a daemon.
        with patch.object(outpace,'urlopen',side_effect=OSError('not reachable')):
            self.assertFalse(outpace.stop_idle_owned_daemon())
            process.terminate.assert_not_called()
        # Once all shared streams are released, this process may release
        # its own child without preventing the next queued timer restart.
        with patch.object(outpace,'urlopen',return_value=Response(b'{"streams":[]}')):
            self.assertTrue(outpace.stop_idle_owned_daemon())
        process.terminate.assert_called_once()
        self.assertIsNone(outpace._OWNED_PROCESS)
        self.assertFalse(outpace._SHUTTING_DOWN)


    def test_gui_handoff_reaps_only_same_verified_idle_process(self):
        """The detached recorder may clean up its former GUI's exact helper."""
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): return None
            def read(self,n): return b'{"streams":[]}'
        with tempfile.TemporaryDirectory() as folder:
            owned=Mock()
            owned.pid=24321
            owned.poll.return_value=None
            outpace._OWNED_PROCESS=owned
            outpace._OWNED_BINARY='/private/DizyTV/outpace/outpace'
            outpace._OWNED_IDENTITY='b'*64
            self.assertTrue(outpace.handoff_owned_daemon(folder))
            marker=Path(folder)/'outpace-handoff.json'
            self.assertTrue(marker.exists())
            self.assertTrue(outpace._SHUTTING_DOWN)
            data=json.loads(marker.read_text())
            self.assertEqual(24321,data['pid'])
            self.assertEqual(outpace._OWNED_BINARY,data['binary'])
            current={'channels':[{'id':'a'*40,'stream':'acestream://'+'b'*40}],
                     'jobs':[{'status':'recording','channel_id':'a'*40,
                              'start':100,'end':9999999999}]}
            with patch.object(outpace,'_process_identity',return_value='b'*64), \\
                 patch('dizytv.storage.Store') as store, \\
                 patch.object(outpace,'urlopen',return_value=Response()), \\
                 patch.object(outpace.os,'kill') as terminate:
                store.return_value.try_read.return_value=current
                self.assertFalse(outpace.reap_handed_off_daemon(folder))
                terminate.assert_not_called()
                self.assertTrue(marker.exists())
                # Once the Ace timer and API sessions are idle, terminate the
                # verified former GUI child exactly once.
                current['jobs']=[]
                self.assertTrue(outpace.reap_handed_off_daemon(folder))
                terminate.assert_called_once_with(24321,outpace.signal.SIGTERM)
                self.assertFalse(marker.exists())

    def test_handoff_rejects_recycled_pid_and_active_native_sessions(self):
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): return None
            def read(self,n): return b'{"streams":[{"clients":1}]}'
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/'outpace-handoff.json'
            marker.write_text(json.dumps({'pid':24321,'binary':'/private/outpace',
                                          'identity':'b'*64}))
            with patch.object(outpace,'_process_identity',return_value='c'*64), \\
                 patch.object(outpace.os,'kill') as terminate:
                self.assertFalse(outpace.reap_handed_off_daemon(folder))
                terminate.assert_not_called()
                self.assertFalse(marker.exists())
            marker.write_text(json.dumps({'pid':24321,'binary':'/private/outpace',
                                          'identity':'b'*64}))
            with patch.object(outpace,'_process_identity',return_value='b'*64), \\
                 patch('dizytv.storage.Store') as store, \\
                 patch.object(outpace,'urlopen',return_value=Response()), \\
                 patch.object(outpace.os,'kill') as terminate:
                store.return_value.try_read.return_value={'jobs':[],'channels':[]}
                self.assertFalse(outpace.reap_handed_off_daemon(folder))
                terminate.assert_not_called()
                self.assertTrue(marker.exists())

    def test_mac_packaged_path_only_and_original_name(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            binary = root / 'outpace' / 'outpace'
            binary.parent.mkdir()
            binary.write_text('fixture')
            binary.chmod(0o755)
            with patch.object(outpace.sys, 'platform', 'darwin'), patch.object(
                outpace.sys, '_MEIPASS', root, create=True
            ):
                self.assertEqual(binary, outpace.packaged_binary())
            with patch.object(outpace.sys, 'platform', 'win32'), patch.object(
                outpace.sys, '_MEIPASS', root, create=True
            ):
                self.assertIsNone(outpace.packaged_binary())

    def test_linux_bundled_native_binary_without_mac_requirement(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            helper=root/'outpace'/'outpace'
            helper.parent.mkdir()
            helper.write_bytes(b'fixture')
            helper.chmod(0o755)
            with patch.object(outpace.sys,'platform','linux'), patch.object(
                outpace.sys,'_MEIPASS',root,create=True):
                self.assertEqual(helper,outpace.packaged_binary())

    def test_reject_remote_or_nonloopback_urls_before_executing(self):
        for url in ('https://127.0.0.1:6878', 'http://192.168.1.3:6878',
                    'http://127.0.0.1:6879', 'http://user:password@localhost:6878',
                    'http://127.0.0.1:6878/path', 'http://127.0.0.1:6878/?token=x'):
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                outpace.local_api_address(url)
        self.assertEqual('http://127.0.0.1:6878',
                         outpace.local_api_address('http://localhost:6878'))

    def test_native_playback_links_only_for_recognised_content(self):
        url=outpace.playback_url('acestream://'+CID,'http://127.0.0.1:6878')
        self.assertEqual('http://127.0.0.1:6878/streams/ace/cid:'+CID,url)
        alt=outpace.playback_url('acestream:?infohash='+CID,'http://127.0.0.1:6878')
        self.assertEqual('http://127.0.0.1:6878/streams/ace/'+CID,alt)
        with self.assertRaises(RuntimeError):
            outpace.playback_url('https://example.com/not-an-ace-stream', 'http://127.0.0.1:6878')

    def test_health_check_requires_both_supported_native_routes(self):
        class Response:
            status=200
            def __init__(self, data):self.payload=io.BytesIO(data)
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return self.payload.read(n)
        with patch.object(outpace,'urlopen',side_effect=[
            Response(b'ok'),Response(b'{"networks":["ace"]}')]):
            self.assertTrue(outpace.api_ready('http://127.0.0.1:6878'))
        with patch.object(outpace,'urlopen',side_effect=[
            Response(b'ok'),Response(b'{"networks":["other"]}')]):
            self.assertFalse(outpace.api_ready('http://127.0.0.1:6878'))

    def test_start_bundled_helper_only_after_safety_checks(self):
        process=Mock()
        process.poll.return_value=None
        with patch.object(outpace,'packaged_binary',return_value=Path('/Applications/DizyTV.app/outpace/outpace')), \
             patch.object(outpace,'api_ready',side_effect=[False,True]), \
             patch.object(outpace.socket,'create_connection',side_effect=ConnectionRefusedError), \
             patch.object(outpace.subprocess,'Popen',return_value=process) as spawn, \
             patch.object(outpace.time,'sleep'):
            self.assertEqual('started',outpace.ensure_ready('http://127.0.0.1:6878'))
        args=spawn.call_args.args[0]
        self.assertEqual('serve',args[1])
        env=spawn.call_args.kwargs['env']
        self.assertEqual('127.0.0.1:6878',env['OUTPACE_BIND'])
        self.assertEqual('0',env['OUTPACE_ENABLE_INBOUND'])
        self.assertEqual('0',env['OUTPACE_ENABLE_PORT_MAPPING'])
        self.assertEqual('0',env['OUTPACE_EXPERIMENTAL_ACE_COMPAT'])

    def test_occupied_local_port_never_launches_another_daemon(self):
        with patch.object(outpace,'api_ready',return_value=False), \
             patch.object(outpace.socket,'create_connection') as connect, \
             patch.object(outpace.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'owns port'):
                outpace.ensure_ready('http://127.0.0.1:6878')
            connect.assert_called_once()
            spawn.assert_not_called()

    def test_engine_mac_uses_native_api_not_experimental_ace_json(self):
        with patch.object(engine.sys,'platform','darwin'), \
             patch.object(outpace,'api_ready',return_value=True), \
             patch.object(engine,'urlopen') as legacy_json:
            address='http://127.0.0.1:6878'
            url=engine.start_playback_session('acestream://'+CID,address)
            self.assertEqual('http://127.0.0.1:6878/streams/ace/cid:'+CID,url)
            legacy_json.assert_not_called()
            self.assertIn('Outpace',engine.engine_diagnostics(address))

    def test_engine_mac_auto_start_and_remote_fallback(self):
        with patch.object(engine.sys,'platform','darwin'), \
             patch.object(outpace,'ensure_ready',return_value='started') as start:
            self.assertEqual('started',engine.ensure_ready('http://127.0.0.1:6878'))
            start.assert_called_once()
        with patch.object(engine.sys,'platform','darwin'), \
             patch.object(outpace,'ensure_ready') as start, \
             patch.object(engine,'running',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'unreachable'):
                engine.ensure_ready('http://192.0.2.1:6878')
            start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
