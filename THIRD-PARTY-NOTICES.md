# Third-party components

DizyTV is an independent application. The Ace Stream engine is separately installed/configured; this project does not rename, redistribute or remove notices from Ace Stream binaries. No channel or XMLTV dataset is bundled.

- **Qt / PySide6 / Shiboken6 6.11.2** — Qt for Python, LGPLv3/GPLv3 or commercial terms, depending on the component. Desktop builds use dynamically linked libraries. Sources, licence terms and replacement/relinking information: <https://www.qt.io/licensing/open-source-lgpl-obligations>, <https://code.qt.io/cgit/pyside/pyside-setup.git/>. Retain the licence files distributed with the wheels. LGPL copies and Qt sources for the exact version must accompany public redistribution as required.
- **python-vlc 3.0.21203** — LGPLv2.1 or later. <https://github.com/oaubert/python-vlc>. Desktop VLC/libVLC is installed separately by the user, with the correct CPU architecture.
- **libVLC Android** — VideoLAN's embedded library with its upstream LGPL and module-specific notices. <https://code.videolan.org/videolan/vlc-android>. Public APK distribution must provide the applicable notices, exact corresponding sources and LGPL replacement/relinking route. Do not assume the DizyTV source licence replaces upstream licences.
- **Python 3.12** — PSF licence. <https://docs.python.org/3/license.html>.
- **tzdata 2026.2** — IANA timezone database; Python tzdata package Apache 2.0. <https://github.com/python/tzdata>.
- **PyInstaller** — GPL with its bootloader exception permitting bundled application distribution. <https://pyinstaller.org/en/stable/license.html>.

Desktop packages are unsigned development builds (macOS uses an ad-hoc app signature). A debug Android APK is a development artifact. Public release signing and the final redistribution/source-offer review are separate release gates. No open-source licence for DizyTV itself has been selected by the owner yet; a public GitHub repository alone does not grant a source licence.
