"""Locate a private, packaged VideoLAN libVLC before importing python-vlc.

Never install into the host VLC directory. A self-contained desktop package
should not pick up unrelated system DLLs when the bundled runtime exists.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

_dll_directory = None


def bundled_vlc_directory():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "vlc"


def configure_bundled_vlc():
    global _dll_directory
    folder = bundled_vlc_directory()
    if sys.platform == "win32":
        library = folder / "libvlc.dll"
        core = folder / "libvlccore.dll"
        plugins = folder / "plugins"
    elif sys.platform == "darwin":
        library = folder / "libvlc.dylib"
        core = folder / "libvlccore.dylib"
        plugins = folder / "plugins"
    else:
        return False  # Distro-managed VLC and its matching plugins on Linux.
    if not (library.is_file() and core.is_file() and plugins.is_dir()):
        return False
    os.environ["PYTHON_VLC_LIB_PATH"] = str(library.resolve())
    os.environ["PYTHON_VLC_MODULE_PATH"] = str(plugins.resolve())
    os.environ["VLC_PLUGIN_PATH"] = str(plugins.resolve())
    if sys.platform == "win32":
        folder_str = str(folder.resolve())
        os.environ["PATH"] = folder_str + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory") and _dll_directory is None:
            _dll_directory = os.add_dll_directory(folder_str)
    return True
