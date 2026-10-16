"""Packaged macOS Outpace daemon: a separate AGPL-3.0-or-later program.

DizyTV never downloads an arbitrary executable from a playlist, exposes the
HTTP API on a LAN interface, or starts a bundled daemon for a remote endpoint.
Outpace's native API is used; its experimental Ace-compat API is not enabled.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import urlopen


LOCAL_HOSTS = frozenset(('localhost', '127.0.0.1', '::1'))


def packaged_binary():
    """Only trust the compiled application's own private Outpace binary."""
    if sys.platform != 'darwin' or not hasattr(sys, '_MEIPASS'):
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

    An unrecognised selector fails closed. Outpace's native API resolves
    content IDs as cid:<id>. An infohash works only if Outpace already holds
    a verified descriptor for it.
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
                           'a verified transport descriptor. This channel cannot use its native route.')
    return http_url(base + '/streams/ace/' + quote(identifier, safe=':'))


def ensure_ready(address, startup_seconds=25):
    base = local_api_address(address)
    if api_ready(base):
        return 'connected'
    # Never try to install or replace software behind an unfamiliar local
    # service. Also refuse to launch if the installed bundle is incomplete.
    import socket
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
        raise RuntimeError('The packaged macOS Outpace binary is missing. '
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
    deadline = time.monotonic() + startup_seconds
    while time.monotonic() < deadline:
        if api_ready(base):
            return 'started'
        if process.poll() is not None:
            raise RuntimeError('Packaged Outpace stopped during startup. '
                               'Inspect macOS permissions and the daemon logs.')
        time.sleep(0.35)
    raise RuntimeError('Outpace started but its private localhost API did not become ready.')
