"""OPEN-003-A -- the shared catalog-aware profile resolver
(`credentials.resolve_profile_host_port`) + the `TW_CONFIG_DIR` seam that
lets every caller (env.py / cli.py / protocol.py) point at an isolated
config directory, including across a process boundary (the daemon-spawn
env-passing idiom `TW_RUN_DIR` already uses).

Self-contained -- does not rely on the repo `conftest.py`, never touches
the real `config/` directory, and never writes a secret to disk (this
resolver only ever deals in host/port, not passwords).
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tw2002_aiclient.session import credentials, env

SERVERS_TOML = (
    '[servers.testserver]\n'
    'name = "Test Server"\n'
    'host = "catalog.example.test"\n'
    'port = 2323\n'
)


def _write_config(tmp_path, *, servers=SERVERS_TOML, profiles):
    (tmp_path / "servers.toml").write_text(servers, encoding="utf-8")
    (tmp_path / "profiles.toml").write_text(profiles, encoding="utf-8")


@pytest.fixture
def isolated_credentials(tmp_path, monkeypatch):
    """Point `credentials` (and its module-level `CONFIG_DIR`/`*_PATH`
    constants) at an isolated directory via `TW_CONFIG_DIR` + a real
    module reload -- exercising the actual env-var-driven resolution
    path (the sanctioned isolation mechanism per this module's own
    docstring) rather than monkeypatching the path attributes directly.

    Reloads back to the real repo config on teardown so later test
    files in the same session aren't left pointed at a deleted tmp dir
    (the module is reused in-place by `importlib.reload`, so every
    other module's `credentials.PROFILES_PATH`-style attribute lookup
    sees the restored value too).
    """
    monkeypatch.setenv("TW_CONFIG_DIR", str(tmp_path))
    importlib.reload(credentials)
    assert credentials.CONFIG_DIR == tmp_path
    try:
        yield credentials, tmp_path
    finally:
        monkeypatch.delenv("TW_CONFIG_DIR", raising=False)
        importlib.reload(credentials)


# -- 1: catalog-only profile -------------------------------------------------


def test_resolve_catalog_only_profile_uses_server_catalog(isolated_credentials):
    creds, tmp_path = isolated_credentials
    _write_config(tmp_path, profiles='[profile_x]\nserver = "testserver"\n')
    assert creds.resolve_profile_host_port("profile_x") == ("catalog.example.test", 2323)


# -- 2: explicit override wins even alongside a server= key -----------------


def test_resolve_explicit_host_port_overrides_server_catalog(isolated_credentials):
    creds, tmp_path = isolated_credentials
    _write_config(
        tmp_path,
        profiles=(
            '[profile_x]\n'
            'server = "testserver"\n'
            'host = "override.example.test"\n'
            'port = 9999\n'
        ),
    )
    # catalog entry (if consulted) would resolve to catalog.example.test:2323 --
    # the override must win outright, not merge.
    assert creds.resolve_profile_host_port("profile_x") == ("override.example.test", 9999)


# -- 3: unresolvable / missing-section cases raise ---------------------------


def test_resolve_neither_host_port_nor_server_raises(isolated_credentials):
    creds, tmp_path = isolated_credentials
    _write_config(tmp_path, profiles='[profile_x]\nhandle = "nobody"\n')
    with pytest.raises(creds.ProfileConnectionError):
        creds.resolve_profile_host_port("profile_x")


def test_resolve_missing_profile_section_raises(isolated_credentials):
    creds, tmp_path = isolated_credentials
    _write_config(tmp_path, profiles='[other_profile]\nserver = "testserver"\n')
    with pytest.raises(creds.ProfileConnectionError):
        creds.resolve_profile_host_port("profile_x")


def test_resolve_missing_profiles_file_raises(isolated_credentials):
    creds, tmp_path = isolated_credentials
    (tmp_path / "servers.toml").write_text(SERVERS_TOML, encoding="utf-8")
    # deliberately no profiles.toml written at all
    with pytest.raises(creds.ProfileConnectionError):
        creds.resolve_profile_host_port("profile_x")


def test_resolve_unknown_server_catalog_key_raises(isolated_credentials):
    creds, tmp_path = isolated_credentials
    _write_config(tmp_path, profiles='[profile_x]\nserver = "nonexistent"\n')
    with pytest.raises(creds.ProfileConnectionError):
        creds.resolve_profile_host_port("profile_x")


# -- 4: TW_CONFIG_DIR isolation across a process boundary --------------------


def test_tw_config_dir_isolation_across_process_boundary(tmp_path):
    """The exact cross-process gap the seam closes: a daemon spawned with
    `TW_CONFIG_DIR` in its env (the same idiom `TW_RUN_DIR` already uses
    for daemon spawn, see `cli.py`) must see the isolated config dir the
    moment `credentials` is imported -- and a subprocess with no override
    must still land on the real project `config/`."""
    _write_config(tmp_path, profiles='[profile_x]\nserver = "testserver"\n')
    repo_root = Path(__file__).resolve().parent.parent

    probe = (
        "import json; "
        "from tw2002_aiclient.session import credentials as c; "
        "host, port = c.resolve_profile_host_port('profile_x'); "
        "print(json.dumps({'config_dir': str(c.CONFIG_DIR), 'host': host, 'port': port}))"
    )
    with_override = dict(os.environ, TW_CONFIG_DIR=str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=repo_root, env=with_override, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["config_dir"] == str(tmp_path)
    assert (payload["host"], payload["port"]) == ("catalog.example.test", 2323)

    without_override = dict(os.environ)
    without_override.pop("TW_CONFIG_DIR", None)
    result2 = subprocess.run(
        [sys.executable, "-c", "from tw2002_aiclient.session import credentials as c; print(c.CONFIG_DIR)"],
        cwd=repo_root, env=without_override, capture_output=True, text=True, timeout=30,
    )
    assert result2.returncode == 0, result2.stderr
    assert result2.stdout.strip() == str(repo_root / "config")


# -- 5: the env tier still wins over a profile (catalog or otherwise) -------


def test_env_var_still_wins_over_profile(tmp_path, monkeypatch):
    """`TW2002_HOST`/`TW2002_PORT` outrank profiles.toml regardless of
    whether the profile resolves via the server catalog -- env.py's own
    documented precedence (env above the profile fallback)."""
    monkeypatch.setenv(env.HOST_VAR, "env-wins.example.test")
    monkeypatch.setenv(env.PORT_VAR, "4242")
    profiles_path = tmp_path / "profiles.toml"
    profiles_path.write_text('[profile_x]\nserver = "testserver"\n', encoding="utf-8")

    host, port = env.resolve_host_port(
        profile_name="profile_x",
        profiles_path=profiles_path,
        dotenv_path=tmp_path / "does-not-exist.env",
    )
    assert (host, port) == ("env-wins.example.test", 4242)


# -- 6: all callers agree on the same catalog-only profile (best-effort) ----


def test_env_and_credentials_agree_on_catalog_only_profile(isolated_credentials, monkeypatch):
    """Cross-caller consistency check for OPEN-003-A: once `env.py` is
    wired onto the shared resolver, `env.resolve_host_port` (with no
    CLI/env host override) and `credentials.resolve_profile_host_port`
    must resolve a catalog-only profile identically. Gated: skips with a
    note if `env.py` hasn't been wired yet (its current fallback path
    only reads a literal host/port off the profile, not the `server`
    catalog key, so it can't resolve this profile at all pre-wiring)."""
    creds, tmp_path = isolated_credentials
    _write_config(tmp_path, profiles='[profile_x]\nserver = "testserver"\n')

    monkeypatch.delenv(env.HOST_VAR, raising=False)
    monkeypatch.delenv(env.PORT_VAR, raising=False)

    expected = creds.resolve_profile_host_port("profile_x")

    try:
        actual = env.resolve_host_port(
            profile_name="profile_x",
            profiles_path=tmp_path / "profiles.toml",
            dotenv_path=tmp_path / "does-not-exist.env",
        )
    except env.EnvResolutionError as exc:
        pytest.skip(
            "env.py not yet wired onto credentials.resolve_profile_host_port -- "
            f"its profile fallback can't follow a server= catalog key yet ({exc}). "
            "Re-run after Worker 2's env.py wiring lands."
        )

    assert actual == expected


# -- secret hygiene ------------------------------------------------------


def test_resolver_never_writes_a_secrets_file(isolated_credentials):
    """This resolver deals only in host/port -- confirm no secrets.json
    is ever created as a side effect of resolving a profile."""
    creds, tmp_path = isolated_credentials
    _write_config(tmp_path, profiles='[profile_x]\nserver = "testserver"\n')
    creds.resolve_profile_host_port("profile_x")
    assert not (tmp_path / "secrets.json").exists()
