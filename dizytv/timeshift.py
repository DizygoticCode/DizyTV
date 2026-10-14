"""Opt-in device-local rolling MPEG-TS timeshift for HTTP TS and clear HLS/TS.

A bounded short-lived cache is NOT a permanent recording, and never modifies
the original source URLs, channel IDs, or scheduled recording jobs. Loopback
serving enables libVLC to play cached MPEG-TS segments from an HLS playlist.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, build_opener
import math
import os
import re
import secrets
import shutil
import threading
import time

from .core import http_url
from .network import SafeRedirect

USER_AGENT = 'DizyTV/0.1'
MAX_SEGMENT_BYTES = 16 * 1024 * 1024
PACKET = 188
MIN_RESERVE = 1024**3
SEGMENT_SECONDS = 4.0


@dataclass(frozen=True)
class Segment:
    seq: int
    created: float
    duration: float
    size: int
    path: Path


class RollingWindow:
    """Atomic, byte/time/disk-space-capped segment spool. Only owns its own files."""

    def __init__(self, directory, minutes=30, max_bytes=4 * 1024**3,
                 reserve_bytes=MIN_RESERVE, clock=time.time, free=None):
        if type(minutes) is not int or not 1 <= minutes <= 240:
            raise ValueError('Timeshift duration must be 1–240 minutes')
        if type(max_bytes) is not int or not 256 * 1024**2 <= max_bytes <= 32 * 1024**3:
            raise ValueError('Timeshift storage limit must be between 256 MiB and 32 GiB')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.minutes = minutes
        self.max_bytes = max_bytes
        self.reserve_bytes = max(MIN_RESERVE, reserve_bytes)
        self.clock = clock
        self.free = free or (lambda: shutil.disk_usage(self.directory).free)
        self.lock = threading.RLock()
        self.entries = deque()
        self.total = 0
        self.counter = 0

    def _evict(self):
        now = self.clock()
        while self.entries and (self.total > self.max_bytes or
                now - self.entries[0].created > self.minutes * 60 or
                self.free() < self.reserve_bytes + 2 * MAX_SEGMENT_BYTES):
            item = self.entries.popleft()
            self.total -= item.size
            item.path.unlink(missing_ok=True)

    def append(self, data: bytes, duration: float):
        if not data or len(data) > MAX_SEGMENT_BYTES:
            raise ValueError('Timeshift segment is empty or too large')
        if not 0.1 <= duration <= 30:
            raise ValueError('Invalid MPEG-TS segment duration')
        if self.free() < self.reserve_bytes + len(data) + 2 * MAX_SEGMENT_BYTES:
            with self.lock:
                self._evict()
            if self.free() < self.reserve_bytes + len(data) + 2 * MAX_SEGMENT_BYTES:
                raise OSError('Timeshift stopped: free disk space reserve reached')
        with self.lock:
            seq = self.counter
            self.counter += 1
            tmp = self.directory / f'{seq:012d}.part'
            target = self.directory / f'{seq:012d}.ts'
            try:
                with tmp.open('xb') as output:
                    output.write(data)
                    output.flush()
                os.replace(tmp, target)
            finally:
                tmp.unlink(missing_ok=True)
            item = Segment(seq, self.clock(), duration, len(data), target)
            self.entries.append(item)
            self.total += len(data)
            self._evict()
            return item

    def snapshot(self):
        with self.lock:
            self._evict()
            return list(self.entries)

    def latest_seconds(self):
        return sum(item.duration for item in self.snapshot())

    def starting_seq(self, seconds_back: float):
        entries = self.snapshot()
        if not entries:
            return None
        remaining = max(0, seconds_back)
        for item in reversed(entries):
            remaining -= item.duration
            if remaining <= 0:
                return item.seq
        return entries[0].seq

    def playlist(self, from_seq=None):
        entries = self.snapshot()
        if from_seq is None:
            # Join near live; use a replay URL to start farther back.
            # A 3-fragment live playlist gives VLC almost no margin when
            # fetching over loopback and may stall as fragments expire.
            entries = entries[-12:]
        else:
            entries = [entry for entry in entries if entry.seq >= from_seq]
        if not entries:
            return ''
        target_duration = max(1, math.ceil(max(e.duration for e in entries)))
        lines = ['#EXTM3U', '#EXT-X-VERSION:3',
                 f'#EXT-X-TARGETDURATION:{target_duration}',
                 f'#EXT-X-MEDIA-SEQUENCE:{entries[0].seq}']
        if from_seq is not None:
            lines.append('#EXT-X-START:TIME-OFFSET=0,PRECISE=YES')
        for item in entries:
            lines += [f'#EXTINF:{item.duration:.3f},', f's/{item.seq}.ts']
        return '\n'.join(lines) + '\n'

    def file_for(self, seq):
        with self.lock:
            for item in self.entries:
                if item.seq == seq:
                    return item.path
        return None

    def close(self):
        with self.lock:
            while self.entries:
                self.entries.popleft().path.unlink(missing_ok=True)
            self.total = 0
        # Never recursively delete arbitrary data outside our session directory.
        try:
            self.directory.rmdir()
        except OSError:
            pass


def parse_hls(body, base_url):
    """Return media TS segment URLs, rejecting encrypted/fMP4 and unsupported HLS."""
    if not body.lstrip('\ufeff').startswith('#EXTM3U'):
        raise ValueError('Not an HLS playlist')
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if any(x.startswith('#EXT-X-KEY:') and 'METHOD=NONE' not in x for x in lines):
        raise ValueError('Protected/encrypted HLS is not supported by local timeshift')
    if any(x.startswith('#EXT-X-MAP:') for x in lines):
        raise ValueError('Fragmented-MP4 HLS is not yet supported by local timeshift')
    if '#EXT-X-STREAM-INF' in body:
        for i, line in enumerate(lines[:-1]):
            if line.startswith('#EXT-X-STREAM-INF') and not lines[i+1].startswith('#'):
                return 'variant', [(urljoin(base_url, lines[i+1]), 0)]
        raise ValueError('HLS master playlist has no playable variant')
    result = []
    duration = 4.0
    for line in lines:
        if line.startswith('#EXTINF:'):
            try:
                duration = float(line[8:].split(',', 1)[0])
            except ValueError as exc:
                raise ValueError('Invalid HLS segment duration') from exc
        elif not line.startswith('#'):
            url = http_url(urljoin(base_url, line))
            result.append((url, min(30., max(.1, duration))))
    return 'segments', result


class RollingTimeshift:
    """Captures one selected channel; serves only to 127.0.0.1 with random URL token."""

    def __init__(self, source, directory, minutes=30, max_bytes=4*1024**3,
                 reserve_bytes=MIN_RESERVE, session_id=None):
        self.source = http_url(source)
        self.token = session_id or secrets.token_urlsafe(24)
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,90}',self.token):
            raise ValueError('Invalid local timeshift session token')
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        # Crash leftovers: only files matching our segment naming convention
        # inside a stale session directory, never arbitrary user recordings.
        for stale in root.glob('session-*'):
            try:
                if not stale.is_dir() or stale.is_symlink() or time.time()-stale.stat().st_mtime<86400:
                    continue
                for child in stale.iterdir():
                    if (child.is_file() and not child.is_symlink() and
                        re.fullmatch(r'\d{12}\.(ts|part)',child.name)):
                        child.unlink()
                stale.rmdir()
            except OSError:
                pass
        self.window = RollingWindow(root / ('session-' + self.token), minutes,
                                    max_bytes, reserve_bytes)
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.error = ''
        self._server = None
        self._server_thread = None
        self._capture_thread = None
        self._opened = False
        self._http = build_opener(SafeRedirect)

    def _request(self, url):
        return self._http.open(Request(http_url(url), headers={'User-Agent':USER_AGENT}), timeout=10)

    def _capture_hls(self, source):
        last = deque(maxlen=10000)
        known = set()
        while not self.stop_event.is_set():
            try:
                with self._request(source) as response:
                    data = response.read(2*1024*1024+1)
                    if len(data) > 2*1024*1024:
                        raise ValueError('HLS playlist exceeds 2 MiB')
                    endpoint = response.geturl()
                kind, urls = parse_hls(data.decode('utf-8-sig'), endpoint)
                if kind == 'variant':
                    source = urls[0][0]
                    continue
                for url, duration in urls:
                    if self.stop_event.is_set():
                        break
                    if url in known:
                        continue
                    with self._request(url) as response:
                        chunk = response.read(MAX_SEGMENT_BYTES+1)
                    if not chunk or len(chunk)>MAX_SEGMENT_BYTES:
                        raise ValueError('HLS segment missing or exceeds 16 MiB')
                    if chunk[0] != 0x47:
                        raise ValueError('Only MPEG-TS HLS segments can be cached')
                    self.window.append(chunk, duration)
                    known.add(url); last.append(url)
                    if len(known)>10000:
                        known = set(last)
                    self.ready.set()
                self.stop_event.wait(1.5)
            except (OSError, ValueError, UnicodeError) as exc:
                self.error = str(exc)[:250]
                if not self.ready.is_set():
                    self.ready.set()
                    return
                self.stop_event.wait(2)

    def _capture_ts(self):
        while not self.stop_event.is_set():
            try:
                with self._request(self.source) as response:
                    content = response.headers.get('Content-Type', '').lower()
                    if 'mpegurl' in content or urlparse(response.geturl()).path.lower().endswith('.m3u8'):
                        self._capture_hls(response.geturl())
                        return
                    pieces = []
                    size = 0
                    started = time.monotonic()
                    while not self.stop_event.is_set():
                        block = response.read(PACKET*1024)
                        if not block:
                            break
                        if not pieces and block[0] != 0x47:
                            raise ValueError('Stream is not a direct MPEG-TS feed')
                        pieces.append(block)
                        size += len(block)
                        elapsed = time.monotonic() - started
                        if elapsed >= SEGMENT_SECONDS or size>=8*1024*1024:
                            payload=b''.join(pieces)
                            usable=len(payload)//PACKET*PACKET
                            if usable:
                                self.window.append(payload[:usable],max(.1,elapsed))
                                self.ready.set()
                            remainder=payload[usable:]
                            pieces=[remainder] if remainder else []
                            size=len(remainder)
                            started=time.monotonic()
                    # Short reconnecting TS streams still commit complete packets.
                    if pieces and not self.stop_event.is_set():
                        payload=b''.join(pieces)
                        usable=len(payload)//PACKET*PACKET
                        if usable:
                            self.window.append(payload[:usable],max(.1,time.monotonic()-started))
                            self.ready.set()
            except (OSError, ValueError) as exc:
                self.error = str(exc)[:250]
                if not self.ready.is_set():
                    self.ready.set()
                    return
                self.stop_event.wait(2)

    def _capture(self):
        try:
            if urlparse(self.source).path.lower().endswith('.m3u8'):
                self._capture_hls(self.source)
            else:
                self._capture_ts()
        except Exception as exc:
            self.error = str(exc)[:250]
            self.ready.set()

    def _handler(self):
        session = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                prefix = '/' + session.token + '/'
                if not parsed.path.startswith(prefix):
                    self.send_error(404)
                    return
                path = parsed.path[len(prefix):]
                if path in ('live.m3u8', 'replay.m3u8'):
                    since = None
                    if path == 'replay.m3u8':
                        raw = parse_qs(parsed.query).get('seq', [])
                        if len(raw) != 1 or not raw[0].isdigit():
                            self.send_error(400)
                            return
                        since = int(raw[0])
                    playlist = session.window.playlist(since)
                    if not playlist:
                        self.send_error(503)
                        return
                    payload = playlist.encode('ascii')
                    mime = 'application/vnd.apple.mpegurl'
                elif path.startswith('s/') and path.endswith('.ts'):
                    raw = path[2:-3]
                    if not raw.isdigit():
                        self.send_error(404)
                        return
                    file = session.window.file_for(int(raw))
                    if not file:
                        self.send_error(410)
                        return
                    try:
                        payload = file.read_bytes()
                    except OSError:
                        self.send_error(410)
                        return
                    mime = 'video/mp2t'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type',mime)
                self.send_header('Cache-Control','no-store')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *_):
                pass
        return Handler

    @property
    def base_url(self):
        if not self._server:
            raise RuntimeError('Timeshift is not started')
        return f'http://127.0.0.1:{self._server.server_port}/{self.token}/'

    def live_url(self):
        return self.base_url + 'live.m3u8'

    def replay_url(self, seconds_back):
        seq = self.window.starting_seq(seconds_back)
        if seq is None:
            raise RuntimeError('No cached programmes are ready for rewind')
        return self.base_url + f'replay.m3u8?seq={seq}'

    def start(self, timeout=18):
        if self.stop_event.is_set():
            raise RuntimeError('Timeshift session was already closed')
        if self._opened:
            raise RuntimeError('Timeshift already running')
        self._opened = True
        try:
            self._server = ThreadingHTTPServer(('127.0.0.1',0), self._handler())
            self._server_thread = threading.Thread(target=self._server.serve_forever,daemon=True)
            self._server_thread.start()
            self._capture_thread = threading.Thread(target=self._capture,daemon=True)
            self._capture_thread.start()
            if not self.ready.wait(timeout) or not self.window.snapshot():
                raise RuntimeError(self.error or 'This channel did not provide usable MPEG-TS/HLS segments')
            return self.live_url()
        except Exception:
            self.close()
            raise

    def close(self):
        self.stop_event.set()
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._capture_thread and self._capture_thread is not threading.current_thread():
            self._capture_thread.join(timeout=1)
        self.window.close()
