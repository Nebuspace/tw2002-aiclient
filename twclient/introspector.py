"""TW-27 game-data introspector (DESIGN-v2.md's per-server intro-
spection layer). Pure text -> structured rows, exactly like
`state_parser.py`'s `parse_port_report()`: no I/O, no daemon touch,
just regexes over an already-rendered pyte screen buffer.

This module is the READ side of the two-layer split
`knowledge/reference/tw2002-ships-and-equipment.md` documents: that
file authors portable, server-independent SEMANTICS (what a stat axis
means) and explicitly carries NO numeric ship values; this module
turns a captured StarDock/shipyard/scanner/transwarp/item listing
SCREEN into the per-server VALUES `twclient/game_data.py`'s schema
expects, one row per catalog entry. A field the listing doesn't
actually show is omitted (or left `None`) -- never a guessed default;
an unparseable listing line is silently skipped -- never a garbage
row. A wrong introspected stat poisons `game_data`, so this parser
stays conservative on purpose (same discipline `parse_port_report()`'s
own module section already documents).

Deliberately absent from every returned row: `last_verified_ts`. This
parser has no clock (reading one would be a form of I/O this pure
text-in/rows-out module doesn't need) -- stamping a fresh timestamp on
write is the persist layer's job, exactly as `game_knowledge.py`'s
`upsert_game_data_row()` already does for the hand-authored game-data
tables. The caller that persists these rows (TW-27's consumer) adds
`last_verified_ts` at write time.

Ship rows additionally carry `alignment_requirement`/`rank_requirement`
-- a ship's numeric holds/cost is only half the acquisition story; a
ship the player cannot yet legally commission (alignment/rank gate) is
not a real candidate no matter how good its stats look on paper (see
`ship_upgrade_decision.py`'s own `commissioned` gate, and the "Progres-
sion and commissioning" section of the ships-and-equipment reference).

**PROVENANCE CAVEAT:** this repo has no live-captured StarDock/
shipyard/equipment screen yet. The row grammar below (a columnar
Name/Holds/Fighters/Shields/Odds/Turns-per-warp/Cost/Alignment/Rank/
TransWarp/Abilities table for ships; a Name/Cost/Notes table for
scanners/transwarp/items) is CONSTRUCTED from the documented TW2002
shipyard-listing convention plus this project's own already-proven
real-capture conventions (the "-=-=- ... -=-=-" divider style from
`tests/fixtures/port_trade_screen.txt` and `cim_port_report.txt`) --
it is NOT a byte-for-byte real capture. Expect a refinement pass once
the daemon actually sees a real StarDock screen (the same "extend as
live play reveals more screen shapes" pattern `state_parser.py`'s own
module docstring calls out).
"""

import re

_SHIPYARD_HEADER_RE = re.compile(r"^-=-=-\s+StarDock Shipyard - Ship Registration\s+-=-=-$")
_SHIPYARD_FOOTER_RE = re.compile(r"^-=-=-\s+End of Shipyard Listing\s+-=-=-$")

_SCANNER_HEADER_RE = re.compile(r"^-=-=-\s+Density & Holographic Scanners\s+-=-=-$")
_SCANNER_FOOTER_RE = re.compile(r"^-=-=-\s+End of Scanner Listing\s+-=-=-$")

_TRANSWARP_HEADER_RE = re.compile(r"^-=-=-\s+TransWarp Drive Installation\s+-=-=-$")
_TRANSWARP_FOOTER_RE = re.compile(r"^-=-=-\s+End of TransWarp Listing\s+-=-=-$")

_ITEM_HEADER_RE = re.compile(r"^-=-=-\s+Special Devices & Ordnance\s+-=-=-$")
_ITEM_FOOTER_RE = re.compile(r"^-=-=-\s+End of Item Listing\s+-=-=-$")

# One ship row: `Name  Holds  Ftrs  Shlds  Odds  T/W  Cost  Align  Rank  TW  [Abilities]`.
# The name column is non-greedy and allows embedded single spaces (multi-
# word ship names, e.g. "Fixture Scout") -- it only stops expanding once
# the required 2+-space column gap into the numeric Holds field is found,
# so it can't accidentally swallow the next column (mirrors the
# fixed-width-table anchoring `parse_port_report()`'s row regex already
# relies on). `TW` (transwarp_capable) is a MANDATORY capture, not an
# optional/guessed one -- if a listing genuinely doesn't show this
# column, the row simply fails to match and is skipped rather than this
# parser inventing a False.
_SHIP_ROW_RE = re.compile(
    r"^(?P<name>[A-Za-z][\w'\- ]*?)\s{2,}"
    r"(?P<holds>\d[\d,]*)\s+"
    r"(?P<fighters>\d[\d,]*)\s+"
    r"(?P<shields>\d[\d,]*)\s+"
    r"(?P<odds>\d+(?:\.\d+)?)\s+"
    r"(?P<warp>\d+)\s+"
    r"(?P<cost>\d[\d,]*)\s+"
    r"(?P<align>-?\d+|none|n/a)\s+"
    r"(?P<rank>\S+)\s+"
    r"(?P<tw>[YN])"
    r"(?:\s{2,}(?P<abilities>\S.*))?"
    r"\s*$",
    re.IGNORECASE,
)

# One scanner/transwarp/item row: `Name  Cost  [free-text Notes]`. Shared
# across all three catalogs -- TranswarpRow has no name field in the
# schema, so `parse_transwarp_listing()` below just discards the
# captured name (the label is decorative screen text, e.g. "TransWarp
# Drive", not part of `game_data.TranswarpRow`).
_EQUIP_ROW_RE = re.compile(
    r"^(?P<name>[A-Za-z][\w'\- ]*?)\s{2,}"
    r"(?P<cost>\d[\d,]*)"
    r"(?:\s{2,}(?P<notes>\S.*))?"
    r"\s*$"
)


def _to_int(token: str) -> int:
    return int(token.replace(",", ""))


def _bracketed_lines(rendered_text: str, header_re: "re.Pattern", footer_re: "re.Pattern") -> "list[str]":
    """The raw lines strictly between the LATEST header occurrence and
    the first footer after it, or [] if no closed block is present.

    Anchors to the LAST header (not the first) -- same stale-scrollback
    discipline as `state_parser.py`'s `_latest_cim_report_lines()`: an
    older, already-closed listing can sit above a fresher one in pyte's
    unclaimed scrollback, and a first-match implementation would parse
    the stale listing instead of the current one. A listing with no
    footer yet (still printing) is treated as not confidently closed
    and skipped rather than parsed mid-arrival."""
    lines = rendered_text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if header_re.match(line.strip()):
            header_idx = i  # keep overwriting -- last match wins
    if header_idx is None:
        return []
    for j in range(header_idx + 1, len(lines)):
        if footer_re.match(lines[j].strip()):
            return lines[header_idx + 1 : j]
    return []


def parse_shipyard_listing(
    rendered_text: str, *, source: str = "introspected: stardock_shipyard"
) -> "list[dict]":
    """Batch-parse a StarDock/shipyard ship-purchase listing into a list
    of dicts shaped like `game_data.ShipRow`'s fields (everything except
    `last_verified_ts` -- see module docstring). A line that isn't a
    real data row (the column-header line, a divider, stray narrative
    text) simply fails to match and is skipped, never guessed at."""
    rows = []
    for raw_line in _bracketed_lines(rendered_text, _SHIPYARD_HEADER_RE, _SHIPYARD_FOOTER_RE):
        line = raw_line.rstrip()
        if not line.strip():
            continue
        m = _SHIP_ROW_RE.match(line)
        if not m:
            continue
        align_token = m.group("align").lower()
        rank_token = m.group("rank")
        abilities_token = m.group("abilities")
        rows.append(
            {
                "ship_name": m.group("name").strip(),
                "max_holds": _to_int(m.group("holds")),
                "max_fighters": _to_int(m.group("fighters")),
                "max_shields": _to_int(m.group("shields")),
                "combat_odds_modifier": float(m.group("odds")),
                "turns_per_warp": int(m.group("warp")),
                "base_cost_credits": _to_int(m.group("cost")),
                "alignment_requirement": (
                    None if align_token in ("none", "n/a") else int(align_token)
                ),
                "rank_requirement": None if rank_token.lower() == "none" else rank_token,
                "transwarp_capable": m.group("tw").upper() == "Y",
                "special_abilities": (
                    [a.strip() for a in abilities_token.split(",") if a.strip()]
                    if abilities_token
                    else []
                ),
                "source": source,
            }
        )
    return rows


def _parse_equip_rows(rendered_text: str, header_re: "re.Pattern", footer_re: "re.Pattern") -> "list[tuple]":
    rows = []
    for raw_line in _bracketed_lines(rendered_text, header_re, footer_re):
        line = raw_line.rstrip()
        if not line.strip():
            continue
        m = _EQUIP_ROW_RE.match(line)
        if not m:
            continue
        notes = (m.group("notes") or "").strip()
        rows.append((m.group("name").strip(), _to_int(m.group("cost")), notes))
    return rows


def parse_scanner_listing(
    rendered_text: str, *, source: str = "introspected: stardock_equipment_scanners"
) -> "list[dict]":
    """Batch-parse a scanner catalog listing into `game_data.ScannerRow`-
    shaped dicts (`scanner_type`/`cost_credits`/`capability_notes`/
    `source`; `last_verified_ts` omitted -- see module docstring).
    `capability_notes` is only included when the listing actually shows
    free-text notes for that row."""
    rows = []
    for name, cost, notes in _parse_equip_rows(rendered_text, _SCANNER_HEADER_RE, _SCANNER_FOOTER_RE):
        row = {"scanner_type": name, "cost_credits": cost, "source": source}
        if notes:
            row["capability_notes"] = notes
        rows.append(row)
    return rows


def parse_transwarp_listing(
    rendered_text: str, *, source: str = "introspected: stardock_equipment_transwarp"
) -> "list[dict]":
    """Batch-parse a TransWarp installation listing into
    `game_data.TranswarpRow`-shaped dicts (`cost_credits`/`range_notes`/
    `source`). The row's leading name/label token (e.g. "TransWarp
    Drive") is decorative screen text, not part of the schema, and is
    discarded."""
    rows = []
    for _name, cost, notes in _parse_equip_rows(rendered_text, _TRANSWARP_HEADER_RE, _TRANSWARP_FOOTER_RE):
        row = {"cost_credits": cost, "source": source}
        if notes:
            row["range_notes"] = notes
        rows.append(row)
    return rows


def parse_item_listing(
    rendered_text: str, *, source: str = "introspected: stardock_equipment_items"
) -> "list[dict]":
    """Batch-parse a special-devices/ordnance catalog listing into
    `game_data.ItemRow`-shaped dicts (`item_name`/`cost_credits`/
    `effect_notes`/`source`)."""
    rows = []
    for name, cost, notes in _parse_equip_rows(rendered_text, _ITEM_HEADER_RE, _ITEM_FOOTER_RE):
        row = {"item_name": name, "cost_credits": cost, "source": source}
        if notes:
            row["effect_notes"] = notes
        rows.append(row)
    return rows
