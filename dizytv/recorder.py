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

from .core import safe_filename, stream_url, ace_request_params, ACTIVE
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
        if cancel():
            raise ValueError('Recording stopped by user')
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
        result['status'] = 'partial' if result['bytes'] else ('cancelled' if 'stopped by user' in result['error'] else 'failed')
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


def claim_job(store, job_id, now=None):
    """Check and claim the current job in the same locked state transaction."""
    now=int(time.time()) if now is None else now
    accepted=[]
    def change(state):
        for job in state['jobs']:
            if job['id']!=job_id or job['status'] not in ACTIVE or not job['start']<=now<job['end']:
                continue
            job['resume_late']=now-job['start']>5 or job['status'] in ('starting','recording')
            previous=job.get('path','')
            if previous and Path(previous).is_file():
                segments=job.setdefault('segments',[])
                if not any(s.get('path')==previous for s in segments):
                    segments.append({'path':previous,'bytes':Path(previous).stat().st_size,'status':'partial'})
            job.update(status='recording',path='',bytes=sum(s.get('bytes',0) for s in job.get('segments',[])),error='')
            accepted.append(job['id'])
    state=store.update(change)
    if not accepted:
        return None
    return state, next(j for j in state['jobs'] if j['id']==job_id)


def finish_job(store,job_id,result):
    def change(state):
        for job in state['jobs']:
            if job['id']!=job_id:continue
            prior=sum(s.get('bytes',0) for s in job.get('segments',[]))
            finished=dict(result,bytes=prior+result.get('bytes',0))
            if prior or job.get('resume_late') and finished['status']=='completed':
                finished['status']='partial' if finished['bytes'] else finished['status']
                finished['error']=finished.get('error') or 'Recording resumed after interruption or started late'
            if job['status']=='cancelled' and not finished['bytes']:
                finished.update(status='cancelled',error='Recording stopped by user')
            job.update(finished)
    store.update(change)


def recording_playback_url(channel, settings, directory=None):
    """Prepare a direct recorder URL using the *selected* local engine API.

    Outpace deliberately disables Ace's experimental /ace/getstream endpoint.
    The recorder must use the same native playback URL as DizyTV itself.
    A future queued timer starts its own trusted engine on demand; it does not
    depend on a GUI window or a daemon retained when that window closes.
    """
    source=channel['stream']
    if ace_request_params(source) is None:
        return stream_url(source,settings['engine_url'])
    from .engine import ensure_ready, start_playback_session
    address=settings['engine_url']
    ensure_ready(address,executable_path=settings.get('engine_executable',''),directory=directory)
    return start_playback_session(source,address,directory=directory)


def release_recorder_outpace(directory=None):
    """Stop only an Outpace child this *worker* started, not external engines."""
    if sys.platform=='darwin' or sys.platform.startswith('linux'):
        from .outpace import stop_idle_owned_daemon, reap_handed_off_daemon
        stop_idle_owned_daemon(directory=directory)
        if directory is not None:
            reap_handed_off_daemon(directory)


def worker(directory=None):
    store = Store(directory)
    try:
        with file_lock(store.directory/'worker.lock', blocking=False):
            while True:
                ready = due_jobs(store)
                if ready:
                    claimed=claim_job(store,ready[0]['id'])
                    if claimed is None:continue
                    state,job=claimed
                    channel = next((c for c in state['channels'] if c['id'] == job['channel_id']),None)
                    if not channel:
                        finish_job(store,job['id'],{'status':'failed','bytes':0,'path':'','error':'Channel is missing; refresh or restore the catalogue'})
                        continue
                    prior=sum(s.get('bytes',0) for s in job.get('segments',[]))
                    def cancelled():
                        return not any(j['id']==job['id'] and j['status']=='recording' for j in store.read()['jobs'])
                    try:
                        target=recording_playback_url(channel,state['settings'],directory=store.directory)
                        result = record_stream(
                            target,state['settings']['recording_dir'],job['title'],job['end'],
                            state['settings']['reserve_bytes'],cancelled,
                            lambda size,path:update_job(store,job['id'],
                                {'bytes':prior+size,'path':path}))
                    except (RuntimeError,ValueError,OSError) as exc:
                        # A missing/unsupported Ace engine must fail this job,
                        # not terminate the long-running detached recorder.
                        result={'status':'failed','bytes':0,'path':'',
                                'error':type(exc).__name__+': '+str(exc)[:400]}
                    finally:
                        if ace_request_params(channel['stream']) is not None:
                            release_recorder_outpace(store.directory)
                    finish_job(store,job['id'],result)
                # If a previous timer started Outpace, do not kill it
                # while the UI or another client is still watching. Once
                # the native API has no active media sessions, free only
                # this worker's own child and allow future timers to start.
                release_recorder_outpace(store.directory)
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
