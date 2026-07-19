"""Player Bank -- TW-31 client-side half (multi-character rotation store).

Tracks WHICH characters exist -- each bank entry links back to a
`config/profiles.toml` profile by `name` -- plus simple per-character
rotation bookkeeping (`last_played`, `turns_state`) so a future daemon-side
rotation driver (window-gated, separate wave) can decide whose turn it is
without the LLM/CLI worker tracking it by hand. `cli.py` wiring (a `tw
players` verb) is NOT part of this wave; every function here is designed
to be a thin wrapper's whole implementation when that lands.

**Passwords cannot land in this module -- BY DESIGN, structurally.**
`credentials.Profile` (what `add_player` pulls fields from) has no
password field at all; there is nothing here to leak because nothing
here ever holds one. Password resolution stays entirely inside
`credentials.py`'s env-first `get_password()`/`save_password()` path,
invoked at use-time by whoever actually drives a login (`login.py`'s
automaton) -- never by this module.

The one place free-form caller data enters this module is `add_player`'s
`notes` dict. It's guarded by a best-effort, defense-in-depth filter --
NOT a secrets detector, and not the reason passwords can't leak here
(that structural guarantee above is): values are restricted to scalars
(str/int/float/bool, no nested dict/list -- closes a value-smuggling
bypass where a caller hides a secret a level down under an innocuous
key), string values are length-capped, and keys are checked against a
broadened password/secret/token/credential-alias denylist (`pw`/`pwd`/
`auth`/`apikey`/`creds`/etc, case-insensitive, substring match --
deliberately over-inclusive: a false rejection is always safer than a
false acceptance here). A refused key is never echoed verbatim into an
error message, only a truncated form -- so a secret-shaped KEY name
itself can't land in a log/traceback either.
"""

import contextlib
import datetime
import fcntl
import json
import os
import re
from pathlib import Path

from . import credentials

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "state"
BANK_PATH = STATE_DIR / "player_bank.json"

BANK_VERSION = 1

# Defensive: reject any notes key that LOOKS password/secret-shaped,
# even though a caller should never pass one -- the one place free-form
# data enters this file is the `notes` dict, so that's the one place
# this check needs to guard. Broadened aliases (pw/pwd/auth/apikey/
# creds) beyond the original pass/secret/token/credential set --
# deliberately over-inclusive substring match, not word-boundaried:
# a false rejection here is always safer than a missed real secret.
_SECRET_KEY_RE = re.compile(
    r"pass|password|pw|pwd|auth|apikey|api_key|creds|credential|secret|token", re.I
)

# Structural guard on notes VALUES (closes the value-smuggling bypass:
# hiding a secret string under an innocuous key, or a level down inside
# a nested dict/list where only top-level keys would ever be scanned).
_ALLOWED_NOTES_VALUE_TYPES = (str, int, float, bool)
_MAX_NOTES_VALUE_LEN = 200


class PlayerBankError(Exception):
    """Bank-level errors: duplicate player, unknown player, a
    password-shaped notes key, etc."""


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_bank():
    return {"version": BANK_VERSION, "players": []}


def _lock_path(path):
    return path.with_suffix(path.suffix + ".lock")


@contextlib.contextmanager
def _bank_lock(bank_path=None):
    """Exclusive `fcntl.flock`, held across a mutator's FULL
    load-mutate-save critical section, so two concurrent mutators (two
    CLI invocations, a CLI invocation racing the daemon, etc.) can
    never interleave a lost update. Locks a sibling `<bank>.lock` file,
    never the bank file itself, so lock-free readers (`load_bank`,
    `next_player`) are never blocked by a held write lock -- readers
    are protected from a torn read by `save_bank`'s atomic rename, not
    by this lock. stdlib-only, POSIX-only by design (matches the
    unix-socket/curses/pyte stack this project already runs on)."""
    path = bank_path or BANK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(path)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def load_bank(bank_path=None):
    """Load the bank file, or return a fresh empty bank if it doesn't
    exist yet -- that's the expected pre-first-use state, never an
    error. A corrupt/truncated/empty file, an unsupported `version`, or
    an entry missing its (required) `name` key are all treated as
    fatal structural corruption -- `PlayerBankError`, naming the file,
    NEVER a silent reset to an empty bank (that would be data loss
    dressed as recovery). Lock-free: safe for concurrent readers
    because `save_bank`'s atomic rename means a read never observes a
    partially-written file, only a complete old or new one."""
    path = bank_path or BANK_PATH
    if not path.exists():
        return _new_bank()
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise PlayerBankError(
                f"player_bank file is corrupt (invalid JSON): {path} ({e})"
            ) from e
    if not isinstance(data, dict):
        raise PlayerBankError(
            f"player_bank file has an invalid top-level shape (expected an object): {path}"
        )
    data.setdefault("version", BANK_VERSION)
    if data["version"] != BANK_VERSION:
        raise PlayerBankError(
            f"unsupported player_bank version {data['version']!r} in {path} "
            f"(expected {BANK_VERSION})"
        )
    data.setdefault("players", [])
    for i, p in enumerate(data["players"]):
        if not p.get("name"):
            raise PlayerBankError(
                f"player_bank entry at index {i} is missing a name in {path}"
            )
    return data


def save_bank(bank, bank_path=None):
    """Atomic write: temp-then-rename, chmod 0600 (mirrors
    `credentials.py`'s `_write_secrets` pattern exactly), so a crash
    mid-write can never corrupt an existing bank file -- the
    destination only ever sees a complete, valid write. The bank holds
    real handle/host/game_letter metadata (never passwords, but still
    local-only), so it gets the same 0600 treatment as the secrets
    file rather than an umask-default 0644 -- defense-in-depth beats
    precedent here. On ANY failure before the rename completes, the
    orphaned temp file is removed too -- the destination is left
    exactly as it was AND no stray `.tmp` sibling survives the
    failure."""
    path = bank_path or BANK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(bank, f, indent=2)
            f.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(str(tmp_path), str(path))
        os.chmod(path, 0o600)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def _redact_key_for_error(key):
    """Never echo a caller-supplied key verbatim into an exception
    message -- a secret-shaped KEY (not just a secret-shaped VALUE)
    could otherwise land in a log/traceback. Truncated, not hashed:
    this is for a human debugging a rejection, not a security
    boundary -- the boundary is that the notes dict itself never
    reaches disk on rejection."""
    s = str(key)
    return s[:8] + "…" if len(s) > 8 else s


def _reject_secret_keys(notes):
    for key in notes:
        if _SECRET_KEY_RE.search(str(key)):
            raise PlayerBankError(
                f"refusing to store password-shaped key {_redact_key_for_error(key)!r} "
                "in player_bank notes"
            )


def _validate_notes(notes):
    """Structural guard for the one place free-form caller data enters
    this module. Applied to EVERY key/value pair -- there's no nesting
    left to miss a key inside, since nested containers are refused
    outright below. NOT a secrets detector (see module docstring) --
    best-effort defense-in-depth on top of the structural guarantee
    that this module never handles passwords at all."""
    if not notes:
        return
    _reject_secret_keys(notes)
    for key, value in notes.items():
        if isinstance(value, (dict, list)):
            raise PlayerBankError(
                f"player_bank notes value for key {_redact_key_for_error(key)!r} "
                "must be a scalar -- nested dict/list values are not allowed"
            )
        if not isinstance(value, _ALLOWED_NOTES_VALUE_TYPES):
            raise PlayerBankError(
                f"player_bank notes value for key {_redact_key_for_error(key)!r} "
                f"has an unsupported type ({type(value).__name__})"
            )
        if isinstance(value, str) and len(value) > _MAX_NOTES_VALUE_LEN:
            raise PlayerBankError(
                f"player_bank notes value for key {_redact_key_for_error(key)!r} "
                f"exceeds the {_MAX_NOTES_VALUE_LEN}-character limit"
            )


def _build_entry(profile, notes):
    return {
        "name": profile.name,
        "handle": profile.handle,
        "host": profile.host,
        "port": profile.port,
        "game_letter": profile.game_letter,
        "created": _now_iso(),
        "last_played": None,
        "turns_state": "active",
        "notes": dict(notes) if notes else {},
    }


def _add_player_locked(bank, name, profiles_path, notes):
    """Assumes the caller already holds `_bank_lock` and owns `bank` (a
    dict just returned by `load_bank`/`_new_bank`, not yet saved) --
    mutates it in place and returns the new entry. Never acquires the
    lock itself: exists so `add_player` and `ensure_seeded` can share
    this logic inside ONE lock acquisition each, instead of nesting
    lock acquisitions (which would deadlock -- `flock` blocks a second
    open-file-description on the same lock file even from the same
    process)."""
    if any(p["name"] == name for p in bank["players"]):
        raise PlayerBankError(f"player_already_in_bank:{name}")
    profile = credentials.load_profile(name, profiles_path=profiles_path)
    entry = _build_entry(profile, notes)
    bank["players"].append(entry)
    return entry


def add_player(name, profiles_path=None, notes=None, bank_path=None):
    """Add a player from an EXISTING `config/profiles.toml` profile
    named `name`. Pulls `handle`/`host`/`port`/`game_letter` via
    `credentials.load_profile()` -- never accepts them directly, so a
    bank entry can't drift from the profile actually used to connect.
    Refuses a duplicate `name` and an empty/whitespace-only `name`.
    Validates `notes` up front (before any disk write, before even the
    lock) -- see `_validate_notes` -- the structural scalar/length/key
    guard, not a secrets detector. The load-mutate-save critical
    section runs under `_bank_lock` so a concurrent add/mark can never
    race this one into a lost update."""
    if not name or not name.strip():
        raise PlayerBankError("player_bank entry name must be non-empty")
    _validate_notes(notes)
    path = bank_path or BANK_PATH
    with _bank_lock(path):
        bank = load_bank(path)
        entry = _add_player_locked(bank, name, profiles_path, notes)
        save_bank(bank, path)
    return entry


def list_players(bank_path=None):
    """Full entry dicts (copies -- mutating the returned list/dicts
    never touches the live bank), in bank order."""
    return [dict(p) for p in load_bank(bank_path)["players"]]


def mark_played(name, turns_state=None, bank_path=None):
    """Stamp `last_played` (now, UTC) for `name`, and update
    `turns_state` if given (leaves it unchanged if not -- e.g. a caller
    just recording that a session happened without a state transition).
    Raises `PlayerBankError` if `name` isn't in the bank. Runs under
    `_bank_lock` so a concurrent mark/add can never race this one into
    reverting an unrelated field (e.g. a stale-loaded re-stamp silently
    undoing a concurrent exhaustion mark)."""
    path = bank_path or BANK_PATH
    with _bank_lock(path):
        bank = load_bank(path)
        for p in bank["players"]:
            if p["name"] == name:
                p["last_played"] = _now_iso()
                if turns_state is not None:
                    p["turns_state"] = turns_state
                save_bank(bank, path)
                return dict(p)
        raise PlayerBankError(f"player_not_found:{name}")


def next_player(bank, current=None):
    """PURE rotation-order helper (never touches disk -- `bank` is
    whatever `load_bank()` already returned) for the daemon-side driver
    to wire later: least-recently-played first among players whose
    `turns_state` isn't `"exhausted"`, never-played entries (
    `last_played is None`) sorting ahead of any real timestamp. Returns
    `None` if every player is exhausted (or the bank is empty). If the
    single most-overdue player is `current` and an alternative exists,
    returns the next-most-overdue instead, so a caller can rotate away
    from whoever's turn just ended."""
    eligible = [p for p in bank["players"] if p.get("turns_state") != "exhausted"]
    if not eligible:
        return None

    def sort_key(p):
        last_played = p.get("last_played")
        return (last_played is not None, last_played or "")

    eligible.sort(key=sort_key)
    if len(eligible) > 1 and eligible[0]["name"] == current:
        return eligible[1]["name"]
    return eligible[0]["name"]


def ensure_seeded(seed_profile_name="default", profiles_path=None, bank_path=None):
    """If no bank file exists yet AND a profile named `seed_profile_name`
    exists in `profiles.toml`, create the bank with it as entry #1.
    Idempotent -- if a bank file already exists, returns it UNCHANGED
    (never overwrites); if the seed profile doesn't exist, returns
    `None` and creates nothing.

    `seed_profile_name` intentionally has no project-specific default
    baked in beyond the existing `[default]` profiles.toml convention --
    callers wire in whatever profile name is actually the seed character
    for their local, gitignored `profiles.toml` at call time.

    The existence check happens INSIDE `_bank_lock`, not before it --
    otherwise two first-run callers can each observe "no file yet"
    before either has saved, and the second's seed silently discards
    the first's. Re-checking after acquiring the lock means a second
    caller can only ever observe the first's already-committed bank."""
    path = bank_path or BANK_PATH
    with _bank_lock(path):
        if path.exists():
            return load_bank(path)
        try:
            credentials.load_profile(seed_profile_name, profiles_path=profiles_path)
        except credentials.CredentialError:
            return None
        bank = _new_bank()
        entry = _add_player_locked(bank, seed_profile_name, profiles_path, None)
        save_bank(bank, path)
        return entry
