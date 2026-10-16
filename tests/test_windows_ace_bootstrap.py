"""Source-level safety contracts for the optional original-vendor Ace setup.
No live download or third-party executable is run from CI.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent.parent

class WindowsAceBootstrapTests(unittest.TestCase):
    def test_installer_has_explicit_unchecked_opt_in(self):
        source=(ROOT/'scripts'/'windows-installer.iss').read_text()
        self.assertIn('Name: "acestreamsetup"',source)
        self.assertIn('Flags: unchecked',source)
        self.assertIn('windows-install-acestream.ps1',source)
        self.assertNotIn('Filename: "https://docs.acestream.net/products/"',source)

    def test_download_refuses_untrusted_origin_or_signer(self):
        source=(ROOT/'scripts'/'windows-install-acestream.ps1').read_text()
        for required in ('AllowAutoRedirect = $false','allowedHosts',
                         "Scheme -ne 'https'",'ContentLength','maxBytes',
                         'Get-AuthenticodeSignature','signature.Status',
                         'SignerCertificate.Subject','Start-Process',
                         'DizyTV is installed'):
            with self.subTest(required=required):
                self.assertIn(required,source)
        self.assertNotIn('Invoke-Expression',source)
        self.assertNotIn('/SILENT',source)
        self.assertNotIn('ReadAllBytes',source)
        self.assertIn('OpenRead',source)
        self.assertIn('$response.Dispose()',source)
        self.assertIn('Find-ExistingAceEngine',source)
        self.assertIn('already present',source)
        self.assertIn("HKCU:\\Software\\ACEStream",source)
