"""WO-ADAPTERS-FIGHT-TOLLS: Play/adapter callers can arm the toll policy.

#209 gave the CLI and the daemon a `--fight-tolls` arm. `adapters.explore_start*`
forwarded `dock_new_ports` but not this one, so every adapter caller -- Play
included -- could not arm the toll policy at all and automation stayed
CLI-only. This closes that, and pins the ways it must not become "on".
"""

from __future__ import annotations

import inspect

import pytest

from tw2002_aiclient import adapters
from tw2002_aiclient.session import sector_explore as sx


@pytest.fixture
def sent(monkeypatch):
    """Capture the payload that would go to the daemon."""
    seen = {}

    def fake(verb, payload, run_dir=None):
        seen["verb"] = verb
        seen["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(adapters._cli, "send_request", fake)
    return seen


# --- Accept 1 + 2: the flag is forwarded, exactly ------------------------


@pytest.mark.parametrize("value", [True, False])
def test_the_arm_is_forwarded_with_its_exact_value(sent, value):
    """Both values matter. Forwarding only `True` would look correct in any
    test that arms, while silently dropping an explicit disarm."""
    adapters.explore_start("w-1", fight_tolls=value)
    assert sent["payload"]["fight_tolls"] is value


def test_omitted_means_omitted_so_the_daemon_default_stands(sent):
    """`None` -> the key is absent, leaving the daemon at False. A caller that
    has never been taught about the toll policy cannot arm an attack, and every
    pre-existing caller stays byte-identical on the wire."""
    adapters.explore_start("w-1")
    assert "fight_tolls" not in sent["payload"]
    assert sent["payload"] == {"world_id": "w-1"}


def test_the_profile_wrapper_forwards_it_too(sent, monkeypatch):
    """`explore_start_for_profile` is the entry Play actually uses; a flag
    accepted by the inner function and dropped by the wrapper is the shape that
    looks wired and is not."""
    monkeypatch.setattr(adapters._wi, "world_id_from_profile", lambda p: "w-prof")
    adapters.explore_start_for_profile(object(), fight_tolls=True)
    assert sent["payload"]["fight_tolls"] is True


def test_both_entry_points_expose_the_parameter():
    """Structural: the wrapper must not quietly lose the parameter from its
    signature, which would make the call above a TypeError only at runtime."""
    for fn in (adapters.explore_start, adapters.explore_start_for_profile):
        p = inspect.signature(fn).parameters
        assert "fight_tolls" in p, fn.__name__
        assert p["fight_tolls"].default is None


# --- the part that is NOT a mirror of dock_new_ports ---------------------


@pytest.mark.parametrize("truthy_refusal", ["no", "false", "off", 0, 1, "0"])
def test_a_non_bool_arm_reaches_the_daemon_intact_to_be_refused(sent, truthy_refusal):
    """THE load-bearing pin, and the reason this does not mirror
    `dock_new_ports`.

    `runner.start` refuses a non-bool with `invalid_fight_tolls` because `"no"`
    is truthy in Python. If this adapter coerced with `bool(...)` the daemon
    would receive a perfectly valid `True` and that refusal could never fire --
    `fight_tolls="no"` would arm combat. Local coercion does not defend the
    caller; it destroys the evidence the daemon needs to defend them.

    So the value must arrive UNCHANGED.
    """
    adapters.explore_start("w-1", fight_tolls=truthy_refusal)
    assert sent["payload"]["fight_tolls"] == truthy_refusal
    assert not isinstance(sent["payload"]["fight_tolls"], bool)


@pytest.mark.parametrize("truthy_refusal", ["no", "false", 1, "0"])
def test_the_daemon_really_does_refuse_what_the_adapter_forwards(tmp_path, truthy_refusal):
    """Closes the loop across the seam. The pin above is only worth having if
    the daemon side actually refuses these -- otherwise "forward it intact"
    would just be an untested preference.
    """
    runner = sx.ExploreRunner(object(), sx.ControlLock(), state_dir=tmp_path)
    with pytest.raises(sx.ExploreRefused) as exc:
        runner.start("w-1", fight_tolls=truthy_refusal)
    assert str(exc.value) == "invalid_fight_tolls"


def test_coercing_here_would_have_armed_combat_from_a_refusal_string():
    """Demonstrates the hazard is real rather than theoretical, without
    depending on the adapter's implementation: this is what `bool()` does to
    the exact strings a caller would use to mean 'no'."""
    for refusal in ("no", "false", "off"):
        assert bool(refusal) is True


# --- no default-ON anywhere ----------------------------------------------


def test_nothing_in_this_path_defaults_the_arm_on():
    """Accept 3. Three independent defaults, checked together because the
    failure mode is one of them drifting while the others look fine."""
    assert inspect.signature(adapters.explore_start).parameters["fight_tolls"].default is None
    assert (
        inspect.signature(adapters.explore_start_for_profile)
        .parameters["fight_tolls"].default is None
    )
    assert inspect.signature(sx.ExploreRunner.start).parameters["fight_tolls"].default is False
    assert sx.ExploreReport(world_id="w", started_at="t", min_sectors=1).fight_tolls is False
