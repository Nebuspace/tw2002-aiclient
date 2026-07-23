"""curses screens for tw2002-aiclient."""

from __future__ import annotations

import curses
import string

from . import adapters


def _safe_addstr(win, y, x, text, attr=curses.A_NORMAL):
    try:
        h, w = win.getmaxyx()
        if y < 0 or y >= h or x >= w:
            return
        win.addnstr(y, x, text, max(0, w - x - 1), attr)
    except curses.error:
        pass


def _footer(win, text):
    h, _w = win.getmaxyx()
    _safe_addstr(win, h - 1, 0, text, curses.A_DIM)


# ---------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------


def _launcher_selectable(rows):
    """Indices humans may confirm: active profiles + trailing Create row."""
    create_i = len(rows)
    return [i for i, row in enumerate(rows) if not row.get("retired")] + [create_i]


def _launcher_step(idx, rows, delta):
    """Move selection by delta, skipping retired (grey) rows."""
    selectable = _launcher_selectable(rows)
    if not selectable:
        return 0
    try:
        pos = selectable.index(idx)
    except ValueError:
        # Landed on retired (e.g. after refresh) — snap toward nearest active.
        pos = 0 if delta >= 0 else -1
    return selectable[(pos + delta) % len(selectable)]


def run_launcher(stdscr):
    """Return ('play', profile_name) | ('quit', None) | never returns create."""
    curses.curs_set(0)
    idx = 0
    status = ""
    while True:
        rows = adapters.list_launcher_rows()
        # Last row is always "+ Create new profile"
        create_i = len(rows)
        total = len(rows) + 1
        selectable = _launcher_selectable(rows)
        if idx not in selectable:
            idx = selectable[0] if selectable else 0
        idx = max(0, min(idx, total - 1))
        stdscr.erase()
        _safe_addstr(stdscr, 0, 0, " tw2002-aiclient", curses.A_BOLD)
        _safe_addstr(stdscr, 1, 0, " ─────────────────────────────")
        _safe_addstr(stdscr, 2, 0, "  ↑↓ select · Enter confirm · n new · q quit", curses.A_DIM)
        if status:
            _safe_addstr(stdscr, 3, 0, f"  {status}", curses.A_BOLD)
        base = 5
        for i, row in enumerate(rows):
            marker = "›" if i == idx else " "
            ap = "Autopilot ON " if row["autopilot"] else "Autopilot OFF"
            handle = row["handle"] or row["name"]
            retired = bool(row.get("retired"))
            tag = "  RETIRED" if retired else ""
            line = f"  {marker} {handle:<12} {row['server']:<22} {row['game_letter']}   {ap}{tag}"
            if retired:
                attr = curses.A_DIM
            elif i == idx:
                attr = curses.A_REVERSE
            else:
                attr = curses.A_NORMAL
            _safe_addstr(stdscr, base + i, 0, line, attr)
            if row.get("error"):
                _safe_addstr(stdscr, base + i, min(70, len(line) + 2), "!", curses.A_BOLD)
        create_attr = curses.A_REVERSE if idx == create_i else curses.A_NORMAL
        _safe_addstr(
            stdscr,
            base + create_i + (1 if rows else 0),
            0,
            f"  {'›' if idx == create_i else ' '} + Create new profile",
            create_attr,
        )
        _footer(stdscr, " tw2002-aiclient · ops CLI: ./tw  ·  spectator: ./tw spectate")
        stdscr.refresh()

        ch = stdscr.getch()
        if ch in (ord("q"), 27):
            return "quit", None
        if ch in (curses.KEY_UP, ord("k")):
            idx = _launcher_step(idx, rows, -1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            idx = _launcher_step(idx, rows, 1)
        elif ch in (ord("n"),):
            result = run_create_form(stdscr)
            if result == "created":
                status = "profile created"
                idx = 0
            elif result == "cancel":
                status = ""
        elif ch in (curses.KEY_ENTER, 10, 13):
            if idx == create_i:
                result = run_create_form(stdscr)
                if result == "created":
                    status = "profile created"
                    rows = adapters.list_launcher_rows()
                    # Prefer last active profile; fall back to Create.
                    active = [i for i, r in enumerate(rows) if not r.get("retired")]
                    idx = active[-1] if active else len(rows)
            else:
                if not rows:
                    status = "no profiles — create one"
                    continue
                if rows[idx].get("retired"):
                    status = "retired — unselectable"
                    continue
                return "play", rows[idx]["name"]


# ---------------------------------------------------------------------------
# Create profile form
# ---------------------------------------------------------------------------


_FORM_FIELDS = (
    ("name", "Profile id", "text"),
    ("server", "Server", "server"),
    ("game_letter", "Game letter", "text"),
    ("handle", "Handle", "text"),
    ("ship_name", "Ship (optional)", "text"),
    ("planet_name", "Planet (optional)", "text"),
    ("allow_register", "Allow register", "check"),
    ("autopilot", "Autopilot (Trainer)", "check"),
    ("password", "Password (optional)", "secret"),
)


def run_create_form(stdscr):
    curses.curs_set(0)
    server_keys = adapters.list_server_keys()
    values = {
        "name": "",
        "server": server_keys[0] if server_keys else "",
        "game_letter": "A",
        "handle": "",
        "ship_name": "",
        "planet_name": "",
        "allow_register": False,
        "autopilot": False,
        "password": "",
    }
    focus = 0
    server_idx = 0
    if values["server"] and values["server"] in server_keys:
        server_idx = server_keys.index(values["server"])
    editing = False
    edit_buf = ""
    error = ""

    while True:
        stdscr.erase()
        _safe_addstr(stdscr, 0, 0, " tw2002-aiclient — new profile", curses.A_BOLD)
        _safe_addstr(stdscr, 1, 0, " ↑↓ field · Space/Enter toggle · e edit text · s save · Esc cancel", curses.A_DIM)
        if error:
            _safe_addstr(stdscr, 2, 0, f"  ! {error}", curses.A_BOLD)

        for i, (key, label, kind) in enumerate(_FORM_FIELDS):
            y = 4 + i
            selected = i == focus
            attr = curses.A_REVERSE if selected and not editing else curses.A_NORMAL
            if kind == "check":
                mark = "[x]" if values[key] else "[ ]"
                line = f"  {label:<22} {mark}"
            elif kind == "server":
                if server_keys:
                    shown = adapters.server_label(server_keys[server_idx])
                else:
                    shown = "(no servers in catalog)"
                line = f"  {label:<22} {shown}"
            elif kind == "secret":
                shown = "*" * len(values[key]) if values[key] else "(none)"
                if editing and selected:
                    shown = "*" * len(edit_buf) + "_"
                line = f"  {label:<22} {shown}"
            else:
                shown = values[key]
                if editing and selected:
                    shown = edit_buf + "_"
                line = f"  {label:<22} {shown}"
            _safe_addstr(stdscr, y, 0, line, attr)

        _footer(stdscr, " saves to config/profiles.toml · password → secrets.json")
        stdscr.refresh()

        ch = stdscr.getch()
        key, label, kind = _FORM_FIELDS[focus]

        if editing:
            if ch in (27,):
                editing = False
                curses.curs_set(0)
            elif ch in (curses.KEY_ENTER, 10, 13):
                values[key] = edit_buf
                if key == "game_letter" and edit_buf:
                    values[key] = edit_buf.strip().upper()[:1]
                editing = False
                curses.curs_set(0)
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                edit_buf = edit_buf[:-1]
            elif 32 <= ch < 127:
                edit_buf += chr(ch)
            continue

        if ch in (27, ord("q")) and not editing:
            return "cancel"
        if ch in (curses.KEY_UP, ord("k")):
            focus = (focus - 1) % len(_FORM_FIELDS)
        elif ch in (curses.KEY_DOWN, ord("j")):
            focus = (focus + 1) % len(_FORM_FIELDS)
        elif ch in (ord("s"),):
            try:
                _save_form(values, server_keys, server_idx)
                return "created"
            except Exception as e:  # noqa: BLE001 — show in TUI
                error = str(e)
        elif kind == "check" and ch in (ord(" "), curses.KEY_ENTER, 10, 13):
            values[key] = not values[key]
        elif kind == "server" and ch in (curses.KEY_LEFT, ord("h")):
            if server_keys:
                server_idx = (server_idx - 1) % len(server_keys)
                values["server"] = server_keys[server_idx]
        elif kind == "server" and ch in (curses.KEY_RIGHT, ord("l"), curses.KEY_ENTER, 10, 13, ord(" ")):
            if server_keys:
                if ch in (curses.KEY_ENTER, 10, 13, ord(" ")):
                    server_idx = (server_idx + 1) % len(server_keys)
                else:
                    server_idx = (server_idx + 1) % len(server_keys)
                values["server"] = server_keys[server_idx]
        elif kind in ("text", "secret") and ch in (ord("e"), curses.KEY_ENTER, 10, 13):
            editing = True
            edit_buf = values[key]
            curses.curs_set(1)
        else:
            if editing:
                curses.curs_set(1)
            else:
                curses.curs_set(0)


def _save_form(values, server_keys, server_idx):
    name = (values.get("name") or "").strip()
    if not name:
        raise ValueError("profile id required")
    if not all(c in string.ascii_letters + string.digits + "_-" for c in name):
        raise ValueError("profile id: letters, digits, _- only")
    server = server_keys[server_idx] if server_keys else None
    if not server:
        raise ValueError("no server selected")
    game = (values.get("game_letter") or "").strip().upper()[:1]
    if not game or game not in string.ascii_uppercase:
        raise ValueError("game letter A–Z required")
    handle = (values.get("handle") or "").strip() or None
    allow_register = bool(values.get("allow_register"))
    if not handle and not allow_register:
        raise ValueError("handle required (or check Allow register)")
    adapters.create_profile(
        name,
        server=server,
        game_letter=game,
        handle=handle,
        ship_name=(values.get("ship_name") or "").strip() or None,
        planet_name=(values.get("planet_name") or "").strip() or None,
        allow_register=allow_register,
        autopilot=bool(values.get("autopilot")),
    )
    pw = values.get("password") or ""
    if pw:
        adapters.save_password(name, pw)


# ---------------------------------------------------------------------------
# Play (live panels + Autopilot toggle)
# ---------------------------------------------------------------------------


def _draw_panel_block(stdscr, y, x, lines, *, max_lines=8, attr=curses.A_NORMAL):
    for i, line in enumerate(lines[:max_lines]):
        _safe_addstr(stdscr, y + i, x, f"  {line}", attr)
    return min(len(lines), max_lines)


def run_play(stdscr, profile_name):
    curses.curs_set(0)
    status = "Ensuring session…"
    stdscr.erase()
    _safe_addstr(stdscr, 0, 0, " tw2002-aiclient — play", curses.A_BOLD)
    _safe_addstr(stdscr, 2, 0, f"  Profile   {profile_name}")
    _safe_addstr(stdscr, 4, 0, f"  {status}", curses.A_DIM)
    stdscr.refresh()

    boot = adapters.ensure_and_sync_autopilot(profile_name)
    status = boot.get("message") or ("ready" if boot.get("ok") else "ensure failed")
    stdscr.timeout(1000)  # refresh panels ~1Hz while idle

    while True:
        try:
            profile = adapters.load_profile(profile_name)
            ap_on = bool(profile.autopilot)
        except Exception as e:  # noqa: BLE001
            stdscr.timeout(-1)
            stdscr.erase()
            _safe_addstr(stdscr, 0, 0, f" profile error: {e}")
            stdscr.getch()
            return "launcher"

        live = adapters.poll_status(profile_name)
        panels = adapters.compose_play_panels(live, width=40)

        stdscr.erase()
        _safe_addstr(stdscr, 0, 0, " tw2002-aiclient — play", curses.A_BOLD)
        _safe_addstr(stdscr, 1, 0, f"  {profile.name} · {panels.get('mode', '?')}", curses.A_DIM)
        _safe_addstr(stdscr, 2, 0, f"  {panels.get('metrics', '')}", curses.A_BOLD)
        if panels.get("needs_attention"):
            _safe_addstr(stdscr, 3, 0, "  ! intervention needs attention", curses.A_BOLD)

        ap_label = "Autopilot ON " if ap_on else "Autopilot OFF"
        _safe_addstr(stdscr, 5, 0, f"  [{ap_label.strip()}]", curses.A_BOLD | curses.A_REVERSE)

        y = 7
        y += _draw_panel_block(stdscr, y, 0, panels.get("priorities") or [], max_lines=10)
        y += 1
        y += _draw_panel_block(stdscr, y, 0, panels.get("decisions") or [], max_lines=6)
        y += 1
        y += _draw_panel_block(stdscr, y, 0, panels.get("log") or [], max_lines=5)

        _safe_addstr(stdscr, y + 1, 0, "  a  toggle Autopilot · Esc/q  launcher", curses.A_DIM)
        _safe_addstr(stdscr, y + 2, 0, f"  {status}", curses.A_DIM)
        _footer(stdscr, " panels from tw status + spectate compose — AI does not pilot")
        stdscr.refresh()

        ch = stdscr.getch()
        if ch in (27, ord("q")):
            stdscr.timeout(-1)
            return "launcher"
        if ch in (ord("a"), ord("A"), ord(" ")):
            try:
                result = adapters.toggle_autopilot_and_sync(profile_name)
                status = result.get("message") or "toggled"
            except Exception as e:  # noqa: BLE001
                status = f"toggle failed: {e}"
        # ch == -1 → timeout refresh; any other key ignored
