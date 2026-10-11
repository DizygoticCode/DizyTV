"""Build on the target OS: a native EXE or macOS app, never cross-compile."""
import hashlib
from importlib.metadata import distribution
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
os.chdir(ROOT)
from PIL import Image
licences=ROOT/'assets'/'licenses'
shutil.copyfile(ROOT/'THIRD-PARTY-NOTICES.md',licences/'NOTICES.md')
for package in ('python-vlc','tzdata','pyinstaller'):
    wheel=distribution(package)
    for entry in wheel.files or []:
        if any(word in entry.name.lower() for word in ('license','licence','copying')):
            target=licences/'components'/package/entry.name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(wheel.locate_file(entry),target)
image=Image.open('assets/branding/dizytv-logo.png')
image.save('assets/branding/dizytv.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
image.save('assets/branding/dizytv.icns')
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--name','DizyTV',
      '--paths',str(ROOT),'--add-data','assets'+os.pathsep+'assets',
      '--collect-data','tzdata','--hidden-import','vlc']
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
    value.update(CFBundleShortVersionString='0.1.2',CFBundleVersion='3',LSMinimumSystemVersion='13.0',
                 NSLocalNetworkUsageDescription='Connect to your configured Ace Stream engine for live television and local recording.')
    info.write_bytes(plistlib.dumps(value))
    # Re-sign after Info.plist change. Ad-hoc identity is for development only.
    subprocess.run(['codesign','--force','--deep','--sign','-','dist/DizyTV.app'],check=True)
    subprocess.run(['pkgbuild','--component','dist/DizyTV.app','--install-location','/Applications',
                    '--identifier','dev.dizygotic.dizytv','--version','0.1.2',
                    f'dist/DizyTV-0.1.2-alpha-macos-{platform.machine()}.pkg'],check=True)

for file in Path('dist').glob('*'):
    if file.is_file() and file.suffix in ('.pkg','.exe'):
        file.with_suffix(file.suffix+'.sha256').write_text(hashlib.sha256(file.read_bytes()).hexdigest()+'  '+file.name+'\n')
