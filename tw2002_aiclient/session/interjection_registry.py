"""Closed allow-list of known unsolicited-output shapes with standing responses.

Canon: ``canon/architecture/settle-detection.md`` § Interjection registry.

A settled frame that matches here is *absorbed* (auto-handled) so escalate-on-
unknown stays trustworthy. Anything not registered and not a taught screen
must STOP and surface to the human — this module is a conservative allow-list,
never a catch-all.

Drivers (login today; other play-path callers as they migrate) consult
:func:`match_interjection` so the absorbed-vs-surfaced boundary lives in
exactly one place. Classification anchors (e.g. ``pause_key`` in
``classify.py``) stay where they are; this registry owns the *response*
pairing and the non-class text matches that login historically scattered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

__all__ = [
    "InterjectionHit",
    "SHOW_LOG_RE",
    "INACTIVITY_RE",
    "BEEN_ON_TODAY_RE",
    "CLEAR_AVOIDS_RE",
    "INTERJECTION_IDS",
    "match_interjection",
]


@dataclass(frozen=True)
class InterjectionHit:
    """One registered nuisance plus the standing safe send."""

    id: str
    response: str
    secret: bool = False
    wait_prompt_hint: Optional[str] = None


# Patterns observed live (login corpus / DESIGN-v2 D7). Kept as module-level
# names so scrollback-scope pins in tests/test_login_scrollback_search.py can
# still import them via ``login`` re-exports.
SHOW_LOG_RE = re.compile(r"show\s+today.?s\s+log", re.I)
INACTIVITY_RE = re.compile(r"inactivity\s+warning|critical\s+inactivity", re.I)
BEEN_ON_TODAY_RE = re.compile(
    r"you\s+have\s+been\s+on\s+(?:the\s+game\s+)?today", re.I
)
CLEAR_AVOIDS_RE = re.compile(
    r"do\s+you\s+wish\s+to\s+clear\s+some\s+avoids\s*\?\s*\(\s*Y\s*/\s*N\s*\)",
    re.I,
)

INTERJECTION_IDS = frozenset(
    {
        "pause_key",
        "been_on_today",
        "show_todays_log",
        "clear_avoids",
        "inactivity_warning",
    }
)


def match_interjection(
    cls: str,
    text: str,
    prompt: str,
    *,
    profile: Any = None,
    option_block: str = "",
) -> Optional[InterjectionHit]:
    """Return a hit when the settled screen is a registered nuisance.

    Order matches the historical login automaton nuisance branch (load-bearing
    for scrollback-scope pins). Callers that must refuse a closed-game screen
    sharing ``[Pause]`` must check that refusal *before* absorbing
    ``pause_key`` — closed-game is a hard fail, not an absorbable interjection.
    """
    text = text or ""
    prompt = prompt or ""
    option_block = option_block or ""

    if cls == "pause_key":
        # Blank Enter dismisses ``[Pause]`` / ``-- More --`` / press-any-key.
        return InterjectionHit("pause_key", "")

    if BEEN_ON_TODAY_RE.search(prompt):
        return InterjectionHit("been_on_today", "")

    if cls == "unknown" and not prompt.strip():
        for line in reversed(text.splitlines()):
            stripped = line.strip()
            if not stripped:
                continue
            if BEEN_ON_TODAY_RE.search(stripped):
                return InterjectionHit("been_on_today", "")
            break

    # Whole-grid: the log question sits in the BODY above the prompt.
    if SHOW_LOG_RE.search(text):
        return InterjectionHit("show_todays_log", "N")

    # Prompt-or-option-block only — never whole-grid (stale scrollback).
    if CLEAR_AVOIDS_RE.search(prompt) or CLEAR_AVOIDS_RE.search(option_block):
        clear = bool(getattr(profile, "clear_avoids_on_login", False))
        return InterjectionHit("clear_avoids", "Y" if clear else "N")

    if INACTIVITY_RE.search(prompt) or INACTIVITY_RE.search(option_block):
        return InterjectionHit("inactivity_warning", "")

    return None
