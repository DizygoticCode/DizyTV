"""Start an existing local Ace Stream engine on Windows, never bundle it.

The video still renders in DizyTV's own libVLC player. This helper uses a
background worker, so checking/installing an engine cannot freeze the Qt GUI.
"""
from __future__ import annotations
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import urlopen
from urllib.error import HTTPError, URLError


def engine_endpoint(address):
    parsed=urlparse(address)
    if parsed.scheme not in ('http','https') or not parsed.hostname:
        raise ValueError('Configure a valid Ace Stream engine URL in Settings')
    return parsed.hostname, parsed.port or (443 if parsed.scheme=='https' else 80)


def running(address, timeout=0.5):
    host,port=engine_endpoint(address)
    try:
        with socket.create_connection((host,port),timeout=timeout):
            return True
    except OSError:
        return False


def windows_engine_path(explicit=''):
    """Locate the official installed engine; never download or bundle it."""
    if sys.platform!='win32':
        return None
    if explicit:
        chosen=Path(explicit)
        if chosen.is_file() and chosen.name.lower() in ('ace_console.exe','ace_engine.exe'):
            return chosen
        raise RuntimeError('Selected Ace engine executable was not found. Choose ace_console.exe or ace_engine.exe in Settings.')
    roots=[]
    try:
        import winreg
        access=[winreg.KEY_READ]
        for variant in ('KEY_WOW64_64KEY','KEY_WOW64_32KEY'):
            flag=getattr(winreg,variant,0)
            if flag:access.append(winreg.KEY_READ|flag)
        for keypath in (r'Software\ACEStream',r'Software\Wow6432Node\ACEStream'):
            for flag in access:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,keypath,0,flag) as key:
                        folder,_=winreg.QueryValueEx(key,'InstallDir')
                        if folder:roots.append(Path(folder))
                except (OSError,ValueError):
                    continue
    except ImportError:
        pass
    for env, suffix in (('APPDATA','ACEStream'),('LOCALAPPDATA','ACEStream'),
                        ('PROGRAMFILES','ACEStream'),('PROGRAMFILES(X86)','ACEStream')):
        root=os.environ.get(env)
        if root:roots.append(Path(root)/suffix)
    for root in roots:
        for location in (root,root/'engine'):
            for name in ('ace_engine.exe','ace_console.exe'):
                found=location/name
                if found.is_file():
                    return found
    return None


def engine_diagnostics(address,timeout=3):
    """Distinguish reachable HTTP engine API from a mere open TCP port."""
    host,port=engine_endpoint(address)
    if host not in ('127.0.0.1','localhost','::1'):
        return 'Configured engine is remote; cannot auto-start a Windows engine.'
    api=address.rstrip('/')+'/webui/api/service?method=get_version'
    try:
        with urlopen(api,timeout=timeout) as response:
            payload=response.read(4096)
        data=json.loads(payload)
        result=data.get('result')
        if not isinstance(result,dict) or not result.get('version'):
            return 'Port '+str(port)+' responded, but the Ace Engine API did not identify itself.'
        return ('Ace Engine '+str(result['version'])+' is running on local port '+str(port)+
                '. This verifies the engine, not the stream; its content ID may have no available peers.')
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError):
        return ('Ace Engine API is not responding on localhost port '+str(port)+
                '. Check the engine, its HTTP port and Windows firewall.')


def start_playback_session(stream, address, timeout=20):
    """Ask the engine for the actual VLC URL, not just an open TCP port.

    Ace Engine's documented format=json middleware reports a playback_url or
    a content/peer error. We never pass an unverified outside URL to VLC.
    """
    from .core import ace_request_params, http_url
    params=ace_request_params(stream)
    if params is None:
        raise ValueError('Selected channel has no supported Ace Stream content ID')
    engine=http_url(address).rstrip('/')
    split=urlsplit(engine+'/ace/getstream')
    query=urlencode({**params,'format':'json'})
    request=urlunsplit((split.scheme,split.netloc,split.path,query,''))
    try:
        with urlopen(request,timeout=timeout) as response:
            data=response.read(32769)
    except HTTPError as exc:
        raise RuntimeError('Ace Stream rejected this channel (HTTP '+str(exc.code)+
                           '). The stream may be offline, blocked, or unavailable.') from None
    except (URLError,TimeoutError,OSError) as exc:
        raise RuntimeError('Ace Stream engine is reachable but did not prepare a playable stream. '
                           'Check available peers and try the channel in the official Ace player. '
                           '('+type(exc).__name__+')') from None
    if len(data)>32768:
        raise RuntimeError('Ace Stream returned an oversized session response')
    try:
        payload=json.loads(data)
    except (ValueError,UnicodeDecodeError):
        raise RuntimeError('Ace Stream returned no valid playback session. Update the installed engine.') from None
    if not isinstance(payload,dict):
        raise RuntimeError('Ace Stream returned an invalid playback session')
    error=payload.get('error')
    if error:
        # Never expose a raw URL/token from an engine-generated error.
        detail=re.sub(r'https?://\\S+','[stream URL]',str(error))[:180]
        raise RuntimeError('Ace Stream could not start the channel: '+detail)
    result=payload.get('response')
    playback=result.get('playback_url') if isinstance(result,dict) else None
    if not isinstance(playback,str):
        raise RuntimeError('Engine responded but provided no playback URL. '
                           'The content ID may be stale or have no active peers.')
    parsed=urlparse(playback)
    host,port=engine_endpoint(address)
    try:
        returned_port=parsed.port or (443 if parsed.scheme=='https' else 80)
    except ValueError:
        raise RuntimeError('Engine returned an invalid playback port') from None
    same_host=parsed.hostname==host or (
        host in ('localhost','127.0.0.1','::1')
        and parsed.hostname in ('localhost','127.0.0.1','::1'))
    if parsed.scheme not in ('http','https') or not same_host or returned_port!=port:
        raise RuntimeError('Engine returned a playback URL outside its configured endpoint')
    return http_url(playback)


def ensure_ready(address, startup_seconds=25, executable_path=''):
    """Called off the UI thread. Never launch for a remote/custom engine URL."""
    if running(address):
        return 'connected'
    host,port=engine_endpoint(address)
    if host not in ('127.0.0.1','localhost','::1') or port!=6878 or sys.platform!='win32':
        raise RuntimeError('Ace Stream engine is unreachable at the configured address. Check Settings.')
    executable=windows_engine_path(executable_path)
    if executable is None:
        raise RuntimeError('Ace Stream engine not detected. In Settings, choose your installed ace_console.exe or ace_engine.exe (usually %APPDATA%\\ACEStream\\engine), or use Set up Ace Stream engine.')
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    args=[str(executable)]
    if executable.name.lower()=='ace_console.exe':
        args.append('--client-console')
    subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,close_fds=True,creationflags=flags,cwd=str(executable.parent))
    deadline=time.monotonic()+startup_seconds
    while time.monotonic()<deadline:
        if running(address):
            return 'started'
        time.sleep(0.35)
    raise RuntimeError('Ace engine launched but localhost port 6878 is still unavailable. Check Windows firewall/engine settings and the configured engine URL.')
