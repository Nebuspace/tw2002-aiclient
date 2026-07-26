"""Screen classification via regex anchors on the rendered text.

Best-effort skeleton per canon (engine/screen-understanding.md) — extend as
live play reveals more screen shapes.

Anchors split into two kinds:

- **Gate anchors** (pause_key, login_password, login_name, computer,
  warp_confirm, main_command): each represents a single, currently-active
  blocking request. In real TW2002/TWGS play these are *always* the last
  thing printed — the server is blocked waiting right there, so nothing
  else follows until it's answered. That means a gate anchor should only
  ever be trusted against the CURRENT prompt line; a match found only
  deeper in the full screen is stale leftover text sitting in an unclaimed
  region of the terminal grid (pyte doesn't clear cells the server never
  overwrites), not a real gate. Caught live: a rules screen's decorative
  "[Pause]" marker stayed on screen, unclaimed, above an already-active
  "Enter your choice:" menu prompt — naive whole-text scanning
  misclassified it as pause_key. `computer` lives here (not as a content
  anchor) and is checked BEFORE `main_command`: TW2002's computer
  subsystem prompt is literally "Computer command [TL=...]", a superset
  of the plain "Command [TL=...]" ship prompt, so main_command's pattern
  always matches it too — order is what lets the more specific one win.
  `warp_confirm` is the mid-warp ``Do you really want to warp there?
  (Y/N)`` gate: without it the Sector body still matches `sector_display`
  and Autopilot held forever (live stall).
- **Content anchors** (the system-block titles, sector_display,
  port_trade, menu): describe what KIND of screen you're looking at, and
  legitimately live in the body a few lines above the prompt (e.g.
  "Sector : 1234" sits above a "Command?" prompt) — these ARE allowed to
  match anywhere in the full screen text.

The **system-block anchors** are a distinct family within the content
anchors, listed first because a bracketed `-=-=- <Title> -=-=-` block
closed by its own footer is a far more specific structural signal than
the loose keyword scans that follow it (the same specificity-wins-first
discipline that puts `computer` ahead of `main_command`). They are
content anchors deliberately: on a real capture the ship's
`Command [TL=…]` prompt frequently sits *below* a finished block (the
server printed the block and went back to waiting), and in that case the
LIVE GATE is the truth about what the server wants — the block is
already-printed history. `cim_report` is the one exception, checked
ahead of even the gate anchors, and only because that report is a
data-bearing batch whose provenance gate has to fire before the world
model may ingest it; see `_is_genuine_cim_report`.

One gate class is not merely a label but a PROHIBITION: `money_prompt`
(WO-CLASSIFY-BLOCK-TITLES / `canon/DECISIONS.md` §A.2, Accepted
2026-07-26) names a quantity / money / bank-transfer question the server
is blocked on, and it is pinned NEVER-AUTO-ACTION -- see
`NEVER_AUTO_ACTION_CLASSES` below for what that pin means, why it makes
this module's output strictly SMALLER rather than larger, and who is
obliged to honour it.
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

# -- Other system-block titles (WO-CLASSIFY-BLOCK-TITLES) ------------------
#
# TW2002 brackets every system-generated block as `-=-=- <Title> -=-=-`.
# The CIM pair above was the only one anchored; the REUSABLE part of it is
# not its regexes but the exclusivity discipline in
# `_is_exclusive_closed_block` (extracted from `_is_genuine_cim_report`,
# which now delegates to it unchanged). Two properties of this table are
# load-bearing and must not be "simplified":
#
# 1. HEADER AND FOOTER TITLES ARE NOT SYMMETRIC -- each entry names both
#    explicitly. Real capture: the block opened by "StarDock Shipyard -
#    Cargo Hold Upgrade" closes with "End of Cargo Hold Upgrade Quote",
#    NOT "End of StarDock Shipyard - Cargo Hold Upgrade". A derived
#    `End of <header title>` rule fails on the very screen this table
#    exists to classify; and the looser repair (accept ANY `End of ...`
#    line) is worse still -- it would happily pair one block's header
#    with a DIFFERENT block's closer on a multi-block screen like the
#    StarDock equipment listing (four headers, three footers, none of
#    them matching pairs by title).
# 2. IT IS AN ALLOWLIST, NOT A SHAPE. A `-=-=- <Title> -=-=-` block whose
#    title pair is absent here contributes NOTHING; the screen keeps
#    whatever it already had, normally `unknown` -> escalate to the
#    human. That is deliberate. A generic "any bracketed block" anchor
#    would confidently name screens nobody has ever captured, and on this
#    product a confidently WRONG class is worse than no class at all
#    (`unknown` is the designed safe path -- canon
#    engine/screen-understanding.md, "The Unknown Is First-Class"). Add a
#    row only alongside a real captured fixture that proves the pair.
#
# Case-SENSITIVE, matching the CIM pair above rather than the
# case-insensitive keyword anchors further down: these titles are exact
# server-emitted strings, and the stricter match can only ever fall back
# to the safe path.
_CARGO_HOLD_QUOTE_HEADER_RE = re.compile(r"^-=-=-\s+StarDock Shipyard - Cargo Hold Upgrade\s+-=-=-$")
_CARGO_HOLD_QUOTE_FOOTER_RE = re.compile(r"^-=-=-\s+End of Cargo Hold Upgrade Quote\s+-=-=-$")
_SHIPYARD_LISTING_HEADER_RE = re.compile(r"^-=-=-\s+StarDock Shipyard - Ship Registration\s+-=-=-$")
_SHIPYARD_LISTING_FOOTER_RE = re.compile(r"^-=-=-\s+End of Shipyard Listing\s+-=-=-$")

# (class name, header pattern, footer pattern) -- see the two properties
# above.
#
# DELIBERATELY NOT ANCHORED, from the same captured corpus (recorded so
# the omissions read as decisions, not oversights):
#   - "Docking Log" (tests/fixtures/port_trade_screen.txt) -- printed with
#     NO footer at all, mid-screen, with the arrival narrative and the
#     commerce report around it. There is no closed block to anchor and no
#     exclusivity to check; that screen's live gate (`main_command`) is
#     already its correct class.
#   - "StarDock Special Equipment & Devices" -- an umbrella header that is
#     never closed; the three inner blocks under it ("Density &
#     Holographic Scanners" / "End of Scanner Listing", "TransWarp Drive
#     Installation" / "End of TransWarp Listing", "Special Devices &
#     Ordnance" / "End of Item Listing") ARE closed, but never
#     exclusive -- each has the previous block's output above it
#     (tests/fixtures/stardock_equipment_listing.txt). Anchoring any of
#     them would fire on nothing unless the exclusivity check were
#     weakened, and weakening it is precisely the move that manufactures
#     wrong classifications.
_BLOCK_TITLE_SPECS = (
    ("stardock_cargo_hold_quote", _CARGO_HOLD_QUOTE_HEADER_RE, _CARGO_HOLD_QUOTE_FOOTER_RE),
    ("stardock_shipyard_listing", _SHIPYARD_LISTING_HEADER_RE, _SHIPYARD_LISTING_FOOTER_RE),
)

# -- TWGS "boxed" game-select variant (found live against a real TWGS
# server, distinct from a test server's own "Select a game :" wording --
# see _is_twgs_boxed_game_select_menu below).
_TWGS_SELECTION_PROMPT_RE = re.compile(r"selection\s*\(\s*\?\s*for\s*menu\s*\)\s*:", re.I)
# WO-CLASSIFY-TIMED-OUT: TWGS may leave ``Timed out...`` (or
# ``Timed out waiting for input.``) as the CURRENT last line while the
# Selection prompt is still one line above — still game_select.
_TWGS_TIMED_OUT_PROMPT_RE = re.compile(r"^Timed\s+out", re.I)
# Gate-anchor phrase for the PLAIN ``Select a game :`` variant. Named here
# (same pattern as the ``game_select`` entry in ``_GATE_ANCHORS``) so
# ``_is_plain_timed_out_game_select`` can reuse it rather than duplicate the
# literal — avoids the two drifting apart if the gate anchor is ever tightened.
_PLAIN_GAME_SELECT_RE = re.compile(r"select\s+a\s+game", re.I)
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
# Optional year/edition token between "Wars" and "Game" (a-net: "Trade Wars
# 2002 Game Server"). Bare "TradeWars Game Server" / "Trade Wars Game Server"
# still match. Digits alone must not be required -- only permitted.
_TWGS_BANNER_TITLE_RE = re.compile(
    r"trade\s*wars(?:\s+\d{2,4})?\s+game\s+server", re.I
)
_TWGS_BANNER_VERSION_RE = re.compile(r"\btwgs\s+v[\d.]+[a-z]?\b", re.I)
_TWGS_BANNER_REGISTERED_RE = re.compile(r"server\s+registered\s+to", re.I)
# The 3 banner lines must sit close together (TWGS always prints them as
# 2-3 consecutive lines) -- bounds a stale/forged banner assembled from
# fragments scattered far apart in an unrelated document.
_BANNER_PROXIMITY_MAX_LINES = 6
# Box / block-drawing chars used when a-net embeds the title inside ANSI art
# ~13 rows below the plain version/registered pair (WO-ANET-BANNER-LAYOUT).
_BANNER_ART_LINE_RE = re.compile(
    r"[\u2500-\u259F═║─┌┐└┘├┤┬┴┼╔╗╚╝╠╣╦╩╬│┃]"
)

# -- Adversarial-review hardening: both variant checks above originally
# scanned signals 2/3 (the "Game" header cell / the banner) against the
# WHOLE screen with no tie to the CURRENT prompt, so a STALE
# header/banner left over from an earlier game-select screen could
# combine with a LATER, unrelated menu sharing the same generic
# "Selection (? for menu):" prompt and still misfire game_select -- see
# _range_has_no_dash_style_menu / _range_has_qualifying_game_select_menu
# below, and each function's own updated docstring, for the fix.
# a-net wording is "<#> View Players Online" (optional "View "); prior
# captures used bare "<#> Players Online".
_PLAYERS_ONLINE_OPTION_RE = re.compile(
    r"<\s*#\s*>\s*(?:view\s+)?players\s+online", re.I
)
_VIEW_GAME_DESCRIPTIONS_OPTION_RE = re.compile(r"<\s*!\s*>\s*view\s+game\s+descriptions", re.I)
# ROUND 2 hardening (same-day re-attack): the fix above proves ADJACENCY
# (the header/banner and the qualifying body sit in the same range) but
# not EXCLUSIVITY -- see _range_has_no_menu_after_game_select_markers
# below for what this adds and why. A numbered-option style ("1. Foo",
# "1) Foo") has no existing anchor anywhere else in this module; added
# here since the exclusivity check must catch it same as bracket/dash
# style.
_NUMBERED_OPTION_RE = re.compile(r"^\s*\d+\s*[).:]\s*\S+")


def _range_has_no_dash_style_menu(lines, start, end):
    """No line in `lines[start:end+1]` looks like the module-entry
    menu's dash-style option ("T - Play Trade Wars 2002") -- a
    STRUCTURALLY DIFFERENT, already-known TWGS menu shape used
    elsewhere in this exact automaton (see the module-entry menu anchor
    in the login flow). If one is found between a game-select
    header/banner and the current prompt, that header/banner is stale
    scrollback bleeding into a genuinely different CURRENT screen, not
    this one -- see tests/test_classify.py's stale-scrollback negative
    fixtures."""
    return not any(_DASH_OPTION_RE.search(lines[i]) for i in range(start, end + 1))


def _selection_prompt_context(full_text: str, prompt_line: str) -> tuple[str, int]:
    """Resolve the Selection prompt line + its index for game_select shape checks.

    When the live prompt is a TWGS ``Timed out…`` line, walk upward for the
    most recent ``Selection (? for menu):`` still on the pyte grid and use
    that as the effective prompt (WO-CLASSIFY-TIMED-OUT).
    """
    lines = full_text.splitlines()
    if not lines:
        return (prompt_line or ""), -1
    pl = prompt_line or ""
    if _TWGS_SELECTION_PROMPT_RE.search(pl):
        return pl, len(lines) - 1
    if _TWGS_TIMED_OUT_PROMPT_RE.search(pl.strip()):
        for i in range(len(lines) - 1, -1, -1):
            if _TWGS_SELECTION_PROMPT_RE.search(lines[i]):
                return lines[i].strip(), i
    return pl, len(lines) - 1


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
    """ROUND 2 exclusivity hardening (same-day re-attack). That fix
    proves the qualifying body is ADJACENT to the header/banner (same
    range) -- it never proves the qualifying body is the LAST menu
    content before the prompt. Confirmed live (both variants): a STALE,
    never-cleared copy of a FULL game-select body -- header/banner, game
    list, BOTH markers, "<Q> Quit" -- sitting higher in this same range
    can be followed by a genuinely CURRENT, actually-different
    bracket-style menu (e.g. a live "Utility Menu" with its own "<A>
    Refresh"/"<B> Message a player" options) directly above the prompt,
    and both `_range_has_no_dash_style_menu` (only excludes ONE other
    known menu SHAPE -- dash-style) and
    `_range_has_qualifying_game_select_menu` (counts/markers checked
    across the WHOLE range, so the stale markers still vouch for the
    range as a whole) let it through.

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
    style (all three seen live against a real TWGS server).

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

    Signals 3-4 are what stop a STALE "Game" header left over from an
    EARLIER game-select screen from vouching for a totally different
    CURRENT menu that merely happens to end in the same generic prompt
    -- e.g. a module-entry menu ("T - Play Trade Wars 2002") reached at
    a LATER step in the same login flow, with the earlier door-select
    box's cells still sitting unclaimed in the pyte grid above it.
    Scoping both the exclusivity check and the qualifying-menu check to
    the range between the header and the prompt (rather than the whole
    screen) is the fix -- see tests/test_classify.py's stale-scrollback
    negative fixtures.

    Signal 5, a ROUND 2 hardening (same-day re-attack): signals 3-4
    prove adjacency, not exclusivity -- a stale FULL game-select body
    (markers included) can itself sit in this range ahead of a
    genuinely different, actually-current bracket-style menu that isn't
    dash-style, which signal 3 doesn't cover. See
    `_range_has_no_menu_after_game_select_markers` for the fix.

    Precision guard: a same-prompt, same-bracket-style menu with NO
    boxed "Game" header (e.g. a server's main lobby menu) still fails
    signal 2 and correctly falls through to the generic `menu` content
    anchor instead -- see tests/test_classify.py's negative-fixture
    pair for exactly that shape."""
    prompt_line, prompt_idx = _selection_prompt_context(full_text, prompt_line)
    if not _TWGS_SELECTION_PROMPT_RE.search(prompt_line or ""):
        return False
    lines = full_text.splitlines()
    if not lines or prompt_idx < 0:
        return False
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

    Signals 5-6 are what stop a STALE copy of this banner -- printed
    once at connect time and never cleared from the pyte grid -- from
    vouching for a totally different CURRENT menu reached later in the
    same session that merely happens to end in the same generic prompt
    (e.g. a later utility/sysop menu). Scoping both the exclusivity
    check and the qualifying-menu check to the range between the banner
    and the prompt (rather than the whole screen) is the fix -- see
    tests/test_classify.py's stale-scrollback negative fixtures. A
    forged/quoted banner inside a help screen's narrative text is
    caught the same way: the help screen's own unrelated menu items,
    sitting in that same range, never carry the two distinctive
    game-select-only options either.

    Signal 7, a ROUND 2 hardening (same-day re-attack): signals 5-6
    prove adjacency, not exclusivity -- a stale FULL game-select body
    (markers included) can itself sit in this range ahead of a
    genuinely different, actually-current bracket-style menu that isn't
    dash-style, which signal 5 doesn't cover. See
    `_range_has_no_menu_after_game_select_markers` for the fix.

    Precision guard: a same-prompt, same-bracket-style menu WITHOUT
    this exact banner combination (e.g. a server's later in-game lobby
    menu, or a help screen merely mentioning "TWGS") still fails and
    correctly falls through to the generic `menu` content anchor
    instead -- see tests/test_classify.py's negative-fixture pair for
    exactly that shape."""
    prompt_line, prompt_idx = _selection_prompt_context(full_text, prompt_line)
    if not _TWGS_SELECTION_PROMPT_RE.search(prompt_line or ""):
        return False
    lines = full_text.splitlines()
    if not lines or prompt_idx < 0:
        return False
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
    if not _twgs_banner_signals_coherent(lines, title_idx, version_idx, registered_idx):
        return False
    banner_first_idx = min(title_idx, version_idx, registered_idx)
    banner_last_idx = max(title_idx, version_idx, registered_idx)
    if banner_last_idx >= prompt_idx:
        return False
    if not _range_has_no_dash_style_menu(lines, banner_last_idx + 1, prompt_idx - 1):
        return False
    if not _range_has_qualifying_game_select_menu(lines, banner_last_idx + 1, prompt_idx - 1):
        return False
    return _range_has_no_menu_after_game_select_markers(lines, banner_last_idx + 1, prompt_idx - 1)


def _twgs_banner_signals_coherent(
    lines, title_idx: int, version_idx: int, registered_idx: int
) -> bool:
    """True when the three TWGS startup-banner signals form one identity.

    Compact layout (classic / roguetw): all three lines within
    ``_BANNER_PROXIMITY_MAX_LINES`` — the bound that stops a forged banner
    assembled from fragments scattered through an unrelated document.

    Boxed-title layout (a-net, WO-ANET-BANNER-LAYOUT): the plain
    version + registered pair stay compact at the top, and the title sits
    *below* that pair on a line that also carries box/block art (title
    embedded in the ANSI frame around the game list). Do **not** simply
    raise the proximity ceiling — a bare quoted title 13 rows down in
    prose still fails; only an art-embedded title is admitted.
    """
    banner_first_idx = min(title_idx, version_idx, registered_idx)
    banner_last_idx = max(title_idx, version_idx, registered_idx)
    if banner_last_idx - banner_first_idx <= _BANNER_PROXIMITY_MAX_LINES:
        return True

    core_first = min(version_idx, registered_idx)
    core_last = max(version_idx, registered_idx)
    if core_last - core_first > _BANNER_PROXIMITY_MAX_LINES:
        return False
    # Title must sit below the plain top-of-screen pair (not above / between).
    if title_idx <= core_last:
        return False
    title_line = lines[title_idx]
    if not _TWGS_BANNER_TITLE_RE.search(title_line):
        return False
    if not _BANNER_ART_LINE_RE.search(title_line):
        return False
    return True


def _is_plain_timed_out_game_select(full_text: str, prompt_line: str) -> bool:
    """The plain ``Select a game :`` variant when TWGS appends ``Timed out...``
    as the live last line (WO-PLAY-GAME-LETTER-AUTOSELECT).

    ``Select a game :`` normally fires the ``game_select`` gate anchor against
    the current prompt line.  When TWGS appends ``Timed out...`` as the final
    line (host timed out waiting for the game choice), the gate anchor no
    longer sees it — the prompt is ``Timed out...``, not ``Select a game :``.

    Mirrors the timed-out resolution ``_selection_prompt_context`` applies for
    the TWGS ``Selection (? for menu):`` variants: walk upward from the
    timed-out last line and look for the ``Select a game`` anchor text above
    it.  The TWGS boxed and banner variants are handled by their own functions
    (which call ``_selection_prompt_context`` and then require the TWGS
    selection prompt); this function covers ONLY the plain variant where the
    gate anchor phrase itself is the on-screen prompt line immediately before
    the ``Timed out...`` line.

    Stale-scrollback guard (same discipline as ``_is_twgs_boxed_game_select_menu``
    / ``_is_twgs_server_banner_game_select_menu``): if a structurally DIFFERENT
    TWGS menu (the module-entry menu's dash-style options -- "T - Play Trade
    Wars 2002") appears BETWEEN the found ``Select a game`` line and the
    ``Timed out...`` prompt, the ``Select a game`` text is stale scrollback
    bleeding into a genuinely different current screen, NOT a live
    game-select screen -- refuse.  See ``_range_has_no_dash_style_menu`` and
    tests/test_classify.py's stale-plain-game-select negative fixtures.
    """
    if not _TWGS_TIMED_OUT_PROMPT_RE.search((prompt_line or "").strip()):
        return False
    lines = full_text.splitlines()
    # Walk upward from the second-to-last line (skipping the Timed out… line).
    for i in range(len(lines) - 2, -1, -1):
        if _PLAIN_GAME_SELECT_RE.search(lines[i]):
            # Found the ``Select a game`` line -- now check that nothing
            # between it and the Timed out… prompt looks like a
            # structurally different, already-known TWGS menu shape.
            return _range_has_no_dash_style_menu(lines, i + 1, len(lines) - 2)
    return False


def _is_exclusive_closed_block(full_text: str, header_re, footer_re) -> bool:
    """Is the screen's LATEST `header_re` … `footer_re` block CLOSED and
    the screen's SOLE content? The exclusivity discipline extracted
    verbatim from `_is_genuine_cim_report` (which now delegates here), so
    the CIM report and every other anchored block title are judged by one
    implementation instead of divergent copies of a subtle check.

    Why this, and not the block's own text, is the trust signal: a screen
    that merely REPRODUCES a block's punctuation -- a help screen quoting
    it as a worked example, a forged transmission, a fragment of stale
    scrollback -- can reproduce that shape byte-for-byte. What it cannot
    reproduce is being ALONE on the screen. A worked example needs a
    lead-in ("...looks like this:"); a forged transmission needs a label
    ("Incoming transmission from..."); a trailing remark ("Use it to scan
    ...") is the kind of narrative framing real system output never
    carries. So the block is trusted only when nothing but blank lines
    (or the command-prompt echo that triggered it) precedes its header,
    and nothing but blank lines follow its footer up to the screen's own
    final (prompt) line.

    Two more disciplines, both load-bearing:
    - anchors to the LAST header in the buffer (same stale-scrollback
      rule as `state_parser._latest_cim_report_lines`), so an older copy
      higher up never outranks the freshest one;
    - a block with no footer yet (still printing) is not confidently
      closed, and is never trusted mid-arrival.
    """
    lines = full_text.splitlines()
    if not lines:
        return False

    header_idx = None
    for i, line in enumerate(lines):
        if header_re.match(line.strip()):
            header_idx = i  # keep overwriting -- last match wins

    if header_idx is None:
        return False

    footer_idx = None
    for j in range(header_idx + 1, len(lines)):
        if footer_re.match(lines[j].strip()):
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


def _block_matcher(header_re, footer_re):
    """Bind one `_BLOCK_TITLE_SPECS` row into the `(name, matcher)` anchor
    shape the anchor lists use -- the block-title sibling of
    `_regex_matcher`."""
    return lambda text: _is_exclusive_closed_block(text, header_re, footer_re)


def _is_genuine_cim_report(full_text: str) -> bool:
    """Adversarial-review finding: `parse_port_report` ran on EVERY
    response with zero provenance check -- any screen merely
    REPRODUCING the report's header/footer punctuation (a help screen
    quoting it as a worked example, a forged chat/broadcast line) got
    ingested into the world-model as real sector data. Text-matching the
    report's own shape can't be the trust signal, since a quoted example
    or a forged transmission can (and in adversarial probes, does)
    reproduce that shape byte-for-byte.

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
    confidently closed, so it's never trusted mid-arrival.

    WO-CLASSIFY-BLOCK-TITLES moved that structural check, unchanged, into
    `_is_exclusive_closed_block` so the other anchored block titles are
    judged by the SAME implementation and cannot drift from it. This
    function keeps its own name, its own regexes and -- critically -- its
    own priority: `cim_report` is the one block class checked ahead of the
    gate anchors, because the report is a data-bearing batch whose
    provenance gate must fire even though its live prompt is an ordinary
    `main_command` prompt. Every other block title is an ordinary content
    anchor, where that same live gate correctly wins."""
    return _is_exclusive_closed_block(full_text, _CIM_REPORT_HEADER_RE, _CIM_REPORT_FOOTER_RE)


# -- money_prompt (WO-CLASSIFY-BLOCK-TITLES / DECISIONS.md §A.2) ----------
#
# The one class whose whole purpose is to FORBID, not to enable. See
# `NEVER_AUTO_ACTION_CLASSES` for the pin; these are the shapes that earn
# it, and every one is grounded rather than guessed:
#
#   QUANTITY -- VERIFIED (live capture). The real captured StarDock
#   purchase screen ends in `How many holds would you like to buy [0-20]
#   ?` (tests/fixtures/stardock_cargo_hold_quote.txt), and canon records
#   the same shape at a port (`How many holds of Fuel Ore… [12]?`) and on
#   a fighter deploy (`How many fighters… [100]?`). Canon's P-QTY is
#   emphatic about why this shape is dangerous rather than merely
#   uninteresting: the bracketed `[0-20]` is a RANGE HINT, while the
#   `[12]` / `[100]` variants are DEFAULTS a bare Enter accepts. The two
#   are indistinguishable by shape, so a blank Enter here means "buy 12"
#   on one screen and nothing definable on the other. Refusing the whole
#   family is the only answer that is right on both.
#
#   BANK TRANSFER -- HYPOTHESIS (named by the ruling, no capture in this
#   repo yet). A prompt line naming credits together with a
#   transfer/deposit/withdraw verb. Tagged rather than asserted, in the
#   same spirit as this module's other constructed grammars; tighten or
#   widen it when a real bank capture lands.
#
# TWO DELIBERATE NON-CLAIMS, recorded so they read as decisions:
#
#   1. `Your offer [N]?` is NOT claimed, even though it is unambiguously a
#      money prompt. That exact shape is already owned, prescriptively, by
#      `canon/engine/auto-haggle.md` -- a built-in guarded money-path rule
#      that answers it under its own parser and STOP-on-desync contract.
#      Claiming it here would silently overrule a different Accepted canon
#      concept. The collision is real and is escalated, not resolved in
#      code (see this module's WO report / DECISIONS.md).
#   2. The bare free-input solicitation (`Enter your selection:`) is NOT
#      claimed. `menu.crawler._FREE_INPUT_PROMPT_RE` matches it on
#      purpose -- there, a false "unsafe" only under-explores a graph. A
#      false CLASS here is different in kind: it is this module telling
#      the rest of the app it KNOWS what a screen is, and canon
#      (screen-understanding, "The Unknown Is First-Class") is explicit
#      that a confident wrong answer is worse than `unknown`.
#
# `re.MULTILINE` deliberately: both patterns are line-anchored, so on
# `classify_screen`'s last-resort whole-text scan (no prompt line at all)
# they still require a WHOLE LINE to be a money question rather than
# firing on a fragment buried in stale scrollback.
_MONEY_PROMPT_QUANTITY_RE = re.compile(r"^\s*how\s+m(?:any|uch)\b.*[?:]\s*$", re.I | re.M)
_MONEY_PROMPT_TRANSFER_RE = re.compile(
    r"^(?=.*\bcredits?\b)(?=.*\b(?:transfer|deposit|withdraw)\b).*[?:]\s*$",
    re.I | re.M,
)


def _is_money_prompt(text: str) -> bool:
    """Is this a quantity / money / bank-transfer question the server is
    blocked on? See the table above for each shape's provenance and for
    the two shapes deliberately NOT claimed."""
    return bool(_MONEY_PROMPT_QUANTITY_RE.search(text) or _MONEY_PROMPT_TRANSFER_RE.search(text))


_GATE_ANCHORS = [
    ("pause_key", _regex_matcher(re.compile(r"\[\s*pause\s*\]|press\s+.*\bkey\b|--\s*more\s*--", re.I))),
    ("login_password", _regex_matcher(re.compile(r"password", re.I))),
    (
        "login_name",
        _regex_matcher(re.compile(r"what\s+is\s+your\s+name|enter\s+your\s+name|your\s+name\s*[?:]", re.I)),
    ),
    # Auto-login automaton anchors -- all three are single, currently-
    # active blocking questions in the real TWGS/TW2002 flow, captured
    # live driving a real TWGS server.
    ("ansi_prompt", _regex_matcher(re.compile(r"use\s+ansi\s+graphics", re.I))),
    # The server-level door-select screen ("<A> Alien Retribution ...
    # Select a game :") — more specific than, and MUST be checked before,
    # the generic bracket-style `menu` content anchor it would otherwise
    # also match (gate anchors run before content anchors — see below).
    ("game_select", _regex_matcher(re.compile(r"select\s+a\s+game", re.I))),
    # The NEW-vs-RETURNING branch point: this prompt only appears when
    # the handle was NOT found in the player database, so answering it
    # is structurally always "yes, create one".
    ("char_create", _regex_matcher(re.compile(r"start\s+a\s+new\s+character", re.I))),
    # Checked before main_command — see module docstring.
    ("computer", _regex_matcher(re.compile(r"computer\s+command", re.I))),
    # Mid-warp Y/N (live stall): must beat sector_display when the Sector
    # body is still on screen above this prompt.
    (
        "warp_confirm",
        _regex_matcher(
            re.compile(
                r"do\s+you\s+really\s+want\s+to\s+warp\s+there\s*\?\s*\(\s*Y\s*/\s*N\s*\)",
                re.I,
            )
        ),
    ),
    ("main_command", _regex_matcher(re.compile(r"command\s*\[\s*tl\s*=", re.I))),
    # LAST among the gates, and the position is load-bearing. Everything
    # above answers a screen some part of this app DRIVES: `login.py`'s
    # automaton, `guardian.py`'s keepalive and `protocol.py`'s `ensure`
    # each act on a specific named class. Appending here means
    # `money_prompt` can never take a screen away from one of them -- the
    # only classifications it can change are ones that were going to fall
    # through to a content anchor or to `unknown`, and both of those are
    # already "nobody drives this". So the anchor's whole effect is to
    # move screens INTO the never-auto-action set and never out of any
    # driven one. Do not promote it up this list to "make it more
    # specific": specificity is not the problem it solves.
    #
    # It still sits ahead of every CONTENT anchor, and that IS the point.
    # On the real captured purchase screen the exclusive
    # `stardock_cargo_hold_quote` block sits directly above a live buy
    # question; if the content anchor won, the screen would carry a
    # benign, teachable identity while the server sat blocked on a money
    # question -- precisely the hole DECISIONS §A.2 exists to close. The
    # block is still recognized (`_is_exclusive_closed_block` reports it
    # unchanged); it is the CLASS the app is told that becomes the
    # prohibition.
    ("money_prompt", _is_money_prompt),
]

_CONTENT_ANCHORS = [
    # System-block titles first: an exclusive, closed `-=-=- <Title> -=-=-`
    # block is a far more specific structural signal than the keyword
    # scans below it (same specificity-first discipline as `computer`
    # ahead of `main_command`). Content anchors, NOT gate anchors -- see
    # the module docstring: when a finished block sits above a live
    # `Command [TL=…]` prompt the gate is the truth about what the server
    # wants, and gate anchors are checked first. The one exception,
    # `cim_report`, is checked ahead of everything for its own stated
    # reason.
    *((name, _block_matcher(header_re, footer_re)) for name, header_re, footer_re in _BLOCK_TITLE_SPECS),
    ("sector_display", _regex_matcher(re.compile(r"sector\s*:?\s*\d+", re.I))),
    (
        "port_trade",
        _regex_matcher(re.compile(r"\bfuel\s+ore\b|\borganics\b|\bequipment\b|commodity|trading\s*port", re.I)),
    ),
    ("menu", _is_menu),
]

_ANCHORS = _GATE_ANCHORS + _CONTENT_ANCHORS

# Every class name either entry point can return: the anchor tables plus
# `cim_report` (decided ahead of them by `_is_genuine_cim_report`) and the
# `unknown` fall-through. Private -- its only job is the assert below.
_RETURNABLE_CLASSES = frozenset(name for name, _matcher in _ANCHORS) | {"cim_report", "unknown"}

# -- the never-auto-action pin --------------------------------------------
#
# `canon/DECISIONS.md` §A.2 (Accepted 2026-07-26), aligning canon's P-QTY:
# a `money_prompt` is escalate-only. No taught rule, no macro, no crawler
# keystroke, no keepalive nudge may fire on a screen carrying one of these
# classes; the App hands the keyboard to the human instead.
#
# WHY A SET RATHER THAN A COMMENT. Naming a screen is normally a licence
# to act on it: canon (engine/screen-understanding.md, "The Unknown Is
# First-Class") makes `unknown` the stop-and-escalate trigger, so every
# OTHER class is, by construction, a screen a taught rule is allowed to
# match. That makes the vocabulary monotone in the dangerous direction --
# every label added is a screen moved from "must escalate" to "may be
# taught". This frozenset is the one lever that pushes the other way: a
# class listed here is named AND forbidden, so `money_prompt` SUBTRACTS
# its screens from the teachable set instead of adding them. That is the
# whole safety argument for the class existing, and it only holds while
# consumers derive their refusals from this name rather than restating
# it. `menu.crawler._NON_MENU_GATE_CLASSES` already does; anything that
# later decides whether a rule may fire owes the same.
#
# The import-time check is not ceremony: a typo here fails OPEN (a class
# nothing ever returns forbids nothing at all), which is exactly the
# failure a silent constant would hide until a money screen got driven.
NEVER_AUTO_ACTION_CLASSES = frozenset({"money_prompt"})

assert NEVER_AUTO_ACTION_CLASSES <= _RETURNABLE_CLASSES, (
    "NEVER_AUTO_ACTION_CLASSES names a class no anchor can ever return: "
    f"{sorted(NEVER_AUTO_ACTION_CLASSES - _RETURNABLE_CLASSES)}"
)

# -- FAIL-SAFE secret-entry detection for the `tw attach` interactive
# keystroke path specifically -- see is_probable_secret_prompt()'s own
# docstring for why this is a DELIBERATELY broader, separate predicate
# from the `login_password` gate anchor above (which stays narrow -- it
# also drives the AUTOMATED login automaton's own behavior, not just its
# logging, so widening it would change the login automaton's decisions,
# not just what gets redacted).
_SECRET_PROMPT_RE = re.compile(
    r"password|\bpin\b|pass\s*code|access\s*code|\bcode\b|verify|\bsecret\b",
    re.I,
)


def is_probable_secret_prompt(prompt_line: str) -> bool:
    """Is the CURRENT prompt line plausibly asking for a secret
    (password/PIN/passcode/access code/verification code/etc)? Used
    ONLY by the `tw attach` interactive keystroke path (the send-time
    secret decision, attach-keystroke recording) -- NEVER by
    classify_screen()/the login automaton, which stay on the narrower
    `login_password` gate anchor above (see this function's own
    module-level comment for why widening THAT anchor would be the
    wrong fix).

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
    are found live."""
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

    `cim_report` is checked FIRST, ahead of even gate anchors: a genuine
    CIM report's own prompt line is an ordinary `main_command` prompt
    like any other (the report is what's ABOVE the prompt, not the
    prompt itself), so it would never be reached via the gate-anchors-
    on-prompt-line pass below -- exactly the same specificity-wins-over-
    generic precedent as `computer` being checked before `main_command`,
    just evaluated against the whole screen instead of the prompt line
    since that's what the structural check needs (see
    `_is_genuine_cim_report`).

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
    if (
        _is_twgs_boxed_game_select_menu(full_text, prompt_line)
        or _is_twgs_server_banner_game_select_menu(full_text, prompt_line)
        or _is_plain_timed_out_game_select(full_text, prompt_line)
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
