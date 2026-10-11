import unittest
from unittest.mock import patch
from dizytv import engine


class EngineTests(unittest.TestCase):
    def test_parse_engine_endpoint(self):
        self.assertEqual(('127.0.0.1',6878),engine.engine_endpoint('http://127.0.0.1:6878'))
        with self.assertRaises(ValueError):
            engine.engine_endpoint('file:///C:/app')

    def test_already_running_engine_never_spawns_process(self):
        with patch.object(engine,'running',return_value=True),patch.object(engine.subprocess,'Popen') as spawn:
            self.assertEqual('connected',engine.ensure_ready('http://127.0.0.1:6878'))
            spawn.assert_not_called()

    def test_missing_engine_gives_actionable_error(self):
        with patch.object(engine,'running',return_value=False),patch.object(engine.sys,'platform','win32'),patch.object(engine,'windows_engine_path',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'not installed'):
                engine.ensure_ready('http://127.0.0.1:6878')

    def test_remote_engine_never_autolaunches_local_process(self):
        with patch.object(engine,'running',return_value=False),patch.object(engine,'windows_engine_path') as path:
            with self.assertRaisesRegex(RuntimeError,'unreachable'):
                engine.ensure_ready('http://192.168.1.2:6878')
            path.assert_not_called()

    def test_existing_engine_started_once(self):
        with patch.object(engine.sys,'platform','win32'),patch.object(engine,'windows_engine_path',return_value=__import__('pathlib').Path('C:/ACEStream/engine/ace_console.exe')),patch.object(engine,'running',side_effect=[False,False,True]),patch.object(engine.subprocess,'Popen') as spawn,patch.object(engine.time,'sleep'):
            self.assertEqual('started',engine.ensure_ready('http://127.0.0.1:6878',startup_seconds=5))
            spawn.assert_called_once()
            self.assertEqual('ace_console.exe',spawn.call_args.args[0][0].split('/')[-1])
