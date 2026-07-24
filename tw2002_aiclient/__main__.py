"""python -m tw2002_aiclient"""

import sys


def main() -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("requires a real terminal", file=sys.stderr)
        return 2
    from tw2002_aiclient.app import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
