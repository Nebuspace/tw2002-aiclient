"""Best-effort structured state extraction (DESIGN.md §5).

Skeleton parsers over the rendered screen text. Unknown/missing fields are
simply omitted — partial state is fine; extend as live play reveals more
screen shapes.

**Root-fix (DESIGN-v2.md §8, 2026-07-19):** `parse_state()` scans the
WHOLE rendered buffer, which can hold stale scrollback pyte never clears
(the exact trap classify.py's own module docstring warns about) above
the genuinely current line -- a naive first-match-wins `re.search()`
then reports the STALE value instead of the CURRENT one. Caught live: a
lingering "We'll sell them for 132 credits." offer sentence outranked
the real "You have 100,485 credits" balance line and silently corrupted
a reward delta by +90,661cr; a stale pre-warp "Sector : 1234" likewise
outranked the post-warp "Sector : 5678". Both `sector` and `credits`
below anchor to the LAST match in the buffer -- the bottom-most, most
recently printed occurrence -- not the first. (This fix used to live as
a local workaround in ledger.py's `snapshot_state()`; it now lives here,
once, so every consumer gets the corrected value.)

A completed-transaction screen can also print "You have N credits"
TWICE on one screen -- once mid-screen as the port's pre-transaction
status context, once at the very end as the actual post-transaction
result (both caught live: "...You have 100,101 credits...<accept the
offer>...You have 100,485 credits..." on ONE rendered screen) -- so
`_YOU_HAVE_CREDITS_RE` below takes the LAST match too.

**Line-anchored (mack Finding 2's F2 carve-out, closed 2026-07-19):**
`_SECTOR_RE` used to match "sector" ANYWHERE in the buffer, including
mid-sentence inside ordinary narrative/chat text -- mack's confirmed
live trace: the bot really in sector 100 at a real port, with a
same-screen chat line ("...Sector: 8675, come check it out!") arriving
AFTER the real status line. The last-match discipline above (needed
for the real stale-scrollback case) then picked the PHANTOM 8675 --
misattributing the bot's real observed port data to a sector it never
visited, while its actual current sector went unrecorded that pass.
The genuine in-game status line is always its OWN line (`Sector : N`,
optionally indented); a chat/narrative mention embeds "Sector: N"
mid-sentence, never as a bare line-leading label. `_SECTOR_RE` is now
anchored to the START of a line (`re.MULTILINE`) so it only matches the
former shape -- verified against every existing `parse_state()`
consumer/fixture (all of which already render the status line as its
own line) before landing this."""

import re

_SECTOR_RE = re.compile(r"^\s*sector\s*:?\s*(\d+)", re.I | re.M)
# The sibling status-block markers a genuine TW2002 sector-status display
# prints directly beneath its own "Sector : N" line -- "Ports :" and
# "Warps to Sector(s) :" are the two shapes already independently
# established by this file's own tests/fixtures (see
# `is_genuine_sector_status()` below for why co-occurrence with one of
# these, not mere presence of "sector" text, is the trust signal; mirrors
# `_WARPS_RE`'s same "Warps to Sector(s)" literal shape).
_SECTOR_STATUS_SIBLING_RE = re.compile(r"^\s*(?:ports?\s*:|warps?\s+to\s+sector\(s\)\s*:)", re.I)
# TL= is ambiguous across TWGS variants: the classic shape is a plain turn
# count ("TL=00753:0/0/0/850"), but this live server's MBBS Gold build
# uses TL= for a HH:MM:SS countdown ("TL=00:00:00") instead — matching
# that blindly as a turn count silently produced a misleading
# turns_left=0. The lookahead rejects the HH:MM:SS shape specifically so
# a real digit-count TL= (this server or another) still extracts cleanly.
_TURNS_RE = re.compile(r"\btl\s*=\s*(?!\d{2}:\d{2}:\d{2}\b)(\d+)", re.I)
_TURN_TIMER_RE = re.compile(r"\btl\s*=\s*(\d{2}:\d{2}:\d{2})\b", re.I)
# This live server never actually shows turns via TL= (see above) — the
# real number shows up after docking instead: "29990 turns left."
# Horizontal whitespace ONLY between the count and "turns left" — a plain
# `\s+` crossed newlines and forged turns_left from the prior line's
# sector id on ship-info screens ("Current Sector : 2594\nTurns left : 1622"
# → turns_left=2594). Caught live WO-HUD-CREDITS-TURNS-JOIN.
_TURNS_LEFT_PLAIN_RE = re.compile(r"(\d[\d,]*)[ \t]+turns?\s+left\b", re.I)
# Ship-info / Computer readout label-first form (same live I-info screen):
# "Turns left     : 1622"
_TURNS_LEFT_LABEL_RE = re.compile(r"^\s*turns?\s+left\s*[:=]\s*(\d[\d,]*)", re.I | re.M)
# Ship-info sector line — `_SECTOR_RE` only matches a bare "Sector : N"
# line-start, not "Current Sector : N".
_CURRENT_SECTOR_RE = re.compile(r"^\s*current\s+sector\s*[:=]\s*(\d+)", re.I | re.M)
# Ship-info / Computer readout: "Holds: 40  Fighters: 500  Shields: 200".
# Deliberately NOT the corp toll banner ("Fighters: N (belong…)[Toll]").
_SHIP_HFS_RE = re.compile(
    r"Holds:\s*(\d[\d,]*)\s+Fighters:\s*(\d[\d,]*)\s+Shields:\s*(\d[\d,]*)",
    re.I,
)
# Fighter toll Option? dialogue — aboard count only (not enemy toll count).
_FIGHTER_ABOARD_VS_RE = re.compile(
    r"Your\s+fighters\s*:\s*(\d+)\s+vs\.?\s*theirs\s*:\s*(\d+)",
    re.I,
)
# Two shapes seen: a hypothetical "Credits: 12,345" label-first form, and
# the real "You have 100,000 credits" amount-first form live servers
# actually use — tried in that order.
_CREDITS_LABEL_FIRST_RE = re.compile(r"credits?\s*[:=]\s*(\d[\d,]*)", re.I)
_CREDITS_AMOUNT_FIRST_RE = re.compile(r"(\d[\d,]*)\s+credits\b", re.I)
# The most specific and reliable credits phrasing: an unambiguous balance
# statement, not a price mention (a port's "We'll sell them for N
# credits" offer also matches _CREDITS_AMOUNT_FIRST_RE, but never this).
# Checked first, ahead of the two generic shapes above — see module
# docstring.
_YOU_HAVE_CREDITS_RE = re.compile(r"you\s+have\s+(\d[\d,]*)\s+credits\b", re.I)
# WO-FA1 root-fix (2026-07-21): the old `([\d\s\-]+)` capture group choked
# on the REAL live screen shape, which wraps each destination in
# parens -- "Warps to Sector(s) :  (379) - (597) - (1302) - (3424) -
# (4069) - (4182)" -- "(" isn't in that character class, so the group
# couldn't even start matching right after the label and `parse_state()`
# silently dropped the "warps" key entirely (not merely truncated to the
# first sector), starving `explore.py`'s frontier BFS of the very edges
# it needs to ever pick a next hop. Anchored to line-start (`re.MULTILINE`,
# mirrors `_SECTOR_STATUS_SIBLING_RE`'s own established convention for
# this exact label) and captures the REST OF THE LINE verbatim,
# punctuation and all -- `parse_state()` below then pulls every digit run
# out of that captured text with a bare `\d+` findall, which is agnostic
# to whichever separator shape (bare hyphens, paren-wrapped, mixed
# spacing) a given TWGS variant happens to print. Same last-match
# discipline as `_SECTOR_RE`/credits above: `parse_state()` takes the
# LAST line match, not the first, so a stale scrollback "Warps to
# Sector(s)" block from a prior sector never outranks the current one.
#
# CRITICAL fix (mack/cipher adversarial re-verify, 2026-07-21): the `\s*`
# immediately before the capture group used to include `\n` (`\s` matches
# any whitespace, newline included) -- on a genuinely EMPTY warps line
# ("Warps to Sector(s) :  " with nothing after it, followed by a blank
# line), that `\s*` happily consumed the newline(s) too and the greedy
# `(.*)$` capture then landed on a LATER, unrelated line instead ("Command
# [TL=00753:0/0/0/850] (?=Help)? :" -> a bogus warps=[753,0,0,0,850]).
# Worse, this poisoned screen still passes `is_genuine_sector_status`
# (the sibling-marker check only looks for the LABEL, not real content),
# so the cold-start seed would have written the garbage into the world-
# model every tick. `[ \t]*` (horizontal whitespace only, never `\n`)
# closes this while changing nothing about the good-case parse: `.`
# already can't cross a newline without DOTALL, so the label-to-capture
# gap only ever needed to skip same-line spacing, never a linebreak.
#
# CRITICAL fix, completed (cipher re-verify, 2026-07-21): the prior fix
# above only converted the `\s*` immediately BEFORE the capture group --
# the `\s*` between `sector\(s\)` and the optional `:?` was still plain
# `\s*` and still crossed a newline. Live repro: "Warps to Sector(s)"
# alone on its own line (the LABEL, no colon), with ":  (9001)-(9002)"
# pushed to the very next physical line, still captured `[9001, 9002]`
# from that next line -- and since this is a distinct, later fragment on
# the SAME screen as a genuine sector-status block, `is_genuine_sector_
# status()` still returns True for the real block, so the cold-start
# seed would persist the forged pair as if they were the real current
# sector's warps (cipher's guard-defeat PoC: this also slips past the
# HIGH backstop in autopilot.py, since that check re-parses the exact
# same buffer and sees the identical forged fragment). Both post-
# `sector(s)` `\s*` occurrences now use `[ \t]*` -- neither can ever
# cross into a second physical line; the whole label-through-value span
# this regex matches is now guaranteed to stay on ONE line.
_WARPS_RE = re.compile(r"^\s*warps?\s+to\s+sector\(s\)[ \t]*:?[ \t]*(.*)$", re.I | re.M)
# Sector-status flyby port line (WO-PORT-CHAIN-SEED): "Ports : None" or
# "Ports : Hammurabi Annex, Class 2 (BSB)". Same line-start + last-match
# discipline as `_WARPS_RE` / `_SECTOR_RE`. Horizontal-whitespace-only
# gaps so a soft-wrap / empty value cannot pull the next physical row.
_PORTS_LINE_RE = re.compile(r"^\s*ports?\s*:[ \t]*(.*)$", re.I | re.M)
# Trailing three-letter Buy/Sell class code when the status line literally
# prints it -- e.g. "(BSB)". Never invent commodities from this code.
_PORTS_CLASS_LETTER_RE = re.compile(r"\(([BS]{3})\)\s*$", re.I)
_COMMODITIES = ("Fuel Ore", "Organics", "Equipment")
# Real port-trade table columns: NAME  STATUS  TRADING  %-OF-MAX  ONBOARD
# ("Fuel Ore   Buying    2650    100%       0") — three numbers per row,
# not one. The percentage is the SECOND number (the one before "%"); a
# naive "first number after buying/selling" match grabs the trading
# amount (2650) and misreports it as a percentage.
_COMMODITY_RE_TMPL = r"{name}\s+(buying|selling)\s+(\d[\d,]*)\s+(\d+)\s*%"

# -- Docked commerce-report block scoping (WO-FA2b REVISE, cipher F1 + mack
# convergent finding, 2026-07-21): `parse_state()`'s commodity extraction
# used to `pattern.search(rendered_text)` per commodity -- FIRST match over
# the WHOLE buffer, unscoped to any particular report and not even
# last-match like every sibling field (sector/credits/warps) -- a straight
# violation of this module's own hard rule. Before WO-FA2b nothing ever
# PERSISTED a docked port read, so it was inert; `write_port_only` turns it
# into real, persisted corruption the moment a stale/forged commodity
# fragment sits ANYWHERE earlier in the buffer (a prior port visit's
# scrollback, a forged chat line) -- cipher's two PoCs
# (scratchpad/poc_commodity_stale.py, poc_commodity_full.py) and mack's
# cross-block repro all confirmed the override. The fix: commodities are
# extracted ONLY from the contiguous block immediately beneath the LATEST
# commerce-report anchor line -- the SAME block `is_genuine_port_report`
# (below) validates -- via this one shared helper, so the gate and the
# written values always read the IDENTICAL block. Mirrors
# `_latest_cim_report_lines`'s own last-match-anchored, contiguous-block
# convention.
_PORT_REPORT_HEADER_RE = re.compile(r"^\s*commerce\s+report\s+for\s+.+:", re.I)
_PORT_REPORT_COLUMN_HEADER_RE = re.compile(
    r"^\s*items\b.*\bstatus\b.*\btrading\b.*%\s*of\s*max\b.*\bonboard\b", re.I
)


def _latest_commerce_report_block(rendered_text: str) -> "list[str]":
    """The contiguous non-blank lines immediately beneath the LATEST
    commerce-report anchor line (the "Commerce report for <name>:" header,
    or the "Items ... Status ... Trading ... % of max ... OnBoard" column
    header printed just above the row table -- either qualifies, and
    whichever sits CLOSER to the rows naturally wins the last-match scan
    since it's textually later) -- `[]` when no anchor line is present at
    all, or when the anchor is immediately followed by a blank line (an
    empty/header-only report has no block worth reading). Shared by
    `is_genuine_port_report` (is there a real row in this block at all?)
    and `parse_state`'s commodity extraction (what does this block's row
    actually say?) so both always agree on which block is "the" genuine
    report -- see the section comment above for why that agreement is the
    fix."""
    lines = rendered_text.splitlines()

    anchor_idx = None
    for i, line in enumerate(lines):
        if _PORT_REPORT_HEADER_RE.match(line) or _PORT_REPORT_COLUMN_HEADER_RE.match(line):
            anchor_idx = i  # keep overwriting -- last match wins, same as is_genuine_sector_status

    if anchor_idx is None:
        return []

    block = []
    for line in lines[anchor_idx + 1 :]:
        if not line.strip():
            break  # the contiguous report block ends at the first blank line
        block.append(line)
    return block


# -- Port-haggle state machine (DESIGN-v2.md §9, seeded from live-captured
# haggle exchanges, 2026-07-19). Two shapes seen for the port's price
# statement -- the opening quote AND every subsequent re-quote after a
# round of countering both use the SAME "We'll buy/sell them for N
# credits." wording (real captured round 2: "We'll buy them for 2,214
# credits." -> counter 2450 -> "We'll buy them for 2,216 credits."), but
# a "Our final offer is N credits." phrasing was also captured live on a
# different port -- both are tracked, whichever occurs LAST in the
# buffer is the live price (same last-match anchoring as credits/sector
# above; a multi-round haggle accumulates several of these lines on one
# screen as the scrollback grows).
_PORT_QUOTE_DIRECTIONAL_RE = re.compile(r"we'll\s+(sell|buy)\s+them\s+for\s+(\d[\d,]*)\s+credits", re.I)
_PORT_QUOTE_FINAL_RE = re.compile(r"our\s+final\s+offer\s+is\s+(\d[\d,]*)\s+credits", re.I)
# "Your offer [N] ?" -- N is the port's current default (whatever a
# blank/Enter reply would accept). Real capitalization from live screens
# ("Your offer [158] ? ") -- settle.py's wait_prompt regexes match
# case-sensitively, so haggle.py's confirm_prompt reuses this exact case.
_OFFER_PROMPT_RE = re.compile(r"Your\s+offer\s*\[\s*(\d[\d,]*)\s*\]\s*\?", re.I)


def _last_nonblank_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line:
            return line
    return ""


def last_nonblank_line(text: str) -> str:
    """Public wrapper around `_last_nonblank_line()` -- other modules
    (haggle.py's evidence/anchor checks) need the SAME "current prompt
    line only, not the whole possibly-stale buffer" convention this
    module's own gate anchors (`current_default` above) already use,
    without re-deriving the same last-non-blank-line logic a second
    time."""
    return _last_nonblank_line(text)


# FORGED-BALANCE RESIDUAL (documented, not fixed here -- cipher HIGH,
# WO-FA7a revise 3, 2026-07-21): `_YOU_HAVE_CREDITS_RE` (line 77) is
# UNanchored -- only `re.I`, no `^`/`re.MULTILINE` -- and, like every
# sibling last-match field in this module, takes the LAST occurrence
# anywhere in the whole rendered buffer. A forged in-band "You have N
# credits" chat/broadcast line landing AFTER the real balance line on the
# same settled screen therefore overrides it, in EITHER direction: cipher
# PoC'd both an inflate (the caller believes a HIGHER balance than real)
# and a deflate (a LOWER one) through the real dispatch path. The deflate
# direction is the sharper one for THIS function's actual consumers below
# -- it can MASK a real doubling event, suppressing WO-FA7b's 2x-stop
# exactly when it matters most.
#
# TWO subsystems consume this function, both exposed to the same
# residual, neither documented before this note: `protocol.py`'s
# `Session.observe_credits()` (WO-FA7a's passive credits-supervision
# surface, session.py) and `haggle.py`'s own credit-delta verification
# (`haggle.py:174,235` -- `after_credits`/`before_credits`).
#
# Bounded today the same way as its three siblings: SOLO-safe (no other
# player exists on a crawl_sacrificial game to author such a forgery).
# This is the 4th instance of the same forged-last-match residual family
# as `is_genuine_sector_status`'s FORGED-BLOCK residual,
# `sector_from_command_prompt`'s own residual, and
# `is_genuine_port_report`'s FORGED-COMMERCE residual (all above) -- a
# one-off `^` anchor here would only shrink the surface (and risks
# breaking a legitimately mid-line balance shape not yet captured live);
# the real close is the SAME unified anchor-to-live-prompt/exclusivity
# hardening already tracked as ONE FA9-class roadmap prerequisite before
# any autonomous run on a multiplayer/shared server, not a fifth one-off
# fix.
def credits_balance(rendered_text: str) -> "int | None":
    """STRICT balance extraction for `Session.observe_credits()` -- unlike
    `parse_state()`'s `credits` field, this NEVER falls back to the
    generic "N credits" mention (`_CREDITS_AMOUNT_FIRST_RE`), which a
    port's own price quote ("We'll buy them for N credits.") would
    otherwise satisfy just as well and get misread as an actual
    balance. A haggle dialogue screen is dominated by exactly those
    price-quote sentences, so haggle.py's credit-delta verification
    needs this narrower extraction rather than `parse_state()`'s
    caller-friendly-but-looser fallback chain.

    Accepted shapes (last-match, stale-scrollback safe):
      1. "You have N credits" (classic)
      2. Label-first "Credits : N" / "Credits: N" (ship-info `I` screen —
         WO-HUD-CREDITS-TURNS-JOIN; never a price quote)

    Subject to the same documented FORGED-BALANCE residual as siblings
    (FA9 fold).
    """
    matches = _YOU_HAVE_CREDITS_RE.findall(rendered_text)
    if not matches:
        matches = _CREDITS_LABEL_FIRST_RE.findall(rendered_text)
    if not matches:
        return None
    return int(matches[-1].replace(",", ""))


def parse_haggle(rendered_text: str) -> dict:
    """Best-effort extraction of an in-progress port-haggle dialogue:
    `{direction, baseline, latest_quote, current_default}` (any/all
    omitted when absent -- no active haggle on screen). `direction` is
    "sell" (the PORT sells -- we're buying, want a LOWER price) or "buy"
    (the port buys -- we're selling, want a HIGHER price); `baseline` is
    the port's ORIGINAL opening quote (fixed for the whole dialogue, the
    fair-value reference haggle.py's strategy anchors to); `latest_quote`
    is the live, most-recent quoted price (updated every round);
    `current_default` is whatever a blank/Enter reply accepts RIGHT NOW.

    `current_default` is checked against the CURRENT PROMPT LINE ONLY
    (the last non-blank line), never the whole buffer -- classify.py's
    own gate-anchor convention, and for the same reason: a resolved
    dialogue's LAST 'Your offer [...]?' line stays sitting in scrollback
    long after the deal closes (a completion message and the next
    command prompt print AFTER it, not over it), so a whole-buffer
    last-match search would misreport an already-closed haggle as still
    pending. `baseline`/`latest_quote` are legitimate content anchors
    (classify.py's other category) and stay whole-buffer, last-match."""
    haggle = {}

    directional_matches = list(_PORT_QUOTE_DIRECTIONAL_RE.finditer(rendered_text))
    if directional_matches:
        # The direction is stated once, unambiguously, at the OPENING
        # quote and never flips mid-dialogue -- the first match is as
        # good as any, and is the one paired with the true baseline.
        haggle["direction"] = directional_matches[0].group(1).lower()
        haggle["baseline"] = int(directional_matches[0].group(2).replace(",", ""))

    # The live-current quoted price, whichever phrasing last appeared in
    # the buffer (position-sorted, not regex-priority-sorted).
    quote_positions = [(m.end(), m.group(2)) for m in directional_matches]
    quote_positions += [(m.end(), m.group(1)) for m in _PORT_QUOTE_FINAL_RE.finditer(rendered_text)]
    if quote_positions:
        quote_positions.sort(key=lambda t: t[0])
        haggle["latest_quote"] = int(quote_positions[-1][1].replace(",", ""))

    m = _OFFER_PROMPT_RE.search(_last_nonblank_line(rendered_text))
    if m:
        haggle["current_default"] = int(m.group(1).replace(",", ""))

    return haggle


def fighters_aboard(rendered_text: str):
    """Best-effort aboard-fighter count from ship-info or toll Option? screens.

    Last-match-wins across both shapes (same discipline as turns/credits).
    Returns ``None`` when no trustworthy aboard count is visible."""
    candidates: list[tuple[int, int]] = []
    for m in _SHIP_HFS_RE.finditer(rendered_text):
        candidates.append((m.end(), int(m.group(2).replace(",", ""))))
    for m in _FIGHTER_ABOARD_VS_RE.finditer(rendered_text):
        candidates.append((m.end(), int(m.group(1))))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


def parse_state(rendered_text: str) -> dict:
    state = {}

    sectors = _SECTOR_RE.findall(rendered_text)
    if not sectors:
        sectors = _CURRENT_SECTOR_RE.findall(rendered_text)
    if sectors:
        state["sector"] = int(sectors[-1])

    m = _TURNS_RE.search(rendered_text)
    if m:
        state["turns_left"] = int(m.group(1))
    else:
        plain = list(_TURNS_LEFT_PLAIN_RE.finditer(rendered_text))
        label = list(_TURNS_LEFT_LABEL_RE.finditer(rendered_text))
        # Prefer the bottom-most match across both phrasings (last-match
        # hard-rule) so a stale "N turns left" above a live "Turns left : N"
        # ship-info line cannot win.
        candidates = [(m.end(), m.group(1)) for m in plain + label]
        if candidates:
            candidates.sort(key=lambda t: t[0])
            state["turns_left"] = int(candidates[-1][1].replace(",", ""))
        else:
            m = _TURN_TIMER_RE.search(rendered_text)
            if m:
                state["turn_timer"] = m.group(1)

    matches = _YOU_HAVE_CREDITS_RE.findall(rendered_text)
    if not matches:
        matches = _CREDITS_LABEL_FIRST_RE.findall(rendered_text) or _CREDITS_AMOUNT_FIRST_RE.findall(rendered_text)
    if matches:
        state["credits"] = int(matches[-1].replace(",", ""))

    # KNOWN LIMITATION (mack MED, 2026-07-21, accepted -- not fixed here):
    # a "Warps to Sector(s)" line long enough to hit an 80-col terminal's
    # hard wrap (a full 6-destination list with several 5-digit sector
    # numbers can just clear ~79/80 chars -- the WO-FA1 6-warp example
    # above is only 71) soft-wraps onto the NEXT physical screen row with
    # no real newline byte ever sent by the server -- pyte's own auto-wrap,
    # not a logical line break. `session.render_text()` joins screen ROWS
    # with "\n" regardless, so `_WARPS_RE`'s `(.*)$` (correctly, per the
    # CRITICAL fix above, stopping at the first REAL newline) truncates
    # mid-digit at that wrap boundary and drops the tail destination(s).
    # Rejoining a soft-wrapped continuation would need a wrap-detection
    # heuristic (row filled to full width + next row looking like a bare
    # continuation, not a new label) that risks incorrectly merging two
    # genuinely distinct 80-char-wide lines elsewhere in the buffer -- a
    # bigger, riskier fix than this bounded, rare (galaxy-size-dependent)
    # edge case warrants; a truncated warps list here degrades to "fewer
    # known frontier edges this tick" (explore.py just sees a smaller
    # adjacency list, never a wrong one), not a wrong/unsafe value.
    # Revisit if a live galaxy is ever seen wide enough to trigger it.
    warps_lines = _WARPS_RE.findall(rendered_text)
    if warps_lines:
        warps = [int(x) for x in re.findall(r"\d+", warps_lines[-1])]  # last match wins -- see _WARPS_RE comment
        if warps:
            state["warps"] = warps

    # WO-PORT-CHAIN-SEED / WO-TUI-CHAIN-25948-FALSE-PORT: flyby presence
    # from the sector-status "Ports :" line -- NOT commodities (those
    # come only from a commerce report).
    #
    # Scope to the SAME contiguous status block under the LAST "Sector :"
    # line that `is_genuine_sector_status` trusts -- never a whole-buffer
    # Ports match (stale scrollback / prior hop). Within that block:
    #   - "Ports : <name…>" → presence dict (optional class)
    #   - "Ports : None" / blank → explicit port=None (clear prior flyby)
    #   - Ports line ABSENT but block is genuine (Sector + Warps) → also
    #     port=None: this live server omits the Ports line entirely when
    #     the sector has no port (login/redisplay at 25948 showed Sector
    #     + Warps only; key-absent left the BBS flyby ghost).
    # Non-genuine screens leave the key unset (do not clear on unobserved).
    block_lines = _latest_sector_status_block_lines(rendered_text)
    if block_lines is not None:
        ports_value = None
        saw_ports_line = False
        for line in block_lines:
            m = _PORTS_LINE_RE.match(line)
            if m:
                saw_ports_line = True
                ports_value = m.group(1)
        if saw_ports_line:
            state["port"] = _flyby_port_from_ports_line(ports_value)
        elif any(_WARPS_RE.match(line) for line in block_lines):
            # Genuine Sector+Warps, no Ports line → confirmed no port.
            state["port"] = None

    # WO-FA2b REVISE (cipher F1 + mack convergent finding): commodity rows
    # are extracted ONLY from `_latest_commerce_report_block()` -- the
    # SAME contiguous block `is_genuine_port_report` validates -- never
    # from the whole buffer. The old `pattern.search(rendered_text)` was a
    # FIRST match over the entire screen, unscoped and not even last-match
    # like every sibling field here -- a stale/forged commodity fragment
    # anywhere earlier in the buffer (a prior port visit's scrollback, a
    # forged chat line) could override the genuine row while the gate
    # still passed. See `_latest_commerce_report_block`'s own docstring.
    block = _latest_commerce_report_block(rendered_text)
    commodities = []
    for name in _COMMODITIES:
        pattern = re.compile(_COMMODITY_RE_TMPL.format(name=re.escape(name)), re.I)
        last_match = None
        for line in block:
            m = pattern.search(line)
            if m:
                last_match = m  # keep overwriting -- last match wins WITHIN the block
        if last_match:
            commodities.append(
                {
                    "name": name,
                    "status": last_match.group(1).lower(),
                    "amount": int(last_match.group(2).replace(",", "")),
                    "pct": int(last_match.group(3)),
                }
            )
    if commodities:
        # Merge onto flyby presence when both appear on one screen (e.g.
        # sector-status + docked commerce still in the viewport).
        port = dict(state.get("port") or {})
        port["commodities"] = commodities
        state["port"] = port

    aboard = fighters_aboard(rendered_text)
    if aboard is not None:
        state["fighters_aboard"] = aboard

    return state


def _flyby_port_from_ports_line(value: str):
    """Map a sector-status `Ports : …` value to a partial port dict, or
    None when the line says there is no port.

    Presence-only: never invents commodities. Optional `class` is set
    ONLY when the line literally ends with a three-letter Buy/Sell code
    in parens (e.g. `(BSB)`), matching CIM vocabulary -- a bare
    `Class N` numeric label without that code yields presence with no
    `class` key (avoids clobbering a later CIM letter-code with an int).
    """
    raw = (value or "").strip()
    if not raw or raw.casefold() == "none":
        return None
    port = {}
    m = _PORTS_CLASS_LETTER_RE.search(raw)
    if m:
        port["class"] = m.group(1).upper()
    return port


# -- Sector-write provenance for the world-model (mack round-3 residual,
# closed 2026-07-19) --------------------------------------------------------
#
# The round-2 fix above (`_SECTOR_RE`'s line-anchoring) closed the
# mid-sentence forgery, but only required the forged "Sector : N" be
# alone on ITS OWN line -- not alone on the SCREEN. A line-isolated
# "Sector : 8675" embedded in an otherwise-narrative multi-line block
# (a planet-comment/bulletin post, a forged multi-line "transmission")
# still reproduces the exact shape `_SECTOR_RE` requires, and still wins
# via `parse_state()`'s deliberate last-match-wins rule (needed for the
# real stale-scrollback case) over an earlier, genuine status line --
# mack's confirmed repro: a real "Sector : 100" / "Ports : ..." block,
# followed later on the SAME screen by a planet-comment block whose only
# line-isolated "Sector : 8675" has no other status content around it.
#
# Text-matching the sector line's own shape can't be the trust signal
# here either (same lesson as `classify._is_genuine_cim_report`) --
# what a forger embedding one line inside narrative prose has no reason
# to also reproduce is the SIBLING status-block shape a genuine in-game
# system status display always prints immediately beneath its own
# "Sector : N" line: a "Ports :" label (every real sector-status
# capture in this file's own tests/fixtures shows this), or a "Warps
# to Sector(s) :" label (`_WARPS_RE`'s own literal shape). So:
# `is_genuine_sector_status()` finds the LAST-match sector line (the
# same one `parse_state()`'s `sector` field anchors to) and requires a
# sibling status marker among the lines immediately following it, up to
# the next blank line (the real status block is a contiguous run of
# non-blank lines; a blank line is where it ends and the port-trade
# table / narrative body begins) -- never checked against the whole
# screen, since the genuine block earlier in the SAME screen must not
# vouch for an unrelated, later, line-isolated forgery.
#
# This is deliberately scoped to the WORLD-MODEL WRITE path only (see
# protocol.py's `_write_world_model`) -- `parse_state()`'s own `sector`
# field, and every other consumer reading it directly (skills.py's
# start_anchor, ledger.py, protocol.py's replay start-anchor), are
# UNCHANGED: those need the sector off any normal settled game screen,
# not just a screen carrying a full sibling status block.
#
# RESIDUAL (documented, not fixed here -- mack/cipher adversarial
# re-verify of WO-FA1, 2026-07-21): this is a shape check, not a
# provenance check -- a forged in-band chat/broadcast that happens to
# reproduce a "Sector : N" line immediately followed by a sibling marker
# line (no blank line between) still passes. Bounded today by every
# consumer of a `True` result here (see protocol.py's `_write_world_model`
# and `_autopilot_snapshot_kwargs`'s cold-start seed for the full
# blast-radius reasoning) -- becomes a HARD GATE prerequisite before any
# autonomous run on a multiplayer/shared server, where another player
# could actually author such a broadcast.
def _latest_sector_status_block_lines(rendered_text: str):
    """Contiguous non-blank lines under the LAST line-start ``Sector : N``.

    Same last-match + blank-line end discipline as
    ``is_genuine_sector_status``. Returns ``None`` when no sector line
    exists; otherwise the block body (may be empty).
    """
    lines = rendered_text.splitlines()
    sector_idx = None
    for i, line in enumerate(lines):
        if _SECTOR_RE.match(line):
            sector_idx = i
    if sector_idx is None:
        return None
    block = []
    for line in lines[sector_idx + 1 :]:
        if not line.strip():
            break
        block.append(line)
    return block


def is_genuine_sector_status(rendered_text: str) -> bool:
    """True only when the sector `parse_state()` would anchor to (the
    LAST line-start "Sector : N" match, same discipline as `parse_state`
    itself) is immediately followed -- before the next blank line -- by
    one of the sibling status-block markers (`Ports :` / `Warps to
    Sector(s) :`) a genuine in-game sector display always carries. See
    the section docstring above for the provenance rationale."""
    lines = rendered_text.splitlines()

    sector_idx = None
    for i, line in enumerate(lines):
        if _SECTOR_RE.match(line):
            sector_idx = i  # keep overwriting -- last match wins, same as parse_state()'s sector field

    if sector_idx is None:
        return False

    for line in lines[sector_idx + 1 :]:
        if not line.strip():
            break  # the contiguous status block ends at the first blank line
        if _SECTOR_STATUS_SIBLING_RE.match(line):
            return True
    return False


# -- Command-prompt sector anchor (WO-FA2b REVISE, 2026-07-21, replacing the
# original cross-screen `session.last_genuine_sector` anchor) -----------------
#
# mack's CRITICAL finding: pyte is `pyte.Screen` (terminal.py) -- NO
# scrollback, a fixed viewport only. A warp landing on a port sector
# streams sector-arrival + auto-dock + commerce report as ONE continuous
# burst; when that burst exceeds the viewport height, the "Sector : N"
# line scrolls OFF the settled grid before the daemon ever gets a
# settle-checkpoint on it alone -- `is_genuine_sector_status` then fails
# closed, so a cross-call anchor (this WO's original design) goes stale,
# and a LATER commerce report's real port data gets attributed to an
# EARLIER, no-longer-current sector. A stale anchor also survives a
# `session.reconnect()` (nothing resets it), compounding the same defect.
#
# The fix: carry NO cross-screen anchor at all -- the current sector is
# available on the SAME settled screen the commerce report itself is on.
# This live server's ship Command prompt is
# "Command [TL=HH:MM:SS]:[NNNN] (?=Help)? :" (also "Computer command
# [TL=...]:[NNNN]" for the computer subsystem prompt, `classify.py`'s own
# "superset" precedent) -- [NNNN] is the CURRENT SECTOR, not turns-left
# (turns-left is reported separately, see `_TURNS_LEFT_PLAIN_RE`) --
# live-log-verified exact correlation across multiple sectors on the same
# session (already this project's own established test convention --
# `tests/test_protocol_trainer_panel.py`'s `_ANCHOR_SCREEN` literally
# reuses the same number for both "Sector :" and this bracket). Crucially,
# in the >25-line-burst CRITICAL case, the "Sector :" line scrolls away
# but the commerce report + its OWN trailing Command prompt are the final
# settled lines -- so this same-screen anchor is present exactly where
# the old cross-screen one failed.
#
# LAST-match anchored, same discipline as every other field here: the
# genuine trailing prompt is always the settle point (last on screen); a
# forged earlier "Command [...]:[9999]" line is overridden by the real
# one, same forgery-resistance precedent as credits/sector/warps.
#
# RESIDUAL (documented, not fixed here -- cipher re-verify, 2026-07-21):
# taking `matches[-1]` is exactly what makes this forgery-resistant
# against an EARLIER forged prompt (above), but it's the same shape that
# makes it vulnerable to a LATER one -- a forged in-band
# "Command [TL=...]:[NNNN]" fragment (a chat/broadcast/hail line
# reproducing the prompt's own text) landing AFTER the real trailing
# command prompt on the same settled screen would win last-match instead,
# attributing the (now-genuine, post-fix) commerce-report data to a WRONG
# sector. Bounded today the same way as its two siblings: SOLO-safe (no
# other player exists on a crawl_sacrificial game to author such a
# forgery). Live-realism UNCONFIRMED (unlike those siblings' own
# confirmed repros): a well-behaved BBS door redisplays its own command
# prompt after any interrupt/interjection, so the real prompt is normally
# the LAST such match on a genuinely settled screen -- this residual
# would need a hail/broadcast that renders strictly AFTER the settled
# prompt without the door ever redisplaying it, which hasn't been
# observed live. This is the THIRD instance of the same forged-last-match
# residual family as `is_genuine_sector_status`'s FORGED-BLOCK residual
# and `is_genuine_port_report`'s FORGED-COMMERCE residual (below) -- all
# three are closed by the SAME anchor-to-live-prompt/exclusivity
# hardening, tracked as ONE unified FA9-class roadmap prerequisite before
# any autonomous run on a multiplayer/shared server, not three separate
# fixes.
_COMMAND_PROMPT_SECTOR_RE = re.compile(r"command\s*\[\s*tl\s*=[^\]]*\]\s*:\s*\[\s*(\d+)\s*\]", re.I)


def sector_from_command_prompt(rendered_text: str) -> "int | None":
    """The current sector, read off THIS screen's own trailing ship
    Command prompt (`Command [TL=...]:[NNNN]`, or the computer
    subsystem's `Computer command [TL=...]:[NNNN]`) -- see the section
    comment above for why this replaced the cross-screen
    `session.last_genuine_sector` anchor, and for the forged-last-match
    residual this anchor shares with its two siblings. `None` when no
    such prompt is on screen -- either a screen that isn't a command
    prompt at all, or (mack's observation) a CLASSIC-shape TWGS server
    whose Command prompt has no trailing `[NNNN]` bracket at all (e.g.
    "Command [TL=00753:0/0/0/850] (?=Help)? :" -- TL is a plain turn
    count, no second bracket): on such a server this always returns
    `None`, so the docked-commerce write path this anchor feeds
    (`protocol._write_world_model`) never fires there -- a fail-closed
    COVERAGE trade-off (a missed write, never a wrong one), not a bug.
    The live crawl_sacrificial target (tradewarsacademy) uses the
    bracketed shape, so this is not a gap for that server. Callers must
    treat a `None` return as "can't anchor," never guess."""
    matches = _COMMAND_PROMPT_SECTOR_RE.findall(rendered_text)
    if not matches:
        return None
    return int(matches[-1])


# -- Docked commerce-report provenance for the world-model (WO-FA2b write
# path, 2026-07-21) -----------------------------------------------------------
#
# The world-model canon (knowledge/architecture/world-model.md's Write
# Hooks section) prescribes that "every parsed game-state read (sector,
# port commodities) writes its sector's port field" -- but a DOCKED
# commerce-report screen ("Commerce report for <port>: ...") carries NO
# "Sector : N" line of its own to anchor a write to (see
# `sector_from_command_prompt` above for the anchor this feeds instead).
# `parse_state()` already extracts the commodity rows correctly
# (`_COMMODITY_RE_TMPL`, live-confirmed against tests/fixtures/
# port_commerce_report_gorram_primus.txt, scoped to the genuine block via
# `_latest_commerce_report_block` -- see that helper's own docstring) --
# the missing piece here is PROVENANCE: is this screen actually a real
# docked commerce report, or just narrative TEXT that happens to mention
# "Fuel Ore"/"Organics"/"Equipment" (the loose `classify.py` `port_trade`
# content anchor's own keyword-only test, which exists to CLASSIFY a
# screen for display, not to gate a world-model WRITE, and is
# deliberately not reused here for that reason)?
#
# Shape-not-keyword, mirroring `is_genuine_sector_status`'s own
# philosophy: genuine ⇔ `_latest_commerce_report_block()` (the contiguous
# block beneath the LAST "Commerce report for <name>:" header, or the
# column header printed just above the row table -- both real captured
# shapes, see tests/fixtures/port_trade_screen.txt and
# tests/fixtures/port_commerce_report_gorram_primus.txt) contains at
# least one REAL commodity row -- the exact `_COMMODITY_RE_TMPL` shape
# `parse_state()`'s own commodity extraction already requires (name +
# buying/selling + a trading amount + a bounded percentage). A screen
# merely NAMING a commodity in passing ("Rumor: they say this port deals
# heavily in Equipment") has no reason to also reproduce a fully-shaped
# trade row, so it fails this gate even though it would satisfy the loose
# keyword-only `port_trade` classification.
#
# FORGED-COMMERCE RESIDUAL (documented, not fixed here -- mirrors the
# FORGED-BLOCK RESIDUAL on `is_genuine_sector_status`'s own seed path,
# protocol.py's `_autopilot_snapshot_kwargs`): this is a SHAPE check, not
# a full provenance check -- a forged in-band chat/broadcast that
# reproduces the header (or column header) line immediately followed by
# a real-shaped commodity row still passes. With the same-screen anchor
# above, a forged report now writes to the REAL current sector's port
# (never an arbitrary/stale one) -- no longer a wrong-sector write, but
# still writes FORGED commodity data under a real sector. Bounded today
# the same way: SOLO-safe (no other player exists on a crawl_sacrificial
# game to author such a forgery), becomes a HARD GATE prerequisite the
# moment autonomous mode runs on a multiplayer/shared server (FA9-class
# hardening, tracked as a roadmap prerequisite alongside
# `is_genuine_sector_status`'s own residual) -- closing it would need the
# same anchor-to-live-prompt/exclusivity hardening
# `_is_genuine_cim_report`'s "nothing else shares the screen" discipline
# uses, deliberately NOT attempted in this build.
#
# KNOWN RESIDUAL, LOW (mack, documented not fixed): this gate fails
# CLOSED if a TWGS variant's column header differs enough that NEITHER
# `_PORT_REPORT_HEADER_RE` nor `_PORT_REPORT_COLUMN_HEADER_RE` matches --
# a genuine docked commerce report on such a variant would simply never
# get its port data persisted (a missed write, never a wrong one). Extend
# the anchor patterns here as new live commerce-report header shapes are
# captured, same "extend as live play reveals more screen shapes"
# convention this module's own top docstring already calls out.
def is_genuine_port_report(rendered_text: str) -> bool:
    """True only when `_latest_commerce_report_block()` (the contiguous
    block beneath the LAST genuine commerce-report anchor line) contains
    at least one real, fully-shaped commodity row (`_COMMODITY_RE_TMPL`).
    See the section comment above for the provenance rationale, the
    documented forged-commerce residual, and the LOW header-variant
    residual."""
    block = _latest_commerce_report_block(rendered_text)
    commodity_row_patterns = [
        re.compile(_COMMODITY_RE_TMPL.format(name=re.escape(name)), re.I) for name in _COMMODITIES
    ]
    return any(pattern.search(line) for line in block for pattern in commodity_row_patterns)


# -- Batch/CIM port-report parsing (world-model canon,
# knowledge/architecture/world-model.md's "Write Hooks" -- a batch
# port/sector report writes MANY sector records in one pass, added
# 2026-07-19). ----------------------------------------------------------
#
# PROVENANCE CAVEAT: no live-captured multi-sector CIM/scan screen
# exists in this repo yet. The row grammar below (`Sector N  Class:
# XXX F:N% O:N% E:N%  Warps: n-n-n`, bracketed by a `-=-=- Port Report
# (CIM) -=-=-` / `-=-=- End of Report -=-=-` header/footer) is
# CONSTRUCTED from the one TW2002 convention independently verified
# (the three-letter Buy/Sell port-class code -- first letter Fuel Ore,
# second Organics, third Equipment) plus this file's own already-proven
# real-capture conventions (the "Sector" keyword casing from
# `_SECTOR_RE`, the "-=-=- ... -=-=-" divider style from the real
# `tests/fixtures/port_trade_screen.txt` capture). The header/footer
# punctuation and row layout themselves are NOT a live capture --
# expect a refinement pass once the daemon actually sees a real
# CIM/scan screen (the same "extend as live play reveals more screen
# shapes" pattern this module's own docstring already calls out).
_CIM_HEADER_RE = re.compile(r"^-=-=-\s+Port Report \(CIM\)\s+-=-=-$")
_CIM_FOOTER_RE = re.compile(r"^-=-=-\s+End of Report\s+-=-=-$")
_ROW_SECTOR_RE = re.compile(r"^Sector\s+(\S+)")
_ROW_PORT_CLASS_RE = re.compile(r"Class:\s*([BS]{3})\b")
# A percentage is bounded 0-100 -- a careless forgery ("F:150%") is
# rejected outright rather than silently accepted as real port data
# (mack's cheap-orthogonal-hardening suggestion, 2026-07-19 follow-up).
_PCT_RE_FRAGMENT = r"(?:100|[0-9]{1,2})"
_ROW_PORT_PCTS_RE = re.compile(
    rf"F:({_PCT_RE_FRAGMENT})%\s+O:({_PCT_RE_FRAGMENT})%\s+E:({_PCT_RE_FRAGMENT})%"
)
_ROW_WARPS_RE = re.compile(r"Warps:\s*([\d\-]+)")


def _latest_cim_report_lines(rendered_text: str) -> list:
    """The raw lines strictly between the LATEST report header and the
    first footer after it, or [] if no closed report is present.

    Anchoring to the LAST header occurrence (not the first) is the
    same stale-scrollback discipline `parse_state()`'s `sector`/
    `credits` fields use (see module docstring): a report screen can
    sit in pyte's unclaimed scrollback above a genuinely fresher one,
    and a first-match implementation would parse the stale report
    instead of the current one. A report with no footer yet (still
    printing) is treated as not confidently closed and skipped rather
    than parsed mid-arrival."""
    lines = rendered_text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if _CIM_HEADER_RE.match(line.strip()):
            header_idx = i  # keep overwriting -- last match wins
    if header_idx is None:
        return []
    for j in range(header_idx + 1, len(lines)):
        if _CIM_FOOTER_RE.match(lines[j].strip()):
            return lines[header_idx + 1 : j]
    return []


def parse_port_report(rendered_text: str) -> "list[dict]":
    """Batch-ingest a single screen listing MANY sectors at once -- a
    CIM port report, a multi-sector scan, or a holo/density-scan
    listing -- into the list of partial per-sector dicts the
    world-model's `bulk_upsert` ingests (see
    knowledge/architecture/world-model.md's Schema table). Each dict
    is `{"sector_id": int, ...}` plus only whichever of `warps`/`port`
    that row's line actually encodes -- never a field the line doesn't
    provide, and never a guessed/garbage record for a row that can't
    be confidently anchored (silently skipped instead).

    See the section docstring above for the row-grammar provenance
    caveat."""
    records = []
    for raw_line in _latest_cim_report_lines(rendered_text):
        line = raw_line.strip()
        m = _ROW_SECTOR_RE.match(line)
        if not m or not m.group(1).isdigit():
            continue  # not a data row, or an unparseable sector token
        record = {"sector_id": int(m.group(1))}

        cls_m = _ROW_PORT_CLASS_RE.search(line)
        pct_m = _ROW_PORT_PCTS_RE.search(line)
        if cls_m and pct_m:
            code = cls_m.group(1)
            commodities = [
                {
                    "name": name,
                    "status": "buying" if letter == "B" else "selling",
                    "pct": int(pct),
                }
                for name, letter, pct in zip(_COMMODITIES, code, pct_m.groups())
            ]
            record["port"] = {"class": code, "commodities": commodities}

        warp_m = _ROW_WARPS_RE.search(line)
        if warp_m:
            warps = [int(x) for x in re.findall(r"\d+", warp_m.group(1))]
            if warps:
                record["warps"] = warps

        if len(record) > 1:  # more than a bare sector_id -- real content
            records.append(record)
    return records
