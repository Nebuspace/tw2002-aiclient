"""Player bank — metadata-only rotation bookkeeping (WO-P1-015 stub).

Tracks which characters exist (linked to profile names) plus ``last_played`` /
``turns_state``. Passwords are never stored here — structurally absent.
The rotation *driver* is out of scope for this wave.
"""

from __future__ import annotations

import json
from pathlib import Path

from tw2002_aiclient.session import credentials

# session/player_bank.py → session → tw2002_aiclient → repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = PROJECT_ROOT / "state"
BANK_PATH = STATE_DIR / "player_bank.json"

# Honest empty-rotation sentinels (never fabricate a timestamp).
NEVER = "never"
TURNS_UNKNOWN = "-"


def _load_bank_raw() -> dict:
    if not BANK_PATH.exists():
        return {"version": 1, "players": []}
    try:
        with open(BANK_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "players": []}
    if not isinstance(data, dict):
        return {"version": 1, "players": []}
    players = data.get("players")
    if not isinstance(players, list):
        data = {"version": 1, "players": []}
    return data


def list_players() -> list[dict[str, str]]:
    """Return metadata-only bank rows for the launcher touchpoint.

    Shape matches ``tw players list`` columns: name, handle, host, game_letter,
    last_played, turns_state. Missing rotation history uses ``never`` / ``-``.
    """
    bank = _load_bank_raw()
    by_name = {
        str(p.get("name")): p
        for p in bank.get("players", [])
        if isinstance(p, dict) and p.get("name")
    }
    rows: list[dict[str, str]] = []
    for summary in credentials.list_profile_summaries():
        name = str(summary.get("name") or "")
        if not name or summary.get("error"):
            continue
        stored = by_name.get(name, {})
        last = stored.get("last_played")
        if last is None or last == "":
            last_played = NEVER
        else:
            last_played = str(last)[:21]
        turns = stored.get("turns_state")
        turns_state = TURNS_UNKNOWN if turns in (None, "") else str(turns)
        rows.append(
            {
                "name": name,
                "handle": str(summary.get("handle") or "?"),
                "host": str(summary.get("host") or summary.get("server") or "?"),
                "game_letter": str(summary.get("game_letter") or "?"),
                "last_played": last_played,
                "turns_state": turns_state,
            }
        )
    # Bank-only entries (profile removed) still surface as diagnosable rows.
    known = {r["name"] for r in rows}
    for name, stored in by_name.items():
        if name in known:
            continue
        last = stored.get("last_played")
        last_played = NEVER if last in (None, "") else str(last)[:21]
        turns = stored.get("turns_state")
        turns_state = TURNS_UNKNOWN if turns in (None, "") else str(turns)
        rows.append(
            {
                "name": name,
                "handle": str(stored.get("handle") or "?"),
                "host": str(stored.get("host") or "?"),
                "game_letter": str(stored.get("game_letter") or "?"),
                "last_played": last_played,
                "turns_state": turns_state,
            }
        )
    return rows
