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
    """
    path = path or SERVERS_PATH
    if not path.exists():
        return []
    with open(path, "rb") as f:
        data = tomllib.load(f)
    servers = data.get("servers") or {}
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
    for exactly which subtype each failure kind raises.
    """
    profiles_path = profiles_path or PROFILES_PATH
    if not profiles_path.exists():
        raise ProfileNotFound(f"{profiles_path} does not exist")
    try:
        with open(profiles_path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ProfileMalformed(f"{profiles_path} is not valid TOML ({e})") from e
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


def list_profile_summaries() -> list[dict[str, str | None]]:
    """Yield non-secret profile rows for the launcher (never includes secrets).

    Each row includes ``name``, ``handle``, ``server`` (catalog key or bare host),
    resolved ``host`` (catalog host when ``server`` is a key, else explicit host),
    ``game_letter``, and optional ``error``.
    """
    catalog = _catalog()
    if not PROFILES_PATH.exists():
        return []
    with open(PROFILES_PATH, "rb") as f:
        data = tomllib.load(f)
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
