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
