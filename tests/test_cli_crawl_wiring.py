"""`tw crawl` CLI verb wiring -- argparse only (dispatch itself needs a
live daemon and is exercised at the protocol layer instead, see
tests/test_crawl_start_protocol.py)."""

from twclient import cli


def test_crawl_verb_is_wired_with_expected_defaults():
    parser = cli.build_parser()
    args = parser.parse_args(["crawl", "--profile", "sacrificial"])
    assert args.func is cli.cmd_crawl
    assert args.profile == "sacrificial"
    assert args.path is None
    assert args.log_path is None
    assert args.max_nodes == 200
    assert args.step_timeout == 8.0
    assert args.timeout == 600.0


def test_crawl_verb_requires_profile():
    parser = cli.build_parser()
    try:
        parser.parse_args(["crawl"])
        assert False, "expected SystemExit for a missing --profile"
    except SystemExit:
        pass


def test_crawl_verb_accepts_overrides():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "crawl",
            "--profile", "sacrificial",
            "--path", "/tmp/gk.json",
            "--log-path", "/tmp/crawl.jsonl",
            "--max-nodes", "50",
            "--step-timeout", "4",
        ]
    )
    assert args.path == "/tmp/gk.json"
    assert args.log_path == "/tmp/crawl.jsonl"
    assert args.max_nodes == 50
    assert args.step_timeout == 4.0
