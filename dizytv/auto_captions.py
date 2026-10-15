"""Explicitly opt-in, local live speech-to-text from an authorised TV stream.

An external FFmpeg executable extracts mono 16k PCM from the *same source URL*
as VLC. A bundled Vosk runtime and included English model transcribe it on Windows;
user-selected model and FFmpeg paths remain optional overrides.
No microphone is opened, no external speech API is used, and audio is never
saved. FFmpeg may establish a second connection to the broadcaster, so this
is deliberately off by default and stops when the channel changes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from urllib.request import Request, urlopen

# Keep the caption audio client identical to VLC's working HTTP identity.
PLAYBACK_USER_AGENT = 'Mozilla/5.0 (compatible; DizyTV/0.1)'


# Optional models are fetched only after the viewer explicitly asks. These are
# the official Vosk/Alpha Cephei small models (Apache-2.0), NOT redistributed.
# Third-party or arbitrary archive URLs are never accepted by this installer.
LANGUAGE_MODELS = {
    'English (bundled)': 'vosk-model-small-en-us-0.15',
    'French': 'vosk-model-small-fr-0.22',
    'German': 'vosk-model-small-de-0.15',
    'Spanish': 'vosk-model-small-es-0.42',
    'Italian': 'vosk-model-small-it-0.22',
    'Dutch': 'vosk-model-small-nl-0.22',
    'Portuguese': 'vosk-model-small-pt-0.3',
    'Russian': 'vosk-model-small-ru-0.22',
    'Polish': 'vosk-model-small-pl-0.22',
    'Japanese': 'vosk-model-small-ja-0.22',
    'Hindi': 'vosk-model-small-hi-0.22',
}
MAX_MODEL_ZIP_BYTES = 100 * 1024 * 1024
MAX_MODEL_EXPANDED_BYTES = 400 * 1024 * 1024


def user_models_directory():
    # Use device app-data rather than Program Files: normal Windows users
    # cannot write additional model downloads into the installed app.
    base = (Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData'/'Local'))
            if os.name == 'nt' else
            Path.home()/'Library'/'Application Support' if sys.platform == 'darwin'
            else Path.home()/'.local'/'share')
    return base/'DizyTV'/'speech-models'


def installed_language_model(language, root=None):
    if language not in LANGUAGE_MODELS:
        raise ValueError('Unsupported speech-model language')
    if language == 'English (bundled)':
        model = bundled_speech_directory()/LANGUAGE_MODELS[language]
    else:
        model = Path(root) if root else user_models_directory()
        model = model/LANGUAGE_MODELS[language]
    return model if (model/'am').is_dir() and (model/'conf').is_dir() else None


def install_language_model(language, root=None, opener=urlopen):
    """Download exactly one official small model, with bounded safe extraction.

    No user-supplied URL, archive traversal, links, ZIP bombs or partially
    installed model. Caller runs this away from the GUI thread.
    """
    if language not in LANGUAGE_MODELS or language == 'English (bundled)':
        raise ValueError('Choose an optional Vosk language to install')
    folder=Path(root) if root else user_models_directory()
    model_name=LANGUAGE_MODELS[language]
    existing=installed_language_model(language,folder)
    if existing is not None:return str(existing)
    folder.mkdir(parents=True,exist_ok=True)
    url='https://alphacephei.com/vosk/models/'+model_name+'.zip'
    with tempfile.TemporaryDirectory(prefix='.vosk-download-',dir=folder) as temporary:
        staging=Path(temporary)
        archive=staging/'model.zip'
        request=Request(url,headers={'User-Agent':'DizyTV/0.1'})
        with opener(request,timeout=35) as response, archive.open('wb') as output:
            # Reject unexpected cross-host or insecure redirects.
            final=response.geturl()
            if not final.startswith('https://alphacephei.com/vosk/models/'):
                raise ValueError('Model download redirected away from the official Vosk host')
            total=0
            while True:
                chunk=response.read(128*1024)
                if not chunk:break
                total+=len(chunk)
                if total>MAX_MODEL_ZIP_BYTES:
                    raise ValueError('Speech model download exceeds the size limit')
                output.write(chunk)
        with zipfile.ZipFile(archive) as zipped:
            infos=zipped.infolist()
            if len(infos)>5000 or sum(i.file_size for i in infos)>MAX_MODEL_EXPANDED_BYTES:
                raise ValueError('Speech model archive exceeds the extraction limit')
            for info in infos:
                name=info.filename.replace('\\','/')
                parts=name.rstrip('/').split('/')
                if (len(parts)<2 or parts[0]!=model_name
                        or any(part in ('','.','..') for part in parts)
                        or info.flag_bits & 0x1
                        or (info.external_attr>>16)&0o170000==0o120000):
                    raise ValueError('Speech model contains an unsafe archive entry')
            extraction=staging/'extracted'
            zipped.extractall(extraction)
        candidate=extraction/model_name
        if not (candidate/'am').is_dir() or not (candidate/'conf').is_dir():
            raise ValueError('Downloaded Vosk model is missing acoustic/configuration files')
        target=folder/model_name
        if target.exists():
            if installed_language_model(language,folder) is not None:return str(target)
            raise ValueError('An incomplete model folder already exists; remove it before retrying')
        os.replace(candidate,target)
        return str(target)



def bundled_speech_directory():
    """PyInstaller stores resources in _MEIPASS; the source checkout has none."""
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'speech'


def verify_caption_engine(model_dir='',ffmpeg_path=''):
    packaged = bundled_speech_directory()
    if not model_dir and (packaged / 'vosk-model-small-en-us-0.15').is_dir():
        model_dir = str(packaged / 'vosk-model-small-en-us-0.15')
    if not model_dir:
        raise ValueError('English speech model is missing; choose an extracted Vosk model in Settings')
    model=Path(model_dir)
    if not model.is_dir() or not (model/'am').is_dir() or not (model/'conf').is_dir():
        raise ValueError('Selected directory is not an extracted Vosk model (missing am/conf)')
    if ffmpeg_path:
        ffmpeg=Path(ffmpeg_path)
        if not ffmpeg.is_file() or ffmpeg.name.lower() not in ('ffmpeg','ffmpeg.exe'):
            raise ValueError('Select the installed FFmpeg executable')
        binary=str(ffmpeg.resolve())
    else:
        bundled = packaged / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        binary = str(bundled.resolve()) if bundled.is_file() else shutil.which('ffmpeg')
        if not binary:
            raise ValueError('FFmpeg is missing; choose an installed executable in Settings')
    try:
        import vosk
    except ImportError as exc:
        raise ValueError('Offline captions component is not included in this desktop build') from exc
    return binary,str(model.resolve())


def ffmpeg_capture_args(binary,url):
    if not isinstance(url,str) or not url:
        raise ValueError('Choose a playing channel first')
    if url.lower().startswith(('http://','https://')):
        from .core import http_url
        http_url(url)
    elif not Path(url).is_file():
        raise ValueError('Only an authorised active HTTP stream or local video file can be transcribed')
    args=[binary,'-hide_banner','-loglevel','error','-nostdin','-re']
    if url.lower().startswith(('http://','https://')):
        # FFmpeg's default Lavf user agent may be rejected by otherwise
        # playable HLS origins; use the same identity as the video player.
        args.extend(['-user_agent',PLAYBACK_USER_AGENT])
    return args+['-i',url,'-map','0:a:0','-vn','-ac','1','-ar','16000',
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
