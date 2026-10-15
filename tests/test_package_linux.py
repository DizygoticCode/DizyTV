import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(
    sys.platform == 'linux'
    and platform.machine() in ('x86_64', 'amd64')
    and shutil.which('dpkg-deb'),
    'requires Linux amd64 and dpkg-deb',
)
class LinuxPackageTests(unittest.TestCase):
    def test_restrictive_build_permissions_remain_accessible_after_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / 'scripts' / 'package_linux.py'
            script.parent.mkdir()
            shutil.copyfile(Path(__file__).resolve().parents[1] / 'scripts' / script.name, script)
            app = root / 'dist' / 'DizyTV'
            internal = app / '_internal'
            internal.mkdir(parents=True)
            internal.chmod(0o700)
            app.chmod(0o700)
            executable = app / 'DizyTV'
            executable.write_text('#!/bin/sh\nexit 0\n')
            executable.chmod(0o700)
            data = internal / 'runtime.dat'
            data.write_bytes(b'private build artifact')
            data.chmod(0o600)
            helper = internal / 'helper'
            helper.write_text('#!/bin/sh\nexit 0\n')
            helper.chmod(0o700)
            link = internal / 'runtime-link.dat'
            link.symlink_to(data.name)
            icon = root / 'assets' / 'branding' / 'dizytv-logo.png'
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b'package fixture icon')

            build = subprocess.run(
                [sys.executable, '-c',
                 'import os,runpy,sys; os.umask(0o077); runpy.run_path(sys.argv[1],run_name="__main__")',
                 str(script)],
                capture_output=True, text=True,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            package, = (root / 'dist').glob('*.deb')
            installed = root / 'installed'
            subprocess.run(['dpkg-deb', '--raw-extract', str(package), str(installed)], check=True)

            for path in (installed, *installed.rglob('*')):
                if path.is_symlink():
                    continue
                with self.subTest(path=path.relative_to(installed)):
                    expected = 0o755 if path.is_dir() or path.name in ('DizyTV', 'dizytv', 'helper') else 0o644
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected)
            installed_link = installed / 'opt' / 'dizytv' / '_internal' / link.name
            self.assertTrue(installed_link.is_symlink())
            self.assertEqual(os.readlink(installed_link), data.name)
            for path, mode in ((app, 0o700), (internal, 0o700), (executable, 0o700),
                               (data, 0o600), (helper, 0o700)):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)


if __name__ == '__main__':
    unittest.main()
