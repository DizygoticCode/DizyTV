"""Explicitly opt-in, local live speech-to-text from an authorised TV stream.

An external FFmpeg executable extracts mono 16k PCM from the *same source URL*
as VLC. A bundled Vosk runtime and user-selected offline model transcribe it.
No microphone is opened, no external speech API is used, and audio is never
saved. FFmpeg may establish a second connection to the broadcaster, so this
is deliberately off by default and stops when the channel changes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import threading


def installed_caption_models():
    """Installed models live in user AppData, not the DizyTV programme folder."""
    home=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))
    root=home/'DizyTV'/'models'
    if not root.is_dir():return []
    return [(path.name,str(path)) for path in sorted(root.glob('vosk-model-small-*'))
            if (path/'am').is_dir() and (path/'conf').is_dir()]


def preferred_caption_model():
    models=installed_caption_models()
    english=next((path for name,path in models if name=='vosk-model-small-en-us-0.15'),None)
    return english or (models[0][1] if models else '')


def bundled_ffmpeg():
    """Portable optional FFmpeg beside the installed DizyTV.exe."""
    if getattr(sys,'frozen',False):
        exe=Path(sys.executable).resolve()
        path=exe.parent/'tools'/'ffmpeg.exe'
        if path.is_file():return str(path)
    return shutil.which('ffmpeg') or ''


def verify_caption_engine(model_dir,ffmpeg_path=''):
    model_dir=model_dir or preferred_caption_model()
    if not model_dir:
        raise ValueError('Choose an extracted offline Vosk speech model in Settings')
    model=Path(model_dir)
    if not model.is_dir() or not (model/'am').is_dir() or not (model/'conf').is_dir():
        raise ValueError('Selected directory is not an extracted Vosk model (missing am/conf)')
    if ffmpeg_path:
        ffmpeg=Path(ffmpeg_path)
        if not ffmpeg.is_file() or ffmpeg.name.lower() not in ('ffmpeg','ffmpeg.exe'):
            raise ValueError('Select the installed FFmpeg executable')
        binary=str(ffmpeg.resolve())
    else:
        binary=bundled_ffmpeg()
        if not binary:
            raise ValueError('FFmpeg is not installed or on PATH; choose its executable in Settings')
    try:
        import vosk
    except ImportError as exc:
        raise ValueError('Offline captions component is not included in this desktop build') from exc
    return binary,str(model.resolve())


def ffmpeg_capture_args(binary,url):
    if not isinstance(url,str) or not url:
        raise ValueError('Choose a playing channel first')
    if url.startswith(('http://','https://')):
        from .core import http_url
        http_url(url)
    elif not Path(url).is_file():
        raise ValueError('Only an authorised active HTTP stream or local video file can be transcribed')
    return [binary,'-hide_banner','-loglevel','error','-nostdin','-re',
            '-i',url,'-map','0:a:0','-vn','-ac','1','-ar','16000',
            '-f','s16le','pipe:1']


def caption_text(value):
    return ''.join(ch for ch in str(value) if ch.isprintable() or ch=='\n').strip()[-240:]


class LocalCaptionWorker:
    """Background CPU recogniser. stop() kills FFmpeg to unblock reads promptly."""

    def __init__(self,binary,url,model_path,on_caption,on_finish):
        self.binary=binary
        self.url=url
        self.model_path=model_path
        self.on_caption=on_caption
        self.on_finish=on_finish
        self._stop=threading.Event()
        self._process=None
        self._thread=threading.Thread(target=self._run,name='dizytv-local-captions',daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        process=self._process
        if process is not None and process.poll() is None:
            try:process.kill()
            except OSError:pass

    def _run(self):
        reason=''
        process=None
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
            SetLogLevel(-1)
            recognizer=KaldiRecognizer(Model(self.model_path),16000)
            if self._stop.is_set():return
            flags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0
            process=subprocess.Popen(ffmpeg_capture_args(self.binary,self.url),
                                     stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL,creationflags=flags)
            self._process=process
            last=''
            while not self._stop.is_set():
                block=process.stdout.read(4096)
                if not block:break
                if recognizer.AcceptWaveform(block):
                    result=json.loads(recognizer.Result()).get('text','')
                else:
                    result=json.loads(recognizer.PartialResult()).get('partial','')
                result=caption_text(result)
                if result and result!=last:
                    self.on_caption(result)
                    last=result
            if not self._stop.is_set():
                reason='Local transcription ended; stream may not provide readable audio.'
        except Exception as exc:
            if not self._stop.is_set():
                reason='Offline caption engine stopped: '+type(exc).__name__
        finally:
            if process is not None and process.poll() is None:
                try:process.kill()
                except OSError:pass
            if process is not None:
                try:process.wait(timeout=2)
                except (OSError,subprocess.TimeoutExpired):pass
            self._process=None
            self.on_finish(reason)
