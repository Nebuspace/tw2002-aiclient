"""Profile + secrets helpers (WO-P0-005 / WO-P1-012).

Read-only password resolution (env → secrets.json → None) plus non-secret
profile list/create for the launcher. Passwords are never written here.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

# session/credentials.py → session → tw2002_aiclient → repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_config_dir() -> Path:
    """Resolve the config directory, honoring `TW_CONFIG_DIR` (absolute,
    or relative to `PROJECT_ROOT`); default `PROJECT_ROOT / "config"`.
    Mirrors `env.py`'s `resolve_run_dir()`/`TW_RUN_DIR` idiom -- the same
    env-override-at-import shape, so a subprocess spawned with
    `TW_CONFIG_DIR` set in its environment (the daemon-spawn idiom
    `cli.py` already uses for `TW_RUN_DIR`) sees the isolated dir the
    moment this module is imported, without any accessor-function call.
    """
    override = os.environ.get("TW_CONFIG_DIR")
    if not override:
        return PROJECT_ROOT / "config"
    p = Path(override)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


CONFIG_DIR = _resolve_config_dir()
SECRETS_PATH = CONFIG_DIR / "secrets.json"
PROFILES_PATH = CONFIG_DIR / "profiles.toml"
SERVERS_PATH = CONFIG_DIR / "servers.toml"


class ProfileConnectionError(Exception):
    """Raised when a profile's (host, port) cannot be resolved -- a
    missing/malformed profile section, or a section with neither an
    explicit host+port nor a resolvable `server` catalog key.

    Callers that only need to know "did resolution fail" can catch this
    base class (e.g. `list_profile_summaries`'s display fallback below).
    Callers that need to react differently per failure kind (e.g.
    `env.py` deciding whether a retry or a user-facing fix is
    appropriate) should catch the specific subtype instead of
    string-matching the message:

      - `ProfileNotFound` -- `profiles.toml` itself, or the
        `[profile_name]` section within it, is absent (or the section
        isn't a table).
      - `ProfileIncomplete` -- the section exists but declares neither a
        usable explicit host+port pair nor a `server` catalog key.
      - `ProfileMalformed` -- something the profile DID declare is
        broken: `port` isn't a valid integer, `server` names a catalog
        key that isn't in `servers.toml` (or whose entry has no
        resolvable host/port), or `profiles.toml` itself isn't valid
        TOML.
      - `ProfileStoreUnreadable` -- a store this resolver reads
        (`profiles.toml` or the `servers.toml` catalog) could not be
        read AT ALL: denied, or the path is not a readable file. Its
        content was never seen, so it is deliberately NOT a
        `ProfileMalformed`.
      - `ProfileStoreMalformed` -- a `ProfileMalformed` SUBTYPE: the
        store was read and its content is unusable (not valid UTF-8,
        not valid TOML, or valid TOML of the wrong shape).

    Absence is never one of these. A store that was never written
    raises `ProfileNotFound` (resolver) or lists as empty (summaries) --
    the one negative anything here is entitled to report.
    """


class ProfileNotFound(ProfileConnectionError):
    """`profiles.toml` or the `[profile_name]` section is absent."""


class ProfileIncomplete(ProfileConnectionError):
    """The section exists but has neither a usable host+port pair nor a
    resolvable `server` catalog key."""


class ProfileMalformed(ProfileConnectionError):
    """A value the profile DID declare is broken: `port` isn't an int,
    `server` names an unknown/incomplete catalog entry, or the on-disk
    TOML itself doesn't parse."""


# Why a config store could not be read. Vocabulary deliberately identical to
# `player_bank.CAUSE_*` (WO-AUDIT-PLAYER-BANK-STORE-HONESTY) rather than a
# second dialect, because `player_bank.list_players()` maps ours straight
# through onto its own `BankUnreadable` -- see the mapping there. Coarse
# enough to branch on, distinct where the operator's next action differs:
# fixing permissions, replacing a wrong path, and repairing a damaged
# document are three different jobs, and `reason` narrows each one further.
CAUSE_DENIED = "denied"  # we were not allowed to look
CAUSE_UNUSABLE = "unusable"  # the path is not a readable file (e.g. a directory)
CAUSE_CORRUPT = "corrupt"  # we looked, and the bytes are not a readable document
CAUSE_MALFORMED = "malformed"  # it parsed, and it is not the table we needed


class _StoreReadFailure:
    """Shared payload for the two store-read failures below.

    A mixin rather than a common base class because those two deliberately
    sit in DIFFERENT places in the `ProfileConnectionError` family (see each
    class) -- what they share is only the `(cause, reason, path)` payload,
    not a position in the tree. `reason` is the bounded, operator-facing
    detail; `path` names WHICH store failed, since this resolver reads two
    (`profiles.toml` and the `servers.toml` catalog).

    **`reason` never carries file content.** For an `OSError` it is the
    libc `strerror`; for a decoder failure it is a TYPE NAME plus integer
    positions only -- never `str(exc)`, whose message can quote the document
    (`tomllib` renders a duplicated table's key: "Cannot declare ('alpha',)
    twice"), and never the exception's own `doc`/`object` attribute, which
    holds the ENTIRE failed-to-parse file. Same boundary the daemon's widest
    catch took (WO-AUDIT-F5-TYPE-NAME): `profiles.toml` is not the secrets
    file, but it lives in the same config directory and the same lane.
    """

    def __init__(self, cause: str, reason: str, path: object) -> None:
        self.cause = cause
        self.reason = reason
        self.path = str(path)
        super().__init__(f"{reason} ({self.path})")


class ProfileStoreUnreadable(_StoreReadFailure, ProfileConnectionError):
    """A config store this resolver needs exists (or may exist) but its
    content was never seen at all: permission denied (on the file itself or
    on the directory containing it), or the path is not a readable file (a
    directory, a symlink loop, a stale mount).

    Never raised for a store that is genuinely ABSENT -- that is a real
    negative, and the only condition entitled to report zero profiles.

    A direct child of `ProfileConnectionError` rather than of
    `ProfileMalformed`: nothing here is malformed, because nothing here was
    read. `cause` is `CAUSE_DENIED` or `CAUSE_UNUSABLE`.
    """


class ProfileStoreMalformed(_StoreReadFailure, ProfileMalformed):
    """A config store was read and its content is not usable: not valid
    UTF-8, not valid TOML, or valid TOML of the wrong shape.

    A child of `ProfileMalformed` on purpose -- `env.py` already classifies
    "unparseable TOML" as `ProfileMalformed` and surfaces it directly rather
    than swallowing it into its generic "nothing here" fallback, and that
    classification is exactly right for these. `cause` is `CAUSE_CORRUPT`
    or `CAUSE_MALFORMED`.
    """


def _decoder_detail(exc: Exception) -> str:
    """Bounded rendering of a decoder failure: type name + integer positions.

    Deliberately NOT `str(exc)`. `tomllib`'s message can lift a key straight
    out of the document, and both decoders keep the whole document on the
    exception (`TOMLDecodeError.doc`, `UnicodeDecodeError.object`). Line /
    column / byte offsets are integers -- they locate the damage without
    quoting any of it. The position attributes are read through `getattr`
    because `tomllib`'s `lineno`/`colno` are newer than the `tomli` fallback
    this module imports on older interpreters; without them the type name
    alone is still an honest answer.
    """
    name = type(exc).__name__
    lineno = getattr(exc, "lineno", None)
    colno = getattr(exc, "colno", None)
    if isinstance(lineno, int) and isinstance(colno, int):
        return f"{name} at line {lineno}, column {colno}"
    start = getattr(exc, "start", None)
    if isinstance(start, int):
        return f"{name} at byte {start}"
    return name


def _load_toml_store(path: Path) -> dict[str, object] | None:
    """Parse `path` as TOML. Return `None` iff the store is genuinely absent.

    Every other condition raises `ProfileStoreUnreadable` (content never
    seen) or `ProfileStoreMalformed` (content seen, unusable), so no caller
    can mistake "I could not read it" for "there is nothing in it".

    `Path.exists()` is deliberately absent here. It answers `False` when the
    *parent directory* is unreadable, which is what made "no profiles" and
    "cannot reach the profiles" indistinguishable at the launcher's first
    line -- before any handler could reason about it (the same trap
    `player_bank._load_bank_raw` documents). Opening the file and
    classifying the failure is what keeps them apart: the same file under an
    unreadable directory raises `PermissionError`, not `FileNotFoundError`
    (proven by execution in `tests/test_credentials_store_honesty.py`).

    A dangling symlink lands in the `None` branch, and honestly so: its
    target does not exist, so there is no store content that went unread.
    """
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        # The only real negative: nothing has ever written this store.
        return None
    except PermissionError as exc:
        # Covers the file itself AND an unreadable parent directory. The
        # reason must name WHICH object to fix: a directory-level denial
        # reported as a bare "Permission denied" sends the operator to
        # chmod a file that is already readable.
        denied = exc.strerror or "permission denied"
        parent = Path(path).parent
        # X_OK is the traversal bit -- precisely what stops us reaching the
        # file. A directory can be search-only (0o111) and the read succeeds.
        if not os.access(parent, os.X_OK):
            denied = f"{denied} on the containing directory: {parent}"
        raise ProfileStoreUnreadable(CAUSE_DENIED, denied, path) from exc
    except OSError as exc:
        # IsADirectoryError, ELOOP, a stale mount... reason carries which.
        # Caught after PermissionError because "I was not allowed to look"
        # and "I looked and the path is unusable" are different situations
        # sharing one exception base.
        raise ProfileStoreUnreadable(
            CAUSE_UNUSABLE, exc.strerror or "could not be opened", path
        ) from exc
    except UnicodeDecodeError as exc:
        # `tomllib.load` decodes the bytes itself, so a non-UTF-8 store
        # raises here. This is NOT an OSError and NOT a TOMLDecodeError --
        # it subclasses ValueError, a *different* ValueError subclass from
        # the TOML decoder, so it used to escape every handler in this
        # module and take the launcher down with a traceback.
        raise ProfileStoreMalformed(
            CAUSE_CORRUPT, f"not valid UTF-8 ({_decoder_detail(exc)})", path
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ProfileStoreMalformed(
            CAUSE_CORRUPT, f"not valid TOML ({_decoder_detail(exc)})", path
        ) from exc


def _env_var_name(profile: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in profile.upper())
    return f"TW2002_PASSWORD_{safe}"


def get_password(profile: str) -> str | None:
    """Resolve `profile`'s password: env-first, then the secrets file.

    Never raises for a merely-absent credential -- returns None, which is
    the expected state for a profile that has no stored/overridden
    credential anywhere.
    """
    env_val = os.environ.get(_env_var_name(profile))
    if env_val:
        return env_val

    if not SECRETS_PATH.exists():
        return None
    with open(SECRETS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    entry = data.get(profile)
    if isinstance(entry, dict) and entry.get("password"):
        return entry["password"]
    return None


def list_servers(path: Path | None = None) -> list[dict[str, object]]:
    """Return catalog rows from ``config/servers.toml`` (key, name, host, port).

    `path` overrides `SERVERS_PATH` when given (default `None` = current
    behavior, unchanged) -- lets `resolve_profile_host_port`'s own
    `servers_path` parameter reach the catalog read without mutating the
    module global.

    An ABSENT catalog is still an empty list -- that is a genuine negative
    and the shipped meaning of "no `servers.toml`". Every other failure
    raises out of `_load_toml_store` instead of pretending the catalog is
    empty, because an empty catalog is a claim: it makes every profile's
    `server=` key look unknown and every host column fall back to the bare
    key. A catalog nobody could read has not earned that claim.

    (Deliberate non-change: a catalog file that parses but declares no
    `[servers.*]` tables at all keeps returning `[]`, matching the absent
    file rather than raising. `player_bank` raises on a missing `players`
    key by the same reasoning that would raise here, but that state is
    reachable in this tree -- an operator can legitimately keep an empty
    catalog -- and no measured defect points at it. Noted so the asymmetry
    is visible rather than accidental.)
    """
    path = path or SERVERS_PATH
    data = _load_toml_store(path)
    if data is None:
        return []
    servers = data.get("servers") or {}
    if not isinstance(servers, dict):
        # `servers = 5` used to reach `.items()` and raise AttributeError
        # straight through the launcher's first draw.
        raise ProfileStoreMalformed(
            CAUSE_MALFORMED,
            f"'servers' is {type(servers).__name__}, expected a table",
            path,
        )
    rows: list[dict[str, object]] = []
    for key, meta in servers.items():
        if not isinstance(meta, dict):
            continue
        rows.append(
            {
                "key": key,
                "name": meta.get("name") or key,
                "host": meta.get("host") or "",
                "port": meta.get("port") or 0,
            }
        )
    return rows


def _catalog(servers_path: Path | None = None) -> dict[str, dict[str, object]]:
    """Server catalog keyed by catalog key -- the shared read both
    `list_profile_summaries` (display) and `resolve_profile_host_port`
    (connection resolution) build off `list_servers()`. `servers_path`
    overrides `SERVERS_PATH` when given (default `None` = current
    behavior, unchanged)."""
    return {str(s["key"]): s for s in list_servers(servers_path)}


def _valid_host(value: object) -> bool:
    """A usable host: a non-empty string."""
    return isinstance(value, str) and value != ""


def _valid_port(value: object) -> bool:
    """A usable port: a positive `int`. Explicitly excludes `bool` --
    `bool` is a subclass of `int` in Python, so a TOML `port = true`
    would otherwise silently pass an `isinstance(value, int)` check and
    coerce to `1` (Mack adversarial-review HIGH)."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def resolve_profile_host_port(
    profile_name: str,
    *,
    profiles_path: Path | None = None,
    servers_path: Path | None = None,
) -> tuple[str, int]:
    """Resolve `profile_name`'s (host, port) out of `config/profiles.toml`.

    `profiles_path`/`servers_path` override `PROFILES_PATH`/`SERVERS_PATH`
    when given (default `None` = the module-level globals, current
    behavior byte-identical) -- lets a caller like `env.py` test-isolate a
    call by passing a path argument instead of mutating the module global
    (a mutate-then-restore swap is a TOCTOU hazard under
    `ThreadingUnixServer`'s `daemon_threads=True`).

    Precedence (OPEN-003 Option A -- the one catalog-aware resolver,
    superseding the divergent copies previously in `env.py`,
    `cli._resolve_profile_connection`, and `protocol._load_profile`):

      1. an explicit ``host`` AND ``port`` both set on the profile --
         used as-is, even if a ``server`` catalog key is also present
         (an explicit override always wins outright, no partial merge).
         Both must be VALID (`_valid_host`/`_valid_port`) -- a present
         but invalid value (empty host, port <= 0, or a bool port) is
         `ProfileMalformed`, not silently accepted (Mack adversarial-
         review HIGH: `host=""` + `port=2323` used to return `('', 2323)`,
         and a TOML `port = true` coerced to `1`).
      2. else a ``server`` catalog key present and resolvable in
         `config/servers.toml` -- that catalog entry's (host, port),
         held to the SAME validity check.
      3. else `ProfileConnectionError`, naming the profile and what's
         missing.

    Raises `ProfileNotFound` / `ProfileIncomplete` / `ProfileMalformed`
    (all `ProfileConnectionError`) -- see that base class's docstring
    for exactly which subtype each failure kind raises. The store read
    itself adds `ProfileStoreUnreadable` (the file or its directory could
    not be read at all) and `ProfileStoreMalformed` (a `ProfileMalformed`
    subtype: the bytes are not valid UTF-8 / TOML).

    `ProfileNotFound` is now reserved for a store that is genuinely absent.
    It used to also fire for a profiles.toml sitting under an unreadable
    directory -- `Path.exists()` answers `False` there -- telling the
    operator "<path> does not exist" about a file that does, and sending
    them to create a profile they already have (WO-AUDIT-CREDENTIALS-
    LAUNCHER-CRASH).
    """
    profiles_path = profiles_path or PROFILES_PATH
    data = _load_toml_store(profiles_path)
    if data is None:
        raise ProfileNotFound(f"{profiles_path} does not exist")
    section = data.get(profile_name)
    if not isinstance(section, dict):
        raise ProfileNotFound(f"no [{profile_name}] section in {profiles_path}")

    host = section.get("host")
    port = section.get("port")
    if host is not None and port is not None:
        problems = []
        if not _valid_host(host):
            problems.append(f"host={host!r} is not a non-empty string")
        if not _valid_port(port):
            problems.append(f"port={port!r} is not a positive integer")
        if problems:
            raise ProfileMalformed(f"[{profile_name}] " + "; ".join(problems))
        return host, port

    server_key = section.get("server")
    if server_key:
        effective_servers_path = servers_path or SERVERS_PATH
        entry = _catalog(servers_path).get(str(server_key))
        if entry is None:
            raise ProfileMalformed(
                f"[{profile_name}] server={server_key!r} not found in "
                f"{effective_servers_path}"
            )
        catalog_host = entry.get("host")
        catalog_port = entry.get("port")
        if not _valid_host(catalog_host) or not _valid_port(catalog_port):
            raise ProfileMalformed(
                f"[{profile_name}]'s server={server_key!r} catalog entry in "
                f"{effective_servers_path} has no resolvable host/port "
                f"(host={catalog_host!r}, port={catalog_port!r})"
            )
        return catalog_host, catalog_port

    raise ProfileIncomplete(
        f"[{profile_name}] has no resolvable host/port -- set both host= and "
        f"port=, or a valid server= catalog key, in {profiles_path}"
    )


def load_profile_summaries() -> list[dict[str, str | None]]:
    """Non-secret profile rows, or raise (never includes secrets).

    The STRICT half of the pair; :func:`list_profile_summaries` is the
    display half that cannot raise. Callers that render their own failure
    (``player_bank.list_players``) take this one; callers that hand their
    result straight to a screen take the other.

    Raises `ProfileStoreUnreadable` / `ProfileStoreMalformed` when either
    store this listing is built from -- ``profiles.toml`` or the
    ``servers.toml`` catalog -- could not be read, rather than returning a
    shorter list. There is no honest partial listing to fall back on in
    either case. Without ``profiles.toml`` there are no rows at all; without
    the catalog every ``server=`` key fails to resolve and the ``host``
    column silently degrades to the bare catalog key -- a positive claim
    about a host, taken from a file nobody managed to read.

    An empty list means exactly one thing: both stores were read and there
    are no profiles.

    Each row includes ``name``, ``handle``, ``server`` (catalog key or bare host),
    resolved ``host`` (catalog host when ``server`` is a key, else explicit host),
    ``game_letter``, and optional ``error``.
    """
    catalog = _catalog()
    data = _load_toml_store(PROFILES_PATH)
    if data is None:
        return []
    rows: list[dict[str, str | None]] = []
    for name, meta in data.items():
        if not isinstance(meta, dict):
            rows.append(
                {
                    "name": name,
                    "handle": "?",
                    "server": "?",
                    "host": "?",
                    "game_letter": "",
                    "error": "profile section is not a table",
                }
            )
            continue
        game_letter = str(meta.get("game_letter") or "").strip()
        handle = str(meta.get("handle") or "").strip()
        server = str(meta.get("server") or "").strip()
        explicit_host = str(meta.get("host") or "").strip()
        error = None
        if not game_letter:
            error = "missing game_letter"
        elif not server and not (explicit_host and meta.get("port")):
            error = "missing server (catalog key) or host+port"
        elif not handle and not meta.get("allow_register"):
            error = "missing handle"
        display_server = server or explicit_host or "?"
        try:
            # Reuse the shared resolver for the common case; it never
            # raises for a merely-incomplete profile here because this
            # is a *display* row (must not start raising) -- fall back
            # to the legacy lenient lookup for any profile the strict
            # resolver can't (yet) resolve.
            host, _port = resolve_profile_host_port(name)
        except ProfileConnectionError:
            if server and server in catalog:
                host = str(catalog[server].get("host") or server)
            elif explicit_host:
                host = explicit_host
            else:
                host = display_server
        rows.append(
            {
                "name": name,
                "handle": handle or "?",
                "server": display_server,
                "host": host,
                "game_letter": game_letter,
                "autopilot": bool(meta.get("autopilot")),
                "error": error,
            }
        )
    return rows


def _store_failure_row(exc: _StoreReadFailure) -> dict[str, str | None]:
    """Render a store-read failure as one non-launchable diagnostic row.

    Not a profile and not shaped like one: the name is the failing store's
    file name in parentheses (no profile section can be called that -- the
    create path constrains section names to ``[A-Za-z0-9_]+``), every other
    field is this function's own ``?`` unknown marker, and ``error`` is set,
    which is what makes the launcher refuse to launch it and tint it as a
    fault. It invents no host, no handle and no game letter, because none
    were read.

    The row carries ``reason`` and not ``str(exc)``: the exception's text
    appends the full store path, which on an 80-column launcher line would
    push the operator's actual next action off the right edge. Callers that
    want the path have the exception.
    """
    return {
        "name": f"({Path(exc.path).name})",
        "handle": "?",
        "server": "?",
        "host": "?",
        "game_letter": "",
        "autopilot": False,
        "error": f"{exc.cause}: {exc.reason}",
    }


def list_profile_summaries() -> list[dict[str, str | None]]:
    """Non-secret profile rows for the launcher; NEVER raises.

    The display half of the pair (see :func:`load_profile_summaries`). The
    launcher builds its screen straight off this call at startup, before the
    operator can do anything at all, so a raise here is not an error message
    -- it is a dead launcher. Three of the conditions below used to do
    exactly that, and a fourth was worse: an unreadable config directory
    returned ``[]``, which the launcher draws as "no characters yet, create
    one" (WO-AUDIT-CREDENTIALS-LAUNCHER-CRASH).

    A store that could not be read comes back as a single non-launchable
    diagnostic row instead, so the failure is on screen and the empty list
    keeps meaning what it says. The rows are NOT mixed: a listing that
    could not be built is not partially shown -- see
    :func:`load_profile_summaries` for why neither store failure leaves an
    honest partial listing behind.

    An empty list still means exactly one thing: both stores were read and
    there are no profiles.
    """
    try:
        return load_profile_summaries()
    except (ProfileStoreUnreadable, ProfileStoreMalformed) as exc:
        return [_store_failure_row(exc)]


def _profile_section_name(handle: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", handle.strip().lower()).strip("_")
    return slug or "profile"


def create_profile(
    *,
    server: str,
    game_letter: str,
    handle: str,
    name: str | None = None,
) -> str:
    """Append a non-secret profile section to ``config/profiles.toml``.

    Stores a catalog ``server`` key (not a copied host/port). Returns the
    section name written. Never writes a credential field.
    """
    server = server.strip()
    game_letter = game_letter.strip().upper()[:1]
    handle = handle.strip()
    if not server:
        raise ValueError("server catalog key is required")
    if not game_letter:
        raise ValueError("game_letter is required")
    if not handle:
        raise ValueError("handle is required")

    catalog_keys = {str(s["key"]) for s in list_servers()}
    if server not in catalog_keys:
        raise ValueError(f"unknown server catalog key: {server!r}")

    section = name.strip() if name else _profile_section_name(handle)
    if not re.fullmatch(r"[A-Za-z0-9_]+", section):
        raise ValueError(f"invalid profile section name: {section!r}")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = ""
    if PROFILES_PATH.exists():
        existing = PROFILES_PATH.read_text(encoding="utf-8")
        if re.search(rf"^\[{re.escape(section)}\]\s*$", existing, re.M):
            raise ValueError(f"profile already exists: {section}")

    block = (
        f"\n[{section}]\n"
        f'server = "{server}"\n'
        f'game_letter = "{game_letter}"\n'
        f'handle = "{handle}"\n'
        f"allow_register = false\n"
        f"crawl_sacrificial = false\n"
        f"autopilot = false\n"
    )
    if existing and not existing.endswith("\n"):
        existing += "\n"
    PROFILES_PATH.write_text(existing + block, encoding="utf-8")
    return section
