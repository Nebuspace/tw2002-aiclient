#!/usr/bin/env python3
"""Offline: classify live a-net frame bytes vs fixture (WO-ANET-STEP5-LIVE-BYTES)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tw2002_aiclient.session.classify import classify, classify_screen  # noqa: E402

FRAME = Path(
    "/tmp/claude-501/-Users-mrathbone-github-Nebuspace-tw2002-aiclient/"
    "a0854ced-c3bf-4204-a5b8-c700ee37255f/scratchpad/anet-frame-A.json"
)
FIXTURE = ROOT / "tests/fixtures/game_select_menu_banner_anet_boxed_title.txt"


def main() -> None:
    data = json.loads(FRAME.read_text())
    rows = [str(r).rstrip("\n") for r in data["screen"]]
    live_text = "\n".join(rows)
    live_prompt = str(data.get("prompt") or (rows[-1] if rows else "")).strip()
    fixture_text = FIXTURE.read_text()
    fixture_rows = fixture_text.splitlines()
    fixture_prompt = fixture_rows[-1].strip() if fixture_rows else ""

    print("LIVE_ROWS", len(rows))
    print("LIVE_PROMPT_REPR", repr(live_prompt[:80]))
    print("LIVE_HAS_SELECTION", any("Selection" in r for r in rows))
    print("LIVE_HAS_TITLE", any("Trade Wars 2002 Game Server" in r for r in rows))
    print("LIVE_classify", classify(live_text))
    print("LIVE_classify_screen", classify_screen(live_text, live_prompt))
    print("LIVE_recorded_classification", data.get("classification"))
    print("FIXTURE_ROWS", len(fixture_rows))
    print("FIXTURE_PROMPT_REPR", repr(fixture_prompt))
    print("FIXTURE_classify", classify(fixture_text))
    print("FIXTURE_classify_screen", classify_screen(fixture_text, fixture_prompt))

    # Structural diff summary (no full dump)
    live_set = {r.strip() for r in rows if r.strip()}
    fix_set = {r.strip() for r in fixture_rows if r.strip()}
    only_live = sorted(live_set - fix_set)
    only_fix = sorted(fix_set - live_set)
    print("ONLY_LIVE_NONEMPTY_LINES", len(only_live))
    for line in only_live[:12]:
        print("  L+", repr(line[:100]))
    print("ONLY_FIXTURE_NONEMPTY_LINES", len(only_fix))
    for line in only_fix[:12]:
        print("  F+", repr(line[:100]))


if __name__ == "__main__":
    main()
