"""T0 of WO-GOALS-STATUS-VOCABULARY — the starved-`status`-key guard.

**What this exists to catch, and why nothing else can.** A cockpit panel that
reads `status["turns_left"]` when no product code writes it renders an honest
`?` forever and passes its own suite, because the suite supplies what the daemon
does not. The panel is not lying and no assertion is wrong — the surface is
simply, permanently uninformative. That is invisible to every other test in this
repo, and it is how most of GOALS survived a rebirth unnoticed.

**Exact-set equality, deliberately, in both directions:**

* a newly-read key with no producer is **not** in the allowlist → red. Catches
  regrowth — a new panel field shipped without a wire.
* a listed key that has **since** been supplied → red. Forces the entry's
  deletion. A subset check would let stale entries accumulate, silently
  re-permitting the exact regression the guard was built to stop. That failure
  mode is not hypothetical here: a "DONE" split once left its file larger than
  when the work was ordered, because nothing compared the result to the promise.

The allowlist below is a **scoped backlog, not a suppression list** — every entry
carries the tranche that owns it and why it is not wired yet. A bare list of
names reads as work nobody owns, which is how `WO-COACH-CHAIN-TRIGGER` sat marked
"blocked" for hours after the work it described had shipped.

Scanner traps and the dataflow narrowing are documented in
`tests/status_vocabulary.py`; the controls for all three are pinned below.
"""

from __future__ import annotations

import ast

import pytest

from tests.status_vocabulary import (
    consumed_keys,
    emitted_keys,
    repo_root,
    starved_keys,
)

# key -> (tranche, why it has no producer yet)
#
# Tranches are WO-GOALS-STATUS-VOCABULARY's own split, by PRODUCER LOCATION
# rather than by panel — panels cut across producers, and #162 established that
# the fix for a GOALS field can live client-side rather than in the daemon.
STARVED_ALLOWLIST: dict[str, tuple[str, str]] = {
    # -- BLOCKED: no producer exists to wire, and building one is a different
    #    WO's job. T1 was scheduled as FIVE world-model fields "the client
    #    already holds"; resolving each one's actual producer left exactly one
    #    (`known_sectors`, now wired by `world_stats.py` and deleted from this
    #    list). The other four were starved one layer deeper than the panel —
    #    the reader existed, the writer never did. Each reason below is the
    #    evidence, not the original assumption:
    "formations_count": (
        "BLOCKED",
        "needs `catalog_provider.genesis_candidates`; that seam is unimplemented "
        "and the planner returns mode='unavailable' — WO-FORMATIONS-CATALOG-PORT",
    ),
    # stardock_found / stardock_sectors — supplied by world_stats.WorldStats
    # (WO-GOALS-STARDOCK-STATUS); landmarks writers already on main.
    # -- T3: no extractor exists; needs new screen parsing and captured fixtures.
    "galaxy_size": (
        "T3",
        "nothing in the package produces one and `state_parser` refuses to invent "
        "one; the Map row degrades honestly to '· N sectors' without it",
    ),
    # -- T2: the daemon already has an extractor, it is simply unwired.
    #    Touches `_status_response`, so scheduling it needs a DEPLOY-WINDOW.
    # Still starved after WO-HUD-STATUS-BRIDGE, and deliberately so: that WO
    # supplied `hud.credits` (from the existing `credits_snapshot` sticky
    # pair), not a TOP-LEVEL `credits`. The guard is exact-set and correctly
    # kept telling them apart -- deleting this entry because "the HUD shows
    # credits now" would declare a field supplied that no producer writes.
    "credits": ("T2", "`state_parser.read_credits_balance` exists, unwired; needs a window"),
    # -- T3: no extractor exists; needs new screen parsing and captured fixtures.
    "fighters_aboard": ("T3", "needs screen parsing; also a coach trigger input"),
    "ship_prices_count": ("T3", "needs shipyard-screen parsing; gated by stardock_found"),
    "hold_price_label": ("T3", "needs shipyard-screen parsing; gated by stardock_found"),
    "fighter_buy_status": ("T3", "needs shipyard-screen parsing"),
    # -- T4: whole nested panel payloads, each its own surface-sized WO.
    "autopilot_trace": ("T4", "whole DECISIONS trace payload; no autopilot emits one yet"),
    "focus": ("T4", "whole FOCUS payload; own WO"),
    "tx": ("T4", "liveness TX readout; `liveness.py` documents its own pending wire"),
    "spinner_frame": ("T4", "app per-draw tick; `liveness.py` documents its own pending wire"),
}

# T1 is absent by design: it had one wireable field, it was wired, its entry is
# gone. "BLOCKED" is not a tranche of this WO at all — it marks a key whose
# producer belongs to a named other WO, which is the honest owner for a field no
# amount of wiring here can supply.
_VALID_TRANCHES = {"BLOCKED", "T2", "T3", "T4"}


def _diff(actual: set[str], expected: set[str]) -> tuple[list[str], list[str]]:
    """``(newly_starved, now_supplied)`` — the guard's whole comparison.

    Extracted as a pure function so the *comparison itself* is testable on
    synthetic inputs. Without that, weakening this to a subset check
    (``now_supplied = []``) passes every test in this file on today's tree,
    because today's two sets already match — the weakening is invisible until
    the day it matters, which is the day someone wires a field and forgets its
    entry. A guard whose own logic nothing pins is one edit from decoration.
    """
    return sorted(actual - expected), sorted(expected - actual)


def test_the_comparison_flags_both_directions():
    """Synthetic, because on the real tree the two sets are equal by
    construction and a one-directional check looks identical to a correct one."""
    assert _diff({"a"}, set()) == (["a"], []), "regrowth direction not flagged"
    assert _diff(set(), {"a"}) == ([], ["a"]), "stale-entry direction not flagged"
    assert _diff({"a"}, {"b"}) == (["a"], ["b"]), "both directions must report"
    assert _diff({"a"}, {"a"}) == ([], []), "an exact match must be silent"


def test_starved_status_keys_match_the_allowlist_exactly():
    starved = starved_keys()
    actual, expected = set(starved), set(STARVED_ALLOWLIST)

    newly_starved, now_supplied = _diff(actual, expected)

    problems = []
    if newly_starved:
        problems.append(
            "READ BUT NEVER WRITTEN, and not declared — a panel field shipped "
            "without a producer. Wire it, or add it to STARVED_ALLOWLIST with a "
            "tranche and a reason:\n"
            + "\n".join(
                f"    {k}  <- read by {', '.join(sorted(starved[k]))}" for k in newly_starved
            )
        )
    if now_supplied:
        problems.append(
            "LISTED AS STARVED BUT NOW SUPPLIED — delete these entries. Leaving "
            "them lets the guard go on permitting a gap that has been closed:\n"
            + "\n".join(f"    {k}" for k in now_supplied)
        )
    assert not problems, "\n\n".join(problems)


def test_every_allowlist_entry_names_a_tranche_and_a_reason():
    """A bare list of names is a suppression list. The tranche and the reason are
    what make it a backlog someone can act on."""
    for key, entry in STARVED_ALLOWLIST.items():
        tranche, why = entry
        assert tranche in _VALID_TRANCHES, f"{key}: unknown tranche {tranche!r}"
        assert len(why) > 20, f"{key}: reason too thin to act on: {why!r}"


# ---------------------------------------------------------------------------
# Scanner controls. Each pins one way the scan silently returns the wrong
# answer; all three were hit for real while scoping this WO.
# ---------------------------------------------------------------------------


# Producer-side identity anchors — mirror #186 badge pattern / #188 F1.
# Cardinality alone is vacuous once the real map is large; dropping a known
# producer from the scan must redden this pin (WO-TEST-EMITTED-SCAN-IDENTITY).
_EMITTED_SCAN_IDENTITY = (
    "tw2002_aiclient/session/protocol.py",
    "tw2002_aiclient/world_model.py",
)


def _emitted_writer_files(emitted: dict | None = None) -> set[str]:
    """File paths that appear as producer sites in an emitted-keys map."""
    if emitted is None:
        emitted = emitted_keys()
    return {
        site.split(":")[0]
        for sites in emitted.values()
        for site in sites
    }


def _assert_emitted_scan_identity(writers: set[str]) -> None:
    """Shared identity pin — production control and falsify both call this."""
    for expected in _EMITTED_SCAN_IDENTITY:
        assert expected in writers, f"{expected} was not scanned as a producer"


def test_the_scanner_reaches_the_files_it_claims_to_scan():
    """The empty-scan trap: a glob that matches nothing yields no consumed keys,
    hence no starved keys, hence a green guard over a repo full of gaps. Assert
    the scan actually found the surfaces it is supposed to cover."""
    consumed = consumed_keys()
    readers = {f for files in consumed.values() for f in files}
    assert len(consumed) >= 20, f"consumer scan found only {len(consumed)} keys"
    for expected in ("tw2002_aiclient/cockpit/goals.py", "tw2002_aiclient/screens.py"):
        assert expected in readers, f"{expected} was not scanned"
    # Producer side: identity, not cardinality (#190).
    _assert_emitted_scan_identity(_emitted_writer_files())


def test_emitted_identity_floor_goes_red_when_protocol_is_dropped():
    """Falsify Accept: filter protocol.py out of the scan result → the *same*
    identity helper the production pin uses must raise (not set-arithmetic)."""
    victim = "tw2002_aiclient/session/protocol.py"
    real = emitted_keys()
    assert any(
        s.startswith(victim + ":") for sites in real.values() for s in sites
    ), "precondition: protocol.py must be a live producer"
    filtered = {
        key: [s for s in sites if not s.startswith(victim + ":")]
        for key, sites in real.items()
    }
    filtered = {k: v for k, v in filtered.items() if v}
    writers = _emitted_writer_files(filtered)
    assert victim not in writers
    with pytest.raises(AssertionError, match="protocol.py"):
        _assert_emitted_scan_identity(writers)


def test_the_scanner_resolves_named_constant_writes():
    """Positive control for the false NEGATIVE trap.

    `chain_status.py` writes the field as `merged[HOPS_KEY] = ...`. A scan
    matching only string-literal subscripts reported "no writer" for a producer
    that had shipped an hour earlier (#162). Anchored on the real module, so
    breaking the constant resolution reddens this rather than merely a synthetic
    fixture."""
    emitted = emitted_keys()
    assert "chain_hops" in emitted, "constant-keyed writer not seen — see status_vocabulary"
    assert "chain_unit" in emitted
    assert any("chain_status.py" in site for site in emitted["chain_hops"])

    # ...and the write really is constant-keyed, not a literal that would make
    # this control pass without exercising the resolution at all.
    src = (repo_root() / "tw2002_aiclient" / "chain_status.py").read_text()
    tree = ast.parse(src)
    constant_keyed = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Name)
    ]
    assert constant_keyed, "chain_status.py no longer uses a named-constant key"


def test_the_scanner_does_not_count_label_tables_as_producers():
    """Negative control for the false POSITIVE trap.

    `goals.py::_LABELS` and `hud.py::_FIELD_LABELS` are dict literals keyed by
    field name — display strings, not producers. A scan counting dict-literal
    keys anywhere reported `credits` as supplied when nothing supplies it."""
    # The tables really do contain the key, so this control is not vacuous.
    goals_src = (repo_root() / "tw2002_aiclient" / "cockpit" / "goals.py").read_text()
    assert '"credits":' in goals_src, "the label table no longer mentions credits"

    assert "credits" not in emitted_keys(), "a label table was counted as a producer"
    assert "credits" in starved_keys()


def _synthetic_repo(tmp_path):
    """A miniature package exercising all three producer/non-producer shapes.

    Built rather than borrowed on purpose. An earlier version of this control
    asserted against the *real* tree and passed whether or not the rule it named
    was present — the tree simply had no unrelated dict using a status field
    name, so the weakening it claimed to catch was invisible. A control that
    only fires when the codebase happens to contain the hazard is not a control.
    """
    pkg = tmp_path / "tw2002_aiclient"
    (pkg / "cockpit").mkdir(parents=True)
    (pkg / "session").mkdir(parents=True)

    (pkg / "cockpit" / "panel.py").write_text(
        "def compose(status):\n"
        "    a = status.get('wired_field')\n"
        "    b = status['orphan_field']\n"
        "    c = status.get('label_only_field')\n"
        "    return a, b, c\n"
    )
    (pkg / "screens.py").write_text("def draw(status):\n    return status.get('wired_field')\n")
    (pkg / "session" / "protocol.py").write_text(
        "def _status_response(session, server):\n    return {'ok': True}\n"
    )
    (pkg / "overlay.py").write_text(
        "WIRED = 'wired_field'\n"
        "\n"
        "# A label table: dict literal bound to a name, never returned. NOT a producer.\n"
        "_LABELS = {'label_only_field': ('Label', 'Lbl')}\n"
        "\n"
        "def merge(status):\n"
        "    merged = dict(status)\n"
        "    merged[WIRED] = 1          # constant-keyed write into a RETURNED dict\n"
        "    return merged\n"
        "\n"
        "def unrelated_cache(x):\n"
        "    cache = {}\n"
        "    cache['orphan_field'] = x  # function returns NOTHING -- not a producer\n"
        "    print(cache)\n"
        "\n"
        "def build(status):\n"
        "    out = dict(status)\n"
        "    scratch = {}\n"
        "    scratch['scratch_field'] = 1  # function DOES return, but not THIS dict\n"
        "    out[WIRED] = 1\n"
        "    return out\n"
    )
    return tmp_path


def test_the_scanner_rules_hold_on_a_synthetic_tree(tmp_path):
    """All three producer rules at once, on a tree built to contain each hazard.

    * `wired_field` — constant-keyed write into a dict the function returns →
      a producer. (Breaking constant resolution loses it.)
    * `orphan_field` — written into a dict that is never returned → NOT a
      producer. Before the dataflow narrowing every `cache["x"] = v` in the
      package counted, 49 'emitted' keys against 27 real ones; that over-count
      fails UNSAFE, silently retiring a real gap the day an unrelated dict
      happens to share a field name.
    * `label_only_field` — a dict literal bound to a name → NOT a producer.
    """
    root = _synthetic_repo(tmp_path)
    consumed, emitted, starved = (
        consumed_keys(root),
        emitted_keys(root),
        starved_keys(root),
    )

    assert set(consumed) == {"wired_field", "orphan_field", "label_only_field"}
    assert "wired_field" in emitted, "constant-keyed write into a returned dict was missed"
    # Two distinct halves of the narrowing, and an injection proved a fixture
    # exercising only the first leaves the second untested:
    #   orphan_field  -- enclosing function returns nothing at all
    #   scratch_field -- enclosing function DOES return, but a different dict
    assert "orphan_field" not in emitted, "a never-returned dict was counted as a producer"
    assert "scratch_field" not in emitted, "a sibling dict in a returning function was counted"
    assert "label_only_field" not in emitted, "a label table was counted as a producer"
    assert set(starved) == {"orphan_field", "label_only_field"}
