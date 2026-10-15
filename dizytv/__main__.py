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
    parser.add_argument('--data-dir')
    args=parser.parse_args()
    if args.worker:
        from dizytv.recorder import worker
        worker(args.data_dir)
        return 0
    configure_desktop_environment()
    from dizytv.desktop import run
    return run(args.data_dir,args.smoke_test)


if __name__=='__main__':sys.exit(main())
