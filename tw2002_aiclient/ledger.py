"""Trace ledger — per-dispatch semantic JSONL sink (PWO-094 / PWO-025 residual).

Canon: ``canon/engine/trace-ledger.md``. Append-only rows at
``state/ledger.jsonl`` (path overridable for tests). Passive passive substrate —
records decisions; never chooses a live keystroke.

World scoping (PWO-090 residual / DECISION-LEDGER-WORLD-ID-STAMP): new rows
may carry an optional ``world_id`` stamp; :func:`read_entries` can filter by
it. Existing rows are never rewritten. No per-world ledger path (Option B
held).

Actor attribution is the reborn invariant: live senders are
``VALID_SENDERS`` (``app``, ``human``) only — never ``ai``.

Secret sends store ``input: "<redacted>"`` and redact ``prompt`` too
(password-anchor match *or* ``secret=True``), matching the TX redaction
discipline already LIVE under PWO-111 — this module does not invent a
second redaction vocabulary.
"""

from __future__ import annotations

import difflib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from tw2002_aiclient.session.session import VALID_SENDERS
from tw2002_aiclient.session.state_parser import (
    OUTCOME_READ,
    read_credits_balance,
    read_turns_left_from_screen,
)

_PKG_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_ROOT.parent
DEFAULT_LEDGER_PATH = _REPO_ROOT / "state" / "ledger.jsonl"

REDACTED = "<redacted>"
_CARGO_HOLDS_RE = re.compile(r"(\d[\d,]*)\s+empty\s+cargo\s+holds", re.I)
_PASSWORD_PROMPT_RE = re.compile(r"password", re.I)

_BACKSPACE_SYMBOL = "⌫"
_BACKSPACE_BYTES = ("\x7f", "\x08")
_MAX_PROMPT_LEN = 60


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def snapshot_state(text: str) -> dict[str, Any]:
    """Best-effort pre/post_state — omit unknown keys (never invent zero)."""
    state: dict[str, Any] = {}
    credits = read_credits_balance(text)
    if credits.outcome == OUTCOME_READ and credits.balance is not None:
        state["credits"] = credits.balance
    turns = read_turns_left_from_screen(text)
    if turns.outcome == OUTCOME_READ and turns.turns is not None:
        state["turns_left"] = turns.turns
    m = _CARGO_HOLDS_RE.search(text)
    if m:
        state["cargo_holds_empty"] = int(m.group(1).replace(",", ""))
    return state


def extract_prompt(pre_text: str) -> str:
    """Last non-blank pre-send line; password-shaped prompts redacted."""
    for line in reversed(pre_text.splitlines()):
        line = line.strip()
        if line:
            return REDACTED if _PASSWORD_PROMPT_RE.search(line) else line
    return ""


def compute_reward(pre_state: Mapping[str, Any], post_state: Mapping[str, Any]) -> dict[str, int]:
    """``{d_credits, d_turns, d_cargo}`` — each key only when both sides known."""
    reward: dict[str, int] = {}
    if "credits" in pre_state and "credits" in post_state:
        reward["d_credits"] = int(post_state["credits"]) - int(pre_state["credits"])
    if "turns_left" in pre_state and "turns_left" in post_state:
        reward["d_turns"] = int(post_state["turns_left"]) - int(pre_state["turns_left"])
    if "cargo_holds_empty" in pre_state and "cargo_holds_empty" in post_state:
        reward["d_cargo"] = (
            int(post_state["cargo_holds_empty"]) - int(pre_state["cargo_holds_empty"])
        )
    return reward


def summarize_screen_delta(pre_text: str, post_text: str, max_len: int = 120) -> str:
    pre_lines = pre_text.splitlines()
    post_lines = post_text.splitlines()
    if pre_lines == post_lines:
        return "unchanged"
    sm = difflib.SequenceMatcher(a=pre_lines, b=post_lines, autojunk=False)
    added = removed = changed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            changed += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "insert":
            added += j2 - j1
    return f"+{added}/-{removed}/~{changed} lines"[:max_len]


class LedgerWriter:
    """Append-only JSONL sink — one row per settled ``do``/``send``."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_LEDGER_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: Mapping[str, Any]) -> None:
        line = json.dumps(dict(entry), ensure_ascii=False) + "\n"
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line)

    def record_do(
        self,
        pre_text: str,
        input_text: str,
        *,
        secret: bool,
        post_text: str,
        settled_class: str,
        actor: str,
        session_id: str,
        capture: str | None = None,
        intent: str | None = None,
        interrupted_by_human: bool = False,
        world_id: str | None = None,
        rule_id: str | None = None,
        target_player: str | None = None,
    ) -> dict[str, Any]:
        """Build and append one per-dispatch row.

        ``actor`` must be in ``VALID_SENDERS`` (``app``|``human``). ``session_id``
        is required on every row per canon. Secret sends never persist the
        credential — ``input`` and ``prompt`` become ``<redacted>``.

        ``world_id``, when a non-empty string, is stamped on the row so retro /
        mining can filter without splitting the JSONL file. Omitted when
        unknown — never invent a slug; never rewrite older rows.

        ``rule_id`` / ``target_player`` are optional accountability stamps for
        the post-session report (omit when unknown — never invent).
        """
        if actor not in VALID_SENDERS:
            raise ValueError(
                f"actor must be one of {VALID_SENDERS}, got {actor!r} "
                "(no live 'ai' sender — AI authors rules, never keystrokes)"
            )
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id is required on every ledger row")

        pre_state = snapshot_state(pre_text)
        post_state = snapshot_state(post_text)
        prompt = extract_prompt(pre_text)
        if secret:
            prompt = REDACTED
        entry: dict[str, Any] = {
            "ts": _now_iso(),
            "actor": actor,
            "session_id": session_id,
            "prompt": prompt,
            "pre_state": pre_state,
            "input": REDACTED if secret else input_text,
            "post_state": post_state,
            "settled_class": settled_class,
            "screen_delta_summary": summarize_screen_delta(pre_text, post_text),
            "reward": compute_reward(pre_state, post_state),
            "interrupted_by_human": interrupted_by_human,
        }
        if capture is not None:
            entry["capture"] = capture
        if intent is not None:
            entry["intent"] = intent
        if world_id is not None and str(world_id).strip():
            entry["world_id"] = str(world_id).strip()
        if rule_id is not None and str(rule_id).strip():
            entry["rule_id"] = str(rule_id).strip()
        if target_player is not None and str(target_player).strip():
            entry["target_player"] = str(target_player).strip()
        self.append(entry)
        return entry


def read_entries(
    path: str | Path | None = None,
    *,
    world_id: str | None = None,
) -> list[dict[str, Any]]:
    """Read the ledger in append order; skip corrupt trailing lines.

    When ``world_id`` is a non-empty string, return only rows whose stamped
    ``world_id`` matches (exact). Rows lacking the field are excluded from a
    filtered read — they stay on disk untouched (Option A: no rewrite).
    """
    p = Path(path) if path is not None else DEFAULT_LEDGER_PATH
    if not p.exists():
        return []
    entries: list[dict[str, Any]] = []
    want = str(world_id).strip() if world_id is not None and str(world_id).strip() else None
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if want is not None and row.get("world_id") != want:
                continue
            entries.append(row)
    return entries


def live_actor_counts(
    path: str | Path | None = None,
) -> tuple[int | None, int | None]:
    """Count live ``app`` / ``human`` rows for the coverage meter.

    Returns ``(None, None)`` when the ledger file is absent (counts
    *unavailable* → ``COV ?``). Returns ``(0, 0)`` when the file exists but
    has no countable live rows (known-empty window → ``COV ? · App 0 · Hum 0``).

    Only ``VALID_SENDERS`` actors count; unknown / missing / ``ai`` rows are
    skipped (never invent a third live driver). Never raises.
    """
    p = Path(path) if path is not None else DEFAULT_LEDGER_PATH
    try:
        if not p.exists():
            return None, None
    except OSError:
        return None, None
    app_n = 0
    human_n = 0
    try:
        for entry in read_entries(p):
            actor = entry.get("actor")
            if actor == "app":
                app_n += 1
            elif actor == "human":
                human_n += 1
    except OSError:
        return None, None
    return app_n, human_n



def render_keystroke(input_text: str) -> str:
    if input_text == REDACTED:
        return f"«{REDACTED}»"
    if input_text == "":
        return "«⏎ Enter (default)»"
    if input_text in _BACKSPACE_BYTES:
        return f"«{_BACKSPACE_SYMBOL}»"
    if len(input_text) == 1 and ord(input_text) < 0x20:
        return f"«^{chr(ord(input_text) + 64)}»"
    return f"«{input_text}»"


def _truncate_prompt(prompt: str) -> str:
    if len(prompt) <= _MAX_PROMPT_LEN:
        return prompt
    return "…" + prompt[-(_MAX_PROMPT_LEN - 1) :]


def _render_result(entry: Mapping[str, Any]) -> str:
    reward = entry.get("reward") or {}
    if "d_credits" in reward:
        pre_c = (entry.get("pre_state") or {}).get("credits")
        post_c = (entry.get("post_state") or {}).get("credits")
        if pre_c is not None and post_c is not None:
            return f"{reward['d_credits']:+d}cr ({pre_c:,}→{post_c:,})"
        return f"{reward['d_credits']:+d}cr"
    if "d_turns" in reward:
        return f"{reward['d_turns']:+d} turn(s)"
    if "d_cargo" in reward:
        return f"{reward['d_cargo']:+d} cargo"
    return str(entry.get("screen_delta_summary") or "no change")


def render_trail_line(entry: Mapping[str, Any]) -> str:
    ts = entry.get("ts") or ""
    time_part = ts.split("T", 1)[1].rstrip("Z") if "T" in ts else ts
    settled_class = entry.get("settled_class") or "unknown"
    prompt = _truncate_prompt(str(entry.get("prompt") or ""))
    keystroke = render_keystroke(str(entry.get("input", "")))
    result = _render_result(entry)
    return f'{time_part} {settled_class}  Q ▸ "{prompt}"  ⌨ ▸ {keystroke}  → {result}'
