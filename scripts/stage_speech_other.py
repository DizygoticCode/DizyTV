"""Stage the same pinned English Vosk model on macOS and Ubuntu/Debian.

macOS FFmpeg is a native, wheel-provided executable copied into DizyTV.
Linux uses ffmpeg from the .deb package manager dependency. Downloads occur
only in CI before shipping installers; never silently on a user's computer.
"""
from __future__ import annotations
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile
# Support both the direct CI command (python scripts/stage_speech_other.py)
# and the package-style import used by unit tests.
if __package__:
    from .stage_windows_speech import MODEL_NAME, MODEL_URL, MODEL_SHA256, fetch_verified
else:
    from stage_windows_speech import MODEL_NAME, MODEL_URL, MODEL_SHA256, fetch_verified

ROOT=Path(__file__).resolve().parent.parent
DEST=ROOT/'vendor'/'speech'

def stage_model(archive, destination):
    target=destination/MODEL_NAME
    target.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as model:
        entries=model.infolist()
        if len(entries)>300 or sum(e.file_size for e in entries)>400*1024*1024:
            raise RuntimeError('Unexpected Vosk archive size')
        for entry in entries:
            parts=PurePosixPath(entry.filename.replace('\\','/')).parts
            if (not parts or parts[0]!=MODEL_NAME or any(
                    item in ('','.','..') for item in parts) or
                    (entry.external_attr>>16)&0o170000==0o120000):
                raise RuntimeError('Unsafe model archive entry')
            if entry.is_dir():continue
            path=destination.joinpath(*parts)
            path.parent.mkdir(parents=True,exist_ok=True)
            with model.open(entry) as source,path.open('wb') as output:
                shutil.copyfileobj(source,output)
    if not (target/'am').is_dir() or not (target/'conf').is_dir():
        raise RuntimeError('Downloaded English model incomplete')

def main():
    if os.name=='nt':
        raise SystemExit('Windows has a separate pinned FFmpeg/Vosk stage')
    with tempfile.TemporaryDirectory(prefix='dizytv-speech-stage-') as folder:
        archive=Path(folder)/'model.zip'
        fetch_verified(MODEL_URL,MODEL_SHA256,archive)
        if DEST.exists():shutil.rmtree(DEST)
        DEST.mkdir(parents=True)
        stage_model(archive,DEST)
    if sys.platform=='darwin':
        import imageio_ffmpeg
        exe=Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
        wheel_binaries=Path(imageio_ffmpeg.__file__).resolve().parent/'binaries'
        # imageio_ffmpeg.get_ffmpeg_exe honours an environment override. A
        # system PATH or IMAGEIO_FFMPEG_EXE override must never make us silently
        # package an unverified external executable in the Mac installer.
        if wheel_binaries not in exe.parents or not exe.is_file():
            raise RuntimeError('Pinned macOS FFmpeg wheel did not provide its own native executable')
        target=DEST/'ffmpeg'
        shutil.copy2(exe,target)
        target.chmod(0o755)
        subprocess.run([str(target),'-version'],check=True,stdout=subprocess.DEVNULL)
    print('Pinned English Vosk model and platform FFmpeg stage complete')

if __name__=='__main__':main()
