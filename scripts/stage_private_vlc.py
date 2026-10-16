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
VERSION = "3.0.24"
BASE = "https://download.videolan.org/pub/videolan/vlc/3.0.24"
ARCHIVES = {
    "windows-x64": (
        BASE + "/win64/vlc-3.0.24-win64.zip",
        "fcf30850371ad10c9373cc4f0f4501e7dee49e3e9ae9f20c72fb2661a1ca6323",
        100 * 1024 * 1024,
    ),
    "macos-arm64": (
        BASE + "/macosx/vlc-3.0.24-universal.dmg",
        "2c8e89f7f42e53c2fb0e87b6dfa39b49f1364b25080aaa2e476ac74c0d7beb3c",
        128 * 1024 * 1024,
    ),
    "macos-x86_64": (
        BASE + "/macosx/vlc-3.0.24-universal.dmg",
        "2c8e89f7f42e53c2fb0e87b6dfa39b49f1364b25080aaa2e476ac74c0d7beb3c",
        128 * 1024 * 1024,
    ),
}

def fetch_pinned(target, destination, opener=urlopen):
    url, expected, limit = ARCHIVES[target]
    request = __import__("urllib.request", fromlist=["Request"]).Request(
        url, headers={"User-Agent": "DizyTV-build/0.1"})
    digest = hashlib.sha256()
    count = 0
    try:
        with opener(request, timeout=100) as source, destination.open("xb") as output:
            final = source.geturl()
            from urllib.parse import urlsplit
            parsed=urlsplit(final)
            if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
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
            raise RuntimeError("VLC archive SHA-256 mismatch for " + target)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

def stage_windows_zip(archive, destination):
    # Preserve original layout and licence notices, not just a stripped DLL.
    with zipfile.ZipFile(archive) as packed:
        info = packed.infolist()
        if len(info) > 2500 or sum(x.file_size for x in info) > 400 * 1024 * 1024:
            raise RuntimeError("Unexpected VLC archive size")
        for entry in info:
            name = PurePosixPath(entry.filename.replace("\\", "/"))
            parts = name.parts
            if (not parts or parts[0] != "vlc-3.0.24"
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
    architectures=subprocess.run(
        ["lipo", "-archs", str(private / "lib" / "libvlc.dylib")],
        check=True, capture_output=True, text=True).stdout.split()
    if not {"arm64", "x86_64"}.issubset(set(architectures)):
        raise RuntimeError("Official universal VLC does not contain both Mac architectures")
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
    print("Pinned VLC 3.0.24 runtime staged for " + target)

if __name__ == "__main__":
    main()
