"""Stage the unmodified official VideoLAN VLC 3 x64 runtime for Windows builds.

CI downloads a *pinned* VLC archive. The installer ships the private runtime
inside DizyTV; Windows users do not run the VLC installer separately.
No VLC player GUI executable, wallpaper add-on, updater or system PATH change.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "vendor" / "vlc"
VERSION = "3.0.24"
ARCHIVE_NAME = "vlc-3.0.24-win64.zip"
ARCHIVE_URL = ("https://download.videolan.org/pub/videolan/vlc/"
               + VERSION + "/win64/" + ARCHIVE_NAME)
# Compare archive bytes against the published VideoLAN release checksum;
# an HTTPS mirror redirect is not implicitly trusted.
ARCHIVE_SHA256 = "fcf30850371ad10c9373cc4f0f4501e7dee49e3e9ae9f20c72fb2661a1ca6323"
MAX_ARCHIVE_BYTES = 110 * 1024 * 1024
MAX_EXPANDED_BYTES = 550 * 1024 * 1024
MAX_FILES = 2500


def verified_download(url=ARCHIVE_URL, destination=None, opener=urlopen):
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS VLC archive URLs are permitted")
    if destination is None:
        raise ValueError("Choose a staging archive path")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    length = 0
    try:
        with opener(Request(url, headers={"User-Agent": "DizyTV-native-build"}), timeout=120) as response:
            if not response.geturl().startswith("https://"):
                raise ValueError("Insecure VLC download redirect")
            with destination.open("wb") as saved:
                while chunk := response.read(1024 * 1024):
                    length += len(chunk)
                    if length > MAX_ARCHIVE_BYTES:
                        raise ValueError("VLC archive exceeds the size limit")
                    digest.update(chunk)
                    saved.write(chunk)
        if digest.hexdigest() != ARCHIVE_SHA256:
            raise ValueError("VLC archive SHA-256 checksum mismatch")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def stage_archive(archive_path, destination):
    """Extract only private libVLC binaries, plugins and publisher notices."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vlc-stage-", dir=destination.parent) as td:
        ready = Path(td) / "vlc"
        ready.mkdir()
        root_name = "vlc-" + VERSION
        total = 0
        count = 0
        lib = {"libvlc.dll": False, "libvlccore.dll": False}
        plugin_count = 0
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                name = member.filename.replace("\\", "/")
                parts = PurePosixPath(name).parts
                if not parts or parts[0] != root_name:
                    raise ValueError("Unexpected VideoLAN archive root")
                if any(p in ("..", ".") for p in parts):
                    raise ValueError("Unsafe VLC archive member")
                mode = (member.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise ValueError("VLC archive contains a link")
                if member.is_dir():
                    continue
                count += 1
                total += member.file_size
                if count > MAX_FILES or total > MAX_EXPANDED_BYTES:
                    raise ValueError("VLC expanded package too large")
                relative = parts[1:]
                if not relative:
                    continue
                # Native libraries at top level, decoder/protocol/audio plugins,
                # and authoritative VideoLAN licence notices only.
                allowed = (
                    (len(relative) == 1 and
                     (relative[0].lower().endswith(".dll") or
                      relative[0].lower() in ("copying.txt", "readme.txt", "news.txt")))
                    or (relative[0] == "plugins" and len(relative) >= 2
                        and relative[-1].lower().endswith(".dll"))
                )
                if not allowed:
                    continue
                target = ready.joinpath(*relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                if len(relative) == 1 and relative[0].lower() in lib:
                    lib[relative[0].lower()] = True
                if relative[0] == "plugins":
                    plugin_count += 1
        if not all(lib.values()) or plugin_count == 0:
            raise ValueError("VLC archive lacks its core DLLs or plugin directory")
        if not (ready / "COPYING.txt").is_file():
            raise ValueError("VLC redistribution notice missing")
        old = Path(td) / "old"
        if destination.exists():
            os.replace(destination, old)
        try:
            os.replace(ready, destination)
        except Exception:
            if old.exists():
                os.replace(old, destination)
            raise


def main():
    with tempfile.TemporaryDirectory(prefix="dizytv-vlc-download-") as td:
        archive = Path(td) / ARCHIVE_NAME
        verified_download(destination=archive)
        stage_archive(archive, DESTINATION)
    print("Pinned official VLC 3 x64 DLLs and plugins staged for DizyTV packaging")


if __name__ == "__main__":
    main()
