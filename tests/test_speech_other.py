import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.stage_speech_other import stage_model, MODEL_NAME

class SpeechCrossPlatformTests(unittest.TestCase):
    def test_safe_extraction_preserves_model_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            source=path/'ok.zip'
            with zipfile.ZipFile(source,'w') as z:
                z.writestr(f'{MODEL_NAME}/am/final.mdl',b'acoustic')
                z.writestr(f'{MODEL_NAME}/conf/model.conf',b'config')
            stage_model(source,path/'speech')
            self.assertTrue((path/'speech'/MODEL_NAME/'am'/'final.mdl').is_file())

    def test_model_archive_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);source=path/'bad.zip'
            with zipfile.ZipFile(source,'w') as z:
                z.writestr(f'{MODEL_NAME}/../bad.txt',b'bad')
            with self.assertRaisesRegex(RuntimeError,'Unsafe'):
                stage_model(source,path/'speech')


    def test_macos_ffmpeg_must_come_from_pinned_wheel_not_path_override(self):
        import sys
        import types
        from unittest.mock import patch
        from scripts import stage_speech_other as speech

        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            external=root/'unverified'/'ffmpeg'
            external.parent.mkdir()
            external.write_bytes(b'not-a-pinned-binary')
            wheel_root=root/'wheel'
            (wheel_root/'binaries').mkdir(parents=True)
            model_name=speech.MODEL_NAME

            def fake_model(_url,_hash,archive):
                with zipfile.ZipFile(archive,'w') as z:
                    z.writestr(model_name+'/am/final.mdl',b'fixture')
                    z.writestr(model_name+'/conf/model.conf',b'fixture')

            fake_wheel=types.SimpleNamespace(
                __file__=str(wheel_root/'__init__.py'),
                get_ffmpeg_exe=lambda:str(external))
            with patch.object(speech,'DEST',root/'speech'), \
                 patch.object(speech.sys,'platform','darwin'), \
                 patch.object(speech,'fetch_verified',side_effect=fake_model), \
                 patch.dict(sys.modules,{'imageio_ffmpeg':fake_wheel}):
                with self.assertRaisesRegex(RuntimeError,'pinned|Pinned'):
                    speech.main()
                self.assertFalse((root/'speech'/'ffmpeg').exists())

            official=wheel_root/'binaries'/'ffmpeg-macos'
            official.write_bytes(b'wheel-verified-fixture')
            fake_wheel.get_ffmpeg_exe=lambda:str(official)
            with patch.object(speech,'DEST',root/'speech'), \
                 patch.object(speech.sys,'platform','darwin'), \
                 patch.object(speech,'fetch_verified',side_effect=fake_model), \
                 patch.object(speech.subprocess,'run') as run, \
                 patch.dict(sys.modules,{'imageio_ffmpeg':fake_wheel}):
                speech.main()
                self.assertEqual((root/'speech'/'ffmpeg').read_bytes(),official.read_bytes())
                run.assert_called_once()
