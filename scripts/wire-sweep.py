#!/usr/bin/env python3
"""Draw-wire sweep — prove a cockpit surface actually reaches the screen.

# The defect this exists for

This codebase splits chrome into pure composers (``tw2002_aiclient/cockpit/*.py``,
no ``curses``) and a draw layer (``screens.py``). Tests overwhelmingly target
the composer, because composers are testable. **The call site is the one place
the convention does not test**, so a surface can carry a thorough suite — even a
real-terminal PTY proof — while the product never passes it to the composer at
all. It renders nothing, and CI is green.

Three confirmed instances (2026-07-27): the coverage meter, the CONN chip, and
the `P` panic key. Deleting each wire left the full suite green at 4917–4976
tests. None was found by writing better tests; each was found by deleting the
wire and watching nothing complain.

Hence the standing Accept criterion (hub ADOPT 2026-07-27, Cursor ACK):

    For any new chip, key, or intent: delete its screens.py/app.py argument,
    re-run, and show something goes red. If nothing does, the wire is unpinned.

This script mechanises that, because a rule run by hand is run inconsistently —
and the hand-run version has a specific, known failure mode (below).

# Usage

    python3 scripts/wire-sweep.py --control coverage_meter \\
        liveness_text arm_chip conn_chip coverage_meter status_offer teach_band

Exit 0 = every wire PINNED. Exit 1 = at least one UNPINNED. Exit 2 = the run is
void (see the positive control).

# Why a positive control is mandatory, not optional

A sweep that reports "everything is pinned" is **indistinguishable from a sweep
whose deletion silently did nothing**. So ``--control`` names a wire already
known to be pinned; if it does not come back red, the run is reported VOID and
exits 2. Every other result in that run is meaningless rather than reassuring.
This is not defensive decoration — it is the only thing separating a green
sweep from a broken one.

# Why deletion is paren-matched and AST-gated

The obvious implementation — delete the line matching ``name=`` — is wrong for
any kwarg whose value spans lines, and it fails *dangerously*: it leaves a
syntax error, pytest collects almost nothing, the failure count is non-zero, and
a naive reading books that as PINNED. That exact false positive happened on
``teach_band`` during the first sweep and was caught only because the *test
count had moved* (4538 against a 4987 baseline).

So: the value's extent is found by tracking paren depth, the result must
``ast.parse()`` before it is written, and a run whose collected-test count does
not match the baseline is reported CONTAMINATED — never PINNED. A verdict that
cannot tell "the pin fired" from "I broke the file" is not a verdict.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

# Shared junitxml honesty (WO-CERT-JUNIT-HARDFAIL) — same directory as this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from junitxml_guard import counts as _counts  # noqa: E402

PINNED = "PINNED"
UNPINNED = "UNPINNED"
CONTAMINATED = "CONTAMINATED"
ANCHOR_MISS = "ANCHOR-MISS"


def run_suite(repo: Path, tests: str) -> tuple[int, int, int]:
    """Run pytest; counts come from junitxml — never from the terminal.

    The terminal's exit status is unusable here: ``pytest | tail`` reports
    *tail*'s status, and pytest itself exits 0 having run zero tests when
    collection dies. The report is the only honest source.
    """
    xml = repo / ".wire-sweep.xml"
    if xml.exists():
        xml.unlink()
    subprocess.run(
        [sys.executable, "-m", "pytest", tests, "-q", f"--junitxml={xml}"],
        cwd=repo, capture_output=True, text=True,
    )
    return _counts(xml)


def delete_kwarg(src: str, name: str) -> str:
    """Remove ``name=<expr>,`` from a call, however many lines the value spans.

    Raises ``LookupError`` if the anchor is absent or ambiguous — aborting is
    correct, because a miss that is silently treated as "nothing to delete"
    reports the wire as PINNED when it was never tested at all.

    Deletes **only** the named kwarg. A line-oriented implementation over-deletes
    whenever several kwargs share a line: the first sweep's regex removed
    ``liveness_text=liveness_text, width=cs_w, unicode_ok=uok,`` whole, and the
    resulting 57 failures were mostly the missing ``width``, not the wire under
    test. It still reached the right verdict here, but by accident — an
    over-deletion can just as easily turn an UNPINNED wire green-adjacent by
    breaking something else loudly.

    The exact-one-occurrence guard also disambiguates a kwarg from a same-named
    local: ``liveness_text=`` (kwarg) does not match ``liveness_text = `` (the
    assignment above it) only because of the space. If a reformat ever made both
    match, ``hits != 1`` aborts rather than deleting the wrong one — the failure
    is loud, not silent.
    """
    anchor = f"{name}="
    hits = src.count(anchor)
    if hits != 1:
        raise LookupError(f"{name!r} appears {hits} times — expected exactly 1")
    start = src.index(anchor)
    # Back up to the start of the line so indentation goes with it.
    line_start = src.rfind("\n", 0, start) + 1
    i = src.index("=", start) + 1
    while src[i] in " ":
        i += 1
    if src[i] == "(":
        depth = 0
        while True:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        end = i + 1
    else:
        end = src.index(",", i)
    while end < len(src) and src[end] in ", ":
        end += 1
    if end < len(src) and src[end] == "\n":
        end += 1
    out = src[:line_start] + src[end:]
    ast.parse(out)  # refuse to write a file that does not compile
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("wires", nargs="+", help="kwarg names to sweep")
    ap.add_argument("--control", required=True,
                    help="a wire ALREADY known pinned; the run is void if it comes back green")
    ap.add_argument("--file", default="tw2002_aiclient/screens.py")
    ap.add_argument("--tests", default="tests/")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()

    if args.control not in args.wires:
        print(f"FATAL: --control {args.control!r} must be among the swept wires", file=sys.stderr)
        return 2

    repo = Path(args.repo).resolve()
    target = repo / args.file
    original = target.read_text()

    base_t, base_f, base_e = run_suite(repo, args.tests)
    print(f"BASELINE: tests={base_t} failures={base_f} errors={base_e}", flush=True)
    if base_t == 0 or base_f or base_e:
        print("FATAL: baseline is not green and non-empty — sweep aborted", file=sys.stderr)
        return 2

    results: dict[str, str] = {}
    try:
        for wire in args.wires:
            try:
                target.write_text(delete_kwarg(original, wire))
            except (LookupError, SyntaxError) as exc:
                results[wire] = ANCHOR_MISS
                print(f"  {wire:18} {ANCHOR_MISS}: {exc}", flush=True)
                target.write_text(original)
                continue
            t, f, e = run_suite(repo, args.tests)
            target.write_text(original)
            if t != base_t:
                # Collection moved => the deletion broke the tree rather than
                # tripping a pin. NEVER book this as PINNED.
                verdict = CONTAMINATED
            elif f or e:
                verdict = PINNED
            else:
                verdict = UNPINNED
            results[wire] = verdict
            print(f"  {wire:18} tests={t:5} failures={f:3} errors={e:3}  -> {verdict}", flush=True)
    finally:
        target.write_text(original)
        assert target.read_text() == original, "RESTORE FAILED — check the tree by hand"

    print("\n==== SUMMARY ====", flush=True)
    for wire, verdict in results.items():
        print(f"  [{'OK ' if verdict == PINNED else 'GAP'}] {wire:18} {verdict}", flush=True)

    if results.get(args.control) != PINNED:
        print(f"\n!! VOID — positive control {args.control!r} came back "
              f"{results.get(args.control)}, not {PINNED}.", flush=True)
        print("!! The deletion mechanism is not proven to do anything.", flush=True)
        print("!! Every GREEN above is meaningless, not reassuring.", flush=True)
        return 2

    print(f"\npositive control ({args.control}): PINNED — sweep is trustworthy", flush=True)
    gaps = [w for w, v in results.items() if v != PINNED]
    if gaps:
        print(f"UNPINNED / unresolved: {', '.join(gaps)}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
