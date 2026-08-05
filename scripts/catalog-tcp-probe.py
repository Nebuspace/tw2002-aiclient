#!/usr/bin/env python3
"""Safe one-shot TCP probe for catalog endpoints (no game turns / no login).

Writes ``config/servers.liveness.json`` only — never secrets, never a
protocol exchange. Public-repo safe: host:port only.

Thin wrapper around :func:`tw2002_aiclient.catalog_cli.run_catalog_tcp_probe`
so ``tw probe`` and this script cannot drift.

Usage (from repo root)::

    .venv/bin/python scripts/catalog-tcp-probe.py
    .venv/bin/python scripts/catalog-tcp-probe.py --limit 14 --timeout 2
    ./tw probe --limit 14
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tw2002_aiclient.catalog_cli import run_catalog_tcp_probe  # noqa: E402
from tw2002_aiclient.server_inventory import (  # noqa: E402
    DEFAULT_INVENTORY_PATH,
    DEFAULT_LIVENESS_PATH,
)


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
    try:
        run_catalog_tcp_probe(
            inventory_path=args.inventory,
            out_path=args.out,
            timeout_s=args.timeout,
            limit=args.limit,
            include_dead=args.include_dead,
            print_lines=True,
        )
    except (OSError, ValueError) as exc:
        print(f"probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
