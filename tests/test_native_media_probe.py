"""Mocked native decode probe tests: never run FFmpeg, VLC or network streams."""
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dizytv.native_media_probe import verify_media_pipeline


class FakeMedia:
    def __init__(self, available=True):
        self.available=available
        self.stats_calls=0
        self.released=False
    def get_stats(self, stats):
        self.stats_calls+=1
        stats.decoded_video=4
        stats.decoded_audio=2
        return self.available
    def release(self):
        self.released=True


class FakePlayer:
    def __init__(self):
        self.released=False
        self.stopped=False
        self.media=None
    def set_media(self, media):
        self.media=media
    def play(self):
        return 0
    def get_state(self):
        return "State.Playing"
    def stop(self):
        self.stopped=True
    def release(self):
        self.released=True


class FakeInstance:
    def __init__(self, media, player):
        self.media=media
        self.player=player
        self.released=False
    def media_player_new(self):
        return self.player
    def media_new_path(self, path):
        assert Path(path).is_file()
        return self.media
    def release(self):
        self.released=True


class NativeMediaProbeTests(unittest.TestCase):
    def test_decodes_local_video_frames_with_vlc_outparameter(self):
        media=FakeMedia()
        player=FakePlayer()
        inst=FakeInstance(media,player)
        vlc=SimpleNamespace(
            Instance=lambda *args:inst,
            MediaStats=lambda:SimpleNamespace(decoded_video=0,decoded_audio=0))
        def pretend_encode(args, **kwargs):
            Path(args[-1]).write_bytes(b'REAL_FFMPEG_NOT_RUN'+b'\0'*8192)
            return subprocess.CompletedProcess(args,0)
        with patch('dizytv.native_media_probe.subprocess.run', side_effect=pretend_encode):
            self.assertEqual(verify_media_pipeline('ffmpeg',vlc),4)
        self.assertGreater(media.stats_calls,0)
        self.assertTrue(media.released)
        self.assertTrue(player.stopped)
        self.assertTrue(player.released)
        self.assertTrue(inst.released)

    def test_cannot_claim_decode_without_libvlc_stats(self):
        media=FakeMedia(available=False)
        player=FakePlayer()
        inst=FakeInstance(media,player)
        vlc=SimpleNamespace(
            Instance=lambda *args:inst,
            MediaStats=lambda:SimpleNamespace(decoded_video=0,decoded_audio=0))
        def pretend_encode(args, **kwargs):
            Path(args[-1]).write_bytes(b'\0'*8192)
            return subprocess.CompletedProcess(args,0)
        with patch('dizytv.native_media_probe.subprocess.run', side_effect=pretend_encode):
            with self.assertRaisesRegex(RuntimeError,'did not decode'):
                verify_media_pipeline('ffmpeg',vlc,timeout=0)
        self.assertTrue(media.released)
        self.assertTrue(inst.released)
