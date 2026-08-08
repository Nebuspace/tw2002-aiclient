"""``tw port-floor`` — snapshot / analyze port floor-price observations.

Filesystem only: reads world-model sector JSON and/or the observation
JSONL store, never opens a session socket, never sends. Lives outside
``session/cli.py`` for the same line-cap reason as ``mine_cli``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tw2002_aiclient import port_floor_capture as pfc

__all__ = ["add_port_floor_parsers", "cmd_port_floor_snapshot", "cmd_port_floor_analyze"]


def _store_path(args: argparse.Namespace) -> Path:
    raw = getattr(args, "store", None)
    if raw:
        return Path(raw)
    return pfc.default_observations_path()


def cmd_port_floor_snapshot(args: argparse.Namespace) -> int:
    """Ingest a world directory's port records into the observation store."""
    world_dir = Path(args.world_dir)
    if not world_dir.exists():
        print(f"error: world dir not found: {world_dir}")
        return 2
    obs = pfc.observations_from_world_dir(world_dir)
    store = _store_path(args)
    n = pfc.append_observations(store, obs)
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "ok": True,
                    "world_dir": str(world_dir),
                    "store": str(store),
                    "observations": n,
                    "world_id": getattr(args, "world_id", None),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        wid = getattr(args, "world_id", None)
        label = f" world_id={wid}" if wid else ""
        print(f"snapshot{label} observations={n} store={store}")
    return 0


def cmd_port_floor_analyze(args: argparse.Namespace) -> int:
    """Run analyze_port_history over the observation store."""
    store = _store_path(args)
    obs = pfc.load_observations(store)
    report = pfc.analyze_port_history(obs)
    if getattr(args, "json", False):
        payload = {
            "ok": True,
            "store": str(store),
            "observation_count": len(obs),
            "regrowth": [
                {
                    "sector_id": e.identity.sector_id,
                    "port_id": e.identity.port_id,
                    "commodity": e.identity.commodity,
                    "pct_per_day": e.pct_per_day,
                    "sample_count": e.sample_count,
                    "tag": e.tag,
                    "verified_vs_live": e.verified_vs_live,
                }
                for e in report.regrowth.values()
            ],
            "floor_price": [
                {
                    "sector_id": e.identity.sector_id,
                    "port_id": e.identity.port_id,
                    "commodity": e.identity.commodity,
                    "floor_price": e.floor_price,
                    "slope": e.slope,
                    "sample_count": e.sample_count,
                    "tag": e.tag,
                    "verified_vs_live": e.verified_vs_live,
                }
                for e in report.floor_price.values()
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(
        f"observations={len(obs)} regrowth={len(report.regrowth)} "
        f"floor_price={len(report.floor_price)} store={store}"
    )
    for e in report.regrowth.values():
        print(
            f"  regrowth sector={e.identity.sector_id} {e.identity.commodity} "
            f"pct/day={e.pct_per_day:.4f} n={e.sample_count} "
            f"verified_vs_live={e.verified_vs_live}"
        )
    for e in report.floor_price.values():
        print(
            f"  floor sector={e.identity.sector_id} {e.identity.commodity} "
            f"floor={e.floor_price:.4f} n={e.sample_count} "
            f"verified_vs_live={e.verified_vs_live}"
        )
    return 0


def add_port_floor_parsers(sub: argparse._SubParsersAction) -> None:
    """Register ``tw port-floor {snapshot,analyze}``."""
    sp = sub.add_parser(
        "port-floor",
        help="port floor-price / regrowth observation store (filesystem only; never sends)",
    )
    sp_sub = sp.add_subparsers(dest="port_floor_verb")

    sp_snap = sp_sub.add_parser(
        "snapshot",
        help="ingest world-model sector JSON into the observation JSONL store",
    )
    sp_snap.add_argument(
        "--world-dir",
        required=True,
        metavar="PATH",
        help="path to a world directory (.../state/world/<world_id>)",
    )
    sp_snap.add_argument(
        "--store",
        default=None,
        metavar="PATH",
        help="observation JSONL path (default: state/port_floor_observations.jsonl)",
    )
    sp_snap.add_argument(
        "--world-id",
        default=None,
        metavar="SLUG",
        help="optional label printed in human output / JSON",
    )
    sp_snap.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp_snap.set_defaults(func=cmd_port_floor_snapshot)

    sp_an = sp_sub.add_parser(
        "analyze",
        help="run regrowth/floor analysis over the observation store",
    )
    sp_an.add_argument(
        "--store",
        default=None,
        metavar="PATH",
        help="observation JSONL path (default: state/port_floor_observations.jsonl)",
    )
    sp_an.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp_an.set_defaults(func=cmd_port_floor_analyze)
