import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.stage_desktop_speech import MODEL_NAME, stage_model


class DesktopSpeechStageTests(unittest.TestCase):
    def test_extract_english_model_without_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"model.zip"
            with zipfile.ZipFile(source,"w") as z:
                z.writestr(MODEL_NAME+"/am/model",b"test")
                z.writestr(MODEL_NAME+"/conf/model.conf",b"settings")
            stage_model(source,root/"bundle")
            self.assertTrue((root/"bundle"/MODEL_NAME/"am/model").exists())
            self.assertTrue((root/"bundle"/MODEL_NAME/"conf/model.conf").exists())

    def test_reject_escape_from_model_root(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"model.zip"
            with zipfile.ZipFile(source,"w") as z:
                z.writestr(MODEL_NAME+"/../unsafe",b"payload")
                z.writestr(MODEL_NAME+"/am/model",b"test")
                z.writestr(MODEL_NAME+"/conf/model.conf",b"settings")
            with self.assertRaisesRegex(ValueError,"Untrusted"):
                stage_model(source,root/"bundle")
