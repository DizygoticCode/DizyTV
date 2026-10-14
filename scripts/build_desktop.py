"""Build on the target OS: a native EXE or macOS app, never cross-compile."""
import hashlib
from importlib.metadata import PackageNotFoundError, distribution
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
# Include every explicitly bundled speech dependency, plus its runtime
# HTTP support distributions. colorama is Windows-only (tqdm dependency).
licence_packages=('python-vlc','tzdata','pyinstaller','vosk',
                  'requests','srt','tqdm','charset-normalizer','idna',
                  'urllib3','certifi','Pillow')
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
    if package=='vosk' and not found:
        # Vosk's published Python wheel currently omits a LICENSE entry.
        # Its Apache-2.0 terms are already shipped in our tracked licences;
        # explicitly copy the canonical text into its attribution folder.
        target=licences/'components'/'vosk'/'Apache-2.0.txt'
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(licences/'Apache-2.0.txt',target)
        found=1
    if package in ('vosk','requests','srt','tqdm') and not found:
        raise RuntimeError('Missing license terms for bundled dependency '+package)
image=Image.open('assets/branding/dizytv-logo.png')
image.save('assets/branding/dizytv.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
image.save('assets/branding/dizytv.icns')
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--name','DizyTV',
      '--paths',str(ROOT),'--add-data','assets'+os.pathsep+'assets',
      '--collect-data','tzdata','--collect-binaries','vosk','--hidden-import','vlc','--hidden-import','vosk']
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
    value.update(CFBundleShortVersionString='0.1.9',CFBundleVersion='10',LSMinimumSystemVersion='13.0',
                 NSLocalNetworkUsageDescription='Connect to your configured Ace Stream engine for live television and local recording.')
    info.write_bytes(plistlib.dumps(value))
    # Re-sign after Info.plist change. Ad-hoc identity is for development only.
    subprocess.run(['codesign','--force','--deep','--sign','-','dist/DizyTV.app'],check=True)
    subprocess.run(['pkgbuild','--component','dist/DizyTV.app','--install-location','/Applications',
                    '--identifier','dev.dizygotic.dizytv','--version','0.1.9',
                    f'dist/DizyTV-0.1.9-alpha-macos-{platform.machine()}.pkg'],check=True)

for file in Path('dist').glob('*'):
    if file.is_file() and file.suffix in ('.pkg','.exe'):
        file.with_suffix(file.suffix+'.sha256').write_text(hashlib.sha256(file.read_bytes()).hexdigest()+'  '+file.name+'\n')
