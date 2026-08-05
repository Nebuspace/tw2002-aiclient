"""``tw servers list`` / ``tw probe`` — research-catalog CLI (WO-BUILD-SERVERS-PROBE-CLI-VERBS).

Daemon-free: reads ``config/servers.inventory.json`` (+ optional liveness
sidecar) and optionally writes measured TCP liveness. Never opens the
session socket, never logs in, never spends turns.

Lives outside ``session/cli.py`` for the same reasons ``rules/cli.py`` does —
filesystem/catalog only, and ``session/cli.py`` is already over the line cap.
"""

from __future__ import annotations

import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from tw2002_aiclient.server_inventory import (
    DEFAULT_INVENTORY_PATH,
    DEFAULT_LIVENESS_PATH,
    PLANNING_PROVENANCE,
    endpoint_key,
    live_prove_planning_available,
    load_inventory,
    summarize_inventory,
)

__all__ = [
    "add_catalog_parsers",
    "cmd_probe",
    "cmd_servers_list",
    "format_servers_report",
    "run_catalog_tcp_probe",
    "tcp_probe",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tcp_probe(host: str, port: int, *, timeout_s: float) -> dict[str, Any]:
    """One TCP connect attempt. Never negotiates telnet / never sends."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s):
            return {"tcp_open": True, "error": None}
    except OSError as exc:
        return {"tcp_open": False, "error": type(exc).__name__}


def format_servers_report(summary: Mapping[str, Any]) -> list[str]:
    """Human lines for ``tw servers list`` (no secrets — host:port only)."""
    lines: list[str] = []
    scraped = summary.get("scraped_at_utc") or "?"
    rows = summary.get("row_count")
    plan_n = summary.get("planning_endpoint_count")
    lines.append(f"inventory scraped_at={scraped}  rows={rows}  planning={plan_n}")
    prov = summary.get("provenance")
    if isinstance(prov, Mapping) and prov:
        bits = " ".join(f"{k}={v}" for k, v in prov.items())
        lines.append(f"provenance: {bits}")
    live = summary.get("liveness")
    if isinstance(live, Mapping) and live:
        bits = " ".join(f"{k}={v}" for k, v in live.items())
        lines.append(f"liveness:   {bits}")
    note = summary.get("connectable_note")
    if isinstance(note, str) and note:
        lines.append(f"note: {note}")
    available = live_prove_planning_available(summary)
    lines.append(
        "live-prove planning: "
        + ("available" if available else "unavailable (no planning endpoints)")
    )
    endpoints = summary.get("planning_endpoints")
    if isinstance(endpoints, list) and endpoints:
        lines.append("planning endpoints (name · endpoint · provenance · liveness):")
        for row in endpoints:
            if not isinstance(row, Mapping):
                continue
            name = row.get("name") or "?"
            ep = row.get("endpoint") or "?"
            provenance = row.get("provenance") or "?"
            liveness = row.get("liveness") or "?"
            lines.append(f"  {name}  {ep}  {provenance}  {liveness}")
    return lines


def run_catalog_tcp_probe(
    *,
    inventory_path: Path | None = None,
    out_path: Path | None = None,
    timeout_s: float = 2.0,
    limit: int = 0,
    include_dead: bool = False,
    print_lines: bool = True,
) -> dict[str, Any]:
    """Probe planning endpoints; write liveness sidecar; return payload.

    Same contract as ``scripts/catalog-tcp-probe.py`` — shared so ``tw probe``
    and the script cannot drift.
    """
    inv_path = inventory_path or DEFAULT_INVENTORY_PATH
    out = out_path or DEFAULT_LIVENESS_PATH
    inv = load_inventory(inv_path)
    servers = inv.get("servers") if isinstance(inv.get("servers"), list) else []
    targets: list[tuple[str, int, str]] = []
    seen: set[str] = set()
    for row in servers:
        if not isinstance(row, dict):
            continue
        status = row.get("status")
        if status not in PLANNING_PROVENANCE and not (
            include_dead and status == "dead"
        ):
            continue
        host = row.get("host")
        port = row.get("port")
        if not isinstance(host, str) or not host.strip():
            continue
        if isinstance(port, bool) or not isinstance(port, int) or port <= 0:
            continue
        key = endpoint_key(host, port)
        if key in seen:
            continue
        seen.add(key)
        targets.append((host.strip(), int(port), key))
        if limit > 0 and len(targets) >= limit:
            break

    probed_at = _utc_now()
    hosts: dict[str, dict[str, Any]] = {}
    open_n = 0
    for host, port, key in targets:
        result = tcp_probe(host, port, timeout_s=timeout_s)
        if result["tcp_open"]:
            open_n += 1
        hosts[key] = {
            "tcp_open": result["tcp_open"],
            "error": result["error"],
            "probed_at_utc": probed_at,
        }
        if print_lines:
            flag = "OPEN" if result["tcp_open"] else "FAIL"
            print(f"{flag}\t{key}\t{result['error'] or ''}")

    payload: dict[str, Any] = {
        "probed_at_utc": probed_at,
        "timeout_s": float(timeout_s),
        "method": "tcp_connect_only",
        "notes": (
            "No login, no telnet negotiation, no game turns. "
            "Provenance stays in servers.inventory.json; this file is "
            "measured liveness only."
        ),
        "hosts": hosts,
        "open_count": open_n,
        "target_count": len(targets),
        "out": str(out),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    # Sidecar on disk omits the helper rollup fields used only by the CLI JSON.
    disk = {
        "probed_at_utc": payload["probed_at_utc"],
        "timeout_s": payload["timeout_s"],
        "method": payload["method"],
        "notes": payload["notes"],
        "hosts": hosts,
    }
    out.write_text(json.dumps(disk, indent=2) + "\n", encoding="utf-8")
    if print_lines:
        print(
            f"RESULT: {open_n} / {len(targets)} tcp_open → {out}",
            file=sys.stderr,
        )
    return payload


def cmd_servers_list(args) -> int:
    """``tw servers list`` — summarize inventory + liveness (read-only)."""
    from tw2002_aiclient.session.tty_encode import print_tty

    inv = getattr(args, "inventory", None)
    live = getattr(args, "liveness", None)
    try:
        summary = summarize_inventory(
            inventory_path=Path(inv) if inv else None,
            liveness_path=Path(live) if live else None,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        err = {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
        if getattr(args, "json", False):
            print(json.dumps(err))
        else:
            print_tty(f"servers: could not read inventory — {type(exc).__name__}")
        return 1

    if getattr(args, "json", False):
        print(json.dumps(summary))
    else:
        for line in format_servers_report(summary):
            print_tty(line)
    return 0


def cmd_probe(args) -> int:
    """``tw probe`` — TCP-only catalog probe (writes liveness sidecar)."""
    inv = getattr(args, "inventory", None)
    out = getattr(args, "out", None)
    try:
        payload = run_catalog_tcp_probe(
            inventory_path=Path(inv) if inv else None,
            out_path=Path(out) if out else None,
            timeout_s=float(getattr(args, "timeout", 2.0) or 2.0),
            limit=int(getattr(args, "limit", 0) or 0),
            include_dead=bool(getattr(args, "include_dead", False)),
            print_lines=not bool(getattr(args, "json", False)),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        err = {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
        if getattr(args, "json", False):
            print(json.dumps(err))
        else:
            print(f"probe: failed — {type(exc).__name__}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(payload))
    return 0


def add_catalog_parsers(sub: Any) -> None:
    """Register ``servers`` and ``probe`` on the root ``tw`` subparsers."""
    sp_servers = sub.add_parser(
        "servers",
        help="research catalog: list inventory + measured liveness (read-only)",
    )
    servers_sub = sp_servers.add_subparsers(dest="servers_verb")
    sp_list = servers_sub.add_parser(
        "list",
        help="summarize config/servers.inventory.json (+ liveness sidecar)",
    )
    sp_list.add_argument(
        "--inventory",
        default=None,
        metavar="PATH",
        help="inventory JSON override",
    )
    sp_list.add_argument(
        "--liveness",
        default=None,
        metavar="PATH",
        help="liveness sidecar JSON override",
    )
    sp_list.add_argument("--json", action="store_true", help="machine-parseable JSON")
    sp_list.set_defaults(func=cmd_servers_list)

    sp_probe = sub.add_parser(
        "probe",
        help="TCP-only catalog probe (no login / no turns); writes liveness sidecar",
    )
    sp_probe.add_argument(
        "--inventory",
        default=None,
        metavar="PATH",
        help="inventory JSON override",
    )
    sp_probe.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help="liveness sidecar output path",
    )
    sp_probe.add_argument("--timeout", type=float, default=2.0)
    sp_probe.add_argument(
        "--limit",
        type=int,
        default=0,
        help="max endpoints to probe (0 = all planning provenance)",
    )
    sp_probe.add_argument(
        "--include-dead",
        action="store_true",
        help="also probe inventory status=dead rows",
    )
    sp_probe.add_argument("--json", action="store_true", help="machine-parseable JSON")
    sp_probe.set_defaults(func=cmd_probe)
