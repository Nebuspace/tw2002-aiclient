"""python -m tw2002_aiclient"""

import sys


def main() -> int:
    from tw2002_aiclient.app import main as app_main

    # --help / -h must work without a TTY (WO-TUI-HELP-ARGV); bare launch
    # still requires a real terminal before curses.
    argv = sys.argv[1:]
    if any(a in ("-h", "--help") for a in argv):
        return app_main(argv)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("requires a real terminal", file=sys.stderr)
        return 2
    return app_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
