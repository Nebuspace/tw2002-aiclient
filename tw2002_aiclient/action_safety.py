"""Action-safety coverage map (PWO-112).

Canon: ``canon/doctrine/action-safety-guards.md`` — the guard ladder that
makes "never fire an unverified or destructive action" structural.

This module is the **proven coverage map**, not a second runtime that
re-implements every guard. Scattered enforcement stays where it lives
(replay / haggle / toll / crawl / NEVER_AUTO consumers); this inventory
names each canon guard class, pins a load-bearing source marker, and
points at the unit proof that already (or newly) covers it.

Claiming PWO-112 DONE without this map staying green is the hazard the
prep doc named: scattered guards ≠ complete coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_ROOT.parent


@dataclass(frozen=True)
class GuardCoverage:
    """One row of the canon action-safety ladder."""

    guard_id: str
    canon_layer: str
    source_relpath: str  # under tw2002_aiclient/
    source_marker: str  # must appear in source (tripwire)
    proof_test_relpath: str  # under repo tests/
    proof_marker: str  # must appear in the proof file
    notes: str = ""


# Canon schema table (action-safety-guards.md §Schema) — one coverage row
# per load-bearing class. NEVER_AUTO money_prompt is the classify denylist
# specialization already audited in test_never_auto_action.py; it is listed
# here so the map is complete, not to replace that audit.
COVERAGE: tuple[GuardCoverage, ...] = (
    GuardCoverage(
        guard_id="send_and_confirm",
        canon_layer="Per-send",
        source_relpath="session/settle.py",
        source_marker="def send_and_confirm(",
        proof_test_relpath="tests/test_menu_crawl_chokepoint.py",
        proof_marker="send_and_confirm",
        notes="Positive next-screen match; idle silence is not consent",
    ),
    GuardCoverage(
        guard_id="start_anchor",
        canon_layer="Per-cycle",
        source_relpath="loops/player.py",
        source_marker="start_anchor",
        proof_test_relpath="tests/test_replay_ledger_integration.py",
        proof_marker="start_anchor_mismatch",
        notes="Sector mismatch / null anchor refuse unless force=True",
    ),
    GuardCoverage(
        guard_id="novelty_halt",
        canon_layer="Per-cycle",
        source_relpath="loops/player.py",
        source_marker="NEVER_AUTO_ACTION_CLASSES",
        proof_test_relpath="tests/test_never_auto_action.py",
        proof_marker="NEVER_AUTO_ACTION_CLASSES",
        notes="Stop-on-unknown / escalate-only classes at fire boundaries",
    ),
    GuardCoverage(
        guard_id="never_auto_money_prompt",
        canon_layer="Per-cycle",
        source_relpath="session/classify.py",
        source_marker="NEVER_AUTO_ACTION_CLASSES = frozenset({\"money_prompt\"})",
        proof_test_relpath="tests/test_never_auto_action.py",
        proof_marker="_INVENTORIED_CONSUMERS",
        notes="money_prompt escalate-only for generic consumers (DECISIONS A.2)",
    ),
    GuardCoverage(
        guard_id="haggle_fresh_render",
        canon_layer="Resolver",
        source_relpath="session/haggle.py",
        source_marker="wait_until_settled",
        proof_test_relpath="tests/test_haggle.py",
        proof_marker="never_settles_before_the_first_read",
        notes="Refuse to parse/act until screen settled",
    ),
    GuardCoverage(
        guard_id="haggle_desync_fallback",
        canon_layer="Resolver",
        source_relpath="session/haggle.py",
        source_marker="DESYNC_FALLBACK",
        proof_test_relpath="tests/test_haggle.py",
        proof_marker="DESYNC_FALLBACK",
        notes="Bare command prompt / no acceptance ⇒ desync, never guess price",
    ),
    GuardCoverage(
        guard_id="never_auto_pay_toll",
        canon_layer="Resolver",
        source_relpath="session/fighter_toll_policy.py",
        source_marker="never Pay",
        proof_test_relpath="tests/test_fighter_toll_policy.py",
        proof_marker="pay_is_never_selected",
        notes="Toll Pay is human-gated; App never selects P",
    ),
    GuardCoverage(
        guard_id="trade_paladin_letters",
        canon_layer="Resolver",
        source_relpath="trade_driver.py",
        source_marker="PALADIN",
        proof_test_relpath="tests/test_trade_driver.py",
        proof_marker="test_paladin_send_letter_refuses",
        notes="Trade driver only sends allowlisted P/T letters",
    ),
    GuardCoverage(
        guard_id="run_stop_loss_credits_unknown",
        canon_layer="Run",
        source_relpath="loops/player.py",
        source_marker="credits_unknown",
        proof_test_relpath="tests/test_credits_floor.py",
        proof_marker="test_an_unobserved_balance_halts_credits_unknown",
        notes="Unknown/stale balance fails closed rather than arming unbounded",
    ),
    GuardCoverage(
        guard_id="crawl_sacrificial_gate",
        canon_layer="Crawl",
        source_relpath="menu/crawl_driver.py",
        source_marker="crawl_sacrificial",
        proof_test_relpath="tests/test_crawl_driver.py",
        proof_marker="crawl_sacrificial",
        notes="Live crawl refuses non-sacrificial profiles before connect",
    ),
    GuardCoverage(
        guard_id="crawl_safe_emit_chokepoint",
        canon_layer="Crawl",
        source_relpath="menu/crawler.py",
        source_marker="emit_key_if_safe",
        proof_test_relpath="tests/test_menu_crawl_chokepoint.py",
        proof_marker="emit_key_if_safe",
        notes="Every crawl keystroke passes the single safe-emit chokepoint",
    ),
    GuardCoverage(
        guard_id="alignment_no_pvp_aggression",
        canon_layer="Always",
        source_relpath="alignment_gate.py",
        source_marker="refuse_pvp_aggression_rule",
        proof_test_relpath="tests/test_alignment_gate.py",
        proof_marker="refuse_pvp_aggression_rule",
        notes="PvP aggression rules refused at write/promote/bridge (PWO-113)",
    ),
)


def all_coverage() -> tuple[GuardCoverage, ...]:
    return COVERAGE


def coverage_ids() -> frozenset[str]:
    return frozenset(g.guard_id for g in COVERAGE)


def source_path(entry: GuardCoverage) -> Path:
    return _PKG_ROOT / entry.source_relpath


def proof_path(entry: GuardCoverage) -> Path:
    return _REPO_ROOT / entry.proof_test_relpath


def assert_coverage_map_intact() -> None:
    """Fail loud if any inventory row lost its source or proof pin."""
    seen: set[str] = set()
    for entry in COVERAGE:
        if entry.guard_id in seen:
            raise AssertionError(f"duplicate guard_id: {entry.guard_id}")
        seen.add(entry.guard_id)
        src = source_path(entry)
        if not src.is_file():
            raise AssertionError(f"{entry.guard_id}: missing source {src}")
        src_text = src.read_text(encoding="utf-8")
        if entry.source_marker not in src_text:
            raise AssertionError(
                f"{entry.guard_id}: source marker missing in "
                f"{entry.source_relpath}: {entry.source_marker!r}"
            )
        proof = proof_path(entry)
        if not proof.is_file():
            raise AssertionError(f"{entry.guard_id}: missing proof {proof}")
        proof_text = proof.read_text(encoding="utf-8")
        if entry.proof_marker not in proof_text:
            raise AssertionError(
                f"{entry.guard_id}: proof marker missing in "
                f"{entry.proof_test_relpath}: {entry.proof_marker!r}"
            )
