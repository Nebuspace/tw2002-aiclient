"""Opportunistic Class-0 fighter unit-price observe (WO-AICLIENT-WIRE-FIGHTER-PRICE-OBSERVE-FROM-SCREEN).

On the play-loop idle tick, read the settle-edge watch event text and feed it
to ``play.fighter_price_scalars.observe_screen``. Pure observe path: no send,
no crawl, no connection open.

Fail-closed: empty text / no match / missing scalars write nothing. Never
raises on the play-loop idle tick. Does **not** invent a measured Class-0
constant and does **not** arm purchase EXECUTE.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from tw2002_aiclient import game_data_capture as _gdc


@dataclass(frozen=True)
class FighterPriceCaptureResult:
    """Outcome of one opportunistic unit-price observe attempt."""

    attempted: bool
    unit_price: Optional[int] = None
    reason: Optional[str] = None


class FighterPriceCapture:
    """Per-play-session dedupe so the 1 Hz idle tick does not re-parse forever."""

    __slots__ = ("_last_fingerprint",)

    def __init__(self) -> None:
        self._last_fingerprint: Optional[str] = None

    def tick(
        self, play: object, profile: object = None, *, state_dir=None
    ) -> FighterPriceCaptureResult:
        """Idle-tick entry. Never raises. ``profile``/``state_dir`` unused (API parity)."""
        _ = profile, state_dir
        try:
            return self._tick(play)
        except Exception:  # noqa: BLE001 — play-loop containment
            return FighterPriceCaptureResult(False, reason="error_contained")

    def _tick(self, play: object) -> FighterPriceCaptureResult:
        scalars = getattr(play, "fighter_price_scalars", None)
        observe = getattr(scalars, "observe_screen", None)
        if not callable(observe):
            return FighterPriceCaptureResult(False, reason="no_scalars")
        event = _latest_event(play)
        if event is None:
            return FighterPriceCaptureResult(False, reason="no_event")
        text = _gdc.screen_text_from_event(event)
        if not isinstance(text, str) or not text.strip():
            return FighterPriceCaptureResult(False, reason="no_text")
        fingerprint = _text_fingerprint(text)
        if fingerprint == self._last_fingerprint:
            return FighterPriceCaptureResult(False, reason="unchanged")
        parsed = observe(text)
        self._last_fingerprint = fingerprint
        if parsed is None:
            return FighterPriceCaptureResult(False, reason="no_price_match")
        return FighterPriceCaptureResult(True, unit_price=int(parsed))


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
