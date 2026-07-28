"""Coaching knowledge-base loader — canon I1/I4 (`canon/engine/coaching-engine.md`).

Loads the authored strategy cards and the numeric coaching parameters they cite.
Pure I/O + schema validation: no world-model dependency, no world-model import,
and **no card text of its own** — every string a caller renders comes from
``data/coach/strategies.json``, which is the single authored source canon
requires (a second source of card prose is what canon forbids).

Ported at the rebirth from pre-rebirth ``twclient/coach_kb.py`` (deleted by the
``452d896`` scaffold) per ``WO-COACH-ENGINE-PORT``. The one deliberate change is
``default_kb_paths`` — see the note there.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

REQUIRED_STRATEGY_FIELDS = frozenset({
    "id",
    "title",
    "what",
    "when_trigger",
    "tradeoffs",
    "steps",
    "okf_refs",
    "hypothesis_flags",
})

REQUIRED_PARAM_FIELDS = frozenset({
    "key",
    "value",
    "unit",
    "verified_vs_live",
    "source_note",
})

# -- Data location ----------------------------------------------------------
#
# The pre-rebirth module resolved its data as
# ``Path(__file__).resolve().parent.parent / "data" / "coach"``. That was
# correct ONLY because it sat at ``twclient/coach_kb.py``, one level below the
# repo root. A bare ``parent.parent`` silently encodes an assumption about how
# deep the module is nested, and nothing in the expression states it -- move the
# file into a subpackage and it resolves to a directory that does not exist,
# with no error until a load is attempted. Naming the two steps separately makes
# the assumption greppable, and `test_coach_kb.py` pins the resolved directory
# against the repo's real one so a future move fails loudly at test time rather
# than silently at runtime.
_PACKAGE_DIR = Path(__file__).resolve().parent      # …/tw2002_aiclient
_REPO_ROOT = _PACKAGE_DIR.parent                    # …/<repo>
DEFAULT_DATA_DIR = _REPO_ROOT / "data" / "coach"


@dataclass(frozen=True)
class StrategyCard:
    id: str
    title: str
    what: str
    when_trigger: str  # trigger id, e.g. ``docked_at_port``
    tradeoffs: tuple[str, ...]
    steps: tuple[str, ...]
    okf_refs: tuple[str, ...]
    hypothesis_flags: tuple[str, ...]
    priority: int = 50


@dataclass(frozen=True)
class CoachParam:
    key: str
    value: float | int | str | bool
    unit: str
    verified_vs_live: bool
    source_note: str


@dataclass(frozen=True)
class CoachKB:
    version: int
    strategies: tuple[StrategyCard, ...]
    params: tuple[CoachParam, ...] = field(default_factory=tuple)

    def by_trigger(self, trigger: str) -> list[StrategyCard]:
        return [s for s in self.strategies if s.when_trigger == trigger]

    def param(self, key: str) -> Optional[CoachParam]:
        for p in self.params:
            if p.key == key:
                return p
        return None


def _as_str_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list of strings")
    return tuple(str(x) for x in value)


def validate_strategy(row: Mapping[str, Any]) -> StrategyCard:
    missing = REQUIRED_STRATEGY_FIELDS - frozenset(row.keys())
    if missing:
        raise ValueError(f"strategy missing fields: {sorted(missing)}")
    return StrategyCard(
        id=str(row["id"]),
        title=str(row["title"]),
        what=str(row["what"]),
        when_trigger=str(row["when_trigger"]),
        tradeoffs=_as_str_tuple(row["tradeoffs"], field_name="tradeoffs"),
        steps=_as_str_tuple(row["steps"], field_name="steps"),
        okf_refs=_as_str_tuple(row["okf_refs"], field_name="okf_refs"),
        hypothesis_flags=_as_str_tuple(
            row["hypothesis_flags"], field_name="hypothesis_flags"
        ),
        priority=int(row.get("priority", 50)),
    )


def validate_param(row: Mapping[str, Any]) -> CoachParam:
    missing = REQUIRED_PARAM_FIELDS - frozenset(row.keys())
    if missing:
        raise ValueError(f"param missing fields: {sorted(missing)}")
    return CoachParam(
        key=str(row["key"]),
        value=row["value"],
        unit=str(row["unit"]),
        verified_vs_live=bool(row["verified_vs_live"]),
        source_note=str(row["source_note"]),
    )


def load_coach_kb(
    strategies_path: str | Path,
    params_path: str | Path | None = None,
) -> CoachKB:
    raw = json.loads(Path(strategies_path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("strategies root must be a JSON object")
    version = int(raw.get("version", 1))
    strategies = tuple(validate_strategy(s) for s in raw.get("strategies") or ())
    params: tuple[CoachParam, ...] = ()
    if params_path is not None:
        praw = json.loads(Path(params_path).read_text(encoding="utf-8"))
        if not isinstance(praw, dict):
            raise ValueError("params root must be a JSON object")
        params = tuple(validate_param(p) for p in praw.get("params") or ())
    ids = [s.id for s in strategies]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate strategy id")
    return CoachKB(version=version, strategies=strategies, params=params)


def default_kb_paths(root: Path | None = None) -> tuple[Path, Path]:
    """``(strategies.json, params.json)`` under ``root`` (default: repo data dir)."""
    base = Path(root) if root is not None else DEFAULT_DATA_DIR
    return base / "strategies.json", base / "params.json"
