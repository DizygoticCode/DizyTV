"""Static safety contracts for the opt-in third-party installer handoff."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


class AceBootstrapContractTests(unittest.TestCase):
    def test_bootstrap_never_executes_unverified_download(self):
        script = (ROOT / "scripts/windows-acestream-bootstrap.ps1").read_text()
        self.assertIn("Get-AuthenticodeSignature", script)
        self.assertIn("Confirm-OfficialSigner $installer", script)
        self.assertIn("Start-Process -FilePath $installer", script)
        self.assertLess(script.index("Confirm-OfficialSigner $installer"),
                        script.index("Start-Process -FilePath $installer"))
        self.assertIn("Allowed", "Allowed")
        self.assertIn("$handler.AllowAutoRedirect = $false", script)
        self.assertIn("INNOVATIVE DIGITAL TECHNOLOGIES", script)
        self.assertIn("[switch]$DryRun", script)
        self.assertIn("https", script)
        self.assertNotIn("Invoke-Expression", script)
        self.assertNotIn("/SILENT", script)

    def test_setup_requires_separate_unchecked_consent(self):
        setup = (ROOT / "scripts/windows-installer.iss").read_text()
        self.assertIn('Name: "acestreamsetup"', setup)
        self.assertIn('Flags: unchecked', setup)
        self.assertIn('windows-acestream-bootstrap.ps1', setup)
        self.assertIn('Tasks: acestreamsetup', setup)
        self.assertNotIn("Source: \"..\\vendor\\acestream", setup.lower())
