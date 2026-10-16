import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from dizytv.media_runtime import configure_private_vlc, runtime_paths
from scripts.stage_private_vlc import ARCHIVES, fetch_pinned, stage_windows_zip


class PrivateVLCTests(unittest.TestCase):
    def test_windows_runtime_prefers_package_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'vlc'/'plugins').mkdir(parents=True)
            (root/'vlc'/'libvlc.dll').write_bytes(b'fixture')
            with patch.dict(os.environ, {}, clear=False):
                dll, plugins=runtime_paths(root, 'win32')
                self.assertEqual(dll,root/'vlc'/'libvlc.dll')
                self.assertEqual(plugins,root/'vlc'/'plugins')
                # Mock os.add_dll_directory even when executing on Linux.
                with patch('dizytv.media_runtime.os.add_dll_directory',create=True):
                    configure_private_vlc(root,'win32')
                self.assertEqual(os.environ['PYTHON_VLC_LIB_PATH'],str(dll))
                self.assertEqual(os.environ['VLC_PLUGIN_PATH'],str(plugins))

    def test_broken_private_windows_runtime_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError,'incomplete'):
                runtime_paths(Path(folder),'win32')

    def test_mac_runtime_points_to_nested_original_VLC_app(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            lib=root/'vlc'/'VLC.app'/'Contents'/'MacOS'/'lib'
            lib.mkdir(parents=True)
            (lib/'libvlc.dylib').write_bytes(b'fixture')
            plugins=lib.parent/'plugins'
            plugins.mkdir()
            self.assertEqual(runtime_paths(root,'darwin'),(lib/'libvlc.dylib',plugins))

    def test_staging_unmodified_module_layout_and_reject_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            archive=root/'vlc.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('vlc-3.0.24/libvlc.dll',b'libvlc')
                z.writestr('vlc-3.0.24/libvlccore.dll',b'vlccore')
                z.writestr('vlc-3.0.24/plugins/codec/codec.dll',b'module')
                z.writestr('vlc-3.0.24/COPYING.txt',b'licence')
                z.writestr('vlc-3.0.24/lua/http/index.html',b'unneeded GUI')
                z.writestr('vlc-3.0.24/plugins/plugins.dat',b'plugin cache')
            stage_windows_zip(archive,root/'install')
            self.assertTrue((root/'install'/'plugins'/'codec'/'codec.dll').exists())
            self.assertTrue((root/'install'/'COPYING.txt').exists())
            self.assertTrue((root/'install'/'plugins'/'plugins.dat').exists())
            self.assertFalse((root/'install'/'lua'/'http'/'index.html').exists())
            with zipfile.ZipFile(archive,'a') as z:
                z.writestr('vlc-3.0.24/../bad.txt',b'bad')
            with self.assertRaisesRegex(RuntimeError,'Unsafe'):
                stage_windows_zip(archive,root/'invalid')

    def test_vlc_release_is_security_current_and_mac_both_architectures(self):
        from scripts.stage_private_vlc import VERSION
        self.assertEqual("3.0.24",VERSION)
        self.assertEqual(ARCHIVES["macos-arm64"][:2],ARCHIVES["macos-x86_64"][:2])
        self.assertIn("universal",ARCHIVES["macos-arm64"][0])

    def test_wrong_digest_refuses_download_before_install(self):
        class Fake:
            def __init__(self):self.fp=io.BytesIO(b'not official archive')
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def geturl(self):return ARCHIVES['windows-x64'][0]
            def read(self,n):return self.fp.read(n)
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'bad.zip'
            with self.assertRaisesRegex(RuntimeError,'SHA-256 mismatch'):
                fetch_pinned('windows-x64',target,opener=lambda *args,**kwargs:Fake())
            self.assertFalse(target.exists())
