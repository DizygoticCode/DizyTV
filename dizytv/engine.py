"""Start an existing local Ace Stream engine on Windows, never bundle it.

The video still renders in DizyTV's own libVLC player. This helper uses a
background worker, so checking/installing an engine cannot freeze the Qt GUI.
"""
from __future__ import annotations
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


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


def windows_engine_path():
    if sys.platform!='win32':
        return None
    roots=[]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\ACEStream') as key:
            root,_=winreg.QueryValueEx(key,'InstallDir')
            roots.append(Path(root))
    except (OSError,ValueError):
        pass
    roots.append(Path(os.environ.get('APPDATA',str(Path.home()/'AppData'/'Roaming')))/'ACEStream'/'engine')
    for root in roots:
        for name in ('ace_console.exe','ace_engine.exe'):
            found=root/name
            if found.is_file():
                return found
    return None


def ensure_ready(address, startup_seconds=10):
    """Called off the UI thread. Never launch for a remote/custom engine URL."""
    if running(address):
        return 'connected'
    host,port=engine_endpoint(address)
    if host not in ('127.0.0.1','localhost','::1') or port!=6878 or sys.platform!='win32':
        raise RuntimeError('Ace Stream engine is unreachable at the configured address. Check Settings.')
    executable=windows_engine_path()
    if executable is None:
        raise RuntimeError('Ace Stream engine is not installed. Install it from the official provider once; DizyTV will launch it automatically afterwards.')
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    args=[str(executable)]
    if executable.name.lower()=='ace_console.exe':
        args.append('--client-console')
    subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,close_fds=True,creationflags=flags)
    deadline=time.monotonic()+startup_seconds
    while time.monotonic()<deadline:
        if running(address):
            return 'started'
        time.sleep(0.35)
    raise RuntimeError('Installed Ace Stream engine was launched but its HTTP API did not start. Check the engine installation.')
