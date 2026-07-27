"""Analyze draft human-approval gate — WO-P5-070.

After an Analyze overlay closes, the AI teacher's proposed rule is a
**draft** — inert until the human explicitly approves it.  This module
owns the draft schema, the ``y/N`` approval gate (same default-deny key
policy as :mod:`armconfirm`), and promotion to a playback-eligible stub.

No live I/O, no send path, no ledger writer — ``app.py`` records
approval attribution on confirm only.
"""

from __future__ import annotations

from tw2002_aiclient.cockpit import assign_trigger

CONFIRM = "confirm"
CANCEL = "cancel"

_CONFIRM_KEYS = frozenset({ord("y"), ord("Y")})

DRAFT_APPROVE_TONE = "info"
CONFIRM_HINT = "y/N"
_HINT_GAP = "  "


def create_analyze_draft(screen_class: object = None) -> dict:
    """Return an inert analyze-sourced draft rule (never playback-eligible)."""
    stub = assign_trigger.create_stub(screen_class)
    stub["source"] = "analyze"
    stub["approved"] = False
    stub["playback_eligible"] = False
    return stub


def promote_to_approved(draft: object) -> dict | None:
    """Copy ``draft`` with approval flags set, or ``None`` if not a dict."""
    if not isinstance(draft, dict):
        return None
    out = dict(draft)
    when = out.get("when")
    if isinstance(when, dict):
        out["when"] = dict(when)
        guards = when.get("guards")
        if isinstance(guards, list):
            out["when"]["guards"] = list(guards)
    out["approved"] = True
    out["playback_eligible"] = True
    return out


def compose_draft_approve_line(screen: object = None, *, unicode_ok: object = True) -> str:
    """``Approve analyze draft (<screen>)?  y/N`` — never raises."""
    label = screen if isinstance(screen, str) and screen else "?"
    return f"Approve analyze draft ({label})?{ _HINT_GAP}{CONFIRM_HINT}"


def resolve_draft_approve_key(key: object) -> str:
    """``CONFIRM`` for ``y``/``Y`` only; ``CANCEL`` for everything else."""
    if isinstance(key, bool) or not isinstance(key, int):
        return CANCEL
    return CONFIRM if key in _CONFIRM_KEYS else CANCEL
