import unittest
from unittest.mock import patch
from dizytv import engine


class EngineTests(unittest.TestCase):
    def test_running_engine_api_version_is_reported_distinct_from_stream_peers(self):
        from unittest.mock import Mock
        import io
        context=Mock()
        context.__enter__=Mock(return_value=io.BytesIO(b'{"result":{"version":"3.2.1"},"error":null}'))
        context.__exit__=Mock(return_value=None)
        with patch.object(engine,'urlopen',return_value=context):
            report=engine.engine_diagnostics('http://127.0.0.1:6878')
            self.assertIn('3.2.1',report)
            self.assertIn('not the stream',report)

    def test_parse_engine_endpoint(self):
        self.assertEqual(('127.0.0.1',6878),engine.engine_endpoint('http://127.0.0.1:6878'))
        with self.assertRaises(ValueError):
            engine.engine_endpoint('file:///C:/app')

    def test_already_running_engine_never_spawns_process(self):
        with patch.object(engine.sys,'platform','win32'), \
             patch.object(engine,'running',return_value=True), \
             patch.object(engine.subprocess,'Popen') as spawn:
            self.assertEqual('connected',engine.ensure_ready('http://127.0.0.1:6878'))
            spawn.assert_not_called()

    def test_missing_engine_gives_actionable_error(self):
        with patch.object(engine,'running',return_value=False),patch.object(engine.sys,'platform','win32'),patch.object(engine,'windows_engine_path',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'not detected'):
                engine.ensure_ready('http://127.0.0.1:6878')

    def test_explicit_engine_selection_rejects_unknown_executables(self):
        from pathlib import Path
        with patch.object(engine.sys,'platform','win32'),patch.object(Path,'is_file',return_value=True):
            with self.assertRaisesRegex(RuntimeError,'Selected Ace engine executable'):
                engine.windows_engine_path('C:/random/unrelated.exe')
            self.assertEqual(Path('C:/App/ace_engine.exe'),
                             engine.windows_engine_path('C:/App/ace_engine.exe'))

    def test_engine_uses_its_install_directory_as_working_directory(self):
        with patch.object(engine.sys,'platform','win32'),patch.object(engine,'windows_engine_path',return_value=__import__('pathlib').Path('C:/ACEStream/engine/ace_console.exe')),patch.object(engine,'running',side_effect=[False,True]),patch.object(engine.subprocess,'Popen') as spawn:
            self.assertEqual('started',engine.ensure_ready('http://127.0.0.1:6878'))
            self.assertEqual(__import__('os').path.normpath('C:/ACEStream/engine'),__import__('os').path.normpath(spawn.call_args.kwargs['cwd']))

    def test_remote_engine_never_autolaunches_local_process(self):
        with patch.object(engine,'running',return_value=False),patch.object(engine,'windows_engine_path') as path:
            with self.assertRaisesRegex(RuntimeError,'unreachable'):
                engine.ensure_ready('http://192.168.1.2:6878')
            path.assert_not_called()

    def test_linux_native_engine_prefers_installed_start_engine(self):
        from pathlib import Path
        with patch.object(engine.sys,'platform','linux'), \
             patch.object(engine.shutil,'which',return_value='/usr/local/bin/start-engine'), \
             patch.object(Path,'is_file',return_value=True), \
             patch.object(engine.os,'access',return_value=True):
            self.assertEqual(Path('/usr/local/bin/start-engine'),engine.linux_engine_path())
            with self.assertRaisesRegex(RuntimeError,'start-engine'):
                engine.linux_engine_path('/tmp/unsafe-script')

    def test_linux_launcher_starts_only_for_local_engine(self):
        from pathlib import Path
        with patch.object(engine.sys,'platform','linux'), \
             patch.object(engine,'running',side_effect=[False,False,True]), \
             patch('dizytv.outpace.api_ready',return_value=False), \
             patch('dizytv.outpace.packaged_binary',return_value=None), \
             patch.object(engine,'linux_engine_path',return_value=Path('/opt/acestream/start-engine')), \
             patch.object(engine.subprocess,'Popen') as spawn:
            self.assertEqual('started',engine.ensure_ready('http://127.0.0.1:6878'))
            spawn.assert_called_once()
            from pathlib import Path
            self.assertEqual('/opt/acestream/start-engine',
                             Path(spawn.call_args.args[0][0]).as_posix())
            self.assertEqual('--client-console',spawn.call_args.args[0][1])
            self.assertEqual('/opt/acestream',
                             Path(spawn.call_args.kwargs['cwd']).as_posix())

    def test_linux_package_prefers_outpace_but_respects_other_local_engine(self):
        from pathlib import Path
        from dizytv import outpace
        with patch.object(engine.sys,'platform','linux'), \
             patch.object(outpace,'api_ready',return_value=False), \
             patch.object(engine,'running',return_value=False), \
             patch.object(outpace,'packaged_binary',return_value=Path('/opt/dizytv/outpace')):
            with patch.object(outpace,'ensure_ready',return_value='started') as start:
                self.assertEqual('started',engine.ensure_ready('http://127.0.0.1:6878'))
                start.assert_called_once()
        with patch.object(engine.sys,'platform','linux'), \
             patch.object(outpace,'api_ready',return_value=False), \
             patch.object(engine,'running',return_value=True), \
             patch.object(outpace,'ensure_ready') as start:
            self.assertEqual('connected',engine.ensure_ready('http://127.0.0.1:6878'))
            start.assert_not_called()

    def test_linux_remote_engine_is_connect_only(self):
        with patch.object(engine.sys,'platform','linux'), \
             patch.object(engine,'running',return_value=False), \
             patch.object(engine,'linux_engine_path') as locate:
            with self.assertRaisesRegex(RuntimeError,'unreachable'):
                engine.ensure_ready('http://192.0.2.10:6878')
            locate.assert_not_called()

    def test_existing_engine_started_once(self):
        with patch.object(engine.sys,'platform','win32'),patch.object(engine,'windows_engine_path',return_value=__import__('pathlib').Path('C:/ACEStream/engine/ace_console.exe')),patch.object(engine,'running',side_effect=[False,False,True]),patch.object(engine.subprocess,'Popen') as spawn,patch.object(engine.time,'sleep'):
            self.assertEqual('started',engine.ensure_ready('http://127.0.0.1:6878',startup_seconds=5))
            spawn.assert_called_once()
            self.assertTrue(spawn.call_args.args[0][0].lower().endswith('ace_console.exe'))
