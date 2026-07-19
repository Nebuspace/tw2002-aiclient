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
"""

import re

_SECTOR_RE = re.compile(r"sector\s*:?\s*(\d+)", re.I)
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
_TURNS_LEFT_PLAIN_RE = re.compile(r"(\d[\d,]*)\s+turns?\s+left", re.I)
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
_WARPS_RE = re.compile(r"warps?\s+to\s+sector\(s\)\s*:?\s*([\d\s\-]+)", re.I)
_COMMODITIES = ("Fuel Ore", "Organics", "Equipment")
# Real port-trade table columns: NAME  STATUS  TRADING  %-OF-MAX  ONBOARD
# ("Fuel Ore   Buying    2650    100%       0") — three numbers per row,
# not one. The percentage is the SECOND number (the one before "%"); a
# naive "first number after buying/selling" match grabs the trading
# amount (2650) and misreports it as a percentage.
_COMMODITY_RE_TMPL = r"{name}\s+(buying|selling)\s+(\d[\d,]*)\s+(\d+)\s*%"

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


def credits_balance(rendered_text: str) -> "int | None":
    """The STRICT "you have N credits" balance only -- unlike
    `parse_state()`'s `credits` field, this NEVER falls back to the
    generic "N credits" mention (`_CREDITS_AMOUNT_FIRST_RE`), which a
    port's own price quote ("We'll buy them for N credits.") would
    otherwise satisfy just as well and get misread as an actual
    balance. A haggle dialogue screen is dominated by exactly those
    price-quote sentences, so haggle.py's credit-delta verification
    needs this narrower, unambiguous extraction rather than
    `parse_state()`'s caller-friendly-but-looser fallback chain.
    Last-match anchored, same stale-scrollback discipline as
    `parse_state()`'s own `credits` field (see module docstring)."""
    matches = _YOU_HAVE_CREDITS_RE.findall(rendered_text)
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


def parse_state(rendered_text: str) -> dict:
    state = {}

    sectors = _SECTOR_RE.findall(rendered_text)
    if sectors:
        state["sector"] = int(sectors[-1])

    m = _TURNS_RE.search(rendered_text)
    if m:
        state["turns_left"] = int(m.group(1))
    else:
        m = _TURNS_LEFT_PLAIN_RE.search(rendered_text)
        if m:
            state["turns_left"] = int(m.group(1).replace(",", ""))
        else:
            m = _TURN_TIMER_RE.search(rendered_text)
            if m:
                state["turn_timer"] = m.group(1)

    matches = _YOU_HAVE_CREDITS_RE.findall(rendered_text)
    if not matches:
        matches = _CREDITS_LABEL_FIRST_RE.findall(rendered_text) or _CREDITS_AMOUNT_FIRST_RE.findall(rendered_text)
    if matches:
        state["credits"] = int(matches[-1].replace(",", ""))

    m = _WARPS_RE.search(rendered_text)
    if m:
        warps = [int(x) for x in re.findall(r"\d+", m.group(1))]
        if warps:
            state["warps"] = warps

    commodities = []
    for name in _COMMODITIES:
        pattern = re.compile(_COMMODITY_RE_TMPL.format(name=re.escape(name)), re.I)
        m = pattern.search(rendered_text)
        if m:
            commodities.append(
                {
                    "name": name,
                    "status": m.group(1).lower(),
                    "amount": int(m.group(2).replace(",", "")),
                    "pct": int(m.group(3)),
                }
            )
    if commodities:
        state["port"] = {"commodities": commodities}

    return state


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
_ROW_PORT_PCTS_RE = re.compile(r"F:(\d+)%\s+O:(\d+)%\s+E:(\d+)%")
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
