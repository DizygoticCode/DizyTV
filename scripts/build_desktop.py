"""Build on the target OS: a native EXE or macOS app, never cross-compile."""
import hashlib
from importlib.metadata import PackageNotFoundError, distribution
import os
import platform
import re
import shutil
import tomllib
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
os.chdir(ROOT)
from PIL import Image
licences=ROOT/'assets'/'licenses'
shutil.copyfile(ROOT/'THIRD-PARTY-NOTICES.md',licences/'NOTICES.md')
# Include every explicitly bundled speech dependency, plus its runtime
# HTTP support distributions. colorama is Windows-only (tqdm dependency).
licence_packages=('python-vlc','tzdata','pyinstaller','vosk',
                  'requests','srt','tqdm','charset-normalizer','idna',
                  'urllib3','certifi','Pillow','cffi','pycparser')
for package in (*licence_packages,'colorama'):
    try:wheel=distribution(package)
    except PackageNotFoundError:
        if package=='colorama':continue
        raise
    found=0
    for entry in wheel.files or []:
        if any(word in entry.name.lower() for word in ('license','licence','copying')):
            target=licences/'components'/package/entry.name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(wheel.locate_file(entry),target)
            found+=1
    if not found:
        # Some PyPI wheels omit their upstream LICENSE/LICENCE. Use exact
        # checked-in upstream licence texts rather than failing packaging or
        # silently shipping without attribution.
        fallbacks={
            'vosk':licences/'Apache-2.0.txt',
            'requests':licences/'Apache-2.0.txt',
            'srt':licences/'upstream'/'srt-LICENSE.txt',
            'tqdm':licences/'upstream'/'tqdm-LICENCE.txt',
        }
        source=fallbacks.get(package)
        if source:
            if not source.is_file():
                raise RuntimeError('Missing tracked licence for '+package)
            target=licences/'components'/package/source.name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
            found=1
    if package in ('vosk','requests','srt','tqdm','cffi','pycparser') and not found:
        raise RuntimeError('Missing licence terms for bundled dependency '+package)
image=Image.open('assets/branding/dizytv-logo.png')
image.save('assets/branding/dizytv.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
image.save('assets/branding/dizytv.icns')
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--name','DizyTV',
      '--paths',str(ROOT),'--add-data','assets'+os.pathsep+'assets',
      '--collect-data','tzdata','--collect-binaries','vosk','--hidden-import','vlc','--hidden-import','vosk']
if os.name=='nt':
    speech=ROOT/'vendor'/'speech'
    if not (speech/'ffmpeg.exe').is_file() or not (speech/'vosk-model-small-en-us-0.15'/'am').is_dir() or not (speech/'vosk-model-small-en-us-0.15'/'conf').is_dir():
        raise RuntimeError('Missing staged Windows FFmpeg/Vosk model: refusing to build an incomplete installer')
    args += ['--add-data',str(speech)+os.pathsep+'speech']
if sys.platform=='darwin':
    args += ['--windowed','--icon','assets/branding/dizytv.icns','--osx-bundle-identifier','dev.dizygotic.dizytv']
elif os.name=='nt':
    args += ['--windowed','--icon','assets/branding/dizytv.ico']
args += ['dizytv/__main__.py']
subprocess.run(args,check=True)

if sys.platform=='darwin':
    import plistlib
    info=Path('dist/DizyTV.app/Contents/Info.plist')
    value=plistlib.loads(info.read_bytes())
    # Read the packaging version from pyproject instead of keeping a stale
    # macOS-only number after the Windows/Android release has been bumped.
    project_version = tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    matched = re.fullmatch(r'(\\d+\\.\\d+\\.\\d+)a\\d+', project_version)
    if not matched:
        raise RuntimeError('Unsupported alpha project version: '+project_version)
    mac_version = matched.group(1)
    value.update(CFBundleShortVersionString=mac_version,CFBundleVersion=mac_version,LSMinimumSystemVersion='13.0',
                 NSLocalNetworkUsageDescription='Connect to your configured Ace Stream engine for live television and local recording.')
    info.write_bytes(plistlib.dumps(value))
    # Re-sign after Info.plist change. Ad-hoc identity is for development only.
    subprocess.run(['codesign','--force','--deep','--sign','-','dist/DizyTV.app'],check=True)
    subprocess.run(['pkgbuild','--component','dist/DizyTV.app','--install-location','/Applications',
                    '--identifier','dev.dizygotic.dizytv','--version',mac_version,
                    f'dist/DizyTV-{mac_version}-alpha-macos-{platform.machine()}.pkg'],check=True)

for file in Path('dist').glob('*'):
    if file.is_file() and file.suffix in ('.pkg','.exe'):
        file.with_suffix(file.suffix+'.sha256').write_text(hashlib.sha256(file.read_bytes()).hexdigest()+'  '+file.name+'\n')
