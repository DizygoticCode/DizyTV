"""Stage checksum-pinned Windows caption assets for the *offline* DizyTV installer.

Only the Windows build runs this script. The downloads happen in CI during
packaging, never during the user's installation or first caption session.
Keep the archive versions/hashes fixed until explicitly reviewed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "vendor" / "speech"
FFMPEG_URL = ("https://github.com/GyanD/codexffmpeg/releases/download/8.1.2/"
              "ffmpeg-8.1.2-essentials_build.zip")
FFMPEG_SHA256 = "db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec"
MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = ("https://github.com/BartekReterski/VoskModels/releases/download/v1/"
             + MODEL_NAME + ".zip")
MODEL_SHA256 = "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"


def fetch_verified(url: str, sha256: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "DizyTV-build/0.1.11"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as target:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            target.write(chunk)
    if digest.hexdigest() != sha256:
        destination.unlink(missing_ok=True)
        raise RuntimeError("SHA256 mismatch for " + destination.name)


def stage_archives(ffmpeg_archive: Path, model_archive: Path, destination: Path) -> None:
    """Extract only expected files, never arbitrary paths or symlinks."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(ffmpeg_archive) as archive:
        ffmpeg_files = [item for item in archive.infolist()
                        if item.filename.replace("\\", "/").endswith("/bin/ffmpeg.exe")
                        and not item.is_dir()]
        if len(ffmpeg_files) != 1 or ffmpeg_files[0].file_size > 200 * 1024 * 1024:
            raise RuntimeError("Unexpected FFmpeg archive layout")
        with archive.open(ffmpeg_files[0]) as src, (destination / "ffmpeg.exe").open("wb") as dst:
            shutil.copyfileobj(src, dst)
    with zipfile.ZipFile(model_archive) as archive:
        count = 0
        total = 0
        for entry in archive.infolist():
            path = Path(entry.filename)
            parts = path.parts
            if not parts or parts[0] != MODEL_NAME:
                raise RuntimeError("Unexpected model archive path")
            if entry.is_dir():
                continue
            if any(part in (".", "..") for part in parts) or len(parts) < 2:
                raise RuntimeError("Unsafe model archive path")
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError("Model archive symlink is not allowed")
            total += entry.file_size
            count += 1
            if total > 400 * 1024 * 1024 or count > 300:
                raise RuntimeError("Model archive exceeds staging limits")
            out = destination.joinpath(*parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    model = destination / MODEL_NAME
    if not (model / "am").is_dir() or not (model / "conf").is_dir():
        raise RuntimeError("Bundled Vosk model is incomplete")
    if not (destination / "ffmpeg.exe").is_file():
        raise RuntimeError("Bundled FFmpeg is missing")


def main() -> None:
    archives = ROOT / "build" / "speech-downloads"
    ffmpeg = archives / "ffmpeg-8.1.2-essentials_build.zip"
    model = archives / (MODEL_NAME + ".zip")
    fetch_verified(FFMPEG_URL, FFMPEG_SHA256, ffmpeg)
    fetch_verified(MODEL_URL, MODEL_SHA256, model)
    stage_archives(ffmpeg, model, STAGE)
    print("Checksum-verified FFmpeg + Vosk model staged for native installer")


if __name__ == "__main__":
    main()
