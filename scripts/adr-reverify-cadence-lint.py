#!/usr/bin/env python3
"""ADR re-verification cadence lint (generalized).

Flags Folded / Distributed-fold ADRs whose ``(re-verified YYYY-MM-DD)`` tag is
missing or older than a staleness window, and Index↔body N/M mismatches.

Ported from Nebuspace ``.samantha/scripts/adr-reverify-cadence-lint.py`` with
``--dir`` / ``--index`` so the same tool can target:

* tw2002-aiclient ``canon/ADR/`` + ``index.md`` (default when run from this repo)
* sw2102-docs ``ADR/`` + ``README.md`` (pass ``--dir`` / ``--index``)

Usage::

    python3 scripts/adr-reverify-cadence-lint.py
    python3 scripts/adr-reverify-cadence-lint.py --stale-days 30
    python3 scripts/adr-reverify-cadence-lint.py --json
    python3 scripts/adr-reverify-cadence-lint.py \\
        --dir /path/to/sw2102-docs/ADR --index README.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADR_DIR = REPO_ROOT / "canon" / "ADR"
DEFAULT_INDEX_NAME = "index.md"

SETTLED_STATUS_RE = re.compile(r"(?m)^(?:\*\*)?(Folded into|Distributed-fold)")
REVERIFIED_TAG_RE = re.compile(r"\(re-verified (\d{4}-\d{2}-\d{2})\b[^)]*\)")
# sw2102-docs: "# 0073 — Title" · aiclient: "# ADR 001 — Title" / "# ADR 003 — …"
TITLE_RE = re.compile(r"^# (?:ADR )?(\d{1,4}) — ", re.M)
# Filename stems: 001-… or 0073-…
STEM_ID_RE = re.compile(r"^(\d{1,4})")

# Index Status cell N/M — sw2102 table uses bare ADR id in col1;
# aiclient uses markdown links ``[001](...)``.
INDEX_NM_RE = re.compile(
    r"^\|\s*(?:\[)?(\d{1,4})(?:\])?[^|]*\|[^|]+\|\s*"
    r"(?:\*\*)?"
    r"(?:Distributed-fold\s*\((\d+)/(\d+)\)|"
    r"Folded into[^|]*?\((\d+)/(\d+)|"
    r"Folded into[^|]*?re-verified[^|]*?(\d+)/(\d+))",
    re.M,
)

BODY_STATUS_SECTION_RE = re.compile(
    r"^## Status\s*\n+(.*?)(?=\n## |\Z)", re.S | re.M
)
BODY_NM_RE = re.compile(
    r"(?:Distributed-fold[^\n]*?\*\*)?(\d+)/(\d+)\s+"
    r"(?:confirmed live|shipped|items landed|gap closed)",
    re.I,
)


def _normalize_adr_id(raw: str) -> str:
    """Pad numeric ADR ids to 3 digits for stable map keys (001 vs 1)."""
    try:
        return f"{int(raw):03d}"
    except ValueError:
        return raw


def _parse_index_nm(index_path: Path) -> dict[str, tuple[int, int]]:
    if not index_path.exists():
        return {}
    text = index_path.read_text()
    out: dict[str, tuple[int, int]] = {}
    for m in INDEX_NM_RE.finditer(text):
        adr_id = _normalize_adr_id(m.group(1))
        if m.group(2) is not None:
            out[adr_id] = (int(m.group(2)), int(m.group(3)))
        elif m.group(4) is not None:
            out[adr_id] = (int(m.group(4)), int(m.group(5)))
        else:
            out[adr_id] = (int(m.group(6)), int(m.group(7)))
    return out


def _parse_body_nm(text: str) -> tuple[int, int] | None:
    sec = BODY_STATUS_SECTION_RE.search(text)
    if not sec:
        return None
    body = sec.group(1)
    m = BODY_NM_RE.search(body)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Fallback: bare **N/M** or "(re-verified … — N/M …)" early in Status
    bare = re.search(r"\*\*(\d+)/(\d+)\b", body) or re.search(
        r"re-verified[^)]*?(\d+)/(\d+)", body
    )
    if not bare:
        return None
    return int(bare.group(1)), int(bare.group(2))


def _adr_id_from(path: Path, text: str) -> str:
    title_m = TITLE_RE.search(text)
    if title_m:
        return _normalize_adr_id(title_m.group(1))
    stem_m = STEM_ID_RE.match(path.stem)
    if stem_m:
        return _normalize_adr_id(stem_m.group(1))
    return path.stem[:4]


def scan(adr_dir: Path, index_path: Path, stale_days: int) -> dict:
    today = date.today()
    skip_names = {index_path.name.lower(), "readme.md"}
    settled: list[tuple[Path, str]] = []
    for path in sorted(adr_dir.glob("*.md")):
        if path.name.lower() in skip_names:
            continue
        text = path.read_text()
        if SETTLED_STATUS_RE.search(text):
            settled.append((path, text))

    missing = []
    stale = []
    fresh = []
    for path, text in settled:
        adr_id = _adr_id_from(path, text)
        tag_m = REVERIFIED_TAG_RE.search(text)
        if not tag_m:
            missing.append({"adr": adr_id, "file": path.name})
            continue
        tagged_date = datetime.strptime(tag_m.group(1), "%Y-%m-%d").date()
        age_days = (today - tagged_date).days
        entry = {
            "adr": adr_id,
            "file": path.name,
            "re_verified": tag_m.group(1),
            "age_days": age_days,
        }
        if age_days > stale_days:
            stale.append(entry)
        else:
            fresh.append(entry)

    index_nm = _parse_index_nm(index_path)
    nm_mismatch = []
    for path, text in settled:
        adr_id = _adr_id_from(path, text)
        body_nm = _parse_body_nm(text)
        idx_nm = index_nm.get(adr_id)
        if body_nm is None or idx_nm is None:
            continue
        if body_nm != idx_nm:
            nm_mismatch.append({
                "adr": adr_id,
                "file": path.name,
                "index_nm": f"{idx_nm[0]}/{idx_nm[1]}",
                "body_nm": f"{body_nm[0]}/{body_nm[1]}",
            })

    return {
        "adr_dir": str(adr_dir),
        "index": str(index_path),
        "scanned_settled_adrs": len(settled),
        "stale_threshold_days": stale_days,
        "missing_tag": missing,
        "stale_tag": stale,
        "fresh_count": len(fresh),
        "index_body_nm_mismatch": nm_mismatch,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_ADR_DIR,
        help=f"ADR directory (default: {DEFAULT_ADR_DIR})",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help=(
            "Index filename or path. Relative names resolve under --dir "
            f"(default: {DEFAULT_INDEX_NAME})."
        ),
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=45,
        help="Flag a re-verified tag older than this many days (default: 45).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a text report."
    )
    args = parser.parse_args(argv)

    adr_dir = args.dir.resolve()
    if args.index is None:
        index_path = adr_dir / DEFAULT_INDEX_NAME
    else:
        index_arg = args.index
        index_path = (
            index_arg.resolve()
            if index_arg.is_absolute() or len(index_arg.parts) > 1
            else (adr_dir / index_arg).resolve()
        )

    report = scan(adr_dir, index_path, args.stale_days)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"ADR re-verify cadence lint — {report['generated_at']}")
    print(f"dir={report['adr_dir']}  index={report['index']}")
    print(
        f"Scanned {report['scanned_settled_adrs']} settled "
        f"(Folded/Distributed-fold) ADRs; "
        f"stale threshold = {report['stale_threshold_days']} days"
    )
    print(f"  fresh:        {report['fresh_count']}")
    print(f"  stale:        {len(report['stale_tag'])}")
    print(f"  missing tag:  {len(report['missing_tag'])}")
    print(f"  Index↔body N/M mismatch: {len(report['index_body_nm_mismatch'])}")

    if report["missing_tag"]:
        print("\nMissing re-verified tag entirely:")
        for e in report["missing_tag"]:
            print(f"  - ADR-{e['adr']} ({e['file']})")

    if report["stale_tag"]:
        print(f"\nStale (older than {report['stale_threshold_days']}d):")
        for e in sorted(report["stale_tag"], key=lambda e: -e["age_days"]):
            print(
                f"  - ADR-{e['adr']} ({e['file']}) — last {e['re_verified']}, "
                f"{e['age_days']}d ago"
            )

    if report["index_body_nm_mismatch"]:
        print("\nIndex↔body N/M mismatches:")
        for e in report["index_body_nm_mismatch"]:
            print(
                f"  - ADR-{e['adr']} ({e['file']}) — Index {e['index_nm']} "
                f"vs body {e['body_nm']}"
            )

    flagged = (
        len(report["missing_tag"])
        + len(report["stale_tag"])
        + len(report["index_body_nm_mismatch"])
    )
    if flagged:
        print(f"\n{flagged} ADR(s) flagged for re-verification / Index sync.")
        return 1
    print(
        "\nAll settled ADRs are within the re-verification cadence; "
        "Index N/M matches bodies (when both present)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
