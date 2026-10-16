"""Stage the pinned Small English US Vosk model for macOS and Linux packages.

Windows already gets it through scripts/stage_windows_speech.py; other native
desktop installs should not need manual model-folder downloads for English.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from scripts.stage_windows_speech import (
    MODEL_NAME, MODEL_URL, MODEL_SHA256, fetch_verified,
)

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "vendor" / "speech"


def stage_model(archive_path, destination):
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".speech-stage-",dir=destination.parent) as td:
        staged=Path(td)/"speech"
        model=staged/MODEL_NAME
        model.mkdir(parents=True)
        total=0
        count=0
        with zipfile.ZipFile(archive_path) as z:
            for entry in z.infolist():
                parts=PurePosixPath(entry.filename.replace("\\","/")).parts
                if not parts or parts[0]!=MODEL_NAME or any(p in (".","..") for p in parts):
                    raise ValueError("Untrusted Vosk archive path")
                if ((entry.external_attr>>16)&0o170000)==stat.S_IFLNK:
                    raise ValueError("Vosk archive link is forbidden")
                if entry.is_dir():
                    continue
                total+=entry.file_size
                count+=1
                if count>300 or total>400*1024*1024:
                    raise ValueError("Model expanded archive exceeds size cap")
                if len(parts)<2:
                    raise ValueError("Unexpected Vosk model archive member")
                target=staged.joinpath(*parts)
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(entry) as source, target.open("wb") as dst:
                    shutil.copyfileobj(source,dst)
        if not (model/"am").is_dir() or not (model/"conf").is_dir():
            raise ValueError("Acoustic/configuration model files are missing")
        destination.mkdir(parents=True,exist_ok=True)
        target=destination/MODEL_NAME
        if target.exists():
            shutil.rmtree(target)
        os.replace(model,target)


def stage_macos_ffmpeg():
    import imageio_ffmpeg
    source=Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    # Do not silently copy system FFmpeg with unknown version or licence.
    expected=Path(imageio_ffmpeg.__file__).resolve().parent/"binaries"
    if expected not in source.parents or not source.is_file():
        raise RuntimeError("The pinned imageio-ffmpeg wheel did not include a native FFmpeg binary")
    STAGE.mkdir(parents=True,exist_ok=True)
    destination=STAGE/"ffmpeg"
    shutil.copyfile(source,destination)
    destination.chmod(0o755)
    subprocess.run([str(destination),"-version"],check=True,stdout=subprocess.DEVNULL)


def main():
    if sys.platform=="win32":
        return
    STAGE.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dizytv-model-download-") as td:
        path=Path(td)/(MODEL_NAME+".zip")
        fetch_verified(MODEL_URL,MODEL_SHA256,path)
        stage_model(path,STAGE)
    if sys.platform=="darwin":
        stage_macos_ffmpeg()
    print("English Vosk model and applicable local FFmpeg staged")


if __name__=="__main__":
    main()
