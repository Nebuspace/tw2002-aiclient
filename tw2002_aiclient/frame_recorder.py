"""Append-only full-grid settle frames for post-mortem (WO-BUILD-CLI-VERBS-FRAMES).

Every settled ``build_response()`` can append one NDJSON object under
``state/frames/<session_id>.jsonl`` with the full 80×25 ``screen_raw``
(so Option?/qty prompts remain greppable even when spectate clips row 25
or watch coalesces intermediate screens).

Read path is pure filesystem (``tw frames``) — no daemon required for
closed sessions. Keystroke text is never persisted: frames store
``password_prompt`` (boolean from password-shaped prompt text only). Session
keystroke/secret flags are never read. On password-shaped settles the frame
uses only untainted literals (``prompt`` = ledger ``"<redacted>"``, empty
screens, ``state`` None); ``sent_input`` is always omitted from the JSONL
object.

Ported from archive ``twclient/frame_recorder.py`` (WO-FRAMES-0) into the
reborn ``tw2002_aiclient`` tree.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Iterable, Optional

from tw2002_aiclient.session import env as _env

__all__ = [
    "FrameRecorder",
    "diff_frames",
    "frames_dir",
    "grep_frames",
    "last_nonblank_line",
    "read_frames",
    "resolve_session_path",
]

_PASSWORD_PROMPT_RE = re.compile(r"password", re.I)

# Same placeholder as tw2002_aiclient.ledger.REDACTED (avoid importing
# ledger here — it pulls session/pyte). Keep strings identical.
REDACTED = "<redacted>"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def frames_dir(state_dir: Optional[Path] = None) -> Path:
    base = Path(state_dir) if state_dir is not None else _env.STATE_DIR
    return base / "frames"


def last_nonblank_line(rows: Iterable[str]) -> str:
    last = ""
    for line in rows:
        stripped = line.rstrip("\n").strip()
        if stripped:
            last = stripped
    return last


def resolve_session_path(
    session: str = "latest",
    *,
    state_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Resolve ``latest`` or an exact session id to a ``.jsonl`` path."""
    d = frames_dir(state_dir)
    if not d.is_dir():
        return None
    if session == "latest":
        files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        return files[-1] if files else None
    path = d / f"{session}.jsonl"
    if path.is_file():
        return path
    alt = d / session
    return alt if alt.is_file() else None


def read_frames(
    session: str = "latest",
    *,
    state_dir: Optional[Path] = None,
) -> list[dict]:
    path = resolve_session_path(session, state_dir=state_dir)
    if path is None:
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def grep_frames(
    pattern: str,
    session: str = "latest",
    *,
    state_dir: Optional[Path] = None,
    flags: int = 0,
) -> list[dict]:
    cre = re.compile(pattern, flags)
    hits = []
    for frame in read_frames(session, state_dir=state_dir):
        blob_parts = [frame.get("prompt") or ""]
        raw = frame.get("screen_raw") or []
        if isinstance(raw, list):
            blob_parts.extend(str(r) for r in raw)
        else:
            blob_parts.append(str(raw))
        if cre.search("\n".join(blob_parts)):
            hits.append(frame)
    return hits


def diff_frames(a: dict, b: dict) -> list[str]:
    """Unified-ish line delta between two frames' ``screen_raw`` grids."""
    ra = a.get("screen_raw") or []
    rb = b.get("screen_raw") or []
    if not isinstance(ra, list):
        ra = str(ra).splitlines()
    if not isinstance(rb, list):
        rb = str(rb).splitlines()
    lines = []
    n = max(len(ra), len(rb))
    for i in range(n):
        left = ra[i] if i < len(ra) else ""
        right = rb[i] if i < len(rb) else ""
        if left != right:
            lines.append(f"{i:02d}- {left}")
            lines.append(f"{i:02d}+ {right}")
    return lines


class FrameRecorder:
    """Thread-safe append-only frame sink for one daemon session."""

    def __init__(
        self,
        session_id: str,
        *,
        state_dir: Optional[Path] = None,
        cols: int = 80,
        rows: int = 25,
    ):
        self.session_id = session_id
        self._dir = frames_dir(state_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{session_id}.jsonl"
        self._lock = threading.Lock()
        self._seq = 0
        self.cols = cols
        self.rows = rows
        meta = {
            "session_id": session_id,
            "cols": cols,
            "rows": rows,
            "started_ts": _now_iso(),
        }
        meta_path = self._dir / f"{session_id}.meta.json"
        if not meta_path.exists():
            meta_path.write_text(json.dumps(meta) + "\n", encoding="utf-8")

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        session,
        *,
        cropped_rows: Optional[list[str]] = None,
        settled_reason: Optional[str] = None,
        classification: Optional[str] = None,
        prompt: Optional[str] = None,
        state: Optional[dict] = None,
        trigger: str = "settle",
    ) -> Optional[dict]:
        """Append one frame. Never raises into the ensure/do success path."""
        try:
            return self._record(
                session,
                cropped_rows=cropped_rows,
                settled_reason=settled_reason,
                classification=classification,
                prompt=prompt,
                state=state,
                trigger=trigger,
            )
        except Exception:  # noqa: BLE001 — post-mortem must not break responses
            return None

    def _record(
        self,
        session,
        *,
        cropped_rows: Optional[list[str]],
        settled_reason: Optional[str],
        classification: Optional[str],
        prompt: Optional[str],
        state: Optional[dict],
        trigger: str,
    ) -> dict:
        # Detect password-shaped prompts on a local string only.
        # Never read session keystroke or secret-flag attributes — CodeQL
        # taints *secret*-named flows into clear-text JSONL storage
        # (py/clear-text-storage-sensitive-data).
        probe = prompt if prompt is not None else ""
        if not probe and hasattr(session, "render_raw"):
            probe = last_nonblank_line(session.render_raw())
        elif not probe:
            probe = last_nonblank_line(cropped_rows or [])
        password_shaped = bool(_PASSWORD_PROMPT_RE.search(probe or ""))

        with self._lock:
            self._seq += 1
            seq = self._seq
            ts = _now_iso()
            ts_mono = time.monotonic()
            trig = trigger if settled_reason is None else f"settle_{settled_reason}"
            rx_count = getattr(session, "rx_count", None)
            cursor = session.cursor_pos() if hasattr(session, "cursor_pos") else None
            if password_shaped:
                # Literals / untainted constants only — do not alias probe,
                # raw screens, or state into the written dict (CodeQL taint).
                frame = {
                    "seq": seq,
                    "ts": ts,
                    "ts_mono": ts_mono,
                    "trigger": trig,
                    "session_id": self.session_id,
                    "rx_count": rx_count,
                    "settled_reason": settled_reason,
                    "classification": classification,
                    "prompt": REDACTED,
                    "password_prompt": True,
                    "cols": self.cols,
                    "rows": self.rows,
                    "screen_raw": [],
                    "screen_cropped": [],
                    "cursor": cursor,
                    "state": None,
                }
            else:
                if hasattr(session, "render_raw"):
                    raw = list(session.render_raw())
                else:
                    raw = list(cropped_rows or [])
                cropped = list(cropped_rows) if cropped_rows is not None else raw
                prompt_line = prompt if prompt is not None else last_nonblank_line(raw)
                frame = {
                    "seq": seq,
                    "ts": ts,
                    "ts_mono": ts_mono,
                    "trigger": trig,
                    "session_id": self.session_id,
                    "rx_count": rx_count,
                    "settled_reason": settled_reason,
                    "classification": classification,
                    "prompt": prompt_line,
                    "password_prompt": False,
                    "cols": self.cols,
                    "rows": self.rows,
                    "screen_raw": raw,
                    "screen_cropped": cropped,
                    "cursor": cursor,
                    "state": state,
                }
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(frame, ensure_ascii=False) + "\n")
            return frame
