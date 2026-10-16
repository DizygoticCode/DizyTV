"""Opt-in desktop UI watchdog, local only; never sends telemetry.

Enable with Tools > Log UI freezes locally or DIZYTV_UI_DIAGNOSTICS=1.
When the Qt main thread does not deliver a heartbeat for eight seconds, an
independent daemon samples the Python main-thread stack. This can distinguish
application-lock/IO/Python freezes from ordinary libVLC picture buffering.
No stream URLs, playlist data, credentials, or mutable locals are logged.
Stack source paths can disclose a Windows account directory: review before
sharing a diagnostic log publicly.
"""
import os
from pathlib import Path
import sys
import threading
import time
import traceback


class UiHangMonitor:
    def __init__(self, directory, threshold=8, interval=1, clock=None):
        self.directory=Path(directory)
        self.threshold=threshold
        self.interval=interval
        self.clock=clock or time.monotonic
        self._ui_ident=threading.get_ident()
        self._heartbeat_at=self.clock()
        self._flagged=False
        self._stop=threading.Event()
        self._thread=None
        self.path=self.directory/'ui-hangs.log'

    def heartbeat(self):
        """Called only by the Qt event loop (a stopped UI cannot call this)."""
        self._heartbeat_at=self.clock()
        self._flagged=False

    def poll_once(self):
        age=self.clock()-self._heartbeat_at
        if age<self.threshold or self._flagged:
            return False
        self._flagged=True
        self._write_stack(age)
        return True

    def _write_stack(self, age):
        try:
            frame=sys._current_frames().get(self._ui_ident)
            if frame is None:
                return
            stack=''.join(traceback.format_stack(frame,limit=36))
            message=(time.strftime('%Y-%m-%d %H:%M:%S')+
                     ' | DizyTV Qt UI no heartbeat for '+str(round(age,1))+' s'+
                     ' | PID '+str(os.getpid())+'\n'+stack+'\n')
            self.directory.mkdir(parents=True,exist_ok=True)
            if self.path.exists() and self.path.stat().st_size>1024*1024:
                # Bounded local evidence; never block Qt to rotate/write.
                previous=self.path.with_suffix('.previous.log')
                os.replace(self.path,previous)
            with self.path.open('a',encoding='utf-8') as output:
                output.write(message)
        except OSError:
            # Diagnostics must never take down video playback.
            pass

    def start(self):
        if self._thread is not None:
            return
        self._stop.clear()
        self._heartbeat_at=self.clock()
        self._thread=threading.Thread(target=self._run,name='dizytv-ui-hang-watch',
                                      daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.wait(self.interval):
            self.poll_once()

    def stop(self):
        self._stop.set()  # Never join a background diagnostic from the UI.
