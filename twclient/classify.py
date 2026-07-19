"""Screen classification via regex anchors on the rendered text.

Best-effort skeleton per DESIGN.md §4/§5 — extend as live play reveals more
screen shapes.

Anchors split into two kinds:

- **Gate anchors** (pause_key, login_password, login_name, computer,
  main_command): each represents a single, currently-active blocking
  request. In real TW2002/TWGS play these are *always* the last thing
  printed — the server is blocked waiting right there, so nothing else
  follows until it's answered. That means a gate anchor should only ever
  be trusted against the CURRENT prompt line; a match found only deeper
  in the full screen is stale leftover text sitting in an unclaimed
  region of the terminal grid (pyte doesn't clear cells the server never
  overwrites), not a real gate. Caught live: a rules screen's decorative
  "[Pause]" marker stayed on screen, unclaimed, above an already-active
  "Enter your choice:" menu prompt — naive whole-text scanning
  misclassified it as pause_key. `computer` lives here (not as a content
  anchor) and is checked BEFORE `main_command`: TW2002's computer
  subsystem prompt is literally "Computer command [TL=...]", a superset
  of the plain "Command [TL=...]" ship prompt, so main_command's pattern
  always matches it too — order is what lets the more specific one win.
- **Content anchors** (sector_display, port_trade, menu): describe what
  KIND of screen you're looking at, and legitimately live in the body a
  few lines above the prompt (e.g. "Sector : 1234" sits above a
  "Command?" prompt) — these ARE allowed to match anywhere in the full
  screen text.
"""

import re


def _regex_matcher(pattern):
    return lambda text: pattern.search(text) is not None


_BRACKET_OPTION_RE = re.compile(r"[(<]\s*[a-z!]\s*[)>]\s*\S+", re.I)
_DASH_OPTION_RE = re.compile(r"^\s*[a-z]\s*[-:]\s*\S+", re.I)


def _is_menu(text: str) -> bool:
    """A genuine multi-line options menu: at least two DIFFERENT lines
    each look like a bulleted option — classic TW2002 "(A) Foo", TWGS
    server-level "<A> Foo", or the module-entry menu's "T - Foo" dash
    style (all three seen live against a real TWGS server, see README.md).

    Deliberately NOT a single whole-text regex: an inline same-line
    confirmation like "Use (N)ew Name or (B)BS Name [B] ?" has two
    bracket pairs on ONE line and must NOT count as a menu — and once
    that line scrolls into stale (but still on-screen) scrollback, it
    must not get picked up as "menu" for whatever screen comes next just
    because the bracket pattern is still sitting there. Caught live:
    exactly that line falsely classified two subsequent, unrelated
    prompts ("Stardrift is what you want?", "One moment please") as menu.
    """
    qualifying_lines = 0
    for line in text.splitlines():
        if _BRACKET_OPTION_RE.search(line) or _DASH_OPTION_RE.search(line):
            qualifying_lines += 1
            if qualifying_lines >= 2:
                return True
    return False


_GATE_ANCHORS = [
    ("pause_key", _regex_matcher(re.compile(r"\[\s*pause\s*\]|press\s+.*\bkey\b|--\s*more\s*--", re.I))),
    ("login_password", _regex_matcher(re.compile(r"password", re.I))),
    (
        "login_name",
        _regex_matcher(re.compile(r"what\s+is\s+your\s+name|enter\s+your\s+name|your\s+name\s*[?:]", re.I)),
    ),
    # v2 B1 additions (auto-login automaton anchors) — all three are
    # single, currently-active blocking questions in the real TWGS/TW2002
    # flow, captured live driving a real TWGS server (DESIGN-v2.md B1).
    ("ansi_prompt", _regex_matcher(re.compile(r"use\s+ansi\s+graphics", re.I))),
    # The server-level door-select screen ("<A> Alien Retribution ...
    # Select a game :") — more specific than, and MUST be checked before,
    # the generic bracket-style `menu` content anchor it would otherwise
    # also match (gate anchors run before content anchors — see below).
    ("game_select", _regex_matcher(re.compile(r"select\s+a\s+game", re.I))),
    # The NEW-vs-RETURNING branch point: this prompt only appears when
    # the handle was NOT found in the player database, so answering it
    # is structurally always "yes, create one" (DESIGN-v2 B3).
    ("char_create", _regex_matcher(re.compile(r"start\s+a\s+new\s+character", re.I))),
    # Checked before main_command — see module docstring.
    ("computer", _regex_matcher(re.compile(r"computer\s+command", re.I))),
    ("main_command", _regex_matcher(re.compile(r"command\s*\[\s*tl\s*=", re.I))),
]

_CONTENT_ANCHORS = [
    ("sector_display", _regex_matcher(re.compile(r"sector\s*:?\s*\d+", re.I))),
    (
        "port_trade",
        _regex_matcher(re.compile(r"\bfuel\s+ore\b|\borganics\b|\bequipment\b|commodity|trading\s*port", re.I)),
    ),
    ("menu", _is_menu),
]

_ANCHORS = _GATE_ANCHORS + _CONTENT_ANCHORS


def classify(rendered_text: str) -> str:
    """Whole-text anchor scan, gate anchors checked first. Simple and
    order-dependent — fine for a single isolated string (tests, one-off
    checks), but prefer classify_screen() for a live rendered screen where
    stale unclaimed grid content can produce a false gate match.
    """
    for name, matcher in _ANCHORS:
        if matcher(rendered_text):
            return name
    return "unknown"


def classify_screen(full_text: str, prompt_line: str) -> str:
    """Classify a live rendered screen: gate anchors against the current
    prompt line only, content anchors against the whole screen, and gate
    anchors against the whole screen only as a last resort if there's no
    prompt line to check at all. See module docstring for the rationale.
    """
    if prompt_line:
        for name, matcher in _GATE_ANCHORS:
            if matcher(prompt_line):
                return name
    for name, matcher in _CONTENT_ANCHORS:
        if matcher(full_text):
            return name
    if not prompt_line:
        for name, matcher in _GATE_ANCHORS:
            if matcher(full_text):
                return name
    return "unknown"
