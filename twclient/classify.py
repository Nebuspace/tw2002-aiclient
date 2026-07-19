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

# CIM/port-report header+footer -- mirrors state_parser.py's own
# `_CIM_HEADER_RE`/`_CIM_FOOTER_RE` (duplicated deliberately: this is a
# CLASSIFICATION anchor, a different concern from state_parser's
# DATA-EXTRACTION patterns, exactly the same "sector_display" ↔
# `_SECTOR_RE` precedent already in this module).
_CIM_REPORT_HEADER_RE = re.compile(r"^-=-=-\s+Port Report \(CIM\)\s+-=-=-$")
_CIM_REPORT_FOOTER_RE = re.compile(r"^-=-=-\s+End of Report\s+-=-=-$")
_COMMAND_ECHO_LINE_RE = re.compile(r"command\s*\[\s*tl\s*=", re.I)


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


def _is_genuine_cim_report(full_text: str) -> bool:
    """mack Finding 2 (2026-07-19 adversarial review): `parse_port_report`
    ran on EVERY response with zero provenance check -- any screen merely
    REPRODUCING the report's header/footer punctuation (a help screen
    quoting it as a worked example, a forged chat/broadcast line) got
    ingested into the world-model as real sector data. Text-matching the
    report's own shape can't be the trust signal, since a quoted example
    or a forged transmission can (and in mack's probes, does) reproduce
    that shape byte-for-byte.

    What CAN'T be reproduced without also making the screen look
    obviously wrong is EXCLUSIVITY: a genuine system-generated report is
    the server's SOLE output in response to the command that triggered
    it -- nothing else shares the screen with it. A worked example needs
    a lead-in ("...looks like this:"); a forged transmission needs a
    label ("Incoming transmission from..."); a trailing remark ("Use it
    to scan...") is exactly the kind of narrative framing real system
    output never carries. So: trusted only when nothing but blank lines
    (or the command-prompt echo that triggered it) precedes the LATEST
    closed report's header, and nothing but blank lines follow its
    footer up to the screen's own final (prompt) line.

    Anchors to the LAST closed report in the buffer -- same
    stale-scrollback discipline as `state_parser._latest_cim_report_lines`
    -- and treats a report with no footer yet (still printing) as not
    confidently closed, so it's never trusted mid-arrival."""
    lines = full_text.splitlines()
    if not lines:
        return False

    header_idx = None
    for i, line in enumerate(lines):
        if _CIM_REPORT_HEADER_RE.match(line.strip()):
            header_idx = i  # keep overwriting -- last match wins

    if header_idx is None:
        return False

    footer_idx = None
    for j in range(header_idx + 1, len(lines)):
        if _CIM_REPORT_FOOTER_RE.match(lines[j].strip()):
            footer_idx = j
            break
    if footer_idx is None:
        return False

    for line in reversed(lines[:header_idx]):
        stripped = line.strip()
        if not stripped:
            continue
        if _COMMAND_ECHO_LINE_RE.search(stripped):
            break
        return False  # narrative text shares the screen -- not trusted

    for line in lines[footer_idx + 1 : -1]:
        if line.strip():
            return False  # narrative text after the report -- not trusted

    return True


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

    `cim_report` is checked before everything else, same rationale as
    classify_screen() below (see `_is_genuine_cim_report`'s docstring) --
    it needs the FULL text to evaluate (a genuine report's own prompt
    line looks like any other main_command prompt, so it can't be
    reached via the ordinary gate/content anchor lists at all, which
    invoke gate anchors against a single line)."""
    if _is_genuine_cim_report(rendered_text):
        return "cim_report"
    for name, matcher in _ANCHORS:
        if matcher(rendered_text):
            return name
    return "unknown"


def classify_screen(full_text: str, prompt_line: str) -> str:
    """Classify a live rendered screen: gate anchors against the current
    prompt line only, content anchors against the whole screen, and gate
    anchors against the whole screen only as a last resort if there's no
    prompt line to check at all. See module docstring for the rationale.

    `cim_report` (mack Finding 2) is checked FIRST, ahead of even gate
    anchors: a genuine CIM report's own prompt line is an ordinary
    `main_command` prompt like any other (the report is what's ABOVE the
    prompt, not the prompt itself), so it would never be reached via the
    gate-anchors-on-prompt-line pass below -- exactly the same
    specificity-wins-over-generic precedent as `computer` being checked
    before `main_command`, just evaluated against the whole screen
    instead of the prompt line since that's what the structural check
    needs (see `_is_genuine_cim_report`)."""
    if _is_genuine_cim_report(full_text):
        return "cim_report"
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
