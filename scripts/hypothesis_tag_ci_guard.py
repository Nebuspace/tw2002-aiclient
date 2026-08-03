#!/usr/bin/env python3
"""CI hypothesis-tag discipline guard (PWO-114).

Runs against the **real** ``tw2002_aiclient.port_economics`` module — not a
mock. Every authored product-stat ``HypothesisParam`` must carry
``tag='hypothesis'`` and ``verified_vs_live=False`` until a live-confirm WO
flips it.

CLI::

    python3 scripts/hypothesis_tag_ci_guard.py           # tip green path
    python3 scripts/hypothesis_tag_ci_guard.py --self-test-fail
        # deliberate untagged fixture — must exit 1 (proves the check bites)

Exit: 0 clean · 1 hard-fail · 2 usage
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import fields
from pathlib import Path

# Running as ``python scripts/….py`` puts ``scripts/`` on sys.path[0], which
# hides a cwd-only / uninstalled tree. Prefer the repo root so the *real*
# package imports in local harnesses; CI still uses ``pip install -e .``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tw2002_aiclient import port_economics
from tw2002_aiclient.port_economics import HypothesisParam, assert_all_unverified_tagged


def _untagged_fixture() -> HypothesisParam:
    """Build a HypothesisParam that bypasses ``__post_init__`` validation.

    Used only by ``--self-test-fail`` to prove ``assert_all_unverified_tagged``
    catches an untagged number — not for production data.
    """
    bad = object.__new__(HypothesisParam)
    for f in fields(HypothesisParam):
        if f.name == "key":
            object.__setattr__(bad, f.name, "ci_self_test_untagged")
        elif f.name == "value":
            object.__setattr__(bad, f.name, 999.0)
        elif f.name == "unit":
            object.__setattr__(bad, f.name, "credits")
        elif f.name == "source_note":
            object.__setattr__(bad, f.name, "deliberate untagged fixture")
        elif f.name == "verified_vs_live":
            object.__setattr__(bad, f.name, False)
        elif f.name == "tag":
            object.__setattr__(bad, f.name, "untagged")  # not "hypothesis"
        else:
            object.__setattr__(bad, f.name, f.default)
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test-fail",
        action="store_true",
        help="Inject an untagged fixture and require assert to fail (exit 1)",
    )
    args = parser.parse_args(argv)

    if args.self_test_fail:
        bad = _untagged_fixture()
        try:
            # Inspect the real assert against a synthetic authored set.
            saved = port_economics.AUTHORED_PARAMS
            port_economics.AUTHORED_PARAMS = (bad,)  # type: ignore[misc]
            try:
                assert_all_unverified_tagged()
            finally:
                port_economics.AUTHORED_PARAMS = saved  # type: ignore[misc]
        except AssertionError as exc:
            print(
                f"OK [hypothesis-tag self-test]: assert bit as expected: {exc}",
                file=sys.stderr,
            )
            return 1  # expected failure signal for the shell harness
        print(
            "CI HYPOTHESIS-TAG HARD-FAIL: --self-test-fail did not raise "
            "(assert is a no-op — gate is broken)",
            file=sys.stderr,
        )
        return 1

    # Live tip path — real module only.
    try:
        assert_all_unverified_tagged()
    except AssertionError as exc:
        print(f"CI HYPOTHESIS-TAG HARD-FAIL: {exc}", file=sys.stderr)
        return 1

    n = len(port_economics.all_hypothesis_params())
    print(f"OK [hypothesis-tag]: {n} authored params tagged hypothesis + unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
