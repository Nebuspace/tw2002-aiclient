"""Trace-Ledger — the pattern-learning substrate (DESIGN-v2.md §3 v2.1
item 11a, C1).

Every `do`/`send` verb dispatch (protocol.py) is appended to a single,
ever-growing JSONL sink at `state/ledger.jsonl`: `{ts, capture, prompt,
pre_state, input, post_state, settled_class, screen_delta_summary,
reward}`. This is the raw material `twclient/miner.py` mines for
recurring profitable input-subsequences (C10), and what
`twclient/skills.py`'s `tw record` capture window tags via `capture` so
a human/AI can later tell "this run was a named trade-loop
capture" from "this was just background play". Auto-on: every
ledger-hooked verb writes here regardless of whether a named `tw record`
capture is active.

`prompt` is the game's actual question (DESIGN-v2.md §10) -- the last
non-blank line of `pre_text`, e.g. "Your offer [158]?" -- so a human
scanning the ledger can tell what an `input` was answering, not just
that it happened. `tw log`/`tw trail` (cli.py) renders each entry as a
one-line Q -> keystroke -> result trail via `render_trail_line()` below,
reading this JSONL file directly (no daemon round trip needed).

`pre_state`/`post_state` reuse `state_parser.parse_state()` read-only
(this module never edits state_parser.py) plus a locally-extracted
`cargo_holds_empty` best-effort field state_parser doesn't parse yet (the
"50 empty cargo holds" line seen live at a trading port, DESIGN-v2 item
11a wants a cargo delta and this is the only cargo signal captured live
so far).

Secret input (password entry) is never persisted verbatim -- the same
redaction contract `tw do/send --secret` already honors elsewhere
(protocol.py's `history_args`, login.py's `session.send(secret=True)`).
"""

import difflib
import json
import re
import threading
import time
from pathlib import Path

from .state_parser import parse_state

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "state"
LEDGER_PATH = STATE_DIR / "ledger.jsonl"

_CARGO_HOLDS_RE = re.compile(r"(\d[\d,]*)\s+empty\s+cargo\s+holds", re.I)

# §10 human-readable log-trail: the game's actual question line for a
# ledger entry's `prompt` field, and its redaction. A password-entry
# prompt (the same "password" anchor classify.py's `login_password` gate
# uses) must never surface the credential's context on disk, mirroring
# the `secret`-input redaction contract below.
_PASSWORD_PROMPT_RE = re.compile(r"password", re.I)


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def snapshot_state(text: str) -> dict:
    """pre/post_state for a ledger entry: state_parser's best-effort
    fields (credits/sector already anchored to the current, last-match
    value there -- see state_parser.py's module docstring) plus a
    ledger-local `cargo_holds_empty` extraction (kept here rather than
    editing state_parser.py -- see module docstring)."""
    state = dict(parse_state(text))
    m = _CARGO_HOLDS_RE.search(text)
    if m:
        state["cargo_holds_empty"] = int(m.group(1).replace(",", ""))
    return state


def extract_prompt(pre_text: str) -> str:
    """The game's actual question for this action -- the last
    non-blank line of `pre_text` (e.g. "How many holds of Fuel Ore
    [50]?", "Your offer [158]?", "Command [TL=...]:"). A password-entry
    prompt is redacted the same as a `secret` input (see `record_do`)."""
    for line in reversed(pre_text.splitlines()):
        line = line.strip()
        if line:
            return "<redacted>" if _PASSWORD_PROMPT_RE.search(line) else line
    return ""


def compute_reward(pre_state: dict, post_state: dict) -> dict:
    """`{d_credits, d_turns, d_cargo}` = post - pre, each key present
    only when BOTH sides have the underlying field -- state_parser's own
    "omit what's unknown" convention, carried through here. `d_turns` is
    typically <= 0 (turns are spent, not gained); a pattern's turn COST
    is `-d_turns` (see miner.py)."""
    reward = {}
    if "credits" in pre_state and "credits" in post_state:
        reward["d_credits"] = post_state["credits"] - pre_state["credits"]
    if "turns_left" in pre_state and "turns_left" in post_state:
        reward["d_turns"] = post_state["turns_left"] - pre_state["turns_left"]
    if "cargo_holds_empty" in pre_state and "cargo_holds_empty" in post_state:
        reward["d_cargo"] = post_state["cargo_holds_empty"] - pre_state["cargo_holds_empty"]
    return reward


def summarize_screen_delta(pre_text: str, post_text: str, max_len=120) -> str:
    """A one-line human-readable summary of what changed on screen -- a
    line-level diff via difflib, not a full grid dump (ledger entries
    stay small enough to grep/scan by eye, unlike the raw transcript
    log)."""
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
    """Append-only JSONL sink, one instance owned by the daemon
    (`server.ledger`, wired in daemon.py) and shared across every
    connection's `do`/`send` dispatch."""

    def __init__(self, path=None):
        self.path = Path(path) if path else LEDGER_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: dict):
        line = json.dumps(entry) + "\n"
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)

    def record_do(self, pre_text, input_text, secret, post_text, settled_class, capture=None):
        """Build and append one ledger entry for a completed `do`/`send`.
        `capture` is the active `tw record` skill name, if any (protocol.py
        reads it off `server.skill_recorder`), else None -- the ledger
        keeps recording regardless of whether a named capture is open."""
        pre_state = snapshot_state(pre_text)
        post_state = snapshot_state(post_text)
        prompt = extract_prompt(pre_text)
        # Belt-and-suspenders redaction: a `--secret` dispatch (password
        # entry) redacts its prompt too, even on the rare screen shape
        # where the prompt line itself doesn't happen to say "password"
        # -- same contract as `input` below.
        if secret:
            prompt = "<redacted>"
        entry = {
            "ts": _now_iso(),
            "capture": capture,
            "prompt": prompt,
            "pre_state": pre_state,
            "input": "<redacted>" if secret else input_text,
            "post_state": post_state,
            "settled_class": settled_class,
            "screen_delta_summary": summarize_screen_delta(pre_text, post_text),
            "reward": compute_reward(pre_state, post_state),
        }
        self.append(entry)
        return entry


def read_entries(path=None):
    """Read the whole ledger as a list of dicts, in append order.
    Best-effort -- a truncated/corrupt trailing line (e.g. a kill -9
    mid-write) is skipped rather than failing the whole read."""
    p = Path(path) if path else LEDGER_PATH
    if not p.exists():
        return []
    entries = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


# -- §10 human-readable trail rendering (`tw log`/`tw trail`) --------------

# Bytes an automated/`--input` keystroke can legitimately carry that must
# never render as invisible whitespace-lookalikes -- DEL and BS are the
# two real backspace-key bytes seen across terminal emulators, rendered
# as one unambiguous glyph rather than caret notation for either.
_BACKSPACE_SYMBOL = "⌫"
_BACKSPACE_BYTES = ("\x7f", "\x08")

_MAX_PROMPT_LEN = 60


def render_keystroke(input_text: str) -> str:
    """The highlighted keystroke portion of a trail line -- always a
    visible, non-empty `«...»` token, never a bare empty string (the
    §10 finding: blank/default-accept keystrokes recorded as `input: ""`
    were otherwise indistinguishable from "nothing happened"). Special
    bytes get a symbolic rendering: blank/Enter, backspace, and other
    control bytes (caret notation, e.g. Ctrl-] -> `^]`)."""
    if input_text == "<redacted>":
        return "«<redacted>»"
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
    return "…" + prompt[-(_MAX_PROMPT_LEN - 1):]


def _render_result(entry: dict) -> str:
    """The `-> ...` result portion: the credits delta plus the
    pre->post absolute reading when available (the ledger's most
    scannable signal), falling back to whichever other reward field is
    present, then the raw screen-delta summary, then a plain
    "no change"."""
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
    return entry.get("screen_delta_summary") or "no change"


def render_trail_line(entry: dict) -> str:
    """One human-readable Q -> keystroke -> result line for a single
    ledger entry (DESIGN-v2.md §10):
    `07:08:45 port_trade  Q ▸ "...your offer [158]?"  ⌨ ▸ «158»  -> +230cr (96,553->96,783)`
    """
    ts = entry.get("ts") or ""
    time_part = ts.split("T", 1)[1].rstrip("Z") if "T" in ts else ts
    settled_class = entry.get("settled_class") or "unknown"
    prompt = _truncate_prompt(entry.get("prompt") or "")
    keystroke = render_keystroke(entry.get("input", ""))
    result = _render_result(entry)
    return f'{time_part} {settled_class}  Q ▸ "{prompt}"  ⌨ ▸ {keystroke}  → {result}'
