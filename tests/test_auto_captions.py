import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from io import BytesIO
import zipfile

from dizytv.auto_captions import (caption_text, ffmpeg_capture_args, verify_caption_engine, PLAYBACK_USER_AGENT,
                                   LANGUAGE_MODELS, installed_language_model, install_language_model, remove_language_model,
                                   managed_language_model, MANAGED_MODEL_MARKER)
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

    def test_bundled_windows_caption_defaults_and_explicit_overrides(self):
        # This also runs on macOS CI: the packaged resource lookup must not
        # depend on a machine-level FFmpeg installation or speech model.
        from dizytv.auto_captions import bundled_speech_directory
        import os
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            model=root/'vosk-model-small-en-us-0.15'
            (model/'am').mkdir(parents=True)
            (model/'conf').mkdir()
            bundled_ffmpeg=root/('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
            bundled_ffmpeg.write_bytes(b'fixture')
            with patch('dizytv.auto_captions.bundled_speech_directory',return_value=root):
                result=verify_caption_engine()
                self.assertEqual(str(bundled_ffmpeg.resolve()),result[0])
                self.assertEqual(str(model.resolve()),result[1])
                other=root/'custom'
                (other/'am').mkdir(parents=True)
                (other/'conf').mkdir()
                # Explicit user selections override the bundled defaults.
                selected=root/'ffmpeg.exe'
                selected.write_bytes(b'fixture')
                chosen=verify_caption_engine(str(other),str(selected))
                self.assertEqual(str(selected.resolve()),chosen[0])
                self.assertEqual(str(other.resolve()),chosen[1])

    def test_speech_language_selection_is_validated(self):
        state=default_state()
        state['settings']['auto_caption_language']='French'
        validate_state(state)
        self.assertEqual('French',restore_backup(export_backup(state))['settings']['auto_caption_language'])
        state['settings']['auto_caption_language']='some/unknown.zip'
        with self.assertRaisesRegex(ValueError,'language'):validate_state(state)

    def test_opt_in_small_vosk_install_accepts_root_folder_and_rejects_traversal(self):
        selected='French'
        prefix=LANGUAGE_MODELS[selected]
        def archive_entry(name):
            memory=BytesIO()
            with zipfile.ZipFile(memory,'w') as out:
                out.writestr(prefix+'/',b'')
                out.writestr(prefix+'/am/',b'')
                out.writestr(prefix+'/conf/',b'')
                out.writestr(prefix+'/am/final.mdl',b'fixture')
                if name:out.writestr(name,b'unsafe')
            return memory.getvalue()
        class FakeDownload:
            def __init__(self,data):self.data=BytesIO(data)
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def geturl(self):return 'https://alphacephei.com/vosk/models/'+prefix+'.zip'
            def read(self,n):return self.data.read(n)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                install_language_model(selected,folder,opener=lambda request,timeout:FakeDownload(archive_entry('../escape')))
            self.assertIsNone(installed_language_model(selected,folder))
            path=install_language_model(selected,folder,opener=lambda request,timeout:FakeDownload(archive_entry('')))
            self.assertTrue(Path(path,'am').is_dir())
            self.assertEqual(Path(path),installed_language_model(selected,folder))
            self.assertEqual(path,install_language_model(selected,folder,opener=lambda request,timeout:None))

    def test_download_progress_cancel_and_safe_remove(self):
        language='French'
        name=LANGUAGE_MODELS[language]
        def content():
            with BytesIO() as data:
                with zipfile.ZipFile(data,'w') as archive:
                    archive.writestr(name+'/am/final.mdl',b'fixture')
                    archive.writestr(name+'/conf/model.conf',b'fixture')
                return data.getvalue()
        class Fake:
            def __init__(self,data,url=None):
                self.source=BytesIO(data)
                self.headers={'Content-Length':str(len(data))}
                self.url=url or 'https://alphacephei.com/vosk/models/'+name+'.zip'
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def geturl(self):return self.url
            def read(self,n):return self.source.read(n)

        with tempfile.TemporaryDirectory() as root:
            data=content()
            progress=[]
            destination=install_language_model(language,root,opener=lambda *a,**k:Fake(data),
                                               progress=lambda done,total:progress.append((done,total)))
            self.assertEqual((len(data),len(data)),progress[-1])
            self.assertEqual(Path(destination),installed_language_model(language,root))
            self.assertEqual(Path(destination),managed_language_model(language,root))
            self.assertTrue((Path(destination)/MANAGED_MODEL_MARKER).is_file())
            # A selected custom model must remain untouched even if its path
            # happens to match the DizyTV-managed language directory.
            self.assertIsNone(managed_language_model(language,root,protected_path=destination))
            with self.assertRaisesRegex(ValueError,'managed download'):
                remove_language_model(language,root,protected_path=destination)
            self.assertEqual(Path(destination),installed_language_model(language,root))
            with patch('dizytv.auto_captions.os.replace',side_effect=OSError('Windows lock')):
                with self.assertRaisesRegex(OSError,'Windows lock'):
                    remove_language_model(language,root)
            # Failed rename: the entire installed model is still published.
            self.assertEqual(Path(destination),managed_language_model(language,root))
            self.assertTrue((Path(destination)/'am'/'final.mdl').exists())
            self.assertTrue(remove_language_model(language,root))
            self.assertFalse(remove_language_model(language,root))
            self.assertIsNone(installed_language_model(language,root))
            self.assertEqual([],list(Path(root).glob('.vosk-trash-*')))
            # If recursive deletion fails, the original model is still
            # unpublished atomically; only a private trash folder remains.
            install_language_model(language,root,opener=lambda *a,**k:Fake(data))
            with patch('dizytv.auto_captions.shutil.rmtree',side_effect=OSError('locked trash')):
                with self.assertRaisesRegex(OSError,'locked trash'):
                    remove_language_model(language,root)
            self.assertIsNone(installed_language_model(language,root))
            self.assertTrue(list(Path(root).glob('.vosk-trash-*')))
            with self.assertRaisesRegex(ValueError,'default English'):
                remove_language_model('English (bundled)',root)

            cancel=threading.Event()
            def stop_after_first_progress(done,total):
                if done:cancel.set()
            with self.assertRaisesRegex(ValueError,'cancelled'):
                install_language_model(language,root,opener=lambda *a,**k:Fake(data),
                                       cancel=cancel,progress=stop_after_first_progress)
            self.assertIsNone(installed_language_model(language,root))
            self.assertEqual([],list(Path(root).glob('.vosk-download-*')))

    def test_manually_installed_model_is_never_removed_without_provenance(self):
        language='French'
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/LANGUAGE_MODELS[language]
            (folder/'am').mkdir(parents=True)
            (folder/'conf').mkdir()
            (folder/'am'/'final.mdl').write_bytes(b'user supplied model')
            self.assertEqual(folder,installed_language_model(language,root))
            self.assertIsNone(managed_language_model(language,root))
            with self.assertRaisesRegex(ValueError,'managed download'):
                remove_language_model(language,root)
            self.assertEqual(b'user supplied model',(folder/'am'/'final.mdl').read_bytes())
            # A marker with the wrong metadata is not accepted either.
            (folder/MANAGED_MODEL_MARKER).write_text('{"installer":"someone else"}')
            self.assertIsNone(managed_language_model(language,root))
            with self.assertRaisesRegex(ValueError,'managed download'):
                remove_language_model(language,root)
            self.assertTrue((folder/'am'/'final.mdl').exists())

    def test_language_download_refuses_unverified_redirect_and_incomplete_body(self):
        name=LANGUAGE_MODELS['French']
        class Fake:
            def __init__(self,url,payload=b'incomplete'):
                self.url=url
                self.payload=BytesIO(payload)
                self.headers={'Content-Length':str(len(payload)+99)}
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def geturl(self):return self.url
            def read(self,n):return self.payload.read(n)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'official Vosk'):
                install_language_model('French',root,opener=lambda *a,**k:
                    Fake('https://evil.example/vosk/models/'+name+'.zip'))
            with self.assertRaisesRegex(ValueError,'incomplete'):
                install_language_model('French',root,opener=lambda *a,**k:
                    Fake('https://alphacephei.com/vosk/models/'+name+'.zip'))
            self.assertIsNone(installed_language_model('French',root))

    def test_ffmpeg_argv_does_not_use_shell_and_handles_stream_audio_only(self):
        url='https://example.com/legal-live.m3u8'
        a=ffmpeg_capture_args('ffmpeg',url)
        self.assertIn('pipe:1',a)
        self.assertEqual(a[a.index('-i')+1],url)
        self.assertEqual(a[a.index('-ar')+1],'16000')
        self.assertEqual(a[a.index('-f')+1],'s16le')
        self.assertEqual('-vn',a[a.index('-vn')])
        self.assertEqual(PLAYBACK_USER_AGENT,a[a.index('-user_agent')+1])
        self.assertLess(a.index('-user_agent'),a.index('-i'))
        uppercase=ffmpeg_capture_args('ffmpeg','HTTPS://example.com/live.m3u8')
        self.assertEqual(PLAYBACK_USER_AGENT,uppercase[uppercase.index('-user_agent')+1])
        self.assertEqual('HTTPS://example.com/live.m3u8',uppercase[uppercase.index('-i')+1])
        with tempfile.TemporaryDirectory() as directory:
            local=Path(directory)/'saved.ts'
            local.write_bytes(b'local')
            local_args=ffmpeg_capture_args('ffmpeg',str(local))
            self.assertNotIn('-user_agent',local_args)
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
