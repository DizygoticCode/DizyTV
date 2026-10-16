"""One owner for native VLC calls; the Qt thread reads immutable snapshots.

Native VLC stop, state and track queries can wait on decoder locks. No caller
waits for this worker: commands use a fixed set of coalescing slots, and a new
play/stop invalidates pending media commands and their completion callbacks.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import os
import sys
import threading
import time

from PySide6.QtCore import QObject, Signal, Slot, Qt


_STATS = ('decoded_audio', 'decoded_video', 'displayed_pictures',
          'played_abuffers', 'lost_pictures', 'demux_bitrate', 'input_bitrate')
_COMMANDS = frozenset(('audio_set_volume', 'set_pause', 'set_time',
                       'set_xwindow', 'set_hwnd', 'set_nsobject',
                       'video_set_spu', 'video_set_subtitle_file'))
_GLOBAL = frozenset(('audio_set_volume', 'set_xwindow', 'set_hwnd', 'set_nsobject'))


@dataclass(frozen=True)
class PlayerResult:
    generation: int
    operation: str
    value: object = None
    error: str | None = None


@dataclass(frozen=True)
class _Command:
    generation: int
    serial: int
    key: str
    operation: str
    args: tuple
    callback: object = None


def _empty_snapshot(state='State.Stopped'):
    return dict(state=state, time=-1, length=-1, seekable=False, spu=-1,
                tracks=(), video_tracks=-1, size=None, stats=None, sampled_at=0.)


class _CachedMedia:
    def __init__(self, stats):
        self._stats = stats

    def get_stats(self, target):
        if self._stats is None:
            return False
        for key, value in self._stats.items():
            setattr(target, key, value)
        return True

    def release(self):
        pass


class AsyncPlayer(QObject):
    """GUI facade. All native handles, including retained media, stay in worker.

    Read methods have the old player names but return the most recent sample.
    Setters enqueue work; callers that need native acceptance use submit() or
    the subtitle helpers, whose callbacks run on this object's Qt thread.
    """
    _completed = Signal(object, object)

    def __init__(self, options=(), video_handle=0, volume=100, parent=None):
        super().__init__(parent)
        self._condition = threading.Condition()
        self._pending = OrderedDict()
        self._latest = {}
        self._generation = 0
        self._serial = 0
        self._closed = False
        self._snapshot = _empty_snapshot()
        self._options = tuple(options)
        self._video_handle = int(video_handle)
        self._volume = int(volume)
        self._native = None
        self._instance = None
        self._stats_factory = None
        self._completed.connect(self._deliver, Qt.QueuedConnection)
        self._thread = threading.Thread(target=self._run, name='DizyTV VLC', daemon=True)
        self._thread.start()

    @property
    def snapshot(self):
        with self._condition:
            result = dict(self._snapshot)
            if result['stats'] is not None:
                result['stats'] = dict(result['stats'])
            return result

    @property
    def generation(self):
        with self._condition:
            return self._generation

    def _enqueue(self, operation, args=(), callback=None, new_media=False):
        with self._condition:
            if self._closed:
                return None
            if new_media:
                self._generation += 1
                self._pending = OrderedDict((key, value) for key, value in
                                             self._pending.items() if key in _GLOBAL)
                self._snapshot = _empty_snapshot(
                    'State.Opening' if operation == 'play_url' else 'State.Stopped')
            self._serial += 1
            key = 'media' if new_media else ('video_output' if operation.startswith('set_')
                     and operation in _GLOBAL else operation)
            command = _Command(self._generation, self._serial, key,
                               operation, tuple(args), callback)
            self._latest[key] = command.serial
            self._pending[key] = command
            if operation == 'set_pause':
                self._snapshot = dict(self._snapshot, state=(
                    'State.Paused' if args[0] else 'State.Playing'))
            elif operation == 'set_time':
                self._snapshot = dict(self._snapshot, time=int(args[0]))
            self._condition.notify()
            return command.generation

    def play_url(self, url, options=(), subtitles_off=False, on_done=None):
        return self._enqueue('play_url', (str(url), tuple(options), bool(subtitles_off)),
                             on_done, new_media=True)

    def stop(self):
        return self._enqueue('stop', new_media=True)

    def submit(self, method, *args, on_done=None):
        if method not in _COMMANDS:
            raise ValueError('Unsupported player command: '+method)
        return self._enqueue(method, args, on_done)

    def set_subtitle(self, track, callback):
        return self.submit('video_set_spu', int(track),
                           on_done=lambda result: callback(result.value, result.error))

    def set_subtitle_file(self, path, callback):
        return self.submit('video_set_subtitle_file', str(path),
                           on_done=lambda result: callback(result.value, result.error))

    def audio_set_volume(self, value): self.submit('audio_set_volume', int(value))
    def set_pause(self, value): self.submit('set_pause', int(value))
    def set_time(self, value): self.submit('set_time', int(value))
    def set_xwindow(self, value): self.submit('set_xwindow', int(value))
    def set_hwnd(self, value): self.submit('set_hwnd', int(value))
    def set_nsobject(self, value): self.submit('set_nsobject', int(value))
    def video_set_spu(self, value): self.submit('video_set_spu', int(value))

    def _read(self, key):
        with self._condition:
            return self._snapshot[key]

    def get_state(self): return self._read('state')
    def get_time(self): return self._read('time')
    def get_length(self): return self._read('length')
    def is_seekable(self): return self._read('seekable')
    def video_get_spu(self): return self._read('spu')
    def video_get_spu_description(self): return self._read('tracks')
    def video_get_track_count(self): return self._read('video_tracks')
    def video_get_size(self, _index=0): return self._read('size')
    def get_media(self): return _CachedMedia(self._read('stats'))

    def shutdown(self):
        """Invalidate callbacks immediately; release natively without a GUI join."""
        with self._condition:
            self._closed = True
            self._generation += 1
            self._pending.clear()
            self._snapshot = _empty_snapshot()
            self._condition.notify()

    release = shutdown

    def _current(self, command):
        with self._condition:
            return (not self._closed and self._latest.get(command.key) == command.serial
                    and (command.operation in _GLOBAL or command.generation == self._generation))

    @Slot(object, object)
    def _deliver(self, command, result):
        if self._current(command) and command.callback is not None:
            command.callback(result)

    def _ensure_native(self):
        if self._native is not None:
            return
        # Package verification/import and instance setup can also be slow.
        from .media_runtime import configure_private_vlc
        configure_private_vlc()
        import vlc
        self._instance = vlc.Instance(*self._options)
        self._native = self._instance.media_player_new()
        self._stats_factory = vlc.MediaStats
        self._native.audio_set_volume(self._volume)
        method = ('set_nsobject' if sys.platform == 'darwin' else
                  'set_hwnd' if os.name == 'nt' else 'set_xwindow')
        getattr(self._native, method)(self._video_handle)

    def _execute(self, command):
        if not self._current(command):
            return
        value = None
        error = None
        try:
            self._ensure_native()
            if not self._current(command):
                return
            if command.operation == 'play_url':
                url, options, subtitles_off = command.args
                self._native.stop()
                if not self._current(command):
                    return
                media = self._instance.media_new(url)
                try:
                    for option in options:
                        media.add_option(option)
                    if not self._current(command):
                        return
                    self._native.set_media(media)
                finally:
                    media.release()
                if not self._current(command):
                    return
                value = self._native.play()
                if value == -1:
                    raise RuntimeError('libVLC could not start playback')
                if subtitles_off and self._current(command):
                    self._native.video_set_spu(-1)
            else:
                value = getattr(self._native, command.operation)(*command.args)
        except Exception as exc:
            error = str(exc)
            if command.operation == 'play_url':
                with self._condition:
                    if self._current(command):
                        self._snapshot = _empty_snapshot('State.Error')
        if command.callback is not None and self._current(command):
            try:
                self._completed.emit(command, PlayerResult(
                    command.generation, command.operation, value, error))
            except RuntimeError:
                # The owning Qt window may already have been destroyed.
                pass

    def _poll(self):
        with self._condition:
            if self._closed or self._pending or self._native is None:
                return
            generation, serial = self._generation, self._serial
            sample = dict(self._snapshot)

        def interrupted():
            with self._condition:
                return self._closed or self._generation != generation or self._serial != serial

        getters = (('state', 'get_state', ()), ('time', 'get_time', ()),
                   ('length', 'get_length', ()), ('seekable', 'is_seekable', ()),
                   ('spu', 'video_get_spu', ()), ('tracks', 'video_get_spu_description', ()),
                   ('video_tracks', 'video_get_track_count', ()), ('size', 'video_get_size', (0,)))
        for key, method, args in getters:
            if interrupted():
                return
            try:
                value = getattr(self._native, method)(*args)
                if key == 'state': value = str(value)
                if key == 'tracks': value = tuple(value or ())
                sample[key] = value
            except (AttributeError, TypeError, RuntimeError, OSError):
                sample[key] = _empty_snapshot()[key]
        if interrupted():
            return
        media = None
        sample['stats'] = None
        try:
            media = self._native.get_media()
            if media is not None and not interrupted():
                counters = self._stats_factory()
                if media.get_stats(counters):
                    sample['stats'] = {key: getattr(counters, key, 0) for key in _STATS}
        except (AttributeError, TypeError, RuntimeError, OSError):
            pass
        finally:
            if media is not None:
                media.release()
        with self._condition:
            if not interrupted():
                sample['sampled_at'] = time.monotonic()
                self._snapshot = sample

    def _run(self):
        try:
            while True:
                with self._condition:
                    if self._closed:
                        return
                    command = self._pending.pop('media', None)
                    if command is None and self._pending:
                        _, command = self._pending.popitem(last=False)
                    if command is None:
                        self._condition.wait(.5)
                        if self._closed:
                            return
                        if self._pending:
                            continue
                if command is not None:
                    self._execute(command)
                self._poll()
        finally:
            # Sequential cleanup after an in-flight native call returns.
            for target, method in ((self._native, 'stop'), (self._native, 'release'),
                                   (self._instance, 'release')):
                if target is not None:
                    try:
                        getattr(target, method)()
                    except Exception:
                        pass
