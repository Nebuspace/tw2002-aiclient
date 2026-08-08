"""Opportunistic density-scan → world_model writeback (WO-WIRE-DENSITY-SCAN-WRITEBACK).

Mirrors ``game_data_capture.GameDataCapture``: on the play-loop idle tick,
if the settle-edge watch event already shows density-scan rows, parse them
and persist a ``density_scan`` observation tagged HYPOTHESIS. Pure observe
path: no send, no crawl, no connection open.

Fail-closed: unparseable / junk screens write nothing. Never raises on the
play-loop idle tick.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from tw2002_aiclient import density_scan as _density_scan
from tw2002_aiclient import game_data_capture as _gdc
from tw2002_aiclient import world_identity as _world_identity
from tw2002_aiclient import world_model as _world_model


@dataclass(frozen=True)
class DensityCaptureResult:
    """Outcome of one opportunistic density writeback attempt."""

    attempted: bool
    sectors_written: int = 0
    screen_class: Optional[str] = None
    reason: Optional[str] = None


class DensityScanCapture:
    """Per-play-session dedupe so the 1 Hz idle tick does not rewrite the
    same density screen every second while the operator sits on it."""

    __slots__ = ("_last_fingerprint",)

    def __init__(self) -> None:
        self._last_fingerprint: Optional[str] = None

    def tick(self, play: object, profile: object, *, state_dir=None) -> DensityCaptureResult:
        """Idle-tick entry. Never raises."""
        try:
            return self._tick(play, profile, state_dir=state_dir)
        except Exception:  # noqa: BLE001 — play-loop containment
            return DensityCaptureResult(False, reason="error_contained")

    def _tick(self, play: object, profile: object, *, state_dir) -> DensityCaptureResult:
        event = _latest_event(play)
        if event is None:
            return DensityCaptureResult(False, reason="no_event")
        text = _gdc.screen_text_from_event(event)
        if not text.strip():
            return DensityCaptureResult(False, reason="no_text")
        hint = None
        if isinstance(event, Mapping):
            raw = event.get("classification")
            if isinstance(raw, str) and raw:
                hint = raw
        readings = _density_scan.parse_density_scan(text)
        if not readings:
            return DensityCaptureResult(
                False, screen_class=hint, reason="no_density_rows"
            )
        try:
            world_id = _world_identity.world_id_from_profile(profile)
        except Exception:  # noqa: BLE001
            return DensityCaptureResult(
                False, screen_class=hint, reason="no_world_id"
            )
        if not isinstance(world_id, str) or not world_id:
            return DensityCaptureResult(
                False, screen_class=hint, reason="no_world_id"
            )
        fingerprint = f"{world_id}:density:{_text_fingerprint(text)}"
        if fingerprint == self._last_fingerprint:
            return DensityCaptureResult(
                False, screen_class=hint, reason="unchanged"
            )
        result = capture_screen(
            world_id,
            text,
            screen_class=hint,
            state_dir=state_dir,
        )
        if result.attempted:
            self._last_fingerprint = fingerprint
        return result


def capture_screen(
    world_id: str,
    text: str,
    *,
    screen_class: str | None = None,
    state_dir: str | Path | None = None,
) -> DensityCaptureResult:
    """Parse density rows + persist. Never sends. Fail-closed on junk."""
    readings = _density_scan.parse_density_scan(text)
    if not readings:
        return DensityCaptureResult(
            False, screen_class=screen_class, reason="no_density_rows"
        )
    written = _world_model.write_density_scan(
        world_id, readings, state_dir=state_dir
    )
    if not written:
        return DensityCaptureResult(
            False, screen_class=screen_class, reason="no_density_rows"
        )
    return DensityCaptureResult(
        True,
        sectors_written=len(written),
        screen_class=screen_class or "density_scan",
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
