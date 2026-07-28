#!/usr/bin/env python3
"""Hard-fail guard for seat certs that claim green via ``--junitxml``.

WO-CERT-JUNIT-HARDFAIL: a zero-exit pytest run with a missing, empty, unparseable,
or zero-test junitxml must not be reported as PASS. Call after pytest exits 0;
do not invoke when pytest already exited non-zero (that is already a hard fail).

CLI::

    python3 scripts/junitxml_guard.py /path/to/junit.xml
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def counts(xml: Path) -> tuple[int, int, int]:
    """Return ``(tests, failures, errors)`` from a pytest junitxml file.

    On missing / empty / disqualifying / unparseable input returns
    ``(0, -1, -1)`` so callers can treat ``failures < 0`` as "unusable artifact".
    """
    if not xml.exists() or xml.stat().st_size == 0:
        return (0, -1, -1)
    # XXE / billion-laughs hardening without a new dependency: pytest's writer
    # never emits DOCTYPE/ENTITY — their presence means this is not our artifact.
    head = xml.read_bytes()[:8192].lower()
    if b"<!doctype" in head or b"<!entity" in head:
        return (0, -1, -1)
    try:
        root = ET.parse(xml).getroot()
    except ET.ParseError:
        return (0, -1, -1)
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    return (
        sum(int(s.get("tests", 0)) for s in suites),
        sum(int(s.get("failures", 0)) for s in suites),
        sum(int(s.get("errors", 0)) for s in suites),
    )


def require_honest_junitxml(xml: Path) -> tuple[int, int, int]:
    """Require a usable junitxml with ≥1 collected test.

    Returns the ``(tests, failures, errors)`` triple on success.
    Exits process with code 1 and an explicit message on hard-fail conditions.
    """
    path = Path(xml)
    if not path.exists():
        print(
            f"CERT HARD-FAIL: junitxml missing: {path}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if path.stat().st_size == 0:
        print(
            f"CERT HARD-FAIL: junitxml empty: {path}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    tests, failures, errors = counts(path)
    if failures < 0:
        print(
            f"CERT HARD-FAIL: junitxml unparseable or disqualified: {path}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if tests == 0:
        print(
            f"CERT HARD-FAIL: junitxml reports zero tests: {path}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return tests, failures, errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] in ("-h", "--help"):
        print(
            "Usage: junitxml_guard.py <junitxml-path>\n"
            "Exit 0 if file exists, parses, and tests≥1; else exit 1.",
            file=sys.stderr,
        )
        return 2 if len(args) != 1 else 0
    tests, failures, errors = require_honest_junitxml(Path(args[0]))
    print(f"junitxml ok: tests={tests} failures={failures} errors={errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
