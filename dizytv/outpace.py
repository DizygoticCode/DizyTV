"""Packaged macOS/Linux Outpace daemon: a separate AGPL-3.0-or-later program.

DizyTV never downloads an arbitrary executable from a playlist, exposes the
HTTP API on a LAN interface, or starts a bundled daemon for a remote endpoint.
Outpace's native API is used; its experimental Ace-compat API is not enabled.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import urlopen


LOCAL_HOSTS = frozenset(('localhost', '127.0.0.1', '::1'))

# Track only child processes created by this DizyTV instance. Never kill a
# pre-existing listener or the system-installed proprietary Ace engine.
_OWNED_PROCESS = None
_OWNED_IDENTITY = None
_OWNED_BINARY = None
_SHUTTING_DOWN = False
_PROCESS_LOCK = threading.Lock()


def stop_owned_daemon(*,preserve_recordings=False,allow_restart=False):
    """Non-blocking shutdown when the GUI exits, respecting active recordings.

    A helper may be serving a detached recorder after the viewer closes.
    Preserve it in that case and never wait for a subprocess on Qt's thread.
    The detached recording worker can release *its own* helper with
    allow_restart=True so that later queued jobs can start it again.
    """
    global _OWNED_PROCESS, _OWNED_IDENTITY, _OWNED_BINARY, _SHUTTING_DOWN
    with _PROCESS_LOCK:
        if not allow_restart:
            _SHUTTING_DOWN = True
        if preserve_recordings or _OWNED_PROCESS is None:
            return False
        process = _OWNED_PROCESS
        _OWNED_PROCESS = None
        _OWNED_IDENTITY = None
        _OWNED_BINARY = None
    try:
        if process.poll() is None:
            process.terminate()  # sends SIGTERM; do not block in wait()
            return True
    except (OSError, RuntimeError):
        pass
    return False



def _process_identity(pid, binary):
    """Fingerprint only the specific local Outpace child we launched.

    A PID by itself is unsafe: it can be reused after the creator exits. ps
    supplies a start time as well as the *full* command line on Linux/macOS.
    If either is unavailable or does not match our private binary, fail closed.
    """
    if not isinstance(pid, int) or pid <= 1 or not isinstance(binary, str):
        return None
    try:
        checked = subprocess.run(
            ['ps', '-ww', '-p', str(pid), '-o', 'lstart=', '-o', 'args='],
            capture_output=True, text=True, timeout=2, check=False)
        description = checked.stdout.strip()
        if checked.returncode != 0 or not description:
            return None
        if (' ' + binary + ' serve') not in (' ' + description):
            return None
        return hashlib.sha256(description.encode('utf-8')).hexdigest()
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def handoff_owned_daemon(directory):
    """Record verified process ownership for the detached recorder.

    The GUI can close during an Ace recording without killing its stream.
    Only the existing recorder worker may later reap this exact process,
    once both scheduled Ace jobs and native Outpace sessions are idle.
    """
    from .storage import atomic_json
    global _SHUTTING_DOWN
    with _PROCESS_LOCK:
        _SHUTTING_DOWN = True
        process = _OWNED_PROCESS
        identity = _OWNED_IDENTITY
        binary = _OWNED_BINARY
    if process is None or identity is None or binary is None:
        return False
    if process.poll() is not None:
        return False
    try:
        atomic_json(Path(directory) / 'outpace-handoff.json',
                    {'pid': process.pid, 'binary': binary, 'identity': identity})
        return True
    except (OSError, ValueError):
        # Never sacrifice an in-progress recording for cleanup bookkeeping.
        return False


def reap_handed_off_daemon(directory, address='http://127.0.0.1:6878'):
    """Reap the former GUI child only after validating identity and idleness.

    The worker must never stop an unrelated system Ace installation or
    interrupt another viewer's Outpace session.
    """
    from .core import ace_request_params
    from .storage import Store
    marker = Path(directory) / 'outpace-handoff.json'
    if not marker.exists():
        return False
    try:
        data = json.loads(marker.read_text(encoding='utf-8'))
        pid, binary, identity = data['pid'], data['binary'], data['identity']
        if not isinstance(identity, str) or len(identity) != 64:
            return False
        if _process_identity(pid, binary) != identity:
            # Dead/replaced PIDs no longer belong to us.
            marker.unlink(missing_ok=True)
            return False
        store = Store(directory)
        state = store.try_read()
        if state is None:
            return False
        now = time.time()
        channels = {c['id']: c for c in state['channels']}
        for job in state['jobs']:
            if (job.get('status') in ('queued', 'starting', 'recording') and
                    job.get('start', now + 10) <= now + 5 and job.get('end', 0) > now and
                    ace_request_params(channels.get(job.get('channel_id'), {}).get('stream', '')) is not None):
                return False
        base = local_api_address(address)
        with urlopen(base + '/streams', timeout=0.75) as response:
            if response.status != 200:
                return False
            payload = response.read(32769)
        if len(payload) > 32768 or json.loads(payload).get('streams') != []:
            return False
        # Recheck to prevent terminating a recycled PID after network I/O.
        if _process_identity(pid, binary) != identity:
            marker.unlink(missing_ok=True)
            return False
        os.kill(pid, signal.SIGTERM)
        marker.unlink(missing_ok=True)
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError, URLError,
            HTTPError, TimeoutError):
        return False


def stop_idle_owned_daemon(address='http://127.0.0.1:6878'):
    """Release only our own helper after all shared media sessions end.

    The detached recorder and GUI can use the same native Outpace daemon.
    Terminating it as soon as one timer ends would interrupt a second viewer.
    Fail closed when the API is unavailable, malformed, or reports any
    active stream; /streams is explicitly a status-only API.
    """
    with _PROCESS_LOCK:
        if _OWNED_PROCESS is None:
            return False
    try:
        base=local_api_address(address)
        with urlopen(base+'/streams',timeout=0.75) as response:
            if response.status!=200:
                return False
            payload=response.read(32769)
        if len(payload)>32768:
            return False
        sessions=json.loads(payload).get('streams')
        if not isinstance(sessions,list) or sessions:
            return False
    except (URLError,HTTPError,OSError,ValueError,TypeError,AttributeError,TimeoutError):
        return False
    return stop_owned_daemon(allow_restart=True)


def packaged_binary():
    """Only trust the compiled application's own private Outpace binary."""
    if sys.platform != 'darwin' and not sys.platform.startswith('linux'):
        return None
    if not hasattr(sys, '_MEIPASS'):
        return None
    root = Path(sys._MEIPASS)
    candidate = root / 'outpace' / 'outpace'
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    return None


def local_api_address(address):
    parsed = urlsplit(address)
    if (parsed.scheme != 'http' or parsed.hostname not in LOCAL_HOSTS or
            parsed.username is not None or parsed.password is not None or
            parsed.path not in ('', '/') or parsed.query or parsed.fragment or
            parsed.port != 6878):
        raise RuntimeError('Bundled Outpace requires local http://127.0.0.1:6878. '
                           'A separately configured remote Ace engine remains connect-only.')
    return 'http://127.0.0.1:6878'


def api_ready(address, timeout=1):
    """Check both Outpace-native routes, not merely whether a port is open."""
    try:
        base = local_api_address(address)
        with urlopen(base + '/healthz', timeout=timeout) as response:
            if response.status != 200 or response.read(24).strip() != b'ok':
                return False
        with urlopen(base + '/networks', timeout=timeout) as response:
            if response.status != 200:
                return False
            networks = json.loads(response.read(1024)).get('networks', [])
        return isinstance(networks, list) and 'ace' in networks
    except (URLError, HTTPError, OSError, TimeoutError, ValueError, TypeError, AttributeError):
        return False


def playback_url(stream, address):
    """Use the supported native stream route; avoid experimental /ace/* APIs.

    An unrecognised selector fails closed. The pinned Outpace v0.2.0 native
    API resolves content IDs as cid:<id> and accepts bare 40-hex infohashes
    for live streams using default live geometry. This differs from Outpace
    main (which requires a verified descriptor for bare infohashes).
    """
    from .core import ace_request_params, http_url
    base = local_api_address(address)
    params = ace_request_params(stream)
    if not params:
        raise RuntimeError('Selected channel does not contain a supported Ace content ID.')
    if 'id' in params and re.fullmatch(r'[a-fA-F0-9]{40}', params['id']):
        identifier = 'cid:' + params['id']
    elif 'infohash' in params and re.fullmatch(r'[a-fA-F0-9]{40}', params['infohash']):
        identifier = params['infohash']
    else:
        raise RuntimeError('Outpace native playback needs a 40-character content ID or '
                           'a valid 40-character infohash for the pinned v0.2.0 engine.')
    return http_url(base + '/streams/ace/' + quote(identifier, safe=':'))


def ensure_ready(address, startup_seconds=25):
    global _OWNED_PROCESS, _OWNED_IDENTITY, _OWNED_BINARY
    base = local_api_address(address)
    with _PROCESS_LOCK:
        if _SHUTTING_DOWN:
            raise RuntimeError('DizyTV is closing; no new Outpace helper may start')
    if api_ready(base):
        return 'connected'
    # Never try to install or replace software behind an unfamiliar local
    # service. Also refuse to launch if the installed bundle is incomplete.
    try:
        with socket.create_connection(('127.0.0.1', 6878), timeout=0.3):
            raise RuntimeError('Another application owns port 6878. Stop that service '
                               'or configure a different remote engine.')
    except (ConnectionRefusedError, TimeoutError, socket.timeout):
        pass
    except OSError:
        pass
    binary = packaged_binary()
    if binary is None:
        raise RuntimeError('The packaged macOS/Linux Outpace binary is missing. '
                           'Install a verified DizyTV PKG containing Outpace.')
    environment = dict(os.environ)
    environment['OUTPACE_BIND'] = '127.0.0.1:6878'
    environment['OUTPACE_RTMP_BIND'] = '127.0.0.1:1935'
    # No unsolicited incoming seeding/listening, no network port mapping.
    # Outbound P2P transfers are initiated only when a channel is selected.
    environment['OUTPACE_ENABLE_INBOUND'] = '0'
    environment['OUTPACE_ENABLE_PORT_MAPPING'] = '0'
    environment['OUTPACE_EXPERIMENTAL_ACE_COMPAT'] = '0'
    process = subprocess.Popen([str(binary), 'serve'],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, close_fds=True,
                               cwd=str(binary.parent), env=environment)
    with _PROCESS_LOCK:
        closing = _SHUTTING_DOWN
        if not closing:
            _OWNED_PROCESS = process
    if closing:
        process.terminate()
        raise RuntimeError('DizyTV closed while starting the Outpace helper')
    deadline = time.monotonic() + startup_seconds
    while time.monotonic() < deadline:
        if api_ready(base):
            identity = _process_identity(process.pid, str(binary))
            with _PROCESS_LOCK:
                if _OWNED_PROCESS is process:
                    _OWNED_IDENTITY = identity
                    _OWNED_BINARY = str(binary)
            return 'started'
        if process.poll() is not None:
            with _PROCESS_LOCK:
                if _OWNED_PROCESS is process:
                    _OWNED_PROCESS = None
                    _OWNED_IDENTITY = None
                    _OWNED_BINARY = None
            raise RuntimeError('Packaged Outpace stopped during startup. '
                               'Inspect macOS permissions and the daemon logs.')
        time.sleep(0.35)
    # Only stop the helper created by this request; never touch a prior
    # instance or an unrelated localhost service.
    process.terminate()
    with _PROCESS_LOCK:
        if _OWNED_PROCESS is process:
            _OWNED_PROCESS = None
            _OWNED_IDENTITY = None
            _OWNED_BINARY = None
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
    raise RuntimeError('Outpace started but its private localhost API did not become ready.')
