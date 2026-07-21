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

# -- TWGS "boxed" game-select variant (found live against a real TWGS
# server, distinct from twgs.test.example's own "Select a game :"
# wording -- see _is_twgs_boxed_game_select_menu below).
_TWGS_SELECTION_PROMPT_RE = re.compile(r"selection\s*\(\s*\?\s*for\s*menu\s*\)\s*:", re.I)
_GAME_HEADER_LINE_RE = re.compile(r"^[^a-z0-9]*game[^a-z0-9]*$", re.I)
# TWGS commonly renders two side-by-side boxes sharing ONE physical
# terminal row (see the captured fixture: the "Game" box's header shares
# its row with a neighboring notes box) -- split on the vertical
# box-drawing separator so each box's own column is checked in
# isolation, rather than requiring the header to be the ENTIRE row.
_BOX_VERTICAL_SEPARATOR_RE = re.compile(r"[│|]")

# -- A THIRD, non-boxed TWGS game-select variant (found live against a
# real TWGS server): no box-drawing at all, just a plain bracket list --
# see _is_twgs_server_banner_game_select_menu below for why the TWGS
# server startup BANNER (not the bracket list itself) is what's trusted.
_TWGS_BANNER_TITLE_RE = re.compile(r"trade\s*wars\s+game\s+server", re.I)
_TWGS_BANNER_VERSION_RE = re.compile(r"\btwgs\s+v[\d.]+[a-z]?\b", re.I)
_TWGS_BANNER_REGISTERED_RE = re.compile(r"server\s+registered\s+to", re.I)
# The 3 banner lines must sit close together (TWGS always prints them as
# 2-3 consecutive lines) -- bounds a stale/forged banner assembled from
# fragments scattered far apart in an unrelated document.
_BANNER_PROXIMITY_MAX_LINES = 6

# -- Adversarial-review hardening (cipher, 2026-07-20): both variant
# checks above originally scanned signals 2/3 (the "Game" header cell /
# the banner) against the WHOLE screen with no tie to the CURRENT
# prompt, so a STALE header/banner left over from an earlier game-select
# screen could combine with a LATER, unrelated menu sharing the same
# generic "Selection (? for menu):" prompt and still misfire game_select
# -- see _range_has_no_dash_style_menu / _range_has_qualifying_game_select_menu
# below, and each function's own updated docstring, for the fix.
_PLAYERS_ONLINE_OPTION_RE = re.compile(r"<\s*#\s*>\s*players\s+online", re.I)
_VIEW_GAME_DESCRIPTIONS_OPTION_RE = re.compile(r"<\s*!\s*>\s*view\s+game\s+descriptions", re.I)
# ROUND 2 hardening (cipher re-attack, same day): the fix above proves
# ADJACENCY (the header/banner and the qualifying body sit in the same
# range) but not EXCLUSIVITY -- see
# _range_has_no_menu_after_game_select_markers below for what this adds
# and why. A numbered-option style ("1. Foo", "1) Foo") has no existing
# anchor anywhere else in this module; added here since the exclusivity
# check must catch it same as bracket/dash style.
_NUMBERED_OPTION_RE = re.compile(r"^\s*\d+\s*[).:]\s*\S+")


def _range_has_no_dash_style_menu(lines, start, end):
    """No line in `lines[start:end+1]` looks like the module-entry
    menu's dash-style option ("T - Play Trade Wars 2002") -- a
    STRUCTURALLY DIFFERENT, already-known TWGS menu shape used
    elsewhere in this exact automaton (see `_MODULE_ENTRY_MENU_RE` in
    login.py). If one is found between a game-select header/banner and
    the current prompt, that header/banner is stale scrollback bleeding
    into a genuinely different CURRENT screen, not this one -- see
    tests/test_classify.py's stale-scrollback negative fixtures."""
    return not any(_DASH_OPTION_RE.search(lines[i]) for i in range(start, end + 1))


def _range_has_qualifying_game_select_menu(lines, start, end):
    """The range between a header/banner anchor and the prompt (the
    CURRENT screen's own body) must itself carry: (a) at least two
    bracket-style option lines -- `_is_menu`'s own threshold, scoped to
    this range rather than the whole screen, since scanning the whole
    screen is exactly what let a stale menu's bracket lines vouch for
    an unrelated current one; and (b) BOTH of the two option lines that
    are DISTINCTIVE to a genuine TWGS server-level game-select menu
    specifically -- "<#> Players Online" and "<!> View game
    descriptions" -- present on both real captured variants of this
    screen (the boxed and the banner style) and absent from every
    ordinary in-game/utility/help menu probed adversarially. Requiring
    both, scoped to THIS SAME range rather than just anywhere in the
    full screen, is what stops a stale copy of a prior game-select
    screen's own markers from vouching for a different, unrelated
    CURRENT menu that merely happens to end in the same generic
    prompt."""
    bracket_count = sum(1 for i in range(start, end + 1) if _BRACKET_OPTION_RE.search(lines[i]))
    if bracket_count < 2:
        return False
    has_players_online = any(_PLAYERS_ONLINE_OPTION_RE.search(lines[i]) for i in range(start, end + 1))
    has_view_descriptions = any(_VIEW_GAME_DESCRIPTIONS_OPTION_RE.search(lines[i]) for i in range(start, end + 1))
    return has_players_online and has_view_descriptions


def _range_has_no_menu_after_game_select_markers(lines, start, end):
    """ROUND 2 exclusivity hardening (cipher re-attack, 2026-07-20, same
    day as the range-scoping fix above). That fix proves the qualifying
    body is ADJACENT to the header/banner (same range) -- it never
    proves the qualifying body is the LAST menu content before the
    prompt. Confirmed live (both variants): a STALE, never-cleared copy
    of a FULL game-select body -- header/banner, game list, BOTH
    markers, "<Q> Quit" -- sitting higher in this same range can be
    followed by a genuinely CURRENT, actually-different bracket-style
    menu (e.g. a live "Utility Menu" with its own "<A> Refresh"/"<B>
    Message a player" options) directly above the prompt, and both
    `_range_has_no_dash_style_menu` (only excludes ONE other known menu
    SHAPE -- dash-style) and `_range_has_qualifying_game_select_menu`
    (counts/markers checked across the WHOLE range, so the stale
    markers still vouch for the range as a whole) let it through.

    The fix, borrowed from `_is_genuine_cim_report`'s exclusivity
    discipline: find the LATER of the two distinctive markers, then
    count every remaining option-shaped line (bracket, dash, OR
    numbered style) between there and the prompt. Every real captured
    fixture (boxed and banner variant) ends its qualifying body with
    exactly ONE such trailing line -- the conventional "<Q> Quit"
    closer -- so a single trailing option line is tolerated as that
    closer. `_is_menu`'s own definition requires >=2 qualifying lines to
    count as a menu at all, so no genuinely different SECOND menu can
    ever announce itself with only one trailing option line: two or
    more means a separate, later menu block (which needed its own >=2
    options to be a menu) is sharing the range, and the game-select
    reading is rejected -- see tests/test_classify.py's stale-full-body
    negative fixtures for exactly this shape."""
    marker_idxs = [
        i
        for i in range(start, end + 1)
        if _PLAYERS_ONLINE_OPTION_RE.search(lines[i]) or _VIEW_GAME_DESCRIPTIONS_OPTION_RE.search(lines[i])
    ]
    if not marker_idxs:
        return False  # defensive -- callers only reach here once both markers are already confirmed present
    markers_last_idx = max(marker_idxs)
    trailing_option_lines = sum(
        1
        for i in range(markers_last_idx + 1, end + 1)
        if _BRACKET_OPTION_RE.search(lines[i])
        or _DASH_OPTION_RE.search(lines[i])
        or _NUMBERED_OPTION_RE.search(lines[i])
    )
    return trailing_option_lines <= 1


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


def _is_twgs_boxed_game_select_menu(full_text: str, prompt_line: str) -> bool:
    """A second, structurally different TWGS game-select screen shape,
    found live against a real TWGS server: unlike the classic
    "Select a game :" wording (the original `game_select` anchor, still
    matched separately below), this one has NO "select a game" text
    ANYWHERE on screen -- it's an otherwise-generic bracket-style menu
    ("<A> Vanilla TW2002: ...", "<Q> Quit") under a boxed "Game" header,
    ending in "Selection (? for menu):" -- a generic TWGS prompt OTHER
    non-game-select menus also use.

    Trusted only on the combination of ALL FOUR signals, since none of
    them alone is distinctive enough:
    1. the CURRENT prompt line is this generic selection prompt (not
       just present anywhere in stale scrollback);
    2. a header CELL that -- ignoring box-drawing characters and
       whitespace -- is the single bare word "Game" and nothing else.
       Checked per box-column, not per physical terminal row: TWGS
       commonly renders two side-by-side boxes sharing one row (the
       "Game" box's header shares its physical line with a neighboring
       notes box, e.g. "...Game...│ │ Note: Multi-playing..."), so each
       row is first split on the vertical box-drawing separator and
       every resulting cell is checked in isolation. This is narrow
       enough that a menu ITEM merely mentioning "game"
       ("<!> View Game Descriptions") can't match: that cell has other
       words after "game" too, so `$` never lines up. Uses the LAST
       matching header cell in the buffer (stale-scrollback discipline,
       same "last wins" precedent as `_is_genuine_cim_report`) so an
       even-more-recent genuine box (if any) always wins over an older
       stale one;
    3. between that header and the current prompt, nothing looks like a
       STRUCTURALLY DIFFERENT, already-known TWGS menu shape (the
       module-entry menu's dash-style options) -- see
       `_range_has_no_dash_style_menu`;
    4. that same in-between range carries its own genuine bracket-style
       menu body, INCLUDING the two option lines distinctive to a real
       game-select menu specifically ("<#> Players Online" and
       "<!> View game descriptions") -- see
       `_range_has_qualifying_game_select_menu`.

    Signals 3-4 (added 2026-07-20, adversarial review finding) are what
    stop a STALE "Game" header left over from an EARLIER game-select
    screen from vouching for a totally different CURRENT menu that
    merely happens to end in the same generic prompt -- e.g. a module-
    entry menu ("T - Play Trade Wars 2002") reached at a LATER step in
    the same login flow, with the earlier door-select box's cells still
    sitting unclaimed in the pyte grid above it. Scoping both the
    exclusivity check and the qualifying-menu check to the range between
    the header and the prompt (rather than the whole screen, as the
    original version of this function did) is the fix -- see
    tests/test_classify.py's stale-scrollback negative fixtures.

    Signal 5, a ROUND 2 hardening (cipher re-attack, same day): signals
    3-4 prove adjacency, not exclusivity -- a stale FULL game-select
    body (markers included) can itself sit in this range ahead of a
    genuinely different, actually-current bracket-style menu that isn't
    dash-style, which signal 3 doesn't cover. See
    `_range_has_no_menu_after_game_select_markers` for the fix.

    Precision guard: a same-prompt, same-bracket-style menu with NO
    boxed "Game" header (e.g. a server's main lobby menu) still fails
    signal 2 and correctly falls through to the generic `menu` content
    anchor instead -- see tests/test_classify.py's negative-fixture
    pair for exactly that shape."""
    if not _TWGS_SELECTION_PROMPT_RE.search(prompt_line or ""):
        return False
    lines = full_text.splitlines()
    if not lines:
        return False
    prompt_idx = len(lines) - 1
    header_idx = None
    for i, line in enumerate(lines):
        if any(_GAME_HEADER_LINE_RE.match(cell.strip()) for cell in _BOX_VERTICAL_SEPARATOR_RE.split(line)):
            header_idx = i  # keep overwriting -- last (most recent) wins
    if header_idx is None or header_idx >= prompt_idx:
        return False
    if not _range_has_no_dash_style_menu(lines, header_idx + 1, prompt_idx - 1):
        return False
    if not _range_has_qualifying_game_select_menu(lines, header_idx + 1, prompt_idx - 1):
        return False
    return _range_has_no_menu_after_game_select_markers(lines, header_idx + 1, prompt_idx - 1)


def _is_twgs_server_banner_game_select_menu(full_text: str, prompt_line: str) -> bool:
    """A THIRD, structurally different TWGS game-select screen shape,
    found live against a real TWGS server: no box-drawing at all (unlike
    `_is_twgs_boxed_game_select_menu` above) -- just a plain bracket list
    ("<A> ...", "<Q> Quit") ending in the same generic
    "Selection (? for menu):" prompt. With no box to anchor on, the
    bracket list and the prompt are BOTH too generic on their own (any
    TWGS lobby menu can look like this) -- what's actually distinctive
    to THIS screen is the TWGS SERVER STARTUP BANNER printed above it:
    "TradeWars Game Server" / "TWGS v<version>" / "Server registered
    to <host>". That three-line banner is TWGS's own connection-time
    identification, printed once, only ahead of the server-level
    game-select menu -- no other screen in the login flow (or any
    ordinary in-game menu) reprints it.

    Trusted only on the combination of ALL SIX signals:
    1. the CURRENT prompt line is the generic selection prompt (not
       just present anywhere in stale scrollback);
    2. "TradeWars Game Server" appears somewhere on screen;
    3. a "TWGS v<version>" version string appears somewhere on screen;
    4. a "Server registered to ..." line appears somewhere on screen,
       and all three banner lines (2-4) sit within
       `_BANNER_PROXIMITY_MAX_LINES` of each other -- TWGS always
       prints them as 2-3 consecutive lines, so fragments scattered far
       apart in an unrelated document don't count as the real banner;
    5. between the LAST (most recent) of those three banner lines and
       the current prompt, nothing looks like a STRUCTURALLY DIFFERENT,
       already-known TWGS menu shape (the module-entry menu's
       dash-style options) -- see `_range_has_no_dash_style_menu`;
    6. that same in-between range carries its own genuine bracket-style
       menu body, INCLUDING the two option lines distinctive to a real
       game-select menu specifically ("<#> Players Online" and
       "<!> View game descriptions") -- see
       `_range_has_qualifying_game_select_menu`.

    Signals 5-6 (added 2026-07-20, adversarial review finding) are what
    stop a STALE copy of this banner -- printed once at connect time and
    never cleared from the pyte grid -- from vouching for a totally
    different CURRENT menu reached later in the same session that
    merely happens to end in the same generic prompt (e.g. a later
    utility/sysop menu). Scoping both the exclusivity check and the
    qualifying-menu check to the range between the banner and the
    prompt (rather than the whole screen, as the original version of
    this function did) is the fix -- see tests/test_classify.py's
    stale-scrollback negative fixtures. A forged/quoted banner inside a
    help screen's narrative text is caught the same way: the help
    screen's own unrelated menu items, sitting in that same range,
    never carry the two distinctive game-select-only options either.

    Signal 7, a ROUND 2 hardening (cipher re-attack, same day): signals
    5-6 prove adjacency, not exclusivity -- a stale FULL game-select
    body (markers included) can itself sit in this range ahead of a
    genuinely different, actually-current bracket-style menu that isn't
    dash-style, which signal 5 doesn't cover. See
    `_range_has_no_menu_after_game_select_markers` for the fix.

    Precision guard: a same-prompt, same-bracket-style menu WITHOUT
    this exact banner combination (e.g. a server's later in-game lobby
    menu, or a help screen merely mentioning "TWGS") still fails and
    correctly falls through to the generic `menu` content anchor
    instead -- see tests/test_classify.py's negative-fixture pair for
    exactly that shape."""
    if not _TWGS_SELECTION_PROMPT_RE.search(prompt_line or ""):
        return False
    lines = full_text.splitlines()
    if not lines:
        return False
    prompt_idx = len(lines) - 1
    title_idx = version_idx = registered_idx = None
    for i, line in enumerate(lines):
        if _TWGS_BANNER_TITLE_RE.search(line):
            title_idx = i  # last wins
        if _TWGS_BANNER_VERSION_RE.search(line):
            version_idx = i
        if _TWGS_BANNER_REGISTERED_RE.search(line):
            registered_idx = i
    if title_idx is None or version_idx is None or registered_idx is None:
        return False
    banner_first_idx = min(title_idx, version_idx, registered_idx)
    banner_last_idx = max(title_idx, version_idx, registered_idx)
    if banner_last_idx - banner_first_idx > _BANNER_PROXIMITY_MAX_LINES:
        return False
    if banner_last_idx >= prompt_idx:
        return False
    if not _range_has_no_dash_style_menu(lines, banner_last_idx + 1, prompt_idx - 1):
        return False
    if not _range_has_qualifying_game_select_menu(lines, banner_last_idx + 1, prompt_idx - 1):
        return False
    return _range_has_no_menu_after_game_select_markers(lines, banner_last_idx + 1, prompt_idx - 1)


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

# -- WO-CLEANPREEMPT (secret sub-diff): FAIL-SAFE secret-entry detection
# for the `tw attach` interactive keystroke path specifically -- see
# is_probable_secret_prompt()'s own docstring for why this is a
# DELIBERATELY broader, separate predicate from the `login_password`
# gate anchor above (which stays narrow -- it also drives the AUTOMATED
# login automaton's own behavior, not just its logging, so widening it
# would change login.py's decisions, not just what gets redacted).
_SECRET_PROMPT_RE = re.compile(
    r"password|\bpin\b|pass\s*code|access\s*code|\bcode\b|verify|\bsecret\b",
    re.I,
)


def is_probable_secret_prompt(prompt_line: str) -> bool:
    """WO-CLEANPREEMPT (secret sub-diff): is the CURRENT prompt line
    plausibly asking for a secret (password/PIN/passcode/access code/
    verification code/etc)? Used ONLY by the `tw attach` interactive
    keystroke path (Session.send_raw()'s send-time secret decision,
    protocol.record_attach_keystroke()) -- NEVER by classify_screen()/
    login.py's automaton, which stay on the narrower `login_password`
    gate anchor above (see this function's own module-level comment for
    why widening THAT anchor would be the wrong fix).

    Deliberately broad and FAIL-SAFE, not a zero-leak guarantee: a raw
    interactive keystroke stream has no structural "this is a password"
    signal at all (unlike an automated login step, which KNOWS it's
    sending a stored credential) -- the prompt's own TEXT is the only
    signal available, so this errs heavily toward treating an ambiguous
    prompt as secret rather than risking a real one landing in
    cleartext: a redacted ordinary keystroke in the transcript is a
    minor transparency loss; a leaked password/PIN is not. Matches
    "password", "pin" (word-boundaried so it doesn't fire on "pinpoint"/
    "spin"), "passcode"/"pass code", "access code", any other bare
    "...code" prompt, "verify" (email/account verification codes), and
    "secret".

    **KNOWN RESIDUAL, not covered by this predicate** (documented per
    the unbounded-input doctrine, not silently assumed complete): a
    secret-entry prompt phrased with NONE of these words at all (e.g. a
    custom in-game vendor's own idiosyncratic riddle-gate, or a prompt
    in a language this regex doesn't cover) has no signal this function
    can key on -- this is a best-effort heuristic over the prompt's
    literal English text, not a semantic understanding of what the game
    is asking for. Extend the pattern here as new secret-entry shapes
    are found live (cipher's own review/extend remit)."""
    return bool(_SECRET_PROMPT_RE.search(prompt_line or ""))


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
    invoke gate anchors against a single line).

    `game_select`'s boxed-menu variant (`_is_twgs_boxed_game_select_menu`)
    and its non-boxed, banner-anchored sibling
    (`_is_twgs_server_banner_game_select_menu`) are checked right after,
    for the same reason: both are a structural combination of the
    current prompt line PLUS other content found elsewhere in the full
    screen, which the ordinary single-line gate anchors below have no
    way to evaluate on their own."""
    if _is_genuine_cim_report(rendered_text):
        return "cim_report"
    lines = rendered_text.splitlines()
    last_line = lines[-1].strip() if lines else ""
    if _is_twgs_boxed_game_select_menu(rendered_text, last_line) or _is_twgs_server_banner_game_select_menu(
        rendered_text, last_line
    ):
        return "game_select"
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
    needs (see `_is_genuine_cim_report`).

    `game_select`'s boxed-menu variant, and its non-boxed,
    banner-anchored sibling, are checked next, same rationale:
    `_is_twgs_boxed_game_select_menu` and
    `_is_twgs_server_banner_game_select_menu` both need the CURRENT
    prompt line (not just anywhere in stale scrollback) combined with
    other content that can legitimately sit a few lines above it in the
    full screen -- a shape the ordinary prompt-line-only gate-anchor
    pass below can't evaluate on its own (see each function's own
    docstring)."""
    if _is_genuine_cim_report(full_text):
        return "cim_report"
    if _is_twgs_boxed_game_select_menu(full_text, prompt_line) or _is_twgs_server_banner_game_select_menu(
        full_text, prompt_line
    ):
        return "game_select"
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
