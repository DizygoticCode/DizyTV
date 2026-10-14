import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dizytv.auto_captions import caption_text, ffmpeg_capture_args, verify_caption_engine
from dizytv.core import default_state, validate_state, export_backup, restore_backup


class OfflineCaptionTests(unittest.TestCase):
    def test_speech_caption_path_settings_are_local_not_exported(self):
        state=default_state()
        state['settings']['auto_caption_model_dir']='C:/private/user/model'
        state['settings']['auto_caption_ffmpeg_path']='C:/tools/ffmpeg.exe'
        validate_state(state)
        backup=export_backup(state)
        self.assertNotIn('C:/private/user',backup)
        self.assertNotIn('C:/tools/ffmpeg.exe',backup)
        s=restore_backup(backup)
        self.assertEqual('',s['settings']['auto_caption_model_dir'])
        self.assertEqual('',s['settings']['auto_caption_ffmpeg_path'])
        for key in ('auto_caption_model_dir','auto_caption_ffmpeg_path'):
            state['settings'][key]=5
            with self.assertRaises(ValueError):
                validate_state(state)
            state['settings'][key]=''

    def test_local_vosk_model_and_ffmpeg_require_opt_in_prerequisites(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaisesRegex(ValueError,'Vosk'):
                verify_caption_engine(str(root),'')
            (root/'am').mkdir()
            (root/'conf').mkdir()
            with self.assertRaisesRegex(ValueError,'FFmpeg'):
                verify_caption_engine(str(root),str(root/'unknown.exe'))
            exe=root/'ffmpeg.exe'
            exe.write_bytes(b'fake')
            # Dependency is imported only when the user starts captions.
            path=str(exe.resolve())
            result=verify_caption_engine(str(root),path)
            self.assertEqual(path,result[0])
            self.assertEqual(str(root.resolve()),result[1])

    def test_ffmpeg_argv_does_not_use_shell_and_handles_stream_audio_only(self):
        url='https://example.com/legal-live.m3u8'
        a=ffmpeg_capture_args('ffmpeg',url)
        self.assertIn('pipe:1',a)
        self.assertEqual(a[a.index('-i')+1],url)
        self.assertEqual(a[a.index('-ar')+1],'16000')
        self.assertEqual(a[a.index('-f')+1],'s16le')
        self.assertEqual('-vn',a[a.index('-vn')])
        with self.assertRaises(ValueError):
            ffmpeg_capture_args('ffmpeg','--malicious')
        with self.assertRaises(ValueError):
            ffmpeg_capture_args('ffmpeg','ftp://example.com/stream')

    def test_generated_text_is_plain_bounded_and_no_control_characters(self):
        text=caption_text('  hello\nWorld<script>\x00  ')
        self.assertIn('hello',text)
        self.assertNotIn('\x00',text)
        self.assertLessEqual(len(caption_text('s'*900)),240)


if __name__=='__main__':
    unittest.main()
