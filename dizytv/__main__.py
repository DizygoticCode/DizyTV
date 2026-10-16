import argparse
import os
import sys


def configure_desktop_environment():
    # libVLC 3 embeds with set_xwindow(), which requires an X11 XID. Qt's
    # Wayland winId is not one; use XWayland even in a Wayland desktop session.
    # Preserve the explicit headless backends used by tests and packaging CI.
    if sys.platform.startswith('linux'):
        backend = os.environ.get('QT_QPA_PLATFORM', '')
        if not backend or backend.startswith('wayland'):
            os.environ['QT_QPA_PLATFORM'] = 'xcb'


def main():
    parser=argparse.ArgumentParser(description='DizyTV native client')
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--smoke-test',action='store_true')
    parser.add_argument('--verify-native-components',action='store_true')
    parser.add_argument('--data-dir')
    args=parser.parse_args()
    if args.worker:
        from dizytv.recorder import worker
        worker(args.data_dir)
        return 0
    configure_desktop_environment()
    # Select the verified private VLC libraries *before* importing python-vlc.
    from dizytv.media_runtime import configure_private_vlc
    configure_private_vlc()
    if args.verify_native_components:
        # This is run against the *installed* package, not only a source
        # checkout. Force the actual dynamic linker and plugin paths to load.
        import subprocess
        import vlc
        from dizytv.auto_captions import verify_caption_engine
        binary,model=verify_caption_engine()
        subprocess.run([binary,'-version'],check=True,stdout=subprocess.DEVNULL)
        from dizytv.native_media_probe import verify_media_pipeline
        frames=verify_media_pipeline(binary,vlc)
        if frames<3:
            raise RuntimeError('Packaged video decoder did not produce frames')
        if not model:
            raise RuntimeError('Packaged Vosk model is unavailable')
        if sys.platform.startswith('linux'):
            # Assert the original-vendor opt-in installer is embedded within
            # the installed .deb's executable, without accessing the network.
            from dizytv.linux_ace_bootstrap import SHA256, OFFICIAL_URL
            if len(SHA256)!=64 or not OFFICIAL_URL.startswith('https://download.acestream.media/'):
                raise RuntimeError('Packaged Linux Ace bootstrap is missing or invalid')
        print('Verified packaged VLC, FFmpeg, Vosk and optional Linux bootstrap')
        return 0
    from dizytv.desktop import run
    return run(args.data_dir,args.smoke_test)


if __name__=='__main__':sys.exit(main())
