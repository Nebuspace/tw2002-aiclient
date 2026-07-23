"""python -m tw2002_aiclient"""

import sys


def main() -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("requires a real terminal", file=sys.stderr)
        return 2
    print("tw2002-aiclient (placeholder)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
