"""Opportunistic CIM port-report → world_model bulk_upsert (WO-WIRE-BULK-UPSERT-CIM-INGEST).

Mirrors ``density_scan_capture.DensityScanCapture``: on the play-loop idle
tick, if the settle-edge watch event is a genuine ``cim_report``, parse the
batch rows and persist via ``world_model.write_from_cim_report`` →
``bulk_upsert``. Pure observe path: no send, no crawl, no connection open.

Fail-closed: non-``cim_report`` classifications and unparseable screens write
nothing. Never raises on the play-loop idle tick.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from tw2002_aiclient import game_data_capture as _gdc
from tw2002_aiclient import world_identity as _world_identity
from tw2002_aiclient import world_model as _world_model
from tw2002_aiclient.session.classify import classify_screen


@dataclass(frozen=True)
class CimCaptureResult:
    """Outcome of one opportunistic CIM writeback attempt."""

    attempted: bool
    sectors_written: int = 0
    screen_class: Optional[str] = None
    reason: Optional[str] = None


class CimReportCapture:
    """Per-play-session dedupe so the 1 Hz idle tick does not rewrite the
    same CIM report every second while the operator sits on it."""

    __slots__ = ("_last_fingerprint",)

    def __init__(self) -> None:
        self._last_fingerprint: Optional[str] = None

    def tick(self, play: object, profile: object, *, state_dir=None) -> CimCaptureResult:
        """Idle-tick entry. Never raises."""
        try:
            return self._tick(play, profile, state_dir=state_dir)
        except Exception:  # noqa: BLE001 — play-loop containment
            return CimCaptureResult(False, reason="error_contained")

    def _tick(self, play: object, profile: object, *, state_dir) -> CimCaptureResult:
        event = _latest_event(play)
        if event is None:
            return CimCaptureResult(False, reason="no_event")
        text = _gdc.screen_text_from_event(event)
        if not text.strip():
            return CimCaptureResult(False, reason="no_text")
        hint = None
        if isinstance(event, Mapping):
            raw = event.get("classification")
            if isinstance(raw, str) and raw:
                hint = raw
        prompt = ""
        if isinstance(event, Mapping):
            raw_prompt = event.get("prompt")
            if isinstance(raw_prompt, str):
                prompt = raw_prompt
        if not prompt:
            lines = text.splitlines()
            prompt = lines[-1].strip() if lines else ""
        # mack Finding 2: shape alone is not provenance — require cim_report.
        screen_class = hint
        if screen_class != "cim_report":
            screen_class = classify_screen(text, prompt)
        if screen_class != "cim_report":
            return CimCaptureResult(
                False, screen_class=screen_class, reason="not_cim_report"
            )
        try:
            world_id = _world_identity.world_id_from_profile(profile)
        except Exception:  # noqa: BLE001
            return CimCaptureResult(
                False, screen_class=screen_class, reason="no_world_id"
            )
        if not isinstance(world_id, str) or not world_id:
            return CimCaptureResult(
                False, screen_class=screen_class, reason="no_world_id"
            )
        fingerprint = f"{world_id}:cim:{_text_fingerprint(text)}"
        if fingerprint == self._last_fingerprint:
            return CimCaptureResult(
                False, screen_class=screen_class, reason="unchanged"
            )
        result = capture_screen(
            world_id,
            text,
            screen_class=screen_class,
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
) -> CimCaptureResult:
    """Parse + ``bulk_upsert`` once. Caller owns provenance."""
    written = _world_model.write_from_cim_report(
        world_id, text, state_dir=state_dir
    )
    if not written:
        return CimCaptureResult(
            False, screen_class=screen_class, reason="no_cim_rows"
        )
    return CimCaptureResult(
        True,
        sectors_written=len(written),
        screen_class=screen_class or "cim_report",
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
