"""Fail before native builds when platform/package version metadata has drifted."""
from __future__ import annotations
from pathlib import Path
import re
import tomllib

ROOT=Path(__file__).resolve().parent.parent

def expected_version():
    raw=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    match=re.fullmatch(r'([0-9]+\.[0-9]+\.[0-9]+)a([1-9][0-9]*)',raw)
    if not match:
        raise RuntimeError('Expected one semver prerelease version such as 0.1.18a1')
    return match.group(1)+'-alpha'

def verify():
    version=expected_version()
    bindings={
        'dizytv/__init__.py': r'__version__\s*=\s*"([^"]+)"',
        'scripts/package_linux.py': r'VERSION\s*=\s*"([^"]+)"',
        'scripts/windows-installer.iss': r'#define AppVersion\s+"([^"]+)"',
        'android/app/build.gradle.kts': r'versionName\s*=\s*"([^"]+)"',
    }
    for filename,expression in bindings.items():
        content=(ROOT/filename).read_text(encoding='utf-8')
        match=re.search(expression,content)
        if not match or match.group(1)!=version:
            raise RuntimeError(filename+': version does not match '+version)
    workflow=(ROOT/'.github/workflows/native-builds.yml').read_text(encoding='utf-8')
    release_tag='v'+version
    for needle in ('gh release view '+release_tag,
                   'gh release create '+release_tag,
                   'DizyTV-Setup-'+version+'-windows-x64.exe',
                   'DizyTV-'+version+'-android-universal-debug.apk',
                   'DizyTV-'+version+'-linux-amd64.deb',
                   'DizyTV-'+version+'-macos-arm64.pkg',
                   'DizyTV-'+version+'-macos-x86_64.pkg'):
        if needle not in workflow:
            raise RuntimeError('Native publisher metadata missing: '+needle)
    return version

if __name__=='__main__':
    print('Release metadata consistent:',verify())
