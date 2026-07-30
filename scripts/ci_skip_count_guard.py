#!/usr/bin/env python3
"""CI skip-count guard — fail closed when junitxml reports any skipped tests.

WO-TEST-CI-SKIP-COUNT-GUARD: pin ``skipped == 0``. Absence / toy XML must not
look green — require a plausible thousands-scale ``tests`` count **before**
reading ``skipped``.

CLI::

    python3 scripts/ci_skip_count_guard.py /path/to/junit.xml

Exit: 0 clean · 1 hard-fail · 2 usage
"""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# CI offline suite (not live_login / not pty_ui) is thousands of tests.
# Override only for focused unit pins that feed synthetic XML.
DEFAULT_MIN_TESTS = 1000


def _suites(root: ET.Element) -> list[ET.Element]:
    if root.tag == "testsuite":
        return [root]
    return list(root.findall("testsuite"))


def parse_counts(xml: Path) -> tuple[int, int, int, int] | None:
    """Return ``(tests, failures, errors, skipped)`` or ``None`` if unusable."""
    if not xml.exists() or xml.stat().st_size == 0:
        return None
    head = xml.read_bytes()[:8192].lower()
    if b"<!doctype" in head or b"<!entity" in head:
        return None
    try:
        root = ET.parse(xml).getroot()
    except ET.ParseError:
        return None
    suites = _suites(root)
    if not suites:
        return None
    return (
        sum(int(s.get("tests", 0)) for s in suites),
        sum(int(s.get("failures", 0)) for s in suites),
        sum(int(s.get("errors", 0)) for s in suites),
        sum(int(s.get("skipped", 0)) for s in suites),
    )


def require_zero_skips(xml: Path, *, min_tests: int = DEFAULT_MIN_TESTS) -> tuple[int, int, int, int]:
    """Require usable junitxml with ``tests >= min_tests`` and ``skipped == 0``."""
    path = Path(xml)
    if not path.exists():
        print(f"CI SKIP-GUARD HARD-FAIL: junitxml missing: {path}", file=sys.stderr)
        raise SystemExit(1)
    if path.stat().st_size == 0:
        print(f"CI SKIP-GUARD HARD-FAIL: junitxml empty: {path}", file=sys.stderr)
        raise SystemExit(1)
    parsed = parse_counts(path)
    if parsed is None:
        print(
            f"CI SKIP-GUARD HARD-FAIL: junitxml unparseable or disqualified: {path}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    tests, failures, errors, skipped = parsed
    if tests < min_tests:
        print(
            f"CI SKIP-GUARD HARD-FAIL: implausible tests={tests} "
            f"(need >= {min_tests}) in {path}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if skipped != 0:
        print(
            f"CI SKIP-GUARD HARD-FAIL: skipped={skipped} (pin is 0) in {path}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return tests, failures, errors, skipped


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] in ("-h", "--help"):
        print(
            "Usage: ci_skip_count_guard.py <junitxml-path>\n"
            "Exit 0 if tests>=MIN (default 1000) and skipped==0; else exit 1.\n"
            "Env CI_SKIP_GUARD_MIN_TESTS overrides the floor (pins only).",
            file=sys.stderr,
        )
        return 2 if len(args) != 1 else 0
    min_tests = int(os.environ.get("CI_SKIP_GUARD_MIN_TESTS", str(DEFAULT_MIN_TESTS)))
    tests, failures, errors, skipped = require_zero_skips(
        Path(args[0]), min_tests=min_tests
    )
    print(
        f"ci skip-guard ok: tests={tests} failures={failures} "
        f"errors={errors} skipped={skipped} (min_tests={min_tests})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
