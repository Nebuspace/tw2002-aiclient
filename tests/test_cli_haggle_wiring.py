"""`tw haggle` CLI verb wiring -- argparse only (dispatch itself needs a
live daemon and is exercised at the protocol layer instead, see
tests/test_protocol_haggle.py)."""

from twclient import cli


def test_haggle_verb_is_wired_with_expected_defaults():
    parser = cli.build_parser()
    args = parser.parse_args(["haggle"])
    assert args.func is cli.cmd_haggle
    assert args.fair_value is None
    assert args.accept_threshold_pct == 5.0
    assert args.open_aggression_pct == 15.0
    assert args.round_cap == 4
    assert args.step_timeout == 8.0


def test_haggle_verb_accepts_overrides():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "haggle",
            "--fair-value", "3000",
            "--accept-threshold-pct", "2.5",
            "--open-aggression-pct", "10",
            "--round-cap", "2",
            "--step-timeout", "4",
        ]
    )
    assert args.fair_value == 3000.0
    assert args.accept_threshold_pct == 2.5
    assert args.open_aggression_pct == 10.0
    assert args.round_cap == 2
    assert args.step_timeout == 4.0
