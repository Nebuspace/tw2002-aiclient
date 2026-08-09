"""``tw planet-colonization`` — snapshot / analyze planet production observations.

Filesystem only: reads planet record JSON and/or the observation JSONL store,
never opens a session socket, never sends. Lives outside ``session/cli.py`` for
the same line-cap reason as ``port_floor_cli`` / ``mine_cli``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tw2002_aiclient import planet_colonization_capture as pcc

__all__ = [
    "add_planet_colonization_parsers",
    "cmd_planet_colonization_snapshot",
    "cmd_planet_colonization_analyze",
]


def _store_path(args: argparse.Namespace) -> Path:
    raw = getattr(args, "store", None)
    if raw:
        return Path(raw)
    return pcc.default_observations_path()


def cmd_planet_colonization_snapshot(args: argparse.Namespace) -> int:
    """Ingest a planet directory's records into the observation store."""
    planet_dir = Path(args.planet_dir)
    if not planet_dir.exists():
        print(f"error: planet dir not found: {planet_dir}")
        return 2
    obs = pcc.observations_from_planet_dir(planet_dir)
    store = _store_path(args)
    n = pcc.append_observations(store, obs)
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "ok": True,
                    "planet_dir": str(planet_dir),
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


def cmd_planet_colonization_analyze(args: argparse.Namespace) -> int:
    """Run analyze_planet_history over the observation store."""
    store = _store_path(args)
    obs = pcc.load_observations(store)
    report = pcc.analyze_planet_history(obs)
    if getattr(args, "json", False):
        payload = {
            "ok": True,
            "store": str(store),
            "observation_count": len(obs),
            "stored_cargo_bonus": [
                {
                    "sector_id": e.identity.sector_id,
                    "planet_id": e.identity.planet_id,
                    "bonus_per_unit": e.bonus_per_unit,
                    "intercept": e.intercept,
                    "sample_count": e.sample_count,
                    "tag": e.tag,
                    "verified_vs_live": e.verified_vs_live,
                }
                for e in report.stored_cargo_bonus.values()
            ],
            "compounding": [
                {
                    "sector_id": e.identity.sector_id,
                    "planet_id": e.identity.planet_id,
                    "fraction_per_day": e.fraction_per_day,
                    "sample_count": e.sample_count,
                    "tag": e.tag,
                    "verified_vs_live": e.verified_vs_live,
                }
                for e in report.compounding.values()
            ],
            "buy_production": [
                {
                    "sector_id": e.identity.sector_id,
                    "planet_id": e.identity.planet_id,
                    "median_price": e.median_price,
                    "min_price": e.min_price,
                    "max_price": e.max_price,
                    "sample_count": e.sample_count,
                    "tag": e.tag,
                    "verified_vs_live": e.verified_vs_live,
                }
                for e in report.buy_production.values()
            ],
            "plague_band": [
                {
                    "sector_id": e.identity.sector_id,
                    "planet_id": e.identity.planet_id,
                    "min_loss_pct": e.min_loss_pct,
                    "max_loss_pct": e.max_loss_pct,
                    "sample_count": e.sample_count,
                    "tag": e.tag,
                    "verified_vs_live": e.verified_vs_live,
                }
                for e in report.plague_band.values()
            ],
            "gf_growth": [
                {
                    "sector_id": e.identity.sector_id,
                    "planet_id": e.identity.planet_id,
                    "gf_per_min_at_zero_credits": e.gf_per_min_at_zero_credits,
                    "gf_per_min_per_credit": e.gf_per_min_per_credit,
                    "sample_count": e.sample_count,
                    "tag": e.tag,
                    "verified_vs_live": e.verified_vs_live,
                }
                for e in report.gf_growth.values()
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(
        f"observations={len(obs)} "
        f"stored_cargo_bonus={len(report.stored_cargo_bonus)} "
        f"compounding={len(report.compounding)} "
        f"buy_production={len(report.buy_production)} "
        f"plague_band={len(report.plague_band)} "
        f"gf_growth={len(report.gf_growth)} store={store}"
    )
    for e in report.stored_cargo_bonus.values():
        print(
            f"  cargo_bonus sector={e.identity.sector_id} "
            f"bonus/unit={e.bonus_per_unit:.6f} n={e.sample_count} "
            f"verified_vs_live={e.verified_vs_live}"
        )
    for e in report.compounding.values():
        print(
            f"  compounding sector={e.identity.sector_id} "
            f"fraction/day={e.fraction_per_day:.6f} n={e.sample_count} "
            f"verified_vs_live={e.verified_vs_live}"
        )
    for e in report.buy_production.values():
        print(
            f"  buy_production sector={e.identity.sector_id} "
            f"median={e.median_price:.4f} n={e.sample_count} "
            f"verified_vs_live={e.verified_vs_live}"
        )
    for e in report.plague_band.values():
        print(
            f"  plague_band sector={e.identity.sector_id} "
            f"min={e.min_loss_pct:.2f}% max={e.max_loss_pct:.2f}% n={e.sample_count} "
            f"verified_vs_live={e.verified_vs_live}"
        )
    for e in report.gf_growth.values():
        print(
            f"  gf_growth sector={e.identity.sector_id} "
            f"slope={e.gf_per_min_per_credit:.9f} n={e.sample_count} "
            f"verified_vs_live={e.verified_vs_live}"
        )
    return 0


def add_planet_colonization_parsers(sub: argparse._SubParsersAction) -> None:
    """Register ``tw planet-colonization {snapshot,analyze}``."""
    sp = sub.add_parser(
        "planet-colonization",
        help="planet production observation store (filesystem only; never sends)",
    )
    sp_sub = sp.add_subparsers(dest="planet_colonization_verb")

    sp_snap = sp_sub.add_parser(
        "snapshot",
        help="ingest planet record JSON into the observation JSONL store",
    )
    sp_snap.add_argument(
        "--planet-dir",
        required=True,
        metavar="PATH",
        help="path to a planet records directory",
    )
    sp_snap.add_argument(
        "--store",
        default=None,
        metavar="PATH",
        help="observation JSONL path (default: state/planet_colonization_observations.jsonl)",
    )
    sp_snap.add_argument(
        "--world-id",
        default=None,
        metavar="SLUG",
        help="optional label printed in human output / JSON",
    )
    sp_snap.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp_snap.set_defaults(func=cmd_planet_colonization_snapshot)

    sp_an = sp_sub.add_parser(
        "analyze",
        help="run production hypothesis analysis over the observation store",
    )
    sp_an.add_argument(
        "--store",
        default=None,
        metavar="PATH",
        help="observation JSONL path (default: state/planet_colonization_observations.jsonl)",
    )
    sp_an.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp_an.set_defaults(func=cmd_planet_colonization_analyze)
