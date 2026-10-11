import argparse
import sys


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
    from dizytv.desktop import run
    return run(args.data_dir,args.smoke_test)


if __name__=='__main__':sys.exit(main())
