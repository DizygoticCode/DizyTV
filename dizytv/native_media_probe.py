"""Offline video/audio codec smoke test for a packaged libVLC installation.

No IPTV provider, network, P2P, DRM bypass or private URLs are used.
Passing confirms native modules decode the synthetic sample, not that an actual
OS video surface can render pictures; live acceptance remains a device test.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import tempfile
import time


def verify_media_pipeline(ffmpeg_binary, vlc_module, timeout=12):
    with tempfile.TemporaryDirectory(prefix='dizytv-native-probe-') as directory:
        fixture=Path(directory)/'test.ts'
        subprocess.run([
            ffmpeg_binary,'-hide_banner','-loglevel','error','-nostdin',
            '-f','lavfi','-i','testsrc2=size=160x90:rate=10:duration=2',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=44100:duration=2',
            '-shortest','-c:v','mpeg2video','-pix_fmt','yuv420p',
            '-c:a','mp2','-f','mpegts','-y',str(fixture),
        ],check=True,timeout=30)
        if fixture.stat().st_size<4096:
            raise RuntimeError('FFmpeg produced an incomplete offline video fixture')
        instance=vlc_module.Instance('--intf=dummy','--vout=dummy',
                                     '--aout=dummy','--no-video-title-show')
        if instance is None:
            raise RuntimeError('Bundled libVLC could not load its plugins')
        player=None
        media=None
        try:
            player=instance.media_player_new()
            media=instance.media_new_path(str(fixture))
            player.set_media(media)
            if player.play()==-1:
                raise RuntimeError('Bundled libVLC rejected the video fixture')
            deadline=time.monotonic()+timeout
            decoded=0
            while time.monotonic()<deadline:
                # python-vlc 3.x get_stats REQUIRES a MediaStats out-parameter
                # and returns a boolean; calling it without arguments fails.
                stats=vlc_module.MediaStats()
                if media.get_stats(stats):
                    decoded=max(decoded, int(stats.decoded_video))
                    if decoded>=3:
                        return decoded
                state=str(player.get_state())
                if state.endswith('.Error'):
                    break
                time.sleep(0.15)
            raise RuntimeError(
                'Bundled libVLC did not decode three video frames from an offline MPEG-TS fixture')
        finally:
            if player is not None:
                player.stop()
                player.release()
            if media is not None:
                media.release()
            instance.release()
