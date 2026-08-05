"""Opportunistic Layer-B game-data capture (AUDIT-BUILD-GAMEDATA-CAPTURE-LOOP).

When a settle-edge watch event's screen text already contains a StarDock
shipyard listing or cargo-hold quote (introspector header/footer grammar),
parse and persist Layer-B rows. Pure observe path: no send, no crawl, no
connection open.

Why not ``classify_screen`` alone: live fixtures end with ``main_command``
or ``money_prompt`` *after* the listing block, so gate anchors win and the
closed classes ``stardock_shipyard_listing`` / ``stardock_cargo_hold_quote``
are not the settled label. The introspector's last-header bracket match is
the durable signal that a listing is present.

PWO-092 Option B (live session introspect that navigates/sends) stays HELD.
This module only reacts to screens the human/app already landed on.

Hardening family matches ``cockpit/live_refresh.py``: never raises on the
play-loop idle tick.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from tw2002_aiclient import game_data as _game_data
from tw2002_aiclient import introspector as _introspector
from tw2002_aiclient import world_identity as _world_identity

# Documented classify labels for the same listing grammars (may appear on
# the watch event when the prompt is still inside the block). Content
# detection via introspector remains authoritative.
CAPTURE_SCREEN_CLASSES = frozenset(
    {
        "stardock_shipyard_listing",
        "stardock_cargo_hold_quote",
    }
)


@dataclass(frozen=True)
class CaptureResult:
    """Outcome of one opportunistic capture attempt (for pins / STATUS)."""

    attempted: bool
    screen_class: Optional[str]
    ships_persisted: int = 0
    cargo_persisted: bool = False
    reason: Optional[str] = None


class GameDataCapture:
    """Per-play-session dedupe so the 1 Hz idle tick does not rewrite the
    same listing every second while the operator sits on StarDock."""

    __slots__ = ("_last_fingerprint",)

    def __init__(self) -> None:
        self._last_fingerprint: Optional[str] = None

    def tick(self, play: object, profile: object, *, state_dir=None) -> CaptureResult:
        """Idle-tick entry. Never raises."""
        try:
            return self._tick(play, profile, state_dir=state_dir)
        except Exception:  # noqa: BLE001 — play-loop containment
            return CaptureResult(False, None, reason="error_contained")

    def _tick(self, play: object, profile: object, *, state_dir) -> CaptureResult:
        event = _latest_event(play)
        if event is None:
            return CaptureResult(False, None, reason="no_event")
        text = screen_text_from_event(event)
        if not text.strip():
            return CaptureResult(False, None, reason="no_text")
        hint = None
        if isinstance(event, Mapping):
            raw = event.get("classification")
            if isinstance(raw, str) and raw:
                hint = raw
        ships = _introspector.parse_shipyard_listing(text)
        cargo = _introspector.parse_cargo_hold_price(text)
        if not ships and cargo is None:
            return CaptureResult(False, hint, reason="no_listing")
        try:
            world_id = _world_identity.world_id_from_profile(profile)
        except Exception:  # noqa: BLE001
            return CaptureResult(False, hint, reason="no_world_id")
        if not isinstance(world_id, str) or not world_id:
            return CaptureResult(False, hint, reason="no_world_id")
        kind = "shipyard" if ships else "cargo_hold"
        fingerprint = f"{world_id}:{kind}:{_text_fingerprint(text)}"
        if fingerprint == self._last_fingerprint:
            return CaptureResult(False, hint or kind, reason="unchanged")
        result = capture_screen(
            world_id,
            text,
            screen_class=hint or kind,
            state_dir=state_dir,
        )
        if result.attempted:
            self._last_fingerprint = fingerprint
        return result


def screen_text_from_event(event: object) -> str:
    """Join watch-event ``screen`` rows into the introspector's text shape."""
    if not isinstance(event, Mapping):
        return ""
    rows = event.get("screen")
    if isinstance(rows, str):
        return rows
    if not isinstance(rows, (list, tuple)):
        return ""
    lines: list[str] = []
    for row in rows:
        if isinstance(row, str):
            lines.append(row)
        elif isinstance(row, (list, tuple)):
            try:
                lines.append("".join(str(c) for c in row))
            except Exception:  # noqa: BLE001
                continue
    return "\n".join(lines)


def capture_screen(
    world_id: str,
    text: str,
    *,
    screen_class: str | None = None,
    state_dir: str | Path | None = None,
) -> CaptureResult:
    """Parse + persist from raw screen text. Never sends."""
    ships = _introspector.parse_shipyard_listing(text)
    cargo = _introspector.parse_cargo_hold_price(text)
    if not ships and cargo is None:
        return CaptureResult(False, screen_class, reason="no_listing")
    ships_n = 0
    cargo_ok = False
    if ships:
        for row in ships:
            _game_data.persist_ship_row(world_id, row, state_dir=state_dir)
            ships_n += 1
    if cargo is not None:
        _game_data.persist_cargo_hold_row(world_id, cargo, state_dir=state_dir)
        cargo_ok = True
    return CaptureResult(
        True,
        screen_class or ("shipyard" if ships else "cargo_hold"),
        ships_persisted=ships_n,
        cargo_persisted=cargo_ok,
    )


def _latest_event(play: object) -> Optional[dict[str, Any]]:
    provider = getattr(play, "viewport_provider", None)
    if not callable(provider):
        return None
    try:
        snap = provider()
    except Exception:  # noqa: BLE001
        return None
    event = getattr(snap, "latest_event", None)
    if isinstance(event, dict):
        return event
    if isinstance(snap, Mapping):
        inner = snap.get("latest_event")
        return inner if isinstance(inner, dict) else None
    return None


def _text_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
