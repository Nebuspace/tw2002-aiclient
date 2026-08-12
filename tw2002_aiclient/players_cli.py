"""``tw players`` — player-bank CLI (rotation next / rotate + list + add).

Read-only metadata for next/rotate/list: never opens the session socket, never
logs in, never auto-switches. ``add`` writes a non-secret profile section only
(``credentials.create_profile``). Lives outside ``session/cli.py`` for the same
line-cap reason as ``catalog_cli`` / ``rules.cli``.
"""

from __future__ import annotations

import argparse
import sys

from tw2002_aiclient.screens import BANK_EMPTY_LINE, BOUNDARY_LINE_1, BOUNDARY_LINE_2
from tw2002_aiclient.session import player_bank

__all__ = [
    "add_players_parsers",
    "cmd_players_add",
    "cmd_players_list",
    "cmd_players_next",
    "cmd_players_rotate",
]

_ROTATE_REASON_TEXT = {
    "empty_bank": "empty bank",
    "none_eligible": "all cooling down, or only broken profiles",
}


def cmd_players_next(args: argparse.Namespace) -> int:
    """Print the next rotation candidate profile name; exit 1 if none."""
    try:
        rows = player_bank.list_players()
    except player_bank.BankUnreadable as exc:
        print(f"player bank unreadable ({exc.cause}): {exc.reason}", file=sys.stderr)
        return 2
    cooldown = float(getattr(args, "cooldown_hours", player_bank.DEFAULT_ROTATION_COOLDOWN_HOURS))
    name = player_bank.next_player(rows, cooldown_hours=cooldown)
    if name is None:
        print("no eligible player (empty bank, all cooling down, or only broken profiles)")
        return 1
    print(name)
    return 0


def cmd_players_rotate(args: argparse.Namespace) -> int:
    """Print the rotation driver's decision: who's due, and why. Never logs in.

    Same round-robin-by-oldest policy as ``tw players next``
    (:func:`player_bank.advance_rotation` wraps :func:`player_bank.next_player`
    unchanged) — this verb only reports the driver's reasoning alongside it.
    """
    try:
        rows = player_bank.list_players()
    except player_bank.BankUnreadable as exc:
        print(f"player bank unreadable ({exc.cause}): {exc.reason}", file=sys.stderr)
        return 2
    cooldown = float(getattr(args, "cooldown_hours", player_bank.DEFAULT_ROTATION_COOLDOWN_HOURS))
    decision = player_bank.advance_rotation(rows, cooldown_hours=cooldown)
    if decision.name is None:
        reason_text = _ROTATE_REASON_TEXT.get(decision.reason, decision.reason)
        print(f"no eligible player ({reason_text})")
        return 1
    print(decision.name)
    return 0


def cmd_players_list(args: argparse.Namespace) -> int:
    """Print bank rows + no-collusion boundary lines (TUI twin). Never logs in."""
    # Boundary first — same strings as BankViewScreen (canon residual).
    print(BOUNDARY_LINE_1)
    print(BOUNDARY_LINE_2)
    try:
        rows = player_bank.list_players()
    except player_bank.BankUnreadable as exc:
        print(f"player bank unreadable ({exc.cause}): {exc.reason}", file=sys.stderr)
        return 2
    if not rows:
        print(BANK_EMPTY_LINE)
        return 0
    cooldown = float(getattr(args, "cooldown_hours", player_bank.DEFAULT_ROTATION_COOLDOWN_HOURS))
    due = player_bank.next_player(rows, cooldown_hours=cooldown)
    # Column layout mirrors BankViewScreen header/rows.
    print(f"{'name':<16} {'handle':<16} {'host':<24} {'game':<3} {'last_played':<21} turns")
    for entry in rows:
        name = entry.get("name", "?")
        err = entry.get("error")
        if err:
            name = f"{name}!"
        marker = "→ " if entry.get("name") == due else "  "
        print(
            f"{marker}{name:<16} "
            f"{entry.get('handle', '?'):<16} "
            f"{entry.get('host', '?'):<24} "
            f"{entry.get('game_letter', '?'):<3} "
            f"{entry.get('last_played', 'never'):<21} "
            f"{entry.get('turns_state', '-')}"
        )
        if err:
            print(f"  error: {err}")
    return 0


def cmd_players_add(args: argparse.Namespace) -> int:
    """Append a non-secret profile section via ``credentials.create_profile``."""
    from tw2002_aiclient.session import credentials

    try:
        section = credentials.create_profile(
            server=args.server,
            game_letter=args.game_letter,
            handle=args.handle,
            name=getattr(args, "profile", None),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(section)
    return 0


def add_players_parsers(sub: argparse._SubParsersAction) -> None:
    """Register ``tw players next`` / ``list`` / ``rotate`` / ``add``."""
    sp_players = sub.add_parser(
        "players",
        help="player-bank helpers (metadata only - never logs in)",
    )
    players_sub = sp_players.add_subparsers(dest="players_verb")
    sp_next = players_sub.add_parser(
        "next",
        help="print the next profile name under the rotation window (read-only)",
    )
    sp_next.add_argument(
        "--cooldown-hours",
        type=float,
        default=player_bank.DEFAULT_ROTATION_COOLDOWN_HOURS,
        metavar="H",
        help=f"skip last_played within this many hours (default {player_bank.DEFAULT_ROTATION_COOLDOWN_HOURS:g})",
    )
    sp_next.set_defaults(func=cmd_players_next)

    sp_rotate = players_sub.add_parser(
        "rotate",
        help="print the rotation driver's decision — who's due, and why (read-only)",
    )
    sp_rotate.add_argument(
        "--cooldown-hours",
        type=float,
        default=player_bank.DEFAULT_ROTATION_COOLDOWN_HOURS,
        metavar="H",
        help=f"skip last_played within this many hours (default {player_bank.DEFAULT_ROTATION_COOLDOWN_HOURS:g})",
    )
    sp_rotate.set_defaults(func=cmd_players_rotate)

    sp_list = players_sub.add_parser(
        "list",
        help="list bank profiles with no-collusion boundary lines (read-only)",
    )
    sp_list.add_argument(
        "--cooldown-hours",
        type=float,
        default=player_bank.DEFAULT_ROTATION_COOLDOWN_HOURS,
        metavar="H",
        help=f"mark the rotation-due row using this cooldown window (default {player_bank.DEFAULT_ROTATION_COOLDOWN_HOURS:g})",
    )
    sp_list.set_defaults(func=cmd_players_list)

    sp_add = players_sub.add_parser(
        "add",
        help="append a non-secret profile section (metadata only — never logs in)",
    )
    sp_add.add_argument(
        "--server",
        required=True,
        metavar="KEY",
        help="catalog server key (must exist in servers.toml)",
    )
    sp_add.add_argument(
        "--game-letter",
        dest="game_letter",
        required=True,
        metavar="L",
        help="single game letter (A-Z)",
    )
    sp_add.add_argument(
        "--handle",
        required=True,
        help="in-game handle for the profile",
    )
    sp_add.add_argument(
        "--profile",
        help="profile section name (default: derived from handle)",
    )
    sp_add.set_defaults(func=cmd_players_add)
