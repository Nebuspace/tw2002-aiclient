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
CONFIG_DIR = PROJECT_ROOT / "config"
SECRETS_PATH = CONFIG_DIR / "secrets.json"
PROFILES_PATH = CONFIG_DIR / "profiles.toml"
SERVERS_PATH = CONFIG_DIR / "servers.toml"


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


def list_servers() -> list[dict[str, object]]:
    """Return catalog rows from ``config/servers.toml`` (key, name, host, port)."""
    if not SERVERS_PATH.exists():
        return []
    with open(SERVERS_PATH, "rb") as f:
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


def list_profile_summaries() -> list[dict[str, str | None]]:
    """Yield non-secret profile rows for the launcher (never includes secrets).

    Each row includes ``name``, ``handle``, ``server`` (catalog key or bare host),
    resolved ``host`` (catalog host when ``server`` is a key, else explicit host),
    ``game_letter``, and optional ``error``.
    """
    catalog = {str(s["key"]): s for s in list_servers()}
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
