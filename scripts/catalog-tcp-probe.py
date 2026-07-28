#!/usr/bin/env python3
"""Safe one-shot TCP probe for catalog endpoints (no game turns / no login).

Writes ``config/servers.liveness.json`` only — never secrets, never a
protocol exchange. Public-repo safe: host:port only.

Usage (from repo root)::

    .venv/bin/python scripts/catalog-tcp-probe.py
    .venv/bin/python scripts/catalog-tcp-probe.py --limit 14 --timeout 2
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tw2002_aiclient.server_inventory import (  # noqa: E402
    DEFAULT_INVENTORY_PATH,
    DEFAULT_LIVENESS_PATH,
    PLANNING_PROVENANCE,
    endpoint_key,
    load_inventory,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tcp_probe(host: str, port: int, *, timeout_s: float) -> dict:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s):
            return {"tcp_open": True, "error": None}
    except OSError as exc:
        return {"tcp_open": False, "error": type(exc).__name__}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="TCP-only catalog probe (no login / no turns)."
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY_PATH,
        help="path to servers.inventory.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_LIVENESS_PATH,
        help="liveness sidecar JSON to write",
    )
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="max endpoints to probe (0 = all planning provenance)",
    )
    parser.add_argument(
        "--include-dead",
        action="store_true",
        help="also probe inventory status=dead rows",
    )
    args = parser.parse_args(argv)

    inv = load_inventory(args.inventory)
    servers = inv.get("servers") if isinstance(inv.get("servers"), list) else []
    targets: list[tuple[str, int, str]] = []
    seen: set[str] = set()
    for row in servers:
        if not isinstance(row, dict):
            continue
        status = row.get("status")
        if status not in PLANNING_PROVENANCE and not (
            args.include_dead and status == "dead"
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
        if args.limit > 0 and len(targets) >= args.limit:
            break

    probed_at = _utc_now()
    hosts: dict[str, dict] = {}
    open_n = 0
    for host, port, key in targets:
        result = tcp_probe(host, port, timeout_s=args.timeout)
        if result["tcp_open"]:
            open_n += 1
        hosts[key] = {
            "tcp_open": result["tcp_open"],
            "error": result["error"],
            "probed_at_utc": probed_at,
        }
        flag = "OPEN" if result["tcp_open"] else "FAIL"
        print(f"{flag}\t{key}\t{result['error'] or ''}")

    payload = {
        "probed_at_utc": probed_at,
        "timeout_s": float(args.timeout),
        "method": "tcp_connect_only",
        "notes": (
            "No login, no telnet negotiation, no game turns. "
            "Provenance stays in servers.inventory.json; this file is "
            "measured liveness only."
        ),
        "hosts": hosts,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"RESULT: {open_n} / {len(targets)} tcp_open → {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
