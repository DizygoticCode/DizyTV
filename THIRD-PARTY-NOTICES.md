# Third-party components

DizyTV is an independent application. The Ace Stream engine is separately installed/configured; this project does not rename, redistribute or remove notices from Ace Stream binaries. No channel or XMLTV dataset is bundled.

- **Qt / PySide6 / Shiboken6 6.11.2** — Qt for Python, LGPLv3/GPLv3 or commercial terms, depending on the component. Desktop builds use dynamically linked libraries. Sources, licence terms and replacement/relinking information: <https://www.qt.io/licensing/open-source-lgpl-obligations>, <https://code.qt.io/cgit/pyside/pyside-setup.git/>. Copies of LGPLv3 and GPLv3 are included in `assets/licenses`; exact corresponding sources and replacement instructions remain a public release requirement.
- **python-vlc 3.0.21203** — LGPLv2.1 or later. <https://github.com/oaubert/python-vlc>. Desktop VLC/libVLC is installed separately by the user, with the correct CPU architecture.
- **libVLC Android 3.7.5** — VideoLAN's embedded library with its upstream LGPL and module-specific notices. <https://code.videolan.org/videolan/vlc-android>. The APK includes the licence texts and this notice. Exact corresponding sources and the LGPL replacement/relinking route remain a public release requirement. Do not assume the DizyTV source licence replaces upstream licences.
- **Python 3.12** — PSF licence. <https://docs.python.org/3/license.html>.
- **tzdata 2026.2** — IANA timezone database; Python tzdata package Apache 2.0. <https://github.com/python/tzdata>.
- **Vosk 0.3.40** — Apache 2.0 local speech recognition runtime bundled in desktop packages only; speech recognition is off by default and requires a separately obtained model. <https://alphacephei.com/vosk/>. Models have separate licensing information; they are not bundled. FFmpeg is installed separately; no FFmpeg executable is redistributed.
- **requests 2.32.5** — Apache 2.0 HTTP helper used by Vosk. <https://github.com/psf/requests>.
- **cffi** — MIT-licensed C Foreign Function Interface runtime used by the Vosk binding; upstream licence included in the desktop bundle. <https://github.com/python-cffi/cffi>.
- **pycparser** — BSD-3-Clause Python C parser dependency of CFFI; upstream licence included with desktop packages. <https://github.com/eliben/pycparser>.
- **srt 3.5.3** — MIT subtitle/timecode parsing helper used by Vosk. <https://github.com/cdown/srt>.
- **tqdm 4.67.1** — MPL-2.0 AND MIT progress utility used by Vosk, including its file-specific upstream notices. <https://github.com/tqdm/tqdm>.
- **requests/tqdm transitive runtime wheels** — charset-normalizer, idna, urllib3, certifi, and where installed on Windows, colorama. Their copied upstream licence files are included in the desktop bundle under `assets/licenses/components`. <https://github.com/psf/requests>.
- **Pillow 12.3.0** — bundled Python imaging helpers (PIL Software License / HPND-style upstream terms); upstream licence copied into desktop packaging. <https://github.com/python-pillow/Pillow>.
- **PyInstaller 6.22.3** — GPL with its bootloader exception permitting bundled application distribution. <https://pyinstaller.org/en/stable/license.html>.

The desktop build copies upstream licence files from python-vlc, tzdata, Vosk, CFFI, pycparser, requests, srt, tqdm, requests' HTTP dependencies, Pillow and PyInstaller into `assets/licenses/components`, alongside the Python 3.12 licence and this notice. Where a Windows-specific dependency such as colorama is installed, its upstream notices are copied too. Android also bundles **AndroidX DocumentFile 1.0.1** (Apache 2.0), <https://android.googlesource.com/platform/frameworks/support/+/refs/tags/androidx-documentfile-release/documentfile/>. Licence copies are shipped as APK assets. Build-time Kotlin, Gradle, Android Gradle Plugin and JUnit are not application runtime libraries.

Desktop packages are unsigned development builds (macOS uses an ad-hoc app signature). A debug Android APK is a development artifact. Public release signing and the final redistribution/source-offer review are separate release gates. No open-source licence for DizyTV itself has been selected by the owner yet; a public GitHub repository alone does not grant a source licence.
