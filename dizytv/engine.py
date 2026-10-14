"""Start an existing local Ace Stream engine on Windows, never bundle it.

The video still renders in DizyTV's own libVLC player. This helper uses a
background worker, so checking/installing an engine cannot freeze the Qt GUI.
"""
from __future__ import annotations
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
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
