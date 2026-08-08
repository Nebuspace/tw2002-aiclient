"""Always-on five-row best-chain sector bubbles (WO-PLAY-CHAIN-BUBBLE-VIZ).

Pure strings only — no curses, no discovery imports, never raises on hostile
shapes. Semantics ported from pre-rebirth ``4a11a36:twclient/spectate_layout.py``
(``compose_chain_bubbles``) plus the port-only filter from ``af4c230``.

WO-FIX-CHAIN-BUBBLES-ASCII-UNICODE-LEAK: box / connector / empty / star glyphs
switch on the same ``unicode_ok()`` flag ``draw.py`` uses (``TW2002_ASCII=1``),
with ASCII twins matching ``draw.THIN_ASCII`` / ``DOUBLE_ASCII`` and
``chains.EMPTY_ASCII``.
"""

from __future__ import annotations

from tw2002_aiclient.cockpit.draw import (
    DOUBLE_ASCII,
    DOUBLE_UNICODE,
    THIN_ASCII,
    THIN_UNICODE,
    unicode_ok as draw_unicode_ok,
)

__all__ = [
    "CHAIN_VIZ_H",
    "chain_bubble_sectors",
    "compose_chain_bubbles",
    "filter_port_only_sectors",
]

CHAIN_VIZ_H = 5
_CHAIN_CONNECTOR_U = DOUBLE_UNICODE["h"] * 5
_CHAIN_CONNECTOR_A = DOUBLE_ASCII["h"] * 5
_CHAIN_EMPTY_PLACEHOLDER_U = "○ ○  no trade loop yet"
_CHAIN_EMPTY_PLACEHOLDER_A = "o o  no trade loop yet"
_STAR_U = "★"
_STAR_A = "*"
_ELLIPSIS_U = "…"
_ELLIPSIS_A = "..."


def chain_bubble_sectors(chain: object) -> list[int]:
    """Unique hop-order sectors for bubble art (drop closed-cycle repeat)."""
    try:
        if chain is None:
            return []
        if hasattr(chain, "sectors"):
            sectors = list(getattr(chain, "sectors", None) or ())
        elif isinstance(chain, dict):
            sectors = list(chain.get("sectors") or ())
        else:
            return []
        if len(sectors) >= 2 and sectors[0] == sectors[-1]:
            sectors = sectors[:-1]
        out: list[int] = []
        for sid in sectors:
            try:
                out.append(int(sid))
            except (TypeError, ValueError):
                continue
        return out
    except Exception:  # noqa: BLE001 -- hostile shape → empty art
        return []


def filter_port_only_sectors(sectors: object, known_ports: object) -> list[int]:
    """Keep hop order; drop non-port sector ids. ``None`` known_ports = no filter."""
    try:
        seq = list(sectors) if sectors is not None else []
    except Exception:  # noqa: BLE001
        return []
    if known_ports is None:
        out: list[int] = []
        for sid in seq:
            try:
                out.append(int(sid))
            except (TypeError, ValueError):
                continue
        return out
    allow: set[int] = set()
    try:
        for p in known_ports:
            try:
                allow.add(int(p))
            except (TypeError, ValueError):
                continue
    except Exception:  # noqa: BLE001
        return []
    out = []
    for sid in seq:
        try:
            sid_i = int(sid)
        except (TypeError, ValueError):
            continue
        if sid_i in allow:
            out.append(sid_i)
    return out


def _bubble_inner_w(sectors: list[int]) -> int:
    widest = max((len(str(s)) for s in sectors), default=3)
    return max(4, widest)


def _pad_center(text: str, width: int) -> str:
    text = str(text)[:width]
    pad = width - len(text)
    left = pad // 2
    return (" " * left) + text + (" " * (pad - left))


def _center_block(lines: list[str], width: int, height: int) -> list[str]:
    try:
        width = max(1, int(width))
    except (TypeError, ValueError):
        width = 1
    try:
        height = max(1, int(height))
    except (TypeError, ValueError):
        height = 1
    trimmed = [(ln or "")[:width] for ln in lines]
    while len(trimmed) < height:
        trimmed.append("")
    trimmed = trimmed[:height]
    out = []
    for ln in trimmed:
        pad = max(0, width - len(ln))
        left = pad // 2
        out.append((" " * left) + ln + (" " * (pad - left)))
    return out


def _resolve_unicode_ok(unicode_ok: object) -> bool:
    """``None`` → ``draw.unicode_ok()``; otherwise coerce like sibling composers."""
    if unicode_ok is None:
        return draw_unicode_ok()
    return bool(unicode_ok)


def compose_chain_bubbles(
    chain: object,
    *,
    current_sector: object = None,
    port_classes: object = None,
    width: object = 82,
    active_sector: object = None,
    known_ports: object = None,
    caption: object = None,
    unicode_ok: object = None,
) -> list[str]:
    """Return exactly ``CHAIN_VIZ_H`` centered lines. Never raises.

    ``caption`` (WO-CHAIN-BUBBLE-PAIR-FALLBACK): optional short label under
    the bubbles when the operator is not on a painted sector — used to mark
    an unpriced class-pair fallback without inventing margin chrome.

    ``unicode_ok`` defaults to ``draw.unicode_ok()`` (``TW2002_ASCII=1``) so
    the PTY / env path matches every other chrome surface; callers that pass
    an explicit flag keep unit-test control.
    """
    try:
        uok = _resolve_unicode_ok(unicode_ok)
        thin = THIN_UNICODE if uok else THIN_ASCII
        conn = _CHAIN_CONNECTOR_U if uok else _CHAIN_CONNECTOR_A
        empty_ph = (
            _CHAIN_EMPTY_PLACEHOLDER_U if uok else _CHAIN_EMPTY_PLACEHOLDER_A
        )
        star_glyph = _STAR_U if uok else _STAR_A
        ellipsis = _ELLIPSIS_U if uok else _ELLIPSIS_A
        try:
            width_i = max(8, int(width))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            width_i = 82
        classes: dict = port_classes if isinstance(port_classes, dict) else {}
        sectors = filter_port_only_sectors(chain_bubble_sectors(chain), known_ports)
        if not sectors:
            return _center_block([empty_ph], width_i, CHAIN_VIZ_H)

        try:
            cur = int(current_sector) if current_sector is not None else None  # type: ignore[arg-type]
        except (TypeError, ValueError):
            cur = None
        if active_sector is not None and cur is None:
            try:
                cur = int(active_sector)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                cur = None

        inner = _bubble_inner_w(sectors)
        bubble_w = inner + 2
        conn_w = len(conn)

        def _one_bubble(sid: int) -> tuple[str, str, str, str]:
            cls = classes.get(sid)
            if cls is None or cls == "":
                cls = "?"
            cls = str(cls)[:inner]
            top = thin["tl"] + (thin["h"] * inner) + thin["tr"]
            mid_sec = thin["v"] + _pad_center(str(sid), inner) + thin["v"]
            mid_cls = thin["v"] + _pad_center(cls, inner) + thin["v"]
            bot = thin["bl"] + (thin["h"] * inner) + thin["br"]
            return top, mid_sec, mid_cls, bot

        def _fit_count(n: int, truncated: bool) -> int:
            art = n * bubble_w + max(0, n - 1) * conn_w
            if truncated:
                art += 1 + len(f"{ellipsis} {len(sectors)}h")
            return art

        show_n = len(sectors)
        truncated = False
        while show_n > 1 and _fit_count(show_n, truncated=True) > width_i:
            show_n -= 1
            truncated = True
        if show_n < len(sectors):
            truncated = True
        if _fit_count(show_n, truncated=truncated) > width_i:
            show_n = 1
            truncated = len(sectors) > 1

        shown = sectors[:show_n]
        tops: list[str] = []
        mids_s: list[str] = []
        mids_c: list[str] = []
        bots: list[str] = []
        stars: list[str] = []
        for i, sid in enumerate(shown):
            t, ms, mc, b = _one_bubble(sid)
            if i:
                tops.append(" " * conn_w)
                mids_s.append(conn)
                mids_c.append(" " * conn_w)
                bots.append(" " * conn_w)
                stars.append(" " * conn_w)
            tops.append(t)
            mids_s.append(ms)
            mids_c.append(mc)
            bots.append(b)
            stars.append(
                _pad_center(
                    star_glyph if cur is not None and sid == cur else " ",
                    bubble_w,
                )
            )

        top_ln = "".join(tops)
        mid_s_ln = "".join(mids_s)
        mid_c_ln = "".join(mids_c)
        bot_ln = "".join(bots)
        star_ln = "".join(stars)
        if truncated:
            suffix = f" {ellipsis} {len(sectors)}h"
            mid_s_ln = mid_s_ln + suffix
            pad = len(suffix)
            top_ln = top_ln + (" " * pad)
            mid_c_ln = mid_c_ln + (" " * pad)
            bot_ln = bot_ln + (" " * pad)
            star_ln = star_ln + (" " * pad)

        # Honest "class pair" chrome: only when no current-sector star is
        # painted (★/* wins); never invents credits/turn.
        if caption and star_glyph not in star_ln:
            try:
                cap = str(caption).strip()
            except Exception:  # noqa: BLE001
                cap = ""
            if cap:
                star_ln = _pad_center(cap[: max(1, len(star_ln) or width_i)], max(len(star_ln), 1))

        return _center_block(
            [top_ln, mid_s_ln, mid_c_ln, bot_ln, star_ln], width_i, CHAIN_VIZ_H
        )
    except Exception:  # noqa: BLE001 -- never raise to the draw path
        uok = True
        try:
            uok = _resolve_unicode_ok(unicode_ok)
        except Exception:  # noqa: BLE001
            uok = True
        empty_ph = (
            _CHAIN_EMPTY_PLACEHOLDER_U if uok else _CHAIN_EMPTY_PLACEHOLDER_A
        )
        return _center_block([empty_ph], 82, CHAIN_VIZ_H)
