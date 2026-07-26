"""Pure-stdlib `.env` loader + project-rooted path resolution.

Resolution precedence for the game server host/port (highest to lowest):

  1. an explicit CLI arg (e.g. `tw start --host ...`), when actually given
  2. `TW2002_HOST` / `TW2002_PORT` already set in the process environment
  3. `.env` file values (repo-root `.env`, gitignored -- see `.env.example`
     if present, or `config/profiles.toml.example` for the shape)
  4. `config/profiles.toml`'s `[default]` section (host/port only)
  5. no silent fallback host -- raises `EnvResolutionError` naming the
     missing variable

An ABSENT `.env` is silent and falls straight through -- tier 3 is an
optional overlay and most runs have none. An UNREADABLE `.env` is not
absent, and this module refuses to treat it as such
(WO-LOAD-DOTENV-PERMISSION-HONESTY): it is held by `resolve_host_port`
and raised as an `EnvResolutionError` iff resolution actually reaches
tier 3, i.e. iff tiers 1-2 did not already settle host AND port. See
`resolve_host_port` for why that condition, and not "always", is the
honest rule.

This mirrors the env-first idiom `credentials.py` already uses for
`TW2002_PASSWORD_<PROFILE>` (env checked before the on-disk store), just
applied to host/port instead of the password.

This module is also the project's one home for **project-rooted path
resolution** -- `run/`, `logs/`, `state/`, `config/` all resolve relative
to the repo root regardless of the caller's CWD (see canon's Single-
Connection Invariant, `canon/architecture/session-engine.md`), not
relative to wherever `tw`/`twd` happened to be invoked from.

`CONFIG_DIR`/`PROFILES_PATH` are re-exported straight from `credentials.py`
(OPEN-003-A) rather than recomputed here -- `credentials.py` is the one
place that resolves `TW_CONFIG_DIR`, so this module and `credentials.py`
always agree on the config dir without a second copy of that resolution.
"""

import os
from pathlib import Path

from . import credentials

# session/env.py -> session -> tw2002_aiclient -> repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"
CONFIG_DIR = credentials.CONFIG_DIR
STATE_DIR = PROJECT_ROOT / "state"
LOG_DIR = PROJECT_ROOT / "logs"
PROFILES_PATH = credentials.PROFILES_PATH

HOST_VAR = "TW2002_HOST"
PORT_VAR = "TW2002_PORT"

# The sole documented override for the daemon's run/ home (pidfile +
# socket) -- see the Single-Connection Invariant. Unset by default, so
# every caller lands on the one project-rooted `run/` directory.
RUN_DIR_VAR = "TW_RUN_DIR"

SOCK_NAME = "twd.sock"
PID_NAME = "twd.pid"


class EnvResolutionError(Exception):
    """Raised when host/port cannot be resolved from any source."""


class DotenvUnreadable(EnvResolutionError):
    """The `.env` overlay exists (or may exist) but its content was never
    seen: permission denied on the file or on the directory containing it,
    the path is not a readable file, or the bytes are not valid UTF-8.

    Never raised for a genuinely ABSENT `.env`. Absence is the routine
    state of an optional overlay -- most runs have no `.env` at all -- and
    it is the one negative this loader is entitled to report, which it does
    by returning `{}`.

    An `EnvResolutionError` SUBCLASS on purpose, and that is the fail-safe
    half: `daemon.main` catches exactly `EnvResolutionError` around host/
    port resolution, so even a caller that never learns this type by name
    still reaches the operator as a `twd: <line>` rather than as a
    traceback. Same direction c263f16 chose for the profile-store family --
    a new failure defaults to loud-and-actionable, never to an escape.

    `cause` reuses `credentials.CAUSE_*` rather than inventing a second
    dialect for the same three operator jobs (fix permissions, replace a
    wrong path, repair a damaged file). `reason` is bounded and NEVER
    carries file content: a `.env` legitimately holds a
    `TW2002_PASSWORD_<PROFILE>` value (env-first credentials, see
    `canon/doctrine/secrets-and-credentials.md`), so a decode failure is
    rendered as a type name plus integer positions only -- never
    `str(exc)`, and never `exc.object`, which holds the entire file.
    """

    def __init__(self, cause, reason, path):
        self.cause = cause
        self.reason = reason
        self.path = str(path)
        super().__init__(f"{reason} ({self.path})")


def load_dotenv(path=None):
    """Parse a simple `KEY=VALUE` `.env` file into `os.environ`.

    Blank lines and lines starting with `#` are ignored. Values may
    optionally be wrapped in matching single or double quotes, which are
    stripped. Never overwrites a variable already present in the process
    environment -- a real env var always outranks the file (this is what
    makes the CLI-arg/env/.env precedence chain work: by the time
    `resolve_host_port` reads `os.environ`, a pre-existing process env var
    has already blocked the file's value from landing).

    Returns the dict of key/value pairs found in the file (regardless of
    whether they were actually applied to `os.environ`), so callers can
    inspect what the file itself declared.

    An ABSENT file returns `{}`, silently, and that is deliberate: having
    no `.env` is the ordinary state of an optional overlay, not a condition
    worth a word. Every OTHER failure raises `DotenvUnreadable` instead,
    because `{}` is a CLAIM -- "this file declared nothing" -- and a file
    nobody managed to read has not earned it.

    `Path.exists()` is deliberately gone from this function. It was the one
    call that made those two answers indistinguishable, and it did so in
    BOTH directions at once (WO-LOAD-DOTENV-PERMISSION-HONESTY):

      * a `chmod 000` `.env` -- `exists()` answers True, and the following
        `read_text()` then raised a bare `PermissionError` straight out of
        `resolve_host_port`. `daemon.main` catches only
        `EnvResolutionError`, so `twd` died at startup with a full
        traceback in front of the operator: the identical shape c263f16
        had just fixed one function over, for `profiles.toml`.
      * a perfectly readable `.env` under an unreadable DIRECTORY --
        `exists()` answers False there, so this returned `{}` and startup
        went on to report "could not resolve the game server host", which
        sends the operator off to write a `.env` they already have.

    Opening the file and classifying the failure is what holds absent and
    unreadable apart -- the same trap, and the same fix, that
    `credentials._load_toml_store` documents for the profile store.

    A dangling symlink lands in the absent branch (its `open` raises
    ENOENT), and honestly so: the target does not exist, so there is no
    content that went unread.
    """
    path = path or DOTENV_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        # The only real negative: there is no `.env` here at all.
        return {}
    except PermissionError as exc:
        # Covers the file itself AND an unreadable parent directory. The
        # reason must name WHICH object to fix: a directory-level denial
        # reported as a bare "Permission denied" sends the operator to
        # chmod a file that is already readable.
        denied = exc.strerror or "permission denied"
        parent = Path(path).parent
        # X_OK is the traversal bit -- precisely what stops us reaching the
        # file. A directory can be search-only (0o111) and the read still
        # succeeds. Wording deliberately identical to
        # `credentials._load_toml_store`'s rather than a second phrasing of
        # the same advice; it is duplicated instead of shared because
        # `credentials.py` is the human-gated secrets lane and read-only to
        # this work order.
        if not os.access(parent, os.X_OK):
            denied = f"{denied} on the containing directory: {parent}"
        raise DotenvUnreadable(credentials.CAUSE_DENIED, denied, path) from exc
    except OSError as exc:
        # A directory named `.env`, an ELOOP symlink, a stale mount. Caught
        # after PermissionError because "I was not allowed to look" and "I
        # looked, and the path is unusable" are different operator jobs
        # sharing one exception base.
        raise DotenvUnreadable(
            credentials.CAUSE_UNUSABLE, exc.strerror or "could not be opened", path
        ) from exc
    except UnicodeDecodeError as exc:
        # NOT an OSError -- it subclasses ValueError, so it escaped this
        # function entirely too, by a different door than the
        # PermissionError above. `_decoder_detail` renders a type name plus
        # integer offsets and nothing else; `str(exc)` and `exc.object`
        # would both put bytes from a file that can legitimately hold a
        # password into an operator-facing line. Reached through
        # `credentials` rather than copied so there is ONE rendering of a
        # decoder failure in this codebase, not two that can drift.
        raise DotenvUnreadable(
            credentials.CAUSE_CORRUPT,
            f"not valid UTF-8 ({credentials._decoder_detail(exc)})",
            path,
        ) from exc
    values = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not key:
            continue
        values[key] = value
        if key not in os.environ:
            os.environ[key] = value
    return values


def _load_profile_host_port(profile_name, profiles_path):
    """Resolve tier 4 (the `[profile_name]` fallback) via the ONE shared
    resolver, `credentials.resolve_profile_host_port` (OPEN-003-A) --
    replacing this function's own narrow direct-TOML-read copy of the same
    logic. A caller-supplied `profiles_path` (this module's own long-
    standing test-isolation param, predating `TW_CONFIG_DIR`) is passed
    straight through to the shared resolver's own `profiles_path=` keyword
    (OPEN-003-A follow-up: `credentials.py` grew this param specifically so
    no caller needs to mutate its module-level `PROFILES_PATH` global to
    test-isolate a call -- a mutate-then-restore swap is a TOCTOU hazard
    under `ThreadingUnixServer`'s `daemon_threads=True`, flagged by Cipher
    + Mack).

    Never raises for a profile/file/section that's simply ABSENT (the
    file doesn't exist, or has no `[profile_name]` table, or the table
    has no host/port/server at all) -- that's ordinary tier-4 "nothing
    here" for a last-resort fallback, so it returns `(None, None)` and
    lets `resolve_host_port`'s own actionable HOST_VAR/PORT_VAR message
    fire. EVERYTHING ELSE raises `EnvResolutionError`: something WAS
    there and we could not use it (an unparseable port, an unresolvable
    `server=` catalog key, unparseable TOML, a store we were not allowed
    to read at all) -- swallowing THAT into a generic "not found"
    message would hide the real problem from the operator. Distinguished
    by TYPE, via `credentials.py`'s `ProfileConnectionError` family
    (OPEN-003-A follow-up) -- not by sniffing the exception's message
    text.

    The enumeration goes on the ABSENT side, and the loud side is caught
    at the family BASE. That asymmetry is the whole design, not a
    shortcut: the absent set is CLOSED -- `ProfileNotFound` /
    `ProfileIncomplete`, and `ProfileConnectionError`'s own docstring
    pins it, "Absence is never one of these" -- while the loud set is
    OPEN and has already grown twice (`ProfileStoreUnreadable`,
    `ProfileStoreMalformed`). While this function enumerated the loud
    side instead (`except credentials.ProfileMalformed`), a new member
    that was deliberately NOT a `ProfileMalformed` fell through every
    handler here: `ProfileStoreUnreadable` is a direct child of the base
    (nothing was read, so nothing can be called malformed), so a `chmod
    000` `profiles.toml` -- or an unreadable `config/` around it -- left
    `twd` dying at startup with an unhandled traceback in front of the
    operator instead of an actionable line (WO-TWD-PROFILE-STORE-
    UNREADABLE). Catching the base for everything that is not absent
    makes the NEXT family member default to loud-and-actionable rather
    than to a traceback. `tests/test_twd_profile_store_unreadable.py`
    walks the family recursively and holds the closed set closed.

    The message claims nothing about the profile's CONTENT -- a store
    nobody could read is not "misconfigured" -- and leans on `{e}`,
    which for a store-read failure already renders "<reason> (<store
    that failed>)". That parenthetical is load-bearing because this path
    also reaches the `servers.toml` CATALOG through
    `resolve_profile_host_port`, not just `profiles.toml`. `path` is
    still named explicitly so the line stays actionable for the failures
    whose own text names no file at all (a bad `port=` value).
    """
    import tomllib

    path = profiles_path or credentials.PROFILES_PATH
    try:
        return credentials.resolve_profile_host_port(profile_name, profiles_path=profiles_path)
    except (credentials.ProfileNotFound, credentials.ProfileIncomplete):
        # Absent or under-specified profile -- ordinary tier-4 "nothing
        # here" for a last-resort fallback; fall through so
        # resolve_host_port's own actionable HOST_VAR/PORT_VAR message
        # fires, same as a missing file/section always has.
        return None, None
    except credentials.ProfileConnectionError as e:
        # NOT absent, so something WAS there and we could not use it: a
        # bad port int, an unknown server= catalog key, bad TOML, or a
        # store we were never allowed to open. Surface it directly
        # rather than hiding it behind the generic fallback message.
        # The BASE, deliberately -- see this function's docstring: a
        # future family member lands here and stays actionable instead
        # of escaping as a traceback. Names `path` explicitly (not just
        # the exception's own message) so this stays actionable even if
        # credentials.py's own wording ever stops naming the file
        # itself, and says only that the profile "could not be used" --
        # an unread store has earned no claim about its content.
        raise EnvResolutionError(
            f"{path}'s [{profile_name}] profile could not be used: {e} "
            f"-- fix the problem it reports, or set {HOST_VAR}/{PORT_VAR} "
            f"to override it."
        ) from e
    except tomllib.TOMLDecodeError as e:
        # Belt-and-braces: covers a bad-TOML profiles.toml in case
        # credentials.py's resolver ever stops wrapping this itself as
        # a ProfileConnectionError.
        raise EnvResolutionError(
            f"{path} is not valid TOML ({e}) -- fix it or remove it."
        ) from e


def resolve_host_port(cli_host=None, cli_port=None, profile_name="default",
                       profiles_path=None, dotenv_path=None):
    """Resolve (host, port) per the module's precedence order.

    `cli_host`/`cli_port` should be the parsed argparse values with
    `default=None` -- i.e. only non-None when the caller actually passed
    `--host`/`--port`. Raises `EnvResolutionError` with an actionable
    message (naming the missing env var) if nothing resolves.

    An UNREADABLE `.env` is HELD here, not raised on sight, and becomes an
    error iff resolution actually reaches the tier that file would have
    supplied (WO-LOAD-DOTENV-PERMISSION-HONESTY). The condition is exactly
    the `host is None or port is None` branch that already exists below,
    because that branch IS the question "did tiers 1-2 settle this?":

      * if they did, the unread file could not have changed the answer --
        it is outranked by both, its values would have been ignored even
        if we had read them, and reporting it would fail a startup over a
        file that was irrelevant to the outcome. `--host/--port` is
        documented as tier 1; a tier-3 file must not defeat it.
      * if they did NOT, the unread file is precisely the next thing that
        would have been consulted, so proceeding means answering from a
        LOWER tier (`profiles.toml`) than the one the operator actually
        configured. That is not a cosmetic fault here: host/port is a
        connect target, and silently connecting to a different server than
        the `.env` names is a real wrong answer for a game with persistent
        per-server character state. So: loud, before tier 4 is consulted.

    That asymmetry is also what keeps this from bricking anyone. An
    operator with a root-owned `.env` left over from some earlier
    experiment has three ways out, one of them printed in the message
    itself: `twd --host H --port P`, `TW2002_HOST=... TW2002_PORT=... twd`,
    or removing the file (which needs write on the DIRECTORY, not on the
    root-owned file). Raising unconditionally instead would take the first
    two away and leave only the ones requiring `sudo` -- which is why
    "always loud" was rejected, not because loudness is wrong.

    The policy is deliberately isolated to the one `if dotenv_failure`
    below: `load_dotenv`'s own honesty (absent vs unreadable) does not
    depend on it, so a later ruling that this should warn-and-fall-through
    instead changes that single branch and nothing else.
    """
    try:
        load_dotenv(dotenv_path)
        dotenv_failure = None
    except DotenvUnreadable as e:
        # Held, not raised -- tiers 1-2 may still settle this, and if they
        # do, a file we could not read could not have mattered.
        dotenv_failure = e

    host = cli_host
    port = cli_port

    if host is None:
        host = os.environ.get(HOST_VAR) or None
    if port is None:
        env_port = os.environ.get(PORT_VAR)
        if env_port:
            try:
                port = int(env_port)
            except ValueError:
                raise EnvResolutionError(
                    f"{PORT_VAR} is set to {env_port!r}, which is not a valid "
                    f"integer port -- fix it in the environment or .env."
                )

    if host is None or port is None:
        if dotenv_failure is not None:
            # Tiers 1-2 did not settle it, so the file we could not read is
            # the very next thing that would have been consulted. Falling
            # through to tier 4 here would answer from a source the
            # operator's own `.env` outranks -- see this function's
            # docstring. `{dotenv_failure}` already renders
            # "<reason> (<the .env that failed>)", so the path is named
            # without repeating it.
            raise EnvResolutionError(
                f"the .env overlay could not be read: {dotenv_failure} -- fix "
                f"the problem it reports, or remove the file; or pass "
                f"--host/--port or set {HOST_VAR}/{PORT_VAR}, which outrank "
                f".env and resolve without it."
            ) from dotenv_failure
        profile_host, profile_port = _load_profile_host_port(profile_name, profiles_path)
        if host is None:
            host = profile_host
        if port is None:
            port = profile_port

    if host is None:
        raise EnvResolutionError(
            f"could not resolve the game server host: pass --host, set "
            f"{HOST_VAR} in the environment or .env, or add a [{profile_name}] "
            f"host in config/profiles.toml."
        )
    if port is None:
        raise EnvResolutionError(
            f"could not resolve the game server port: pass --port, set "
            f"{PORT_VAR} in the environment or .env, or add a [{profile_name}] "
            f"port in config/profiles.toml."
        )
    return host, port


def resolve_run_dir():
    """Resolve the project-rooted `run/` directory (pidfile + socket home).

    Honors `TW_RUN_DIR` as the sole override (absolute, or relative to
    `PROJECT_ROOT`); defaults to `PROJECT_ROOT / "run"`. Independent of
    the caller's CWD either way -- `tw`/`twd` invoked from any directory
    resolve to the same `run/` home, per the Single-Connection Invariant.

    A whitespace-only override (including `""`) is treated as unset, same
    as a missing var -- both readings land on the identical safe default,
    so there is nothing to protect against (WO-RUN-DIR-NORMALISE, E-03).

    A NON-empty override with leading/trailing whitespace, OR a `\n`/`\r`
    anywhere in it (edge or embedded), is REFUSED, not silently repaired:
    `Path(" /tmp/x").is_absolute()` is False, so a stray leading space
    would otherwise turn an intended absolute path into a *different*,
    PROJECT_ROOT-relative one -- two callers that believe they share a
    run/ home would land on different directories, silently defeating
    the Single-Connection Invariant this function exists to uphold
    (WO-RUN-DIR-NORMALISE, E-01; hub-ratified 2026-07-26, overruling this
    module's own earlier `.strip()` suggestion). The realistic source is
    a shell export, a systemd/Docker env file (CRLF line endings), or a
    copied command with a trailing newline -- never a project `.env`
    line, since `load_dotenv` already strips both key and value before
    either reaches `os.environ`. A plain INTERNAL space is a real, legal
    path component and is left alone -- only edge whitespace and any
    `\n`/`\r` are refused, since no legitimate run-dir path ever contains
    a raw newline or carriage return. Refusing loudly (rather than
    stripping and moving on) surfaces the anomaly at its source instead
    of masking it: `.strip()` would recover from this ONE call site, but
    the same malformed-env-var pipeline could just as easily be polluting
    a var this module cannot auto-repair.
    """
    override = os.environ.get(RUN_DIR_VAR)
    if not override or not override.strip():
        return PROJECT_ROOT / "run"
    if override != override.strip() or "\n" in override or "\r" in override:
        raise EnvResolutionError(
            f"{RUN_DIR_VAR} contains stray whitespace or a newline/carriage-"
            f"return character ({override!r}) -- a leading space silently turns "
            f"an absolute path into a PROJECT_ROOT-relative one, splitting the "
            f"run/ directory two callers expect to share. Fix the value at its "
            f"source: check for accidental quoting, a trailing newline from how "
            f"the .env line or shell export was written, or Windows-style line "
            f"endings in an env file -- rather than guessing which characters "
            f"were intended."
        )
    p = Path(override)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def socket_path(run_dir=None):
    """The unix-domain command socket path under `run_dir` (default:
    `resolve_run_dir()`)."""
    return (run_dir or resolve_run_dir()) / SOCK_NAME


def pid_path(run_dir=None):
    """The daemon pidfile path under `run_dir` (default:
    `resolve_run_dir()`)."""
    return (run_dir or resolve_run_dir()) / PID_NAME
