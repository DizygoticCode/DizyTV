import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.stage_windows_speech import MODEL_NAME, stage_archives


class WindowsSpeechStagingTests(unittest.TestCase):
    def test_stage_only_expected_ffmpeg_and_complete_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ffmpeg_zip = root / "ffmpeg.zip"
            model_zip = root / "model.zip"
            out = root / "assets"
            with zipfile.ZipFile(ffmpeg_zip, "w") as archive:
                archive.writestr("ffmpeg-8.1.2-essentials_build/bin/ffmpeg.exe", b"fake executable")
                archive.writestr("ffmpeg-8.1.2-essentials_build/bin/ffplay.exe", b"not needed")
            with zipfile.ZipFile(model_zip, "w") as archive:
                archive.writestr(MODEL_NAME + "/am/final.mdl", b"acoustic")
                archive.writestr(MODEL_NAME + "/conf/model.conf", b"config")
            stage_archives(ffmpeg_zip, model_zip, out)
            self.assertEqual((out / "ffmpeg.exe").read_bytes(), b"fake executable")
            self.assertTrue((out / MODEL_NAME / "am" / "final.mdl").exists())
            self.assertFalse((out / "ffplay.exe").exists())

    def test_rejects_path_traversal_in_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ffmpeg_zip = root / "ffmpeg.zip"
            model_zip = root / "model.zip"
            with zipfile.ZipFile(ffmpeg_zip, "w") as archive:
                archive.writestr("ffmpeg/bin/ffmpeg.exe", b"exe")
            with zipfile.ZipFile(model_zip, "w") as archive:
                archive.writestr(MODEL_NAME + "/../outside.txt", b"bad")
            with self.assertRaisesRegex(RuntimeError, "Unsafe"):
                stage_archives(ffmpeg_zip, model_zip, root / "assets")


if __name__ == "__main__":
    unittest.main()
