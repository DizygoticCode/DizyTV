"""Stage an unmodified, hash-verified VideoLAN VLC 3 runtime for DizyTV.

The user installer must work without pre-installed VLC. Download only on CI,
never at first run or from a user-supplied playlist. Keep the exact upstream
copyright/licence files and plugins with the runtime. Public distribution
requires reviewing VideoLAN's module-specific corresponding-source obligations.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "vendor" / "vlc"
VERSION = "3.0.21"
BASE = "https://download.videolan.org/pub/videolan/vlc/3.0.21"
ARCHIVES = {
    "windows-x64": (
        BASE + "/win64/vlc-3.0.21-win64.zip",
        "a0b7ec02b50adf6417eed014fb8df50af39690505a4225b85b3dc2ed17d14843",
        100 * 1024 * 1024,
    ),
    "macos-arm64": (
        BASE + "/macosx/vlc-3.0.21-arm64.dmg",
        "15dd65bf6489da9ec6a67f5585c74c40a58993acff41a82958a916dd74178044",
        80 * 1024 * 1024,
    ),
    "macos-x86_64": (
        BASE + "/macosx/vlc-3.0.21-intel64.dmg",
        "d431fd051c3dc7af02bd313c6d05d90cf604b70ed3ec5bba6fd4c49ef3e638d9",
        80 * 1024 * 1024,
    ),
}

def fetch_pinned(target, destination, opener=urlopen):
    url, expected, limit = ARCHIVES[target]
    request = __import__("urllib.request", fromlist=["Request"]).Request(
        url, headers={"User-Agent": "DizyTV-build/0.1"})
    digest = hashlib.sha256()
    count = 0
    with opener(request, timeout=100) as source, destination.open("wb") as output:
        final = source.geturl()
        if final != url and not final.startswith("https://"):
            raise RuntimeError("VLC download redirected to an insecure origin")
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            count += len(block)
            if count > limit:
                raise RuntimeError("VLC archive exceeded size limit")
            digest.update(block)
            output.write(block)
    if digest.hexdigest() != expected:
        destination.unlink(missing_ok=True)
        raise RuntimeError("VLC archive SHA-256 mismatch for " + target)

def stage_windows_zip(archive, destination):
    # Preserve original layout and licence notices, not just a stripped DLL.
    with zipfile.ZipFile(archive) as packed:
        info = packed.infolist()
        if len(info) > 2500 or sum(x.file_size for x in info) > 400 * 1024 * 1024:
            raise RuntimeError("Unexpected VLC archive size")
        for entry in info:
            name = PurePosixPath(entry.filename.replace("\\", "/"))
            parts = name.parts
            if (not parts or parts[0] != "vlc-3.0.21"
                    or any(p in ("", ".", "..") for p in parts)
                    or name.is_absolute()):
                raise RuntimeError("Unsafe VLC archive member")
            # Reject symlinks from any unexpected replacement archive.
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError("VLC archive link not allowed")
            if entry.is_dir():
                continue
            relative = Path(*parts[1:])
            if not relative.parts:
                continue
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            with packed.open(entry) as source, output.open("wb") as dst:
                shutil.copyfileobj(source, dst)
    for item in ("libvlc.dll", "libvlccore.dll"):
        if not (destination / item).is_file():
            raise RuntimeError("Incomplete VLC runtime: " + item)
    if not (destination / "plugins").is_dir() or not any((destination / "plugins").rglob("*.dll")):
        raise RuntimeError("No VLC modules in private runtime")

def stage_macos_dmg(archive, destination):
    if sys.platform != "darwin":
        raise RuntimeError("Mount macOS VLC DMGs only on a native Mac")
    with tempfile.TemporaryDirectory(prefix="dizytv-vlc-mount-") as folder:
        mount = Path(folder) / "mount"
        mount.mkdir()
        subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse",
                        "-mountpoint", str(mount), str(archive)],
                       check=True, stdout=subprocess.DEVNULL)
        try:
            original = mount / "VLC.app"
            lib = original / "Contents" / "MacOS" / "lib" / "libvlc.dylib"
            if not lib.is_file():
                raise RuntimeError("Official VLC DMG has no libvlc")
            # Copy the upstream private bundle intact: dependent dylibs,
            # plugins, module cache, codesign context and licence notices.
            shutil.copytree(original, destination / "VLC.app", symlinks=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)],
                           check=True, stdout=subprocess.DEVNULL)
    private = destination / "VLC.app" / "Contents" / "MacOS"
    if not (private / "lib" / "libvlccore.dylib").is_file():
        raise RuntimeError("VLC macOS bundle missing libvlccore")
    if not any((private / location).is_dir() for location in ("plugins", "modules")) and not (
            private.parent / "Frameworks" / "plugins").is_dir():
        raise RuntimeError("VLC macOS plugin directory is missing")

def main():
    if os.name == "nt":
        target = "windows-x64"
    elif sys.platform == "darwin":
        target = "macos-arm64" if __import__("platform").machine() == "arm64" else "macos-x86_64"
    else:
        raise SystemExit("Linux uses distro-managed libVLC (deb Depends)")
    with tempfile.TemporaryDirectory(prefix="dizytv-stage-vlc-") as directory:
        archive = Path(directory) / ("vlc.zip" if os.name == "nt" else "vlc.dmg")
        fetch_pinned(target, archive)
        if DEST.exists():
            shutil.rmtree(DEST)
        DEST.mkdir(parents=True)
        if os.name == "nt":
            stage_windows_zip(archive, DEST)
        else:
            stage_macos_dmg(archive, DEST)
    print("Pinned VLC 3.0.21 runtime staged for " + target)

if __name__ == "__main__":
    main()
