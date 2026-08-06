"""``tw players next`` — rotation selector CLI (WO-BUILD-PLAYER-ROTATION-SELECTOR).

Read-only: prints the next profile name (or an honest empty message). Never
opens the session socket, never logs in, never auto-switches. Lives outside
``session/cli.py`` for the same line-cap reason as ``catalog_cli`` / ``rules.cli``.
"""

from __future__ import annotations

import argparse
import sys

from tw2002_aiclient.session import player_bank

__all__ = ["add_players_parsers", "cmd_players_next"]


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


def add_players_parsers(sub: argparse._SubParsersAction) -> None:
    """Register ``tw players next`` under the top-level ``players`` verb."""
    sp_players = sub.add_parser(
        "players",
        help="player-bank rotation helpers (metadata only — never logs in)",
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
