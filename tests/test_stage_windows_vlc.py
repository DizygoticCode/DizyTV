import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.stage_windows_vlc import VERSION, stage_archive
from dizytv.native_vlc import configure_bundled_vlc


def make_zip(destination, outside=False, missing_plugin=False):
    root = "vlc-" + VERSION
    with zipfile.ZipFile(destination, "w") as archive:
        archive.writestr(root + "/libvlc.dll", b"libvlc")
        archive.writestr(root + "/libvlccore.dll", b"core")
        archive.writestr(root + "/COPYING.txt", b"VLC licence")
        if not missing_plugin:
            archive.writestr(root + "/plugins/demux/libdemux_plugin.dll", b"demux")
        archive.writestr(root + "/vlc.exe", b"not redistributed")
        if outside:
            archive.writestr(root + "/../bad.dll", b"unsafe")


class WindowsVlcStagingTests(unittest.TestCase):
    def test_only_libraries_plugins_and_notices_are_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "test.zip"
            destination = Path(tmp) / "runtime"
            make_zip(archive)
            stage_archive(archive, destination)
            self.assertEqual((destination / "libvlc.dll").read_bytes(), b"libvlc")
            self.assertTrue((destination / "plugins/demux/libdemux_plugin.dll").is_file())
            self.assertTrue((destination / "COPYING.txt").is_file())
            self.assertFalse((destination / "vlc.exe").exists())

    def test_archive_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "bad.zip"
            make_zip(archive, outside=True)
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                stage_archive(archive, Path(tmp) / "runtime")

    def test_missing_plugin_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "incomplete.zip"
            make_zip(archive, missing_plugin=True)
            with self.assertRaisesRegex(ValueError, "plugin"):
                stage_archive(archive, Path(tmp) / "runtime")

    def test_private_vlc_runtime_paths_are_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vlc"
            path.mkdir()
            (path / "libvlc.dll").write_bytes(b"test")
            (path / "libvlccore.dll").write_bytes(b"test")
            (path / "plugins").mkdir()
            with patch("dizytv.native_vlc.bundled_vlc_directory", return_value=path), \
                 patch("dizytv.native_vlc.sys.platform", "win32"), \
                 patch("dizytv.native_vlc.os.add_dll_directory", create=True), \
                 patch.dict("os.environ", {}, clear=True):
                self.assertTrue(configure_bundled_vlc())
                import os
                self.assertEqual(os.environ["PYTHON_VLC_LIB_PATH"], str((path / "libvlc.dll").resolve()))
                self.assertEqual(os.environ["VLC_PLUGIN_PATH"], str((path / "plugins").resolve()))
