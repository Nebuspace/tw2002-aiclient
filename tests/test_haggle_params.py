"""Pins for the auto-haggle params registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tw2002_aiclient import haggle_params as hp
from tw2002_aiclient.session import haggle as haggle_mod


def test_shipped_json_loads_and_matches_builtin_shape():
    loaded = hp.load_haggle_params()
    assert loaded.round_cap == 4
    assert loaded.accept_threshold_pct == 5.0
    assert loaded.open_aggression_pct == 15.0
    assert loaded.verified_vs_live is True
    assert loaded.source_note
    assert hp.DEFAULT_PARAMS_PATH.is_file()


def test_haggle_module_defaults_come_from_registry():
    assert haggle_mod._DEFAULT_ROUND_CAP == hp.DEFAULT_HAGGLE_PARAMS.round_cap
    assert haggle_mod._DEFAULT_ACCEPT_THRESHOLD_PCT == (
        hp.DEFAULT_HAGGLE_PARAMS.accept_threshold_pct
    )
    assert haggle_mod._DEFAULT_OPEN_AGGRESSION_PCT == (
        hp.DEFAULT_HAGGLE_PARAMS.open_aggression_pct
    )


def test_load_haggle_params_rejects_missing_keys(tmp_path: Path):
    path = tmp_path / "params.json"
    path.write_text(json.dumps({"round_cap": 4}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing keys"):
        hp.load_haggle_params(path)


def test_load_haggle_params_missing_file_uses_builtin(tmp_path: Path):
    missing = tmp_path / "nope.json"
    loaded = hp.load_haggle_params(missing)
    assert loaded == hp.BUILTIN_HAGGLE_PARAMS


def test_shipped_json_has_no_silent_literal_drift():
    raw = json.loads(hp.DEFAULT_PARAMS_PATH.read_text(encoding="utf-8"))
    coerced = hp.load_haggle_params()
    assert coerced.round_cap == int(raw["round_cap"])
    assert coerced.accept_threshold_pct == float(raw["accept_threshold_pct"])
    assert coerced.open_aggression_pct == float(raw["open_aggression_pct"])
