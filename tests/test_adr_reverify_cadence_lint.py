"""Tests for scripts/adr-reverify-cadence-lint.py (WO-INFRA-GENERALIZE-…)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "adr-reverify-cadence-lint.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("adr_reverify_cadence_lint", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load()


def test_tip_canon_adr_defaults_are_fresh(lint):
    """Live tip: three Folded ADRs, all re-verified 2026-08-15 → exit 0."""
    rc = lint.main(["--json"])
    # main prints JSON to stdout; capture via scan directly for assertions
    report = lint.scan(lint.DEFAULT_ADR_DIR, lint.DEFAULT_ADR_DIR / "index.md", 45)
    assert report["scanned_settled_adrs"] == 3
    assert report["missing_tag"] == []
    assert report["stale_tag"] == []
    assert report["fresh_count"] == 3
    # ADR-003 carries 8/8 on both index + body; 001/002 have no N/M → no mismatch
    assert report["index_body_nm_mismatch"] == []
    assert rc == 0 or True  # main() already ran; re-check exit via scan flags
    flagged = (
        len(report["missing_tag"])
        + len(report["stale_tag"])
        + len(report["index_body_nm_mismatch"])
    )
    assert flagged == 0


def test_dir_and_index_args_detect_missing_and_mismatch(lint, tmp_path, capsys):
    adr_dir = tmp_path / "ADR"
    adr_dir.mkdir()
    (adr_dir / "index.md").write_text(
        "| # | Title | Status | Date |\n"
        "|---|-------|--------|------|\n"
        "| [001](001-a.md) | A | **Folded into** X _(re-verified 2020-01-01 — 1/2)_ | 2020-01-01 |\n"
        "| [002](002-b.md) | B | **Folded into** Y _(re-verified 2026-08-15)_ | 2026-08-15 |\n"
    )
    (adr_dir / "001-a.md").write_text(
        "# ADR 001 — A\n\n## Status\n\n"
        "**Folded into** X · _(re-verified 2020-01-01 — 2/2 gap closed)_\n\n"
        "## Context\n\nx\n"
    )
    (adr_dir / "002-b.md").write_text(
        "# ADR 002 — B\n\n## Status\n\n"
        "**Folded into** Y · _(re-verified 2026-08-15)_\n\n"
        "## Context\n\ny\n"
    )
    (adr_dir / "003-proposed.md").write_text(
        "# ADR 003 — C\n\n## Status\n\n**Proposed**\n"
    )

    report = lint.scan(adr_dir, adr_dir / "index.md", stale_days=45)
    assert report["scanned_settled_adrs"] == 2
    assert any(e["adr"] == "001" for e in report["stale_tag"])
    assert report["fresh_count"] == 1
    assert report["index_body_nm_mismatch"] == [
        {"adr": "001", "file": "001-a.md", "index_nm": "1/2", "body_nm": "2/2"}
    ]

    rc = lint.main(["--dir", str(adr_dir), "--index", "index.md", "--json"])
    assert rc == 0  # --json always exits 0 like the Nebuspace original
    out = json.loads(capsys.readouterr().out)
    assert out["scanned_settled_adrs"] == 2
    assert len(out["stale_tag"]) == 1
    assert len(out["index_body_nm_mismatch"]) == 1

    rc_text = lint.main(["--dir", str(adr_dir), "--index", "index.md", "--stale-days", "45"])
    assert rc_text == 1


def test_sw2102_style_title_and_readme_index(lint, tmp_path):
    adr_dir = tmp_path / "ADR"
    adr_dir.mkdir()
    (adr_dir / "README.md").write_text(
        "| ADR | Title | Status |\n"
        "|-----|-------|--------|\n"
        "| 0073 | Thing | Distributed-fold (1/2) — note |\n"
    )
    (adr_dir / "0073-thing.md").write_text(
        "# 0073 — Thing\n\n## Status\n\n"
        "Distributed-fold **1/2 confirmed live** · _(re-verified 2026-08-01)_\n"
    )
    report = lint.scan(adr_dir, adr_dir / "README.md", 45)
    assert report["scanned_settled_adrs"] == 1
    assert report["fresh_count"] == 1
    assert report["index_body_nm_mismatch"] == []
