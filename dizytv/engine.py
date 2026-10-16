"""Connect to independently installed Ace Stream engines on Windows and Linux.

The video still renders in DizyTV's own libVLC player. This helper uses a
background worker, so checking/installing an engine cannot freeze the Qt GUI.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlsplit, urlunsplit, urlencode
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


def linux_engine_path(explicit=''):
    """Find the separately installed Linux start-engine launcher.

    Ace Stream recommends start-engine over the raw executable: the wrapper
    sets the correct library paths. Do not download or bundle engine binaries.
    """
    if not sys.platform.startswith('linux'):
        return None
    if explicit:
        chosen=Path(explicit).expanduser()
        if chosen.name!='start-engine' or not chosen.is_file() or not os.access(chosen,os.X_OK):
            raise RuntimeError('Select an executable Linux Ace Stream start-engine script in Settings.')
        return chosen
    candidates=[
        shutil.which('start-engine'),
        '/opt/acestream/start-engine',
        '/usr/local/bin/start-engine',
        str(Path.home()/'acestream'/'start-engine'),
        str(Path.home()/'.local'/'opt'/'acestream'/'start-engine'),
    ]
    for candidate in candidates:
        if candidate:
            path=Path(candidate).expanduser()
            if path.name=='start-engine' and path.is_file() and os.access(path,os.X_OK):
                return path
    return None


def engine_diagnostics(address,timeout=3):
    """Distinguish reachable HTTP engine API from a mere open TCP port."""
    host,port=engine_endpoint(address)
    if host not in ('127.0.0.1','localhost','::1'):
        return 'Configured engine is remote; automatic local startup is unavailable.'
    if (sys.platform=='darwin' or sys.platform.startswith('linux')) and port==6878:
        from .outpace import api_ready
        if api_ready(address):
            return ('Outpace native engine is running locally. This verifies its API, '
                    'not a playable channel or live peer connectivity.')
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
                '. Check the engine, its HTTP port and local firewall.')


def start_playback_session(stream, address, timeout=20, directory=None):
    """Ask the engine for the actual VLC URL, not just an open TCP port.

    Ace Engine's documented format=json middleware reports a playback_url or
    a content/peer error. We never pass an unverified outside URL to VLC.
    """
    from .core import ace_request_params, http_url, stream_url
    if sys.platform=='darwin' or sys.platform.startswith('linux'):
        host,port=engine_endpoint(address)
        if host in ('127.0.0.1','localhost','::1') and port==6878:
            from .outpace import api_ready, playback_url, register_playback_intent
            # Reserve the gap between preparing a native URL and VLC opening
            # it; an empty /streams listing is not enough to reap the daemon.
            register_playback_intent(directory)
            if api_ready(address):
                return playback_url(stream,address)
    params=ace_request_params(stream)
    if params is None:
        raise ValueError('Selected channel has no supported Ace Stream content ID')
    http_url(address)
    split=urlsplit(stream_url(stream,address))
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
        detail=re.sub(r'https?://\S+','[stream URL]',str(error))[:180]
        raise RuntimeError('Ace Stream could not start the channel: '+detail)
    result=payload.get('response')
    playback=result.get('playback_url') if isinstance(result,dict) else None
    if not isinstance(playback,str):
        raise RuntimeError('Engine responded but provided no playback URL. '
                           'The content ID may be stale or have no active peers.')
    parsed=urlparse(playback)
    host,port=engine_endpoint(address)
    local=('localhost','127.0.0.1','::1')
    # A remote Windows/Linux engine may advertise its own 127.0.0.1.
    # Route that URL through the user-selected endpoint instead so Mac
    # clients do not attempt to connect to their own loopback interface.
    if host not in local and parsed.hostname in local:
        target=urlparse(address)
        playback=urlunsplit((target.scheme,target.netloc,parsed.path,parsed.query,parsed.fragment))
        parsed=urlparse(playback)
    try:
        returned_port=parsed.port or (443 if parsed.scheme=='https' else 80)
    except ValueError:
        raise RuntimeError('Engine returned an invalid playback port') from None
    same_host=parsed.hostname==host or (
        host in local and parsed.hostname in local)
    if parsed.scheme not in ('http','https') or not same_host or returned_port!=port:
        raise RuntimeError('Engine returned a playback URL outside its configured endpoint')
    return http_url(playback)


def ensure_ready(address, startup_seconds=25, executable_path='', directory=None):
    """Use existing engine, or start a *trusted local* installed launcher.

    Remote engines are connect-only. Never auto-install, auto-download, or
    execute an arbitrary playlist URL as a local process.
    """
    host,port=engine_endpoint(address)
    if (sys.platform=='darwin' or sys.platform.startswith('linux')) and host in ('127.0.0.1','localhost','::1') and port==6878:
        from .outpace import register_playback_intent
        register_playback_intent(directory)
    if sys.platform=='darwin' and host in ('127.0.0.1','localhost','::1') and port==6878:
        from .outpace import api_ready, ensure_ready as ensure_outpace
        if api_ready(address) or running(address):
            # An existing original Ace engine or local proxy takes precedence:
            # a listening non-Outpace server must never be replaced by Outpace.
            # Playback session preparation chooses the matching API later.
            return 'connected'
        return ensure_outpace(address,startup_seconds)
    if sys.platform.startswith('linux') and host in ('127.0.0.1','localhost','::1') and port==6878:
        from .outpace import api_ready, packaged_binary, ensure_ready as ensure_outpace
        if api_ready(address):
            return 'connected'
        if running(address):
            # Preserve a legitimate externally installed proprietary engine;
            # never start a competing helper on the same listening port.
            return 'connected'
        # Honour a trusted original-vendor start-engine launcher (including
        # the user's explicit Settings choice) before the bundled Outpace
        # fallback. Otherwise valid proprietary Ace streams break on Linux.
        launcher=linux_engine_path(executable_path)
        if launcher is None and packaged_binary() is not None:
            return ensure_outpace(address,startup_seconds)
    if running(address):
        return 'connected'
    if host not in ('127.0.0.1','localhost','::1') or port!=6878:
        raise RuntimeError('Ace Stream engine is unreachable at the configured address. Check Settings.')
    if sys.platform=='win32':
        executable=windows_engine_path(executable_path)
        if executable is None:
            raise RuntimeError('Ace Stream engine not detected. In Settings, choose your installed ace_console.exe or ace_engine.exe (usually %APPDATA%\\ACEStream\\engine).')
        args=[str(executable)]
        if executable.name.lower()=='ace_console.exe':
            args.append('--client-console')
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    elif sys.platform.startswith('linux'):
        executable=linux_engine_path(executable_path)
        if executable is None:
            raise RuntimeError('Ace Stream engine not detected on Linux. Use Tools → Set up Ace Stream engine for an optional original-publisher download on supported Ubuntu 22.04, or select a trusted start-engine script in Settings.')
        args=[str(executable),'--client-console']
        flags=0
    else:
        raise RuntimeError('Ace Stream engine is unreachable. Start the configured engine separately and retry.')
    subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,close_fds=True,creationflags=flags,
                     cwd=str(executable.parent))
    deadline=time.monotonic()+startup_seconds
    while time.monotonic()<deadline:
        if running(address):
            return 'started'
        time.sleep(0.35)
    raise RuntimeError('Engine launched but localhost port 6878 is still unavailable. Check engine logs, dependencies, permissions and localhost firewall.')
