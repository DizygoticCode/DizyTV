"""Source-only contracts for opt-in launch controls in native installers.

Native package rendering and device launch remain separate release gates.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerFinishOptionsTests(unittest.TestCase):
    def test_windows_launch_is_optional_at_finish_and_never_runs_silently(self):
        script = (ROOT / 'scripts/windows-installer.iss').read_text('utf-8')
        run = script.split('[Run]', 1)[1].split('[Code]', 1)[0]
        matches = [line for line in run.splitlines()
                   if line.strip().startswith('Filename:') and
                   'Description: "Run DizyTV now"' in line]
        self.assertEqual(1, len(matches))
        entry = matches[0]
        self.assertIn('"{app}\\DizyTV.exe"', entry)
        self.assertIn('Flags:', entry)
        for flag in ('postinstall', 'nowait', 'skipifsilent', 'runasoriginaluser'):
            with self.subTest(flag=flag):
                self.assertRegex(entry, r'\b'+flag+r'\b')
        self.assertNotRegex(entry, r'\bunchecked\b')
        self.assertNotIn('Tasks: acestreamsetup', entry)

    def test_mac_installer_has_conclusion_but_no_unsafe_script_launch(self):
        script = (ROOT / 'scripts/build_desktop.py').read_text('utf-8')
        self.assertIn("'productbuild','--distribution'", script)
        self.assertIn("'conclusion',{'file':'conclusion.html'", script)
        self.assertIn("Applications &rarr; DizyTV", script)
        self.assertIn("DizyTV will not start automatically", script)
        self.assertNotIn("'postinstall','open -a'", script)
        workflow = (ROOT / '.github/workflows/native-builds.yml').read_text('utf-8')
        self.assertIn('pkgutil --expand', workflow)
        self.assertIn('smoke-product/Resources/conclusion.html', workflow)

    def test_android_uses_system_installer_without_surprise_autostart(self):
        manifest = (ROOT / 'android/app/src/main/AndroidManifest.xml').read_text('utf-8')
        self.assertIn('android:name=".MatchdayWebActivity" android:exported="false"', manifest)
        self.assertIn('android:name=".MainActivity" android:exported="true"', manifest)


if __name__ == '__main__':
    unittest.main()
