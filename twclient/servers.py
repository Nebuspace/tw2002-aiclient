"""Server catalog — WO-MS-1.

Loads `config/servers.toml` (keyed tables under `[servers.<key>]`).
Profiles may reference a server by key; host/port stay optional then.
No live connections — catalog is directory data only.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
SERVERS_PATH = CONFIG_DIR / "servers.toml"

FRONT_ENDS = frozenset({"direct", "bbs", "auto"})
TRANSPORTS = frozenset({"telnet", "ssl-telnet", "ssh", "rlogin", "ws"})
STATUSES = frozenset({"listed", "online", "offline", "unverified"})


class ServerCatalogError(Exception):
    """Malformed / missing server catalog entry."""


def _load_toml(path: Path) -> dict:
    if not path.exists():
        raise ServerCatalogError(f"servers_catalog_missing:{path}")
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_servers(path=None) -> dict:
    """Return {key: record_dict} for every `[servers.*]` entry."""
    data = _load_toml(Path(path) if path is not None else SERVERS_PATH)
    raw = data.get("servers") or {}
    if not isinstance(raw, dict):
        raise ServerCatalogError("servers_catalog_invalid:expected_table")
    out = {}
    for key, rec in raw.items():
        if not isinstance(rec, dict):
            raise ServerCatalogError(f"servers_catalog_invalid:{key}")
        out[key] = _normalize(key, rec)
    return out


def _normalize(key: str, rec: dict) -> dict:
    hostname = rec.get("hostname")
    if not hostname or not str(hostname).strip():
        raise ServerCatalogError(f"server_incomplete:{key}:missing=hostname")
    if "port" not in rec:
        raise ServerCatalogError(f"server_incomplete:{key}:missing=port")
    try:
        port = int(rec["port"])
    except (TypeError, ValueError) as e:
        raise ServerCatalogError(f"server_bad_port:{key}:{rec.get('port')!r}") from e
    front_end = str(rec.get("front_end") or "auto")
    if front_end not in FRONT_ENDS:
        raise ServerCatalogError(f"server_bad_front_end:{key}:{front_end}")
    transport = str(rec.get("transport") or "telnet")
    if transport not in TRANSPORTS:
        raise ServerCatalogError(f"server_bad_transport:{key}:{transport}")
    status = str(rec.get("status") or "listed")
    if status not in STATUSES:
        raise ServerCatalogError(f"server_bad_status:{key}:{status}")
    return {
        "key": key,
        "hostname": str(hostname).strip(),
        "port": port,
        "transport": transport,
        "front_end": front_end,
        "aliases": list(rec.get("aliases") or []),
        "operator": rec.get("operator"),
        "games": list(rec.get("games") or []) if isinstance(rec.get("games"), list) else rec.get("games"),
        "status": status,
        "last_checked_at": rec.get("last_checked_at"),
        "sources": list(rec.get("sources") or []),
        "notes": rec.get("notes") or "",
    }


def get_server(key: str, path=None) -> dict:
    servers = load_servers(path=path)
    if key not in servers:
        raise ServerCatalogError(f"server_not_found:{key}")
    return servers[key]


def resolve_endpoint(server_key: str, path=None) -> tuple[str, int]:
    """(hostname, port) for a catalog key."""
    rec = get_server(server_key, path=path)
    return rec["hostname"], rec["port"]


def list_servers(path=None) -> list[dict]:
    """Sorted list of normalized server records (for `tw servers list`)."""
    servers = load_servers(path=path)
    return [servers[k] for k in sorted(servers)]
