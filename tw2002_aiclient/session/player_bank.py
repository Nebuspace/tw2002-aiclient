"""Player bank — metadata-only rotation bookkeeping (WO-P1-015 stub).

Tracks which characters exist (linked to profile names) plus ``last_played`` /
``turns_state``. Passwords are never stored here — structurally absent.
The rotation *driver* is out of scope for this wave.

The honesty contract (WO-AUDIT-PLAYER-BANK-STORE-HONESTY)
---------------------------------------------------------
"There is no bank" and "the bank could not be read" are different facts and an
operator can act on only one of them, so they never render alike. Before this
WO, *nine* distinct conditions returned the identical reassuring
``{"version": 1, "players": []}``, and exactly one of them had established it:

1. a bank that was never written — the one real negative
2. a permission denial on the file itself
3. a permission denial on the directory *containing* it (see the
   ``Path.exists()`` note below — this one collapsed at the very first line,
   before any handler got a turn)
4. a directory standing where the file should be
5. a dangling symlink
6. corrupt JSON
7. a non-object top level
8. an absent ``players`` key
9. a ``players`` key that is not a list

A tenth condition did not collapse at all — it crashed. A bank that is not
valid UTF-8 raises ``UnicodeDecodeError``, which subclasses ``ValueError``,
not ``OSError``, and is a *different* ``ValueError`` subclass from
``json.JSONDecodeError``, so the old ``except (OSError, json.JSONDecodeError)``
never caught it. It escaped through ``list_players()`` and painted a Python
traceback over the launcher's bank view.

All of those now raise :class:`BankUnreadable` — carrying a coarse
machine-branchable ``cause`` plus a specific operator-facing ``reason`` —
except (1) and (5), which stay one answer on purpose: a bank never written and
a symlink whose target was never written both mean there is no bank content
that went unread. Only that genuine absence returns an empty bank, because
only that condition established the negative.

Precedent: this store is **one file**, so an unreadable bank is a *total*
failure and the reader aborts — ``cli.py``'s ``cmd_menumap`` shape, which
raises out of the store read and lets the surface render the error. It is
deliberately **not** the in-band ``status="partial"`` shape of
``loops/store.py``: that store is a directory of mutually independent
documents, where one corrupt file among twenty leaves nineteen real rows worth
listing (``loops/store.py`` records this exact asymmetry in-module). Here there
is no uncontaminated partial listing to give — see :func:`list_players`.

``Path.exists()`` is gone on purpose. It answers ``False`` when the *parent
directory* is unreadable, which made "no bank" and "cannot reach the bank"
indistinguishable at the very first line, before any of the ``try`` below could
reason about it. Opening the file and classifying the error is what keeps that
distinction: the same file under an unreadable directory raises
``PermissionError``, not ``FileNotFoundError`` (proven by execution in
``tests/test_player_bank.py``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from tw2002_aiclient.session import credentials

# session/player_bank.py → session → tw2002_aiclient → repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = PROJECT_ROOT / "state"
BANK_PATH = STATE_DIR / "player_bank.json"

# Honest empty-rotation sentinels (never fabricate a timestamp).
NEVER = "never"
TURNS_UNKNOWN = "-"

# Why the bank could not be read. Coarse enough for a caller to branch on,
# distinct where the operator's next action differs: fixing permissions,
# replacing a wrong path, and repairing a damaged document are three different
# jobs, and the specific ``reason`` narrows each one further.
CAUSE_DENIED = "denied"  # we were not allowed to look
CAUSE_UNUSABLE = "unusable"  # the path is not a readable file (e.g. a directory)
CAUSE_CORRUPT = "corrupt"  # we looked, and the bytes are not a readable document
CAUSE_MALFORMED = "malformed"  # it parsed, and it is not a bank


class BankUnreadable(Exception):
    """The bank exists (or may exist) but could not be read.

    Never raised for a bank that is genuinely absent — that is a real negative
    and the one case entitled to report zero players.

    ``cause`` is one of the ``CAUSE_*`` constants; ``reason`` is the specific,
    operator-actionable detail ("Permission denied", "invalid JSON (Expecting
    property name enclosed in double quotes, line 1)"). A caller rendering this
    must not also report a count: nothing here was read.
    """

    def __init__(self, cause: str, reason: str, path: object = None) -> None:
        self.cause = cause
        self.reason = reason
        self.path = str(path if path is not None else BANK_PATH)
        super().__init__(f"{reason} ({self.path})")


def _load_bank_raw() -> dict:
    """Return the parsed bank document, or raise :class:`BankUnreadable`.

    The empty bank is returned for exactly one condition — ``FileNotFoundError``,
    i.e. no bank has ever been written. A dangling symlink lands here too, and
    honestly so: its target does not exist, so there is no bank content that
    went unread.

    Every ``except`` below names a condition that used to be indistinguishable
    from that genuine negative. ``PermissionError`` is caught ahead of the bare
    ``OSError`` because "I was not allowed to look" and "I looked and the path
    is unusable" are different situations sharing one exception base — the same
    collapse this function exists to prevent, one level down.
    """
    try:
        with open(BANK_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        # The only real negative: nothing has ever written a bank.
        return {"version": 1, "players": []}
    except PermissionError as exc:
        # Covers both the file itself and an unreadable parent directory —
        # the case `Path.exists()` used to swallow into "no bank". The reason
        # must name WHICH object to fix: the message carries BANK_PATH, so a
        # directory-level denial reported as a bare "Permission denied" sends
        # the operator to chmod a file that is already readable.
        denied = exc.strerror or "permission denied"
        parent = Path(BANK_PATH).parent
        # X_OK is the traversal bit — precisely what stops us reaching the
        # file. A directory can be search-only (0o111) and the read succeeds.
        if not os.access(parent, os.X_OK):
            denied = f"{denied} on the containing directory: {parent}"
        raise BankUnreadable(CAUSE_DENIED, denied) from exc
    except OSError as exc:
        # IsADirectoryError, ELOOP, a stale mount... reason carries which.
        raise BankUnreadable(CAUSE_UNUSABLE, exc.strerror or "could not be opened") from exc
    except UnicodeDecodeError as exc:
        # Not an OSError and not a JSONDecodeError — the old except clause
        # missed it entirely and it crashed the launcher.
        raise BankUnreadable(CAUSE_CORRUPT, "not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise BankUnreadable(
            CAUSE_CORRUPT, f"invalid JSON ({exc.msg}, line {exc.lineno})"
        ) from exc

    if not isinstance(data, dict):
        raise BankUnreadable(
            CAUSE_MALFORMED,
            f"top-level shape is {type(data).__name__}, expected an object",
        )
    players = data.get("players")
    if players is None:
        # A document with no `players` key does not say "zero players"; it says
        # nothing about players at all. Reporting it as empty would be a claim
        # about contents this file never carried.
        raise BankUnreadable(CAUSE_MALFORMED, "no 'players' list")
    if not isinstance(players, list):
        raise BankUnreadable(
            CAUSE_MALFORMED,
            f"'players' is {type(players).__name__}, expected a list",
        )
    return data


def list_players() -> list[dict[str, str]]:
    """Return metadata-only bank rows for the launcher touchpoint.

    Shape matches ``tw players list`` columns: name, handle, host, game_letter,
    last_played, turns_state. Missing rotation history uses ``never`` / ``-``.

    Raises :class:`BankUnreadable` when the bank could not be read, rather than
    returning a shorter list. There is no honest partial listing to fall back
    on: *every* row this function emits carries ``last_played`` and
    ``turns_state``, both read from the bank, so with the bank unread each
    profile row would render ``never`` / ``-`` — a positive claim about
    rotation history taken from a file nobody managed to read — and every
    bank-only row would silently vanish. Callers render the failure instead of
    a list; see ``app.py``'s bank view.
    """
    bank = _load_bank_raw()
    by_name = {
        str(p.get("name")): p
        for p in bank.get("players", [])
        if isinstance(p, dict) and p.get("name")
    }
    rows: list[dict[str, str]] = []
    for summary in credentials.list_profile_summaries():
        name = str(summary.get("name") or "")
        if not name or summary.get("error"):
            continue
        stored = by_name.get(name, {})
        last = stored.get("last_played")
        if last is None or last == "":
            last_played = NEVER
        else:
            last_played = str(last)[:21]
        turns = stored.get("turns_state")
        turns_state = TURNS_UNKNOWN if turns in (None, "") else str(turns)
        rows.append(
            {
                "name": name,
                "handle": str(summary.get("handle") or "?"),
                "host": str(summary.get("host") or summary.get("server") or "?"),
                "game_letter": str(summary.get("game_letter") or "?"),
                "last_played": last_played,
                "turns_state": turns_state,
            }
        )
    # Bank-only entries (profile removed) still surface as diagnosable rows.
    known = {r["name"] for r in rows}
    for name, stored in by_name.items():
        if name in known:
            continue
        last = stored.get("last_played")
        last_played = NEVER if last in (None, "") else str(last)[:21]
        turns = stored.get("turns_state")
        turns_state = TURNS_UNKNOWN if turns in (None, "") else str(turns)
        rows.append(
            {
                "name": name,
                "handle": str(stored.get("handle") or "?"),
                "host": str(stored.get("host") or "?"),
                "game_letter": str(stored.get("game_letter") or "?"),
                "last_played": last_played,
                "turns_state": turns_state,
            }
        )
    return rows
