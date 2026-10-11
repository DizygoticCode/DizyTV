"""Detached desktop recorder: one worker/device, UTC jobs, original MPEG-TS."""
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import Request, build_opener

from .core import safe_filename, stream_url, ACTIVE
from .network import SafeRedirect
from .storage import Store, file_lock


def record_stream(url, directory, title, end, reserve=1073741824, cancel=lambda:False,
                  progress=lambda *_:None):
    result = {'status':'failed', 'bytes':0, 'error':'', 'path':''}
    outpath = None
    try:
        folder = Path(directory)
        if not directory or not folder.is_dir():
            raise ValueError('Choose an available recording folder in Settings')
        if shutil.disk_usage(folder).free <= reserve:
            raise ValueError('Free space is below the configured reserve')
        name = safe_filename(title, int(time.time()))
        outpath = folder/(Path(name).stem + '_' + uuid.uuid4().hex[:8] + '.ts.part')
        request = Request(url, headers={'User-Agent':'DizyTV/0.1'})
        with build_opener(SafeRedirect).open(request, timeout=10) as response, outpath.open('xb') as output:
            content = response.headers.get('Content-Type','').lower()
            if any(kind in content for kind in ('mpegurl','text/','json','html')):
                raise ValueError('Recording requires a direct MPEG-TS stream; use the Ace engine output')
            started = False
            last_progress = 0
            while time.time() < end:
                if cancel():
                    raise ValueError('Recording stopped by user')
                if shutil.disk_usage(folder).free <= reserve:
                    raise ValueError('Recording stopped at the free-space reserve')
                chunk = response.read1(65536)
                if not chunk:
                    raise ValueError('Stream ended before the recording timer')
                if not started:
                    if chunk[0] != 0x47:
                        raise ValueError('The source did not return MPEG-TS packets')
                    started = True
                output.write(chunk)
                result['bytes'] += len(chunk)
                if time.time() - last_progress > 1:
                    progress(result['bytes'], str(outpath)); last_progress = time.time()
            output.flush(); os.fsync(output.fileno())
        result['status'] = 'completed' if result['bytes'] else 'failed'
    except Exception as exc:
        result['error'] = str(exc)[:1024]
        result['status'] = 'partial' if result['bytes'] else 'failed'
    finally:
        if outpath and outpath.exists():
            if result['bytes']:
                final = outpath.with_suffix('')
                try:
                    outpath.rename(final); result['path'] = str(final)
                except OSError:
                    result['path'] = str(outpath)
            else:
                outpath.unlink(missing_ok=True)
    return result


def due_jobs(store, now=None):
    now = int(time.time()) if now is None else now
    def expire(state):
        for job in state['jobs']:
            if job['status'] in ACTIVE and job['end'] <= now:
                job['status'] = 'partial' if job.get('bytes',0) else 'missed'
                job['error'] = 'Timer expired while recorder was unavailable'
    state = store.update(expire)
    return sorted([j for j in state['jobs'] if j['status'] in ACTIVE and j['start'] <= now < j['end']], key=lambda j:j['start'])


def update_job(store, job_id, values):
    def change(state):
        for job in state['jobs']:
            if job['id'] == job_id:
                job.update(values)
    store.update(change)


def worker(directory=None):
    store = Store(directory)
    try:
        with file_lock(store.directory/'worker.lock', blocking=False):
            while True:
                ready = due_jobs(store)
                if ready:
                    job = ready[0]
                    state = store.read()
                    channel = next((c for c in state['channels'] if c['id'] == job['channel_id']),None)
                    if not channel:
                        update_job(store,job['id'],{'status':'failed','error':'Channel is missing; refresh or restore the catalogue'})
                        continue
                    late = time.time() - job['start'] > 5 or job['status'] in ('starting','recording')
                    update_job(store,job['id'],{'status':'recording','error':''})
                    def cancelled():
                        return not any(j['id']==job['id'] and j['status']=='recording' for j in store.read()['jobs'])
                    result = record_stream(stream_url(channel['stream'],state['settings']['engine_url']),
                                           state['settings']['recording_dir'],job['title'],job['end'],
                                           state['settings']['reserve_bytes'],cancelled,
                                           lambda size,path:update_job(store,job['id'],{'bytes':size,'path':path}))
                    if late and result['status']=='completed':
                        result.update(status='partial',error='Recording started late or resumed after interruption')
                    update_job(store,job['id'],result)
                time.sleep(1)
    except (BlockingIOError, PermissionError):
        return


def ensure_worker(directory=None):
    store = Store(directory)
    args = [sys.executable]
    if not getattr(sys,'frozen',False):
        args += ['-m','dizytv']
    args += ['--worker','--data-dir',str(store.directory)]
    options = {'stdin':subprocess.DEVNULL, 'close_fds':True}
    if os.name == 'nt':
        options['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options['start_new_session'] = True
    with (store.directory/'recorder.log').open('ab') as log:
        return subprocess.Popen(args,stdout=log,stderr=log,**options)
