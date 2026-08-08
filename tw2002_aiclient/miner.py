"""Candidate mining — deterministic drafts from the trace ledger (PWO-095).

Canon concept id: ``candidate_mining`` (see also
``tw2002_aiclient.candidate_mining`` facade). Spec:
``canon/engine/candidate-mining.md``. Pure read of ledger JSONL + pure write
of inert drafts under ``state/skills/_drafts/`` via ``loops.store.drafts_dir``.
Never imports session/protocol/connection — never touches the live wire.

Ranks candidates to *propose*; does not score a live action to play.
Promotion is the existing skills ``_drafts/`` → blessed-store location gate
(human-only); this module never auto-promotes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import defaultdict
from contextlib import suppress
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from tw2002_aiclient.ledger import REDACTED, read_entries
from tw2002_aiclient.loops.store import drafts_dir

_MIN_WINDOW = 2
_MAX_WINDOW = 10
_DEFAULT_MIN_SUPPORT = 2
_DEFAULT_TOP_K = 3

_NUMERIC_RE = re.compile(r"^\d[\d,]*$")
_STEM_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _normalize_input(text: Any) -> Any:
    if isinstance(text, str) and _NUMERIC_RE.match(text):
        return "<NUM>"
    return text


def _turns_spent(entry: Mapping[str, Any]) -> Optional[int]:
    d = (entry.get("reward") or {}).get("d_turns")
    if d is None:
        return None
    return max(-int(d), 0)


def _credits_delta(entry: Mapping[str, Any]) -> int:
    return int((entry.get("reward") or {}).get("d_credits") or 0)


def mine_patterns(
    entries: Sequence[Mapping[str, Any]] | None = None,
    *,
    min_support: int = _DEFAULT_MIN_SUPPORT,
    min_window: int = _MIN_WINDOW,
    max_window: int = _MAX_WINDOW,
    ledger_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Slide windows over the ledger; rank recurring patterns by cr/turn."""
    if entries is None:
        entries = read_entries(ledger_path)
    groups: dict[tuple[Any, tuple[Any, ...], Any], list[dict[str, Any]]] = defaultdict(list)

    for window in range(min_window, max_window + 1):
        for start in range(0, len(entries) - window + 1):
            chunk = list(entries[start : start + window])
            raw_inputs = tuple(e.get("input") for e in chunk)
            if any(i == REDACTED for i in raw_inputs):
                continue
            inputs = tuple(_normalize_input(i) for i in raw_inputs)
            pre_class = entries[start - 1].get("settled_class") if start > 0 else None
            post_class = chunk[-1].get("settled_class")
            d_credits_total = sum(_credits_delta(e) for e in chunk)
            turns_list = [t for t in (_turns_spent(e) for e in chunk) if t is not None]
            turns_total = sum(turns_list) if turns_list else None
            groups[(pre_class, inputs, post_class)].append(
                {
                    "d_credits": d_credits_total,
                    "turns_spent": turns_total,
                    "start_anchor": (chunk[0].get("pre_state") or {}).get("sector"),
                    "steps": [
                        {
                            "input": e.get("input"),
                            "wait_prompt": None,
                            "expected_post_class": e.get("settled_class"),
                        }
                        for e in chunk
                    ],
                }
            )

    patterns: list[dict[str, Any]] = []
    for (pre_class, inputs, post_class), occurrences in groups.items():
        support = len(occurrences)
        if support < min_support:
            continue
        avg_credits = sum(o["d_credits"] for o in occurrences) / support
        turn_occurrences = [o for o in occurrences if o["turns_spent"]]
        cr_per_turn = (
            sum(o["d_credits"] / o["turns_spent"] for o in turn_occurrences)
            / len(turn_occurrences)
            if turn_occurrences
            else None
        )
        cr_per_action = avg_credits / len(inputs) if inputs else 0.0
        patterns.append(
            {
                "pre_class": pre_class,
                "inputs": list(inputs),
                "post_class": post_class,
                "support": support,
                "cr_per_turn": cr_per_turn,
                "cr_per_action": cr_per_action,
                "sample_steps": occurrences[0]["steps"],
                "start_anchor": occurrences[0]["start_anchor"],
            }
        )

    patterns.sort(
        key=lambda p: (
            p["cr_per_turn"] if p["cr_per_turn"] is not None else float("-inf"),
            p["cr_per_action"],
        ),
        reverse=True,
    )
    return patterns


def _sanitize_stem(name: str) -> str:
    stem = _STEM_UNSAFE_RE.sub("_", name).strip("_-")
    if not stem:
        stem = "mined"
    return stem[:80]


def _atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
        os.chmod(tmp_path, 0o600)
        os.replace(str(tmp_path), str(path))
        os.chmod(path, 0o600)
    except Exception:
        with suppress(OSError):
            tmp_path.unlink()
        raise


def write_mined_draft(
    name: str,
    steps: Sequence[Mapping[str, Any]],
    *,
    mined_stats: Mapping[str, Any],
    start_anchor: int | None,
    drafts_path: str | Path | None = None,
    state_dir: str | Path | None = None,
    world_id: str | None = None,
) -> Path:
    """Write an inert mined draft — never to the blessed skills tree."""
    from tw2002_aiclient.loops.store import migrate_flat_loops_to_world

    if drafts_path is None and world_id is not None and str(world_id).strip():
        migrate_flat_loops_to_world(str(world_id).strip(), state_dir=state_dir)
    directory = (
        Path(drafts_path)
        if drafts_path is not None
        else drafts_dir(state_dir, world_id=world_id)
    )
    document = {
        "name": name,
        "source": "mined",
        "start_anchor": start_anchor,
        "created_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mined_stats": dict(mined_stats),
        "steps": [dict(s) for s in steps],
    }
    path = directory / f"{_sanitize_stem(name)}.json"
    _atomic_write_json(path, document)
    return path


def propose_drafts(
    patterns: Sequence[Mapping[str, Any]],
    *,
    top_k: int = _DEFAULT_TOP_K,
    drafts_dir_path: str | Path | None = None,
    state_dir: str | Path | None = None,
    world_id: str | None = None,
) -> list[dict[str, Any]]:
    """Write top profitable patterns as inert drafts (never auto-promote)."""
    proposed: list[dict[str, Any]] = []
    profitable = [
        p
        for p in patterns
        if (p.get("cr_per_turn") or 0) > 0 or (p.get("cr_per_action") or 0) > 0
    ]
    for i, pattern in enumerate(profitable[:top_k]):
        slug = "_".join(str(x) for x in pattern["inputs"]) or "empty"
        safe_slug = "".join(c if c.isalnum() else "_" for c in slug)[:40]
        name = f"mined-{i}-{safe_slug}"
        path = write_mined_draft(
            name,
            pattern["sample_steps"],
            mined_stats={
                "pre_class": pattern["pre_class"],
                "post_class": pattern["post_class"],
                "support": pattern["support"],
                "cr_per_turn": pattern["cr_per_turn"],
                "cr_per_action": pattern["cr_per_action"],
            },
            start_anchor=pattern.get("start_anchor"),
            drafts_path=drafts_dir_path,
            state_dir=state_dir,
            world_id=world_id,
        )
        proposed.append({"name": name, "path": str(path), **dict(pattern)})
    return proposed


def mine_ledger(
    *,
    min_support: int = _DEFAULT_MIN_SUPPORT,
    top_k: int = _DEFAULT_TOP_K,
    entries: Sequence[Mapping[str, Any]] | None = None,
    propose: bool = True,
    ledger_path: str | Path | None = None,
    drafts_dir_path: str | Path | None = None,
    state_dir: str | Path | None = None,
    world_id: str | None = None,
) -> dict[str, Any]:
    """Mine + optionally propose inert drafts. Never promotes / never sends."""
    patterns = mine_patterns(
        entries=entries, min_support=min_support, ledger_path=ledger_path
    )
    drafts = (
        propose_drafts(
            patterns,
            top_k=top_k,
            drafts_dir_path=drafts_dir_path,
            state_dir=state_dir,
            world_id=world_id,
        )
        if propose
        else []
    )
    return {"patterns": patterns, "drafts": drafts}


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run candidate mining over a ledger JSONL (never live)."
    )
    parser.add_argument("--ledger", required=True, help="Path to ledger.jsonl")
    parser.add_argument(
        "--drafts",
        required=True,
        help="Directory for inert drafts (state/skills/_drafts)",
    )
    parser.add_argument("--min-support", type=int, default=_DEFAULT_MIN_SUPPORT)
    parser.add_argument("--top-k", type=int, default=_DEFAULT_TOP_K)
    parser.add_argument(
        "--no-propose",
        action="store_true",
        help="Rank only — do not write draft files",
    )
    args = parser.parse_args(argv)
    result = mine_ledger(
        min_support=args.min_support,
        top_k=args.top_k,
        ledger_path=args.ledger,
        drafts_dir_path=args.drafts,
        propose=not args.no_propose,
    )
    print(f"patterns={len(result['patterns'])} drafts={len(result['drafts'])}")
    for d in result["drafts"]:
        print(
            f"  draft {d['name']} support={d['support']} "
            f"cr/turn={d['cr_per_turn']} path={d['path']}"
        )
    for p in result["patterns"][:5]:
        print(
            f"  pattern inputs={p['inputs']} support={p['support']} "
            f"cr/turn={p['cr_per_turn']} cr/action={p['cr_per_action']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
