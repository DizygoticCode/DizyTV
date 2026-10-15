"""Linux bundle: use the host's matching libVLC runtime and plugins."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = Path(SPEC).resolve().parent.parent
a = Analysis(
    [str(root / 'dizytv' / '__main__.py')],
    pathex=[str(root)],
    binaries=collect_dynamic_libs('vosk'),
    datas=[(str(root / 'assets'), 'assets'), *collect_data_files('tzdata')],
    hiddenimports=['vlc', 'vosk'],
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
