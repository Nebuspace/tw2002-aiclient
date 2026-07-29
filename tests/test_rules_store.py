"""WO-RULE-ENGINE-WIRE, Accept 1 -- the rule library admits documents only
through the kernel's strict parser, and reports what it could not read.

The load-bearing property is **parser unity**. `rule_engine.rule_from_dict`
refuses unknown fields, a bool priority, and a non-bool `approved`; those
refusals only matter on input that arrives from outside the process, which is
exactly and only what this store reads. A second, lenient admission path here
would make every one of them unreachable in production while the kernel's own
unit tests kept passing -- green over a hole.

So each refusal below is proven **through the store**, on a real file, not by
calling the parser directly. A test that called `rule_from_dict` itself would
pass identically against a store that never used it.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from tw2002_aiclient.rule_engine import Rule
from tw2002_aiclient.rules import store as store_mod
from tw2002_aiclient.rules.store import (
    STATUS_ABSENT,
    STATUS_OK,
    STATUS_PARTIAL,
    STATUS_UNREADABLE,
    read_rule_store,
    rules_dir,
)

GOOD = {
    "rule_id": "dock-when-idle",
    "screen_match": "command_prompt",
    "do": "dock",
    "priority": 10,
    "approved": True,
}


def write(dirpath: Path, name: str, payload) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / name
    path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload)
    return path


# ---------------------------------------------------------------------------
# Parser unity -- each refusal proven THROUGH the store, on a real file
# ---------------------------------------------------------------------------


def test_a_well_formed_rule_loads_and_is_a_real_kernel_rule(tmp_path):
    write(tmp_path / "rules", "a.json", GOOD)
    report = read_rule_store(state_dir=tmp_path)

    assert report["status"] == STATUS_OK
    assert report["unreadable"] == []
    (rule,) = report["rules"]
    # `isinstance`, not duck-typing: `replay`-side code and the kernel both
    # depend on the frozen dataclass, and a look-alike with mutable fields
    # would discard that at the last moment.
    assert isinstance(rule, Rule)
    assert (rule.rule_id, rule.do, rule.priority, rule.approved) == (
        "dock-when-idle",
        "dock",
        10,
        True,
    )


@pytest.mark.parametrize(
    "mutation, why",
    [
        ({"unexpected": 1}, "an unknown field is rejected, never silently dropped"),
        ({"priority": True}, "a bool is not an int priority"),
        ({"approved": "yes"}, "a truthy string is how a draft goes live by accident"),
        ({"priority": "10"}, "a numeric string is not an int"),
        ({"scope": "forever"}, "scope is a closed vocabulary"),
        ({"rule_id": ""}, "an empty identity is not an identity"),
    ],
)
def test_the_strict_parsers_refusals_are_reachable_through_the_store(tmp_path, mutation, why):
    """Each of these passes trivially if the store builds `Rule` itself.

    That is the whole point: these are the kernel's refusals, and this asserts
    they still fire on the only input path that reaches production.
    """
    write(tmp_path / "rules", "a.json", {**GOOD, **mutation})
    report = read_rule_store(state_dir=tmp_path)

    assert report["rules"] == [], why
    assert len(report["unreadable"]) == 1
    # Named with a reason, never a bare count -- an operator can only fix a
    # file they are told is broken and why.
    assert report["unreadable"][0]["reason"], "a refusal with no reason is a shrug"
    assert report["status"] == STATUS_PARTIAL


def test_the_refusal_cases_are_not_vacuous_because_the_base_document_loads(tmp_path):
    """Non-vacuity control for the parametrised test above.

    If `GOOD` itself were malformed, every mutation of it would be refused for
    the wrong reason and the parametrised test would pass without testing
    anything. This pins that the base loads.
    """
    write(tmp_path / "rules", "a.json", GOOD)
    assert len(read_rule_store(state_dir=tmp_path)["rules"]) == 1


# ---------------------------------------------------------------------------
# Absent / empty / unreadable are three different facts
# ---------------------------------------------------------------------------


def test_a_store_that_was_never_written_reports_absent_not_empty(tmp_path):
    report = read_rule_store(state_dir=tmp_path)
    assert report["status"] == STATUS_ABSENT
    assert report["rules"] == []


def test_an_empty_store_reports_ok_which_is_a_completed_search(tmp_path):
    (tmp_path / "rules").mkdir()
    report = read_rule_store(state_dir=tmp_path)
    assert report["status"] == STATUS_OK
    assert report["rules"] == []


def test_a_store_we_cannot_list_reports_unreadable_never_empty(tmp_path):
    """The distinction the reflex layer's safety rests on.

    `Path.glob` swallows a `PermissionError` on the directory and yields
    nothing, which is why this module uses `os.listdir` -- see its docstring.
    This is the test that would go green on the `glob` implementation while
    the store was silently reporting a locked library as an empty one.
    """
    d = tmp_path / "rules"
    d.mkdir()
    write(d, "a.json", GOOD)
    os.chmod(d, 0o000)
    try:
        if os.access(d, os.R_OK):  # pragma: no cover - root ignores the mode
            pytest.skip("running as a user that bypasses directory permissions")
        report = read_rule_store(state_dir=tmp_path)
    finally:
        os.chmod(d, 0o755)

    assert report["status"] == STATUS_UNREADABLE
    assert report["rules"] == []
    assert report["reason"], "an unreadable store must say why"


def test_a_directory_named_dot_json_is_reported_not_crashed(tmp_path):
    """The `OSError` case `loops/store.py` records: a directory named `*.json`
    used to escape as an exception and take the whole listing down."""
    d = tmp_path / "rules"
    write(d, "a.json", GOOD)
    (d / "b.json").mkdir()

    report = read_rule_store(state_dir=tmp_path)
    assert len(report["rules"]) == 1, "the good rule still loads"
    assert len(report["unreadable"]) == 1
    assert report["status"] == STATUS_PARTIAL


def test_a_corrupt_file_is_named_rather_than_skipped(tmp_path):
    d = tmp_path / "rules"
    write(d, "a.json", GOOD)
    write(d, "b.json", "{not json")

    report = read_rule_store(state_dir=tmp_path)
    assert len(report["rules"]) == 1
    assert [Path(u["path"]).name for u in report["unreadable"]] == ["b.json"]
    assert report["status"] == STATUS_PARTIAL


def test_non_json_files_are_ignored_without_being_called_unreadable(tmp_path):
    d = tmp_path / "rules"
    write(d, "a.json", GOOD)
    (d / "README.md").write_text("notes")

    report = read_rule_store(state_dir=tmp_path)
    assert report["status"] == STATUS_OK
    assert report["unreadable"] == []


def test_drafts_are_returned_not_filtered_because_the_kernel_owns_approval(tmp_path):
    """Two readers of one fact is how they drift.

    `select_rule` already owns "an unapproved rule is ABSENT, not merely
    low-priority". If the store filtered too, the kernel's rule would become
    unreachable and could rot without any test noticing.
    """
    d = tmp_path / "rules"
    write(d, "a.json", GOOD)
    write(d, "b.json", {**GOOD, "rule_id": "draft-rule", "approved": False})

    rules = read_rule_store(state_dir=tmp_path)["rules"]
    assert sorted(r.rule_id for r in rules) == ["dock-when-idle", "draft-rule"]
    assert any(r.approved is False for r in rules)


# ---------------------------------------------------------------------------
# The bypass guard -- structural, with its own falsification
# ---------------------------------------------------------------------------


def _rule_constructions_in(path: Path) -> list[str]:
    """Every direct `Rule(...)` call in a source file, by line."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name == "Rule":
            found.append(f"{path.name}:{node.lineno}")
    return found


def test_no_module_in_the_rules_package_builds_a_rule_outside_the_parser():
    """Accept 1's bypass guard.

    A lenient twin does not announce itself; it looks like a convenience
    constructor. This fails if any module in `rules/` calls `Rule(...)`
    directly, because the only sanctioned way to turn stored bytes into a
    `Rule` is `rule_from_dict`.
    """
    package = Path(store_mod.__file__).parent
    offenders = []
    for path in sorted(package.glob("*.py")):
        offenders += _rule_constructions_in(path)
    assert offenders == [], (
        f"{offenders} construct a Rule directly, bypassing the strict parser. "
        f"Stored documents must be admitted by rule_from_dict only."
    )


def test_the_bypass_guard_can_actually_detect_a_bypass(tmp_path):
    """Control for the guard above.

    A structural scan that matched nothing would pass on an empty package, on
    a renamed symbol, and on a guard whose walk was broken. This proves the
    scanner fires on the exact construction it forbids.
    """
    planted = tmp_path / "sneaky.py"
    planted.write_text("from tw2002_aiclient.rule_engine import Rule\nx = Rule('a','b','c',1)\n")
    assert _rule_constructions_in(planted) == ["sneaky.py:2"]

    clean = tmp_path / "clean.py"
    clean.write_text("from tw2002_aiclient.rule_engine import rule_from_dict\nx = rule_from_dict({})\n")
    assert _rule_constructions_in(clean) == []


def test_the_store_actually_calls_the_kernel_parser(monkeypatch, tmp_path):
    """Executed proof, not a structural one.

    The AST guard above proves nobody builds a `Rule` the wrong way; it cannot
    prove the store builds one the RIGHT way. Patching the parser the store
    imported and observing the call closes that: if the store grew its own
    admission path, this spy would never fire.
    """
    seen = []

    def spy(payload):
        seen.append(payload)
        raise store_mod.RuleDocumentError("refused by the spy")

    monkeypatch.setattr(store_mod, "rule_from_dict", spy)
    write(tmp_path / "rules", "a.json", GOOD)
    report = read_rule_store(state_dir=tmp_path)

    assert seen == [GOOD], "the store did not route this document through rule_from_dict"
    assert report["rules"] == []
    assert "refused by the spy" in report["unreadable"][0]["reason"]


def test_rules_dir_is_pure_path_math(tmp_path):
    """No filesystem touch -- the seam tests point at `tmp_path` through."""
    assert rules_dir(tmp_path) == tmp_path / "rules"
    assert not (tmp_path / "rules").exists()
