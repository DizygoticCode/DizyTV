"""Package-private libVLC selection, before any Python vlc binding import."""
from __future__ import annotations
import os
from pathlib import Path
import sys

def runtime_paths(bundle=None, platform=None):
    root = Path(bundle) if bundle is not None else Path(getattr(sys, "_MEIPASS", ""))
    plat = platform or sys.platform
    # No system VLC override while running from source.
    if bundle is None and not hasattr(sys, "_MEIPASS"):
        return None
    if plat == "win32":
        folder = root / "vlc"
        dll = folder / "libvlc.dll"
        modules = folder / "plugins"
    elif plat == "darwin":
        # Media-only VLC 3.0.24 runtime, not a nested full VLC.app.
        folder = root / "vlc" / "lib"
        dll = folder / "libvlc.dylib"
        modules = root / "vlc" / "plugins"
    else:
        return None
    if not dll.is_file() or not modules.is_dir():
        raise RuntimeError("DizyTV bundled VLC runtime is incomplete; reinstall a verified package")
    return dll, modules

def configure_private_vlc(bundle=None, platform=None):
    paths = runtime_paths(bundle, platform)
    if paths is None:
        return None
    dll, modules = paths
    os.environ["PYTHON_VLC_LIB_PATH"] = str(dll)
    os.environ["PYTHON_VLC_MODULE_PATH"] = str(modules)
    os.environ["VLC_PLUGIN_PATH"] = str(modules)
    if (platform or sys.platform) == "win32":
        # Keep the handle alive for all libVLC module loads, not only import.
        if hasattr(os, "add_dll_directory"):
            global _WINDOWS_DLL_HANDLE
            _WINDOWS_DLL_HANDLE = os.add_dll_directory(str(dll.parent))
        os.environ["PATH"] = str(dll.parent) + os.pathsep + os.environ.get("PATH", "")
    return paths
