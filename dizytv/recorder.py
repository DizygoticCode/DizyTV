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

from collections import deque
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
import socket

from .core import http_url

MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_RECORDING_SEGMENT_BYTES = 16 * 1024 * 1024
MAX_RECORDING_BYTES = 32 * 1024 ** 3


class RecordingStopped(ValueError):
    pass


def _open_recording(opener, url):
    # Keep redirect validation identical for playlists and segments.
    return opener.open(Request(http_url(url), headers={'User-Agent':'DizyTV/0.1',
                               'Accept-Encoding':'identity'}), timeout=1.5)


def _manifest(text, origin):
    """Read supported, unencrypted TS HLS. Never dereference keys or byte ranges."""
    if not text.lstrip('\ufeff').startswith('#EXTM3U'):
        raise ValueError('The source returned no usable MPEG-TS or HLS playlist')
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if len(lines) > 10000:
        raise ValueError('HLS manifest has too many entries')
    for line in lines:
        if line.startswith('#EXT-X-SESSION-KEY:') or (line.startswith('#EXT-X-KEY:')
                and not __import__('re').search(r'(?:^|[:,])METHOD=NONE(?:,|$)', line)):
            raise ValueError('Protected/encrypted HLS recording is unsupported')
        if line.startswith('#EXT-X-MAP:'):
            raise ValueError('Fragmented-MP4 HLS recording is unsupported')
        if line.startswith(('#EXT-X-BYTERANGE:', '#EXT-X-I-FRAMES-ONLY',
                            '#EXT-X-PART:', '#EXT-X-PRELOAD-HINT:')):
            raise ValueError('HLS byte-range or low-latency partial recording is unsupported')
    if any(line.startswith('#EXT-X-STREAM-INF:') for line in lines):
        for i, line in enumerate(lines[:-1]):
            if line.startswith('#EXT-X-STREAM-INF:') and not lines[i+1].startswith('#'):
                return 'variant', [http_url(urljoin(origin,lines[i+1]))], False
        raise ValueError('HLS master playlist has no playable media variant')
    number = 0
    for line in lines:
        if line.startswith('#EXT-X-MEDIA-SEQUENCE:'):
            try:
                number = int(line.split(':',1)[1])
                if number < 0: raise ValueError()
            except ValueError:
                raise ValueError('Invalid HLS media sequence') from None
    segments = []
    for line in lines:
        if line.startswith('#'): continue
        segments.append((number + len(segments), http_url(urljoin(origin,line))))
    return 'segments', segments, '#EXT-X-ENDLIST' in lines


def _bounded_stream_write(source, output, result, folder, reserve, max_bytes,
                          cancel, progress, *, chunked=False):
    """Record whole MPEG-TS packets; never extend beyond reserve/byte limits."""
    last_progress = 0
    def write(data):
        nonlocal last_progress
        if cancel(): raise RecordingStopped('Recording stopped by user')
        if not data or data[0] != 0x47 or len(data) % 188:
            raise ValueError('The source did not return complete MPEG-TS packets')
        if result['bytes'] + len(data) > max_bytes:
            raise ValueError('Recording stopped at the size limit')
        if shutil.disk_usage(folder).free < reserve + len(data):
            raise ValueError('Recording stopped at the free-space reserve')
        output.write(data)
        result['bytes'] += len(data)
        if time.monotonic() - last_progress > .1:
            progress(result['bytes'],str(output.name))
            last_progress = time.monotonic()
    if chunked:
        write(source)
    else:
        data = source
        while data:
            write(data)
            data = b''
    return write


def _record_hls(url, opener, output, result, folder, end, reserve,
                max_bytes, cancel, progress):
    playlist = url
    variants = set()
    visited = set()
    writer = _bounded_stream_write(b'', output, result, folder, reserve,
                                   max_bytes, cancel, progress)
    while time.time() < end:
        if cancel(): raise RecordingStopped('Recording stopped by user')
        try:
            with _open_recording(opener, playlist) as response:
                body = response.read(MAX_MANIFEST_BYTES+1)
                if len(body)>MAX_MANIFEST_BYTES:
                    raise ValueError('HLS manifest exceeds 2 MiB')
                final_url = response.geturl()
        except (TimeoutError, socket.timeout) as exc:
            if cancel(): raise RecordingStopped('Recording stopped by user') from None
            raise ValueError('HLS manifest request timed out') from None
        kind, rows, ended = _manifest(body.decode('utf-8-sig'),final_url)
        if kind=='variant':
            next_playlist=rows[0]
            if next_playlist in variants or len(variants)>=6:
                raise ValueError('HLS master variant loop detected')
            variants.add(next_playlist)
            playlist=next_playlist
            continue
        fresh = 0
        for sequence, segment_url in rows:
            if time.time() >= end:break
            if cancel(): raise RecordingStopped('Recording stopped by user')
            identity=(playlist,sequence)
            if identity in visited:continue
            try:
                with _open_recording(opener,segment_url) as response:
                    data=response.read(MAX_RECORDING_SEGMENT_BYTES+1)
            except (TimeoutError,socket.timeout) as exc:
                if cancel(): raise RecordingStopped('Recording stopped by user') from None
                raise ValueError('HLS segment request timed out') from None
            if not data or len(data)>MAX_RECORDING_SEGMENT_BYTES:
                raise ValueError('HLS segment is missing or exceeds the size limit')
            if data[0] != 0x47 or len(data)%188:
                raise ValueError('HLS segment did not contain complete MPEG-TS packets')
            writer(data)
            visited.add(identity)
            fresh += 1
            if len(visited)>10000:
                # Bounded memory; keep the newest sequence identifiers.
                visited=set(sorted(visited,key=lambda item:item[1])[-5000:])
        if ended:
            raise ValueError('HLS playlist ended before the recording timer')
        if not fresh:
            # Keep UI/worker cancellable even when the origin has stalled.
            deadline=min(end,time.time()+.15)
            while time.time()<deadline:
                if cancel():raise RecordingStopped('Recording stopped by user')
                time.sleep(min(.05,max(0,deadline-time.time())))




def record_stream(url, directory, title, end, reserve=1073741824, cancel=lambda:False,
                  progress=lambda *_:None, max_bytes=MAX_RECORDING_BYTES):
    """Record clear MPEG-TS directly or from supported HLS, preserving partial video."""
    result = {'status':'failed','bytes':0,'error':'','path':''}
    outpath = None
    try:
        folder=Path(directory)
        if not directory or not folder.is_dir():
            raise ValueError('Choose an available recording folder in Settings')
        if shutil.disk_usage(folder).free <= reserve:
            raise ValueError('Free space is below the configured reserve')
        if cancel():raise RecordingStopped('Recording stopped by user')
        if not isinstance(max_bytes,int) or max_bytes<=0:
            raise ValueError('Invalid recording size limit')
        name=safe_filename(title,int(time.time()))
        outpath=folder/(Path(name).stem+'_'+uuid.uuid4().hex[:8]+'.ts.part')
        opener=build_opener(SafeRedirect)
        with _open_recording(opener,url) as response, outpath.open('xb') as output:
            content=response.headers.get('Content-Type','').lower()
            # Sniff a bounded prefix: some providers serve HLS as octet-stream.
            head=response.read(8)
            hls=('mpegurl' in content or urlsplit(response.geturl()).path.lower().endswith('.m3u8')
                 or head.startswith(b'#EXTM3U'))
            if hls:
                # The first response has already been fetched. Parsing the manifest
                # again is safe; the source may be a short-lived live playlist.
                _record_hls(response.geturl(),opener,output,result,folder,end,
                            reserve,max_bytes,cancel,progress)
            else:
                if any(k in content for k in ('text/','json','html')) or head[:1]!=b'\x47':
                    raise ValueError('Recording requires a direct MPEG-TS stream or clear TS/HLS playlist')
                pending=head
                last_progress=0
                while time.time()<end:
                    if cancel():raise RecordingStopped('Recording stopped by user')
                    try:
                        chunk=response.read1(65536)
                    except (TimeoutError,socket.timeout):
                        if cancel():raise RecordingStopped('Recording stopped by user') from None
                        raise ValueError('Direct MPEG-TS source timed out') from None
                    if not chunk and not pending:
                        raise ValueError('Stream ended before the recording timer')
                    pending+=chunk
                    usable=len(pending)//188*188
                    if usable:
                        data=pending[:usable]
                        if any(data[n]!=0x47 for n in range(0,len(data),188)):
                            raise ValueError('Source returned invalid MPEG-TS packet alignment')
                        if result['bytes']+len(data)>max_bytes:
                            raise ValueError('Recording stopped at the size limit')
                        if shutil.disk_usage(folder).free < reserve+len(data):
                            raise ValueError('Recording stopped at the free-space reserve')
                        output.write(data)
                        result['bytes']+=len(data)
                        pending=pending[usable:]
                        if time.monotonic()-last_progress>.1:
                            progress(result['bytes'],str(outpath))
                            last_progress=time.monotonic()
                if pending and result['bytes']==0:
                    raise ValueError('Source ended with incomplete MPEG-TS packets')
            output.flush()
            os.fsync(output.fileno())
        result['status']='completed' if result['bytes'] else 'failed'
    except RecordingStopped as exc:
        result['error']=str(exc)
        result['status']='partial' if result['bytes'] else 'cancelled'
    except HTTPError as exc:
        # HTTPError reason/URL can contain credentials. Do not display either.
        result['error']='Recording source returned HTTP '+str(exc.code)
        result['status']='partial' if result['bytes'] else 'failed'
    except (URLError,OSError,ValueError,UnicodeError) as exc:
        if isinstance(exc, URLError):
            result['error']='Recording source connection failed'
        else:
            result['error']=str(exc)[:250]
        result['status']='partial' if result['bytes'] else 'failed'
    finally:
        if outpath and outpath.exists():
            if result['bytes']:
                final=outpath.with_suffix('')
                try:
                    outpath.rename(final)
                    result['path']=str(final)
                except OSError:
                    result['path']=str(outpath)
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
