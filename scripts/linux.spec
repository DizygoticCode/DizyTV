"""Linux bundle: use the host's matching libVLC runtime and plugins."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = Path(SPEC).resolve().parent.parent
outpace = root / 'vendor' / 'outpace'
helper = outpace / 'outpace'
licence = outpace / 'LICENSE'
if not helper.is_file() or not licence.is_file():
    raise RuntimeError('Bundled Linux Outpace or original AGPL licence is missing')
a = Analysis(
    [str(root / 'dizytv' / '__main__.py')],
    pathex=[str(root)],
    binaries=[*collect_dynamic_libs('vosk'), (str(helper), 'outpace')],
    datas=[(str(root / 'assets'), 'assets'),
           (str(root / 'vendor' / 'speech'), 'speech'),
           (str(licence), 'outpace'),
           *collect_data_files('tzdata')],
    hiddenimports=['vlc', 'vosk', 'dizytv.linux_ace_bootstrap'],
)
# ctypes analysis automatically finds system VLC. Ship its Python binding,
# while resolving both native libraries from the same installation as plugins.
a.binaries = [entry for entry in a.binaries
              if not Path(entry[0]).name.startswith(('libvlc.so', 'libvlccore.so'))]

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='DizyTV',
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, name='DizyTV')
