"""Player bank — metadata-only rotation bookkeeping (WO-P1-015 stub).

Tracks which characters exist (linked to profile names) plus ``last_played`` /
``turns_state``. Passwords are never stored here — structurally absent.
:func:`next_player` is the read-only rotation *selector* (``tw players next``);
:func:`advance_rotation` is the rotation *driver* (``tw players rotate``) —
decides whose turn is due, still never auto-logs-in or auto-switches.

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

That total-failure rule is about a STORE that could not be read, and it must
not be over-read as licence to drop individual rows. A profile the credential
store flagged as broken is the opposite situation: the bank was read, so that
row's rotation columns are real and it is listed, carrying its error
(WO-PLAYERBANK-LISTING-HONESTY). Dropping it was the module's own thesis
inverted one level down — "no such character" and "that character is broken"
rendered alike. :func:`list_players` carries the full reasoning.

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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tw2002_aiclient.session import credentials

# session/player_bank.py → session → tw2002_aiclient → repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = PROJECT_ROOT / "state"
BANK_PATH = STATE_DIR / "player_bank.json"

# Honest empty-rotation sentinels (never fabricate a timestamp).
NEVER = "never"
TURNS_UNKNOWN = "-"

# The launcher's bank table gives `last_played` exactly this many columns
# (`screens.py`'s `f"{entry.get('last_played', 'never'):<21}"`, which pads but
# does not clip), so a longer stored value must be cut here or the `turns`
# column slides right. Cutting is a layout necessity; cutting SILENTLY was the
# defect (WO-PLAYERBANK-LISTING-HONESTY) -- `2026-07-23T12:00:00+00:00` came
# out as `2026-07-23T12:00:00+0`, which reads as a complete fractional-second
# stamp, and any two stamps differing only past the cut rendered identical.
#
# TRUNCATED is what says a cut happened. It is deliberately NOT one of the
# unknown markers above: `never`/`-`/`?` all mean "this value is absent", and
# this value is present, read, and only partly shown -- a different fact with a
# different next action (widen the view / read the file). `…` is this
# codebase's existing "there is more" mark (`screens.py`'s `Exploring…`,
# `app.py`'s `Ensuring session…`), one cell wide, and cannot be mistaken for
# timestamp content, so a marked value still fits the column exactly.
LAST_PLAYED_WIDTH = 21
TRUNCATED = "…"

# Default window for :func:`next_player` / :func:`advance_rotation` — skip
# anyone whose last_played falls inside this many hours of ``now``. Shared by
# both the selector and the driver; a daemon-side auto-login/auto-switch
# consumer of the driver's decision remains a separate wave.
DEFAULT_ROTATION_COOLDOWN_HOURS = 24.0

# Why the bank could not be read. Coarse enough for a caller to branch on,
# distinct where the operator's next action differs: fixing permissions,
# replacing a wrong path, and repairing a damaged document are three different
# jobs, and the specific ``reason`` narrows each one further.
CAUSE_DENIED = "denied"  # we were not allowed to look
CAUSE_UNUSABLE = "unusable"  # the path is not a readable file (e.g. a directory)
CAUSE_CORRUPT = "corrupt"  # we looked, and the bytes are not a readable document
CAUSE_MALFORMED = "malformed"  # it parsed, and it is not a bank


class BankUnreadable(Exception):
    """A store this listing is built from could not be read.

    Usually the bank itself. It is also raised for a `profiles.toml` /
    `servers.toml` that could not be read, because those rows are half of
    the listing and dropping them silently is the same lie one file over
    (WO-AUDIT-CREDENTIALS-LAUNCHER-CRASH); `path` names which store failed
    and `reason` leads with its file name, so the surface's "bank could not
    be read" headline is corrected by the line under it.

    Never raised for a store that is genuinely absent — that is a real
    negative and the one case entitled to report zero players.

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


def _rotation_columns(stored: dict) -> tuple[str, str]:
    """The two bank-sourced columns for one row: ``(last_played, turns_state)``.

    ONE helper rather than a copy in each of :func:`list_players`' two loops.
    Both loops cut ``last_played`` to the launcher's column width, so before
    this there were two independent copies of a rule that has to agree -- and
    a fix applied to one of them would have left the other still lying, which
    is precisely the drift the sibling dedupe passes (WO-AUDIT-GLYPH-TABLE-
    DEDUPE, WO-AUDIT-SAFE-ADDSTR-DEDUPE) exist to close.

    Absent history stays ``never`` / ``-`` -- never a fabricated timestamp. A
    present value too wide for the column is cut and MARKED (see
    ``TRUNCATED``); it is never cut in silence, because a silently cut value
    presents itself as the whole one.
    """
    last = stored.get("last_played")
    if last in (None, ""):
        last_played = NEVER
    else:
        text = str(last)
        if len(text) <= LAST_PLAYED_WIDTH:
            last_played = text
        else:
            last_played = text[: LAST_PLAYED_WIDTH - len(TRUNCATED)] + TRUNCATED
    turns = stored.get("turns_state")
    turns_state = TURNS_UNKNOWN if turns in (None, "") else str(turns)
    return last_played, turns_state


def _classify_last_played(raw: object) -> tuple[str, datetime | None]:
    """Return ``(kind, instant)`` for rotation ranking.

    * ``("never", None)`` — honest empty sentinel / blank.
    * ``("ok", aware_dt)`` — parseable ISO-ish stamp (``Z`` or offset).
    * ``("unknown", None)`` — truncated display cut, junk, or naive/unparseable.
    """
    text = str(raw or "").strip()
    if not text or text == NEVER:
        return "never", None
    if text.endswith(TRUNCATED):
        return "unknown", None
    candidate = text.replace("Z", "+00:00") if text.endswith("Z") else text
    try:
        instant = datetime.fromisoformat(candidate)
    except ValueError:
        return "unknown", None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return "ok", instant.astimezone(timezone.utc)


def next_player(
    rows: list[dict[str, str]] | None,
    *,
    cooldown_hours: float = DEFAULT_ROTATION_COOLDOWN_HOURS,
    now: datetime | None = None,
) -> str | None:
    """Pick the next profile name to play — read-only selection, never logs in.

    Window gate: rows whose ``last_played`` is within ``cooldown_hours`` of
    ``now`` are skipped. Among the rest, prefer ``never``, then oldest stamp,
    then name (stable). Broken profiles (``error`` key) are never selected.
    Truncated / unparseable stamps fail closed when a cooldown is active.
    Empty / non-list input → ``None``. Does not raise.
    """
    if not isinstance(rows, list) or not rows:
        return None
    try:
        cooldown = float(cooldown_hours)
    except (TypeError, ValueError):
        cooldown = DEFAULT_ROTATION_COOLDOWN_HOURS
    if cooldown < 0:
        cooldown = 0.0
    clock = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    else:
        clock = clock.astimezone(timezone.utc)
    cutoff = clock - timedelta(hours=cooldown)

    best_name: str | None = None
    best_key: tuple | None = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("error"):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        kind, instant = _classify_last_played(row.get("last_played"))
        if kind == "never":
            key: tuple = (0, name)
        elif kind == "ok" and instant is not None:
            if cooldown > 0 and instant > cutoff:
                continue
            key = (1, instant.timestamp(), name)
        else:
            # unknown — cannot prove out-of-window; skip when cooling down
            if cooldown > 0:
                continue
            key = (2, name)
        if best_key is None or key < best_key:
            best_key = key
            best_name = name
    return best_name


class RotationDecision:
    """One rotation-driver verdict: who's due, and why — never an action.

    ``name`` is ``None`` when nobody is due; ``reason`` is ``"due"``,
    ``"empty_bank"`` (no rows at all), or ``"none_eligible"`` (every row is
    either cooling down, unparseable under an active cooldown, or broken —
    :func:`next_player` does not itself distinguish those, so this driver
    does not fabricate a finer distinction than its selector can prove).
    """

    __slots__ = ("name", "reason")

    def __init__(self, name: str | None, reason: str) -> None:
        self.name = name
        self.reason = reason

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RotationDecision):
            return NotImplemented
        return self.name == other.name and self.reason == other.reason

    def __repr__(self) -> str:
        return f"RotationDecision(name={self.name!r}, reason={self.reason!r})"


def advance_rotation(
    rows: list[dict[str, str]] | None = None,
    *,
    cooldown_hours: float = DEFAULT_ROTATION_COOLDOWN_HOURS,
    now: datetime | None = None,
) -> RotationDecision:
    """Decide whose turn is due next — the rotation *driver*, still read-only.

    Policy (this WO's explicit decision, per canon's "rotation driver is not
    yet wired" gap): **round-robin by oldest-``last_played``-first** among
    profiles outside the cooldown window, never-played breaking first. That
    is exactly :func:`next_player`'s own key ordering (``(0, name)`` for
    never-played, then ``(1, timestamp, name)`` oldest-first, unknown/broken
    excluded or pushed last) — this driver does not re-derive that ordering,
    it wraps the one selector that already proves it
    (``test_next_player_prefers_never_then_oldest`` /
    ``test_next_player_skips_cooldown_broken_and_unknown``).

    ``rows`` defaults to :func:`list_players` when omitted, so a caller with
    no rows in hand gets the same live bank ``tw players next`` reads
    (:class:`BankUnreadable` propagates unchanged — this driver does not
    convert it to a decision).

    This is a **decision, not an action**: it never writes ``last_played``,
    never opens a session, never sends a keystroke. No write path for
    ``last_played`` exists anywhere in this codebase today (session-end
    rotation bookkeeping is a separate future wave) — inventing one here
    would mean recording a play session that never happened, which is the one
    thing a decide-and-report driver must never do. Once that write path
    lands, its caller is what marks a rotation *consumed*, at the point a
    session genuinely ends, using the same ``name`` this function reported.
    """
    if rows is None:
        rows = list_players()
    name = next_player(rows, cooldown_hours=cooldown_hours, now=now)
    if name is not None:
        reason = "due"
    elif not rows:
        reason = "empty_bank"
    else:
        reason = "none_eligible"
    return RotationDecision(name=name, reason=reason)


def list_players() -> list[dict[str, str]]:
    """Return metadata-only bank rows for the launcher touchpoint.

    Shape matches ``tw players list`` columns: name, handle, host, game_letter,
    last_played, turns_state. Missing rotation history uses ``never`` / ``-``.
    A row for a profile the credential store flagged carries a seventh key,
    ``error`` — see "Broken profiles" below.

    Raises :class:`BankUnreadable` when the bank could not be read, rather than
    returning a shorter list. There is no honest partial listing to fall back
    on: *every* row this function emits carries ``last_played`` and
    ``turns_state``, both read from the bank, so with the bank unread each
    profile row would render ``never`` / ``-`` — a positive claim about
    rotation history taken from a file nobody managed to read — and every
    bank-only row would silently vanish. Callers render the failure instead of
    a list; see ``app.py``'s bank view.

    The same holds one file over, which is why this reads the STRICT
    ``load_profile_summaries``: an unreadable ``profiles.toml`` drops every
    profile-derived row, leaving a listing that renders as "(bank empty)" —
    a claim about contents, made out of two files, one of which nobody read.
    The display twin ``list_profile_summaries`` cannot be substituted: it
    answers that failure with ``_store_failure_row``, a diagnostic row named
    for the failing FILE, which arriving here would be counted and rendered as
    a *character* in the operator's bank — a fabricated player plus a count
    nothing earned. Raising is this surface's answer to that failure; a row is
    the launcher's.

    Broken profiles (WO-PLAYERBANK-LISTING-HONESTY)
    -----------------------------------------------
    A profile whose summary carries an ``error`` is LISTED, with that ``error``
    on the row. It used to be skipped, and the view then painted the surviving
    rows as a whole bank — the same collapse this module's docstring exists to
    prevent, one level down: "there is no such character" and "that character's
    profile is broken" are different facts, an operator acts on only one of
    them, and they rendered alike (both: absent). Worse where the name also had
    a bank entry: the row did not vanish at all, it re-emerged from the
    bank-only loop below wearing the BANK's stored handle/host/game letter and
    no error mark, so a broken profile read as a healthy character described by
    a store that was never the authority on it.

    Unlike the bank-unreadable case above, an honest row genuinely exists here,
    and that asymmetry is the whole justification: the bank WAS read, so
    ``last_played`` / ``turns_state`` are real rather than manufactured, and
    every identity column that could not be filled already degrades to this
    function's own ``?``. Nothing is invented — no host, no handle, no game
    letter — and the name is kept intact rather than parenthesised the way
    ``credentials._store_failure_row`` mangles its own: that row has no real
    name to protect, this one's name is the bank join key, the operator's
    handle on which profile to repair, and its cross-reference to the launcher
    list.

    ``error`` is present only on a broken row — absent, not ``None``, on a
    healthy one — so a healthy row's six-key shape is unchanged and
    ``entry.get("error")`` is a surface's entire branch (the launcher already
    branches exactly that way on ``ProfileRow.error``).

    ``screens.py``'s ``BankViewScreen`` and ``tw players list`` both mark
    broken rows (name``!`` + ``error:`` follow-up) — WO-FIX-BANKVIEW-BROKEN-
    PROFILE-ERROR closed the TUI half that previously painted six columns only.

    The one row still dropped is a summary with no ``name`` at all. That is
    structurally unreachable from ``load_profile_summaries`` (names are TOML
    section keys) and there would be nothing to show or act on: no join key to
    the bank, no identity to repair. It is a defensive guard, not a filter.
    """
    bank = _load_bank_raw()
    try:
        summaries = credentials.load_profile_summaries()
    except (credentials.ProfileStoreUnreadable, credentials.ProfileStoreMalformed) as exc:
        # `cause` maps straight through — credentials.py speaks this exact
        # CAUSE_* vocabulary on purpose. The reason leads with the failing
        # file's name because the surface headline says "bank".
        raise BankUnreadable(
            exc.cause, f"{Path(exc.path).name}: {exc.reason}", exc.path
        ) from exc
    by_name = {
        str(p.get("name")): p
        for p in bank.get("players", [])
        if isinstance(p, dict) and p.get("name")
    }
    rows: list[dict[str, str]] = []
    for summary in summaries:
        name = str(summary.get("name") or "")
        if not name:
            continue  # nothing to show, nothing to join on -- see the docstring
        last_played, turns_state = _rotation_columns(by_name.get(name, {}))
        row = {
            "name": name,
            "handle": str(summary.get("handle") or "?"),
            "host": str(summary.get("host") or summary.get("server") or "?"),
            "game_letter": str(summary.get("game_letter") or "?"),
            "last_played": last_played,
            "turns_state": turns_state,
        }
        error = summary.get("error")
        if error:
            # Only on broken rows, so a healthy row's shape is untouched and
            # `.get("error")` is the whole branch a surface needs.
            row["error"] = str(error)
        rows.append(row)
    # Bank-only entries (profile removed) still surface as diagnosable rows.
    # A broken profile is NOT one of these any more -- it emitted above, from
    # its own store -- so this loop can no longer re-describe it out of the
    # bank's stale copy.
    known = {r["name"] for r in rows}
    for name, stored in by_name.items():
        if name in known:
            continue
        last_played, turns_state = _rotation_columns(stored)
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
