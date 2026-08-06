"""PWO-092 — game-data introspector (pure text→rows; never sends).

Pure text -> structured rows, like ``state_parser``: no I/O, no daemon touch,
no live TWGS crawl, no send paths.

- **Option A (Accepted):** StarDock/shipyard/equipment listing buffers →
  Layer-B ``game_data`` row dicts (fixture/offline + opportunistic capture).
- **Passive current-ship ``I`` parse (LIVE · PR #471):**
  ``parse_current_ship_info`` → ``Session.observe_current_ship`` / status
  ``ship_type`` / ``current_ship``. Still no send — parses text already on
  screen from a human-issued ``I``.
- **Option B (HELD):** navigate/send to reach StarDock catalog screens for
  an active crawl. Distinct from both Option A and the passive ``I`` path.

``source`` always begins with ``introspected``. ``last_verified_ts`` is
omitted here — the persist layer stamps it on write.

PROVENANCE: tip fixtures under ``tests/fixtures/stardock_*.txt`` are
constructed listings (same caveat as archive); refine when live captures land.
"""

import re

_SHIPYARD_HEADER_RE = re.compile(r"^-=-=-\s+StarDock Shipyard - Ship Registration\s+-=-=-$")
_SHIPYARD_FOOTER_RE = re.compile(r"^-=-=-\s+End of Shipyard Listing\s+-=-=-$")

_CARGO_HOLD_HEADER_RE = re.compile(r"^-=-=-\s+StarDock Shipyard - Cargo Hold Upgrade\s+-=-=-$")
_CARGO_HOLD_FOOTER_RE = re.compile(r"^-=-=-\s+End of Cargo Hold Upgrade Quote\s+-=-=-$")

# The live per-hold credits quote inside a bracketed Cargo Hold Upgrade
# block, e.g. "Holds cost 1,468 credits each, for a total of 29,360
# credits to fill them all." Only the PER-HOLD number is captured -- an
# optional trailing "for a total of ..." clause is decorative
# confirmation math, not a separate field `tw2002_aiclient.game_data.CargoHoldRow`
# tracks.
_CARGO_HOLD_PRICE_RE = re.compile(r"[Hh]olds?\s+cost\s+(?P<cost>\d[\d,]*)\s+credits\s+each")

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
# Drive", not part of `tw2002_aiclient.game_data.TranswarpRow`).
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
    of dicts shaped like `tw2002_aiclient.game_data.ShipRow`'s fields (everything except
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


def parse_cargo_hold_price(
    rendered_text: str, *, source: str = "introspected: stardock_cargo_holds"
) -> "dict | None":
    """The live per-hold credits price StarDock quotes for expanding the
    CURRENT ship's cargo holds, or `None` when there's nothing safe to
    report -- no closed Cargo Hold Upgrade block on screen at all, or a
    closed block whose text doesn't contain a matching price line (e.g.
    a "you already carry the maximum number of holds" quote with no
    price to show). Absence is returned, NEVER a guessed/zero price --
    this is exactly the number `tw2002_aiclient.ship_upgrade_decision`'s
    `cost_per_hold` parameter feeds into the autopilot's upgrade-ROI
    math, so a wrong guess here risks a bad spend decision (see this
    module's docstring).

    Unlike `parse_shipyard_listing`'s multi-row ship catalog, this is a
    single scalar quote for the ship the player currently has in hand --
    see `tw2002_aiclient.game_data.persist_cargo_hold_price`'s docstring for why the
    persist layer accordingly keys this under one fixed singleton key
    rather than a name-keyed table row.

    Same stale-scrollback anchoring as every other parser in this
    module -- `_bracketed_lines` anchors to the LATEST closed Cargo Hold
    Upgrade block; if that block unusually contains more than one
    matching price line, the last one wins."""
    lines = _bracketed_lines(rendered_text, _CARGO_HOLD_HEADER_RE, _CARGO_HOLD_FOOTER_RE)
    cost = None
    for raw_line in lines:
        m = _CARGO_HOLD_PRICE_RE.search(raw_line)
        if m:
            cost = _to_int(m.group("cost"))  # keep overwriting -- last match wins
    if cost is None:
        return None
    return {"cost_per_hold": cost, "source": source}


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
    """Batch-parse a scanner catalog listing into `tw2002_aiclient.game_data.ScannerRow`-
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
    `tw2002_aiclient.game_data.TranswarpRow`-shaped dicts (`cost_credits`/`range_notes`/
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
    `tw2002_aiclient.game_data.ItemRow`-shaped dicts (`item_name`/`cost_credits`/
    `effect_notes`/`source`)."""
    rows = []
    for name, cost, notes in _parse_equip_rows(rendered_text, _ITEM_HEADER_RE, _ITEM_FOOTER_RE):
        row = {"item_name": name, "cost_credits": cost, "source": source}
        if notes:
            row["effect_notes"] = notes
        rows.append(row)
    return rows


# -- current-ship I-info (priority-engine row 2) ---------------------------
#
# Live `I` ship-info screens state the hull the player *has in hand* — not a
# shipyard catalog row. Labels below are captured from
# `tests/fixtures/ship_info_screen.txt` (live TWGS shape). Absence → None;
# never invent cost/shields/alignment from a screen that does not show them.

_SHIP_NAME_RE = re.compile(
    r"^[ \t]*Ship[ \t]+Name[ \t]*:[ \t]*(?P<name>\S.*\S|\S)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_SHIP_INFO_RE = re.compile(
    r"^[ \t]*Ship[ \t]+Info[ \t]*:[ \t]*(?P<info>\S.*\S|\S)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_SHIP_INFO_PORTED_KILLS_RE = re.compile(
    r"\s+Ported=\d+\s+Kills=\d+\s*$",
    re.IGNORECASE,
)
_TURNS_TO_WARP_RE = re.compile(
    r"^[ \t]*Turns[ \t]+to[ \t]+Warp[ \t]*:[ \t]*(?P<n>\d+)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_TOTAL_HOLDS_INFO_RE = re.compile(
    r"^[ \t]*Total[ \t]+Holds[ \t]*:[ \t]*(?P<total>\d[\d,]*)"
    r"[ \t]*-[ \t]*Empty[ \t]*=[ \t]*(?P<empty>\d[\d,]*)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_FIGHTERS_INFO_RE = re.compile(
    r"^[ \t]*Fighters[ \t]*:[ \t]*(?P<n>\d[\d,]*)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_current_ship_info(
    rendered_text: str, *, source: str = "introspected: ship_info"
) -> "dict | None":
    """Parse an ``I`` ship-info screen into a current-ship observation.

    Returns ``None`` when the screen does not state a ship type (the
    ``Ship Info`` line after stripping ``Ported=``/``Kills=``). Never invents
    catalog fields (cost, shields, alignment). ``source`` always begins with
    ``introspected``.
    """
    if not isinstance(rendered_text, str) or not rendered_text.strip():
        return None
    info_matches = list(_SHIP_INFO_RE.finditer(rendered_text))
    if not info_matches:
        return None
    info_raw = info_matches[-1].group("info").strip()
    ship_type = _SHIP_INFO_PORTED_KILLS_RE.sub("", info_raw).strip()
    if not ship_type:
        return None

    out: dict = {
        "ship_type": ship_type,
        "ship_info_raw": info_raw,
        "source": source,
    }
    name_matches = list(_SHIP_NAME_RE.finditer(rendered_text))
    if name_matches:
        out["ship_name"] = name_matches[-1].group("name").strip()
    warp_matches = list(_TURNS_TO_WARP_RE.finditer(rendered_text))
    if warp_matches:
        out["turns_per_warp"] = int(warp_matches[-1].group("n"))
    holds_matches = list(_TOTAL_HOLDS_INFO_RE.finditer(rendered_text))
    if holds_matches:
        m = holds_matches[-1]
        out["total_holds"] = _to_int(m.group("total"))
        out["empty_holds"] = _to_int(m.group("empty"))
    ftr_matches = list(_FIGHTERS_INFO_RE.finditer(rendered_text))
    if ftr_matches:
        out["fighters"] = _to_int(ftr_matches[-1].group("n"))
    return out
