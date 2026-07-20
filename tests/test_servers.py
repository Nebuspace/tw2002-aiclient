"""WO-MS-1 server catalog tests."""

from pathlib import Path

import pytest

from twclient import credentials, servers


def test_catalog_has_48_servers():
    rows = servers.list_servers()
    assert len(rows) == 48


def test_front_end_values_are_contract():
    for rec in servers.list_servers():
        assert rec["front_end"] in servers.FRONT_ENDS
        assert rec["port"] is not None


def test_get_server_and_resolve():
    rows = servers.list_servers()
    key = rows[0]["key"]
    rec = servers.get_server(key)
    host, port = servers.resolve_endpoint(key)
    assert host == rec["hostname"]
    assert port == rec["port"]


def test_adding_server_is_catalog_edit_only(tmp_path: Path):
    """Accept criterion: new server = toml edit, zero code change."""
    src = Path(servers.SERVERS_PATH).read_text()
    catalog = tmp_path / "servers.toml"
    catalog.write_text(
        src
        + "\n[servers.wo_ms1_tmp_probe]\n"
        + 'hostname = "example.invalid"\n'
        + "port = 2345\n"
        + 'transport = "telnet"\n'
        + 'front_end = "auto"\n'
        + "aliases = []\n"
        + 'status = "listed"\n'
        + "sources = [\"test\"]\n"
    )
    rows = servers.list_servers(path=catalog)
    assert len(rows) == 49
    host, port = servers.resolve_endpoint("wo_ms1_tmp_probe", path=catalog)
    assert (host, port) == ("example.invalid", 2345)


def test_profile_resolves_via_server_key(tmp_path: Path):
    # Pick a real catalog key
    key = servers.list_servers()[0]["key"]
    expect_host, expect_port = servers.resolve_endpoint(key)
    profiles = tmp_path / "profiles.toml"
    profiles.write_text(
        f"[via_catalog]\n"
        f'server = "{key}"\n'
        f'game_letter = "F"\n'
        f'handle = "CATALOG"\n'
    )
    prof = credentials.load_profile("via_catalog", profiles_path=profiles)
    assert prof.host == expect_host
    assert prof.port == expect_port
    assert prof.server == key


def test_profile_host_port_backcompat(tmp_path: Path):
    profiles = tmp_path / "profiles.toml"
    profiles.write_text(
        "[legacy]\n"
        'host = "legacy.example"\n'
        "port = 2002\n"
        'game_letter = "A"\n'
        'handle = "LEGACY"\n'
    )
    prof = credentials.load_profile("legacy", profiles_path=profiles)
    assert prof.host == "legacy.example"
    assert prof.port == 2002
    assert prof.server is None


def test_bad_front_end_rejected(tmp_path: Path):
    catalog = tmp_path / "servers.toml"
    catalog.write_text(
        "[servers.bad]\n"
        'hostname = "x.example"\n'
        "port = 23\n"
        'front_end = "nope"\n'
        'transport = "telnet"\n'
        'status = "listed"\n'
    )
    with pytest.raises(servers.ServerCatalogError):
        servers.load_servers(path=catalog)
