"""credentials.is_crawl_sacrificial — fail-closed reader for the third,
`dev`-sender live-drive exception's gate (WO-BUILD-DEV-DRIVE-SENDER-ENFORCEMENT,
canon: canon/doctrine/dev-drive-exception.md).

Reuses the same ``crawl_sacrificial`` flag `menu.crawl_driver.run_live_crawl`
already gates a live crawl on (`_SACRIFICIAL_FLAG`), read straight from
``profiles.toml`` this time rather than off an in-memory profile object.
Every negative shape must answer ``False`` — never raise, never default to
permissive.
"""

from __future__ import annotations

import importlib

import pytest

from tw2002_aiclient.session import credentials


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("TW_CONFIG_DIR", str(tmp_path))
    importlib.reload(credentials)
    assert credentials.CONFIG_DIR == tmp_path
    yield tmp_path
    importlib.reload(credentials)


def _write_profiles(cfg, text):
    (cfg / "profiles.toml").write_text(text)


def test_no_profiles_store_at_all_refuses(cfg):
    assert credentials.is_crawl_sacrificial("sac1") is False


def test_profile_not_present_refuses(cfg):
    _write_profiles(cfg, '[alpha]\nserver = "demo"\ngame_letter = "A"\n')
    assert credentials.is_crawl_sacrificial("sac1") is False


def test_flag_absent_refuses(cfg):
    _write_profiles(cfg, '[sac1]\nserver = "demo"\ngame_letter = "A"\n')
    assert credentials.is_crawl_sacrificial("sac1") is False


def test_flag_false_refuses(cfg):
    _write_profiles(
        cfg, '[sac1]\nserver = "demo"\ngame_letter = "A"\ncrawl_sacrificial = false\n'
    )
    assert credentials.is_crawl_sacrificial("sac1") is False


def test_flag_string_truthy_stand_in_refuses(cfg):
    # TOML `crawl_sacrificial = "true"` parses to the Python str "true",
    # not the bool True -- `is True` refuses it, mirroring
    # crawl_driver._SACRIFICIAL_FLAG's own stricter-than-truthy check.
    _write_profiles(
        cfg, '[sac1]\nserver = "demo"\ngame_letter = "A"\ncrawl_sacrificial = "true"\n'
    )
    assert credentials.is_crawl_sacrificial("sac1") is False


def test_flag_integer_truthy_stand_in_refuses(cfg):
    _write_profiles(
        cfg, '[sac1]\nserver = "demo"\ngame_letter = "A"\ncrawl_sacrificial = 1\n'
    )
    assert credentials.is_crawl_sacrificial("sac1") is False


def test_flag_true_authorizes(cfg):
    _write_profiles(
        cfg, '[sac1]\nserver = "demo"\ngame_letter = "A"\ncrawl_sacrificial = true\n'
    )
    assert credentials.is_crawl_sacrificial("sac1") is True


def test_malformed_profile_section_refuses(cfg):
    _write_profiles(cfg, "sac1 = 5\n")
    assert credentials.is_crawl_sacrificial("sac1") is False


def test_unreadable_store_refuses_not_raises(cfg):
    path = cfg / "profiles.toml"
    _write_profiles(cfg, '[sac1]\ncrawl_sacrificial = true\n')
    path.chmod(0o000)
    try:
        assert credentials.is_crawl_sacrificial("sac1") is False
    finally:
        path.chmod(0o644)
