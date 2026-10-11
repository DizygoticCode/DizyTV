"""Atomic, locked device state shared with the detached desktop recorder."""
import copy
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from .core import default_state, validate_state, MAX_BACKUP

_mutex = threading.RLock()


def data_directory():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData'/'Local'))/'DizyTV'
    if __import__('sys').platform == 'darwin':
        return Path.home()/'Library'/'Application Support'/'DizyTV'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local'/'share'))/'DizyTV'


@contextmanager
def file_lock(path, blocking=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if handle.tell() == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield
    finally:
        handle.close()  # Closing releases an OS lock, including on process death.


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, ensure_ascii=False)
            out.flush(); os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else data_directory()
        self.path = self.directory/'state.json'
        self.directory.mkdir(parents=True, exist_ok=True)

    def _read(self):
        if not self.path.exists():
            return default_state()
        if self.path.stat().st_size > MAX_BACKUP:
            raise ValueError('Device state is too large')
        with self.path.open(encoding='utf-8') as source:
            return validate_state(json.load(source))

    def read(self):
        with _mutex, file_lock(self.directory/'state.lock'):
            return self._read()

    def update(self, change):
        with _mutex, file_lock(self.directory/'state.lock'):
            state = self._read()
            change(state)
            validate_state(state)
            atomic_json(self.path, state)
            return copy.deepcopy(state)

    def replace(self, value):
        validate_state(value)
        return self.update(lambda state: (state.clear(), state.update(copy.deepcopy(value))))
