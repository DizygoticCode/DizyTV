"""Package the Linux x86_64 PyInstaller build as an installable .deb.

The executable links against system libVLC and its plugins, rather than bundling
an unmanaged or incompatible Ace Stream binary. Engine is separately installed.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent.parent
VERSION="0.1.15-alpha"
TARGET=ROOT/'dist'/'DizyTV'
if os.name!='posix' or not TARGET.is_dir() or not (TARGET/'DizyTV').is_file():
    raise SystemExit('Run after scripts/build_desktop.py on a Linux amd64 host')
if os.uname().machine not in ('x86_64','amd64'):
    raise SystemExit('Linux .deb currently targets amd64 only')
icon=ROOT/'assets'/'branding'/'dizytv-logo.png'
output=ROOT/'dist'/f'DizyTV-{VERSION}-linux-amd64.deb'

with tempfile.TemporaryDirectory(prefix='dizytv-deb-') as folder:
    root=Path(folder)
    app=root/'opt'/'dizytv'
    shutil.copytree(TARGET,app)
    (app/'DizyTV').chmod(0o755)
    bin_dir=root/'usr'/'bin'
    bin_dir.mkdir(parents=True)
    launcher=bin_dir/'dizytv'
    launcher.write_text('#!/bin/sh\nexec /opt/dizytv/DizyTV "$@"\n')
    launcher.chmod(0o755)
    applications=root/'usr'/'share'/'applications'
    applications.mkdir(parents=True)
    (applications/'dizytv.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=DizyTV\n'
        'Comment=Live TV, XMLTV guide and local recordings\n'
        'Exec=/usr/bin/dizytv\nIcon=dizytv\nTerminal=false\n'
        'Categories=AudioVideo;Video;Player;\n')
    icons=root/'usr'/'share'/'icons'/'hicolor'/'256x256'/'apps'
    icons.mkdir(parents=True)
    shutil.copyfile(icon,icons/'dizytv.png')
    control=root/'DEBIAN'
    control.mkdir()
    (control/'control').write_text(
        'Package: dizytv\n'
        f'Version: {VERSION}\n'
        'Section: video\nPriority: optional\nArchitecture: amd64\n'
        'Maintainer: DizygoticCode <https://github.com/DizygoticCode/DizyTV>\n'
        'Depends: libvlc5, vlc-plugin-base, vlc-plugin-video-output, libgl1, libxcb-cursor0, libxkbcommon-x11-0\n'
        'Description: DizyTV native live television player\n'
        ' Local TV player with XMLTV guides and recordings.\n'
        ' Uses system libVLC and separately installed Ace Stream engine.\n')
    subprocess.run(['dpkg-deb','--build','--root-owner-group',str(root),str(output)],check=True)
print(output)
