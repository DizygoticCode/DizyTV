from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


class LinuxBuildTests(unittest.TestCase):
    def test_linux_bundle_uses_system_vlc_and_keeps_other_native_libraries(self):
        spec = Path(__file__).resolve().parents[1] / 'scripts' / 'linux.spec'
        self.assertTrue(spec.is_file(), 'Linux requires a build recipe that excludes system VLC')
        other = [('libother.so.1', '/usr/lib/libother.so.1', 'BINARY'),
                 ('vosk/libvosk.so', '/site-packages/vosk/libvosk.so', 'BINARY')]
        analysis = SimpleNamespace(
            binaries=[('libvlc.so.5', '/usr/lib/libvlc.so.5', 'BINARY'),
                      ('libvlccore.so.9', '/usr/lib/libvlccore.so.9', 'BINARY'),
                      ('libvlc.so.5.6.1', '/usr/lib/libvlc.so.5.6.1', 'BINARY'),
                      ('libvlccore.so', 'libvlccore.so.9', 'SYMLINK'), *other],
            pure=[], scripts=[], datas=[],
        )
        hooks = ModuleType('PyInstaller.utils.hooks')
        hooks.collect_data_files = lambda package: []
        hooks.collect_dynamic_libs = lambda package: []
        build = {
            'SPEC': str(spec),
            'Analysis': lambda *args, **kwargs: analysis,
            'PYZ': lambda pure: None,
            'EXE': lambda *args, **kwargs: None,
            'COLLECT': lambda exe, binaries, datas, **kwargs: binaries,
        }
        with patch.dict(sys.modules, {'PyInstaller.utils.hooks': hooks}), \
             patch.object(Path,'is_file',return_value=True):
            result = runpy.run_path(str(spec), init_globals=build)
        self.assertEqual(other, result['coll'])
        self.assertIn('dizytv.linux_ace_bootstrap',
                      spec.read_text(encoding='utf-8'))
        self.assertIn("outpace / 'outpace'", spec.read_text(encoding='utf-8'))
