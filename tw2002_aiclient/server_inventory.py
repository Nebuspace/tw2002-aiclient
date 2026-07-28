"""Research inventory loader — provenance vs TCP liveness (WO-CATALOG-SOURCE-LIVENESS-SPLIT).

``config/servers.inventory.json`` ``status`` is **listing provenance**
(``listed`` / ``listed_bbsguide`` / ``archive_seed`` / ``dead`` graveyard
sample). It is **not** reachability.

Optional measured liveness lives in ``config/servers.liveness.json``
(written by ``scripts/catalog-tcp-probe.py``) and/or per-row
``liveness`` + ``last_probed_utc`` fields on an inventory row when present.

There is **no** ``connectable`` aggregate derived from provenance — that
name was how live-prove planning falsely read ``connectable: 0`` as
"no TWGS".
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

# Provenance vocabulary on inventory ``status`` (directory signal, not TCP).
PROVENANCE_STATUSES = frozenset(
    {"listed", "listed_bbsguide", "archive_seed", "dead"}
)
# Directory-active listings an operator might try (not graveyard-only).
PLANNING_PROVENANCE = frozenset({"listed", "listed_bbsguide", "archive_seed"})

LIVENESS_UNPROBED = "unprobed"
LIVENESS_TCP_OPEN = "tcp_open"
LIVENESS_TCP_CLOSED = "tcp_closed"
LIVENESS_UNREACHABLE = "unreachable"

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY_PATH = _REPO_ROOT / "config" / "servers.inventory.json"
DEFAULT_LIVENESS_PATH = _REPO_ROOT / "config" / "servers.liveness.json"


def endpoint_key(host: object, port: object) -> str:
    h = str(host or "").strip().lower()
    try:
        p = int(port)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        p = 0
    return f"{h}:{p}"


def load_inventory(path: Path | None = None) -> dict[str, Any]:
    """Load the research inventory JSON. Raises on missing/malformed file."""
    inv_path = path or DEFAULT_INVENTORY_PATH
    raw = json.loads(inv_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"inventory root must be an object: {inv_path}")
    servers = raw.get("servers")
    if not isinstance(servers, list):
        raise ValueError(f"inventory.servers must be a list: {inv_path}")
    return raw


def load_liveness_sidecar(path: Path | None = None) -> dict[str, Any]:
    """Load optional TCP-probe sidecar; absent file → empty hosts map."""
    live_path = path or DEFAULT_LIVENESS_PATH
    if not live_path.is_file():
        return {"hosts": {}}
    raw = json.loads(live_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {"hosts": {}}
    hosts = raw.get("hosts")
    if not isinstance(hosts, dict):
        raw = dict(raw)
        raw["hosts"] = {}
        return raw
    return raw


def _row_provenance(row: Mapping[str, Any]) -> str:
    status = row.get("status")
    if isinstance(status, str) and status:
        return status
    return "unknown"


def _row_liveness(
    row: Mapping[str, Any],
    *,
    sidecar_hosts: Mapping[str, Any],
) -> tuple[str, str | None]:
    """Return ``(liveness_token, last_probed_utc|None)``.

    Precedence: explicit row fields, then sidecar by endpoint key, else
    ``unprobed``.
    """
    probed = row.get("last_probed_utc")
    probed_s = probed if isinstance(probed, str) and probed else None
    live = row.get("liveness")
    if isinstance(live, str) and live:
        return live, probed_s

    key = endpoint_key(row.get("host"), row.get("port"))
    side = sidecar_hosts.get(key)
    if isinstance(side, dict):
        side_probed = side.get("probed_at_utc")
        if isinstance(side_probed, str) and side_probed:
            probed_s = side_probed
        if side.get("tcp_open") is True:
            return LIVENESS_TCP_OPEN, probed_s
        if side.get("tcp_open") is False:
            err = side.get("error")
            if isinstance(err, str) and "timeout" in err.lower():
                return LIVENESS_UNREACHABLE, probed_s
            return LIVENESS_TCP_CLOSED, probed_s
    return LIVENESS_UNPROBED, probed_s


def summarize_inventory(
    inventory: Mapping[str, Any] | None = None,
    *,
    inventory_path: Path | None = None,
    liveness_path: Path | None = None,
) -> dict[str, Any]:
    """Split provenance counts from measured liveness.

    Never emits ``connectable`` derived from provenance. Live-prove planning
    should use ``planning_endpoints`` (directory-active rows), not a
    provenance-only reachability fiction.
    """
    inv = inventory if inventory is not None else load_inventory(inventory_path)
    side = load_liveness_sidecar(liveness_path)
    hosts_side = side.get("hosts") if isinstance(side.get("hosts"), dict) else {}

    provenance: Counter[str] = Counter()
    liveness: Counter[str] = Counter()
    planning: list[dict[str, Any]] = []
    servers = inv.get("servers") if isinstance(inv.get("servers"), list) else []

    for row in servers:
        if not isinstance(row, Mapping):
            continue
        prov = _row_provenance(row)
        provenance[prov] += 1
        live_tok, probed = _row_liveness(row, sidecar_hosts=hosts_side)
        liveness[live_tok] += 1
        if prov in PLANNING_PROVENANCE:
            planning.append(
                {
                    "name": row.get("name"),
                    "host": row.get("host"),
                    "port": row.get("port"),
                    "provenance": prov,
                    "liveness": live_tok,
                    "last_probed_utc": probed,
                    "endpoint": endpoint_key(row.get("host"), row.get("port")),
                }
            )

    return {
        "scraped_at_utc": inv.get("scraped_at_utc"),
        "row_count": sum(provenance.values()),
        "provenance": dict(sorted(provenance.items())),
        "liveness": dict(sorted(liveness.items())),
        "planning_endpoints": planning,
        "planning_endpoint_count": len(planning),
        # Explicit: do not invent a connectable rollup from provenance.
        "connectable_note": (
            "absent — do not derive reachability from provenance; "
            "use liveness.tcp_open or run scripts/catalog-tcp-probe.py"
        ),
    }


def live_prove_planning_available(summary: Mapping[str, Any]) -> bool:
    """True when directory-active endpoints exist for live-prove sizing.

    Unprobed / unreachable liveness must **not** collapse this to false —
    that was the ``connectable: 0`` defect.
    """
    count = summary.get("planning_endpoint_count")
    if isinstance(count, int):
        return count > 0
    endpoints = summary.get("planning_endpoints")
    return isinstance(endpoints, list) and len(endpoints) > 0
