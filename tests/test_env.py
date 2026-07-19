"""`.env` loader + host/port resolution order tests (no network, tmp_path
only, never touches the real repo-root .env or config/profiles.toml)."""

import pytest

from twclient import env


def _write_dotenv(tmp_path, body):
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def _write_profiles(tmp_path, body):
    path = tmp_path / "profiles.toml"
    path.write_text(body, encoding="utf-8")
    return path


def _clear_env(monkeypatch):
    monkeypatch.delenv(env.HOST_VAR, raising=False)
    monkeypatch.delenv(env.PORT_VAR, raising=False)


# -- load_dotenv ------------------------------------------------------------

def test_load_dotenv_missing_file_returns_empty(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    assert env.load_dotenv(tmp_path / "nope.env") == {}


def test_load_dotenv_parses_key_value_pairs(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    p = _write_dotenv(tmp_path, "TW2002_HOST=example.com\nTW2002_PORT=23\n")
    values = env.load_dotenv(p)
    assert values == {"TW2002_HOST": "example.com", "TW2002_PORT": "23"}


def test_load_dotenv_ignores_blank_lines_and_comments(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    p = _write_dotenv(tmp_path, "\n# a comment\nTW2002_HOST=example.com\n  \n# TW2002_PORT=999\n")
    values = env.load_dotenv(p)
    assert values == {"TW2002_HOST": "example.com"}


def test_load_dotenv_strips_matching_quotes(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    p = _write_dotenv(tmp_path, 'TW2002_HOST="example.com"\nTW2002_PORT=\'23\'\n')
    values = env.load_dotenv(p)
    assert values == {"TW2002_HOST": "example.com", "TW2002_PORT": "23"}


def test_load_dotenv_applies_values_to_os_environ(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    p = _write_dotenv(tmp_path, "TW2002_HOST=example.com\n")
    env.load_dotenv(p)
    import os

    assert os.environ["TW2002_HOST"] == "example.com"


def test_load_dotenv_never_overwrites_existing_process_env(tmp_path, monkeypatch):
    monkeypatch.setenv(env.HOST_VAR, "from-real-env")
    p = _write_dotenv(tmp_path, "TW2002_HOST=from-dotenv-file\n")
    env.load_dotenv(p)
    import os

    assert os.environ[env.HOST_VAR] == "from-real-env"


# -- resolve_host_port precedence -------------------------------------------

def test_cli_arg_wins_over_everything(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(env.HOST_VAR, "from-env")
    monkeypatch.setenv(env.PORT_VAR, "9999")
    dotenv_path = _write_dotenv(tmp_path, "TW2002_HOST=from-dotenv\nTW2002_PORT=8888\n")
    profiles_path = _write_profiles(
        tmp_path, '[default]\nhost="from-profile"\nport=7777\ngame_letter="F"\nhandle="H"\n'
    )
    host, port = env.resolve_host_port(
        "from-cli", 1234, profiles_path=profiles_path, dotenv_path=dotenv_path
    )
    assert (host, port) == ("from-cli", 1234)


def test_process_env_wins_over_dotenv_file_and_profiles(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(env.HOST_VAR, "from-env")
    monkeypatch.setenv(env.PORT_VAR, "9999")
    dotenv_path = _write_dotenv(tmp_path, "TW2002_HOST=from-dotenv\nTW2002_PORT=8888\n")
    profiles_path = _write_profiles(
        tmp_path, '[default]\nhost="from-profile"\nport=7777\ngame_letter="F"\nhandle="H"\n'
    )
    host, port = env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)
    assert (host, port) == ("from-env", 9999)


def test_dotenv_file_wins_over_profiles_toml(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    dotenv_path = _write_dotenv(tmp_path, "TW2002_HOST=from-dotenv\nTW2002_PORT=8888\n")
    profiles_path = _write_profiles(
        tmp_path, '[default]\nhost="from-profile"\nport=7777\ngame_letter="F"\nhandle="H"\n'
    )
    host, port = env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)
    assert (host, port) == ("from-dotenv", 8888)


def test_profiles_toml_is_the_last_resort(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    dotenv_path = tmp_path / "nope.env"
    profiles_path = _write_profiles(
        tmp_path, '[default]\nhost="from-profile"\nport=7777\ngame_letter="F"\nhandle="H"\n'
    )
    host, port = env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)
    assert (host, port) == ("from-profile", 7777)


def test_mixed_sources_resolve_independently_per_field(tmp_path, monkeypatch):
    """host comes from an explicit CLI arg, port falls all the way
    through to profiles.toml -- each field resolves through the chain
    independently."""
    _clear_env(monkeypatch)
    dotenv_path = tmp_path / "nope.env"
    profiles_path = _write_profiles(
        tmp_path, '[default]\nhost="from-profile"\nport=7777\ngame_letter="F"\nhandle="H"\n'
    )
    host, port = env.resolve_host_port(
        "from-cli", None, profiles_path=profiles_path, dotenv_path=dotenv_path
    )
    assert (host, port) == ("from-cli", 7777)


def test_raises_actionable_error_naming_host_var_when_unresolved(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    dotenv_path = tmp_path / "nope.env"
    profiles_path = tmp_path / "nope.toml"
    with pytest.raises(env.EnvResolutionError, match=env.HOST_VAR):
        env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)


def test_raises_actionable_error_naming_port_var_when_only_port_unresolved(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(env.HOST_VAR, "from-env")
    dotenv_path = tmp_path / "nope.env"
    profiles_path = tmp_path / "nope.toml"
    with pytest.raises(env.EnvResolutionError, match=env.PORT_VAR):
        env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)


def test_incomplete_profile_is_treated_as_unresolved_not_a_crash(tmp_path, monkeypatch):
    """A profiles.toml missing the [default] section (or missing
    required fields) must not raise CredentialError out of
    resolve_host_port -- it's just one more exhausted source."""
    _clear_env(monkeypatch)
    dotenv_path = tmp_path / "nope.env"
    profiles_path = _write_profiles(tmp_path, '[other]\nhost="x"\nport=23\ngame_letter="F"\nhandle="H"\n')
    with pytest.raises(env.EnvResolutionError, match=env.HOST_VAR):
        env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)


# -- malformed port sources raise EnvResolutionError, never a naked crash --

def test_malformed_env_port_raises_actionable_error_not_a_bare_valueerror(tmp_path, monkeypatch):
    """TW2002_PORT=abc must not surface a naked ValueError traceback --
    it's an actionable EnvResolutionError naming the var and the bad
    value, same phrasing family as the other resolution errors."""
    _clear_env(monkeypatch)
    monkeypatch.setenv(env.HOST_VAR, "from-env")
    monkeypatch.setenv(env.PORT_VAR, "abc")
    dotenv_path = tmp_path / "nope.env"
    profiles_path = tmp_path / "nope.toml"
    with pytest.raises(env.EnvResolutionError, match=f"{env.PORT_VAR}.*abc"):
        env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)


def test_malformed_profiles_toml_port_raises_actionable_error_not_a_bare_valueerror(tmp_path, monkeypatch):
    """A profiles.toml [default] port that can't convert to int (e.g. a
    quoted non-numeric string) must not surface a naked ValueError out
    of credentials.Profile -- it's an actionable EnvResolutionError."""
    _clear_env(monkeypatch)
    dotenv_path = tmp_path / "nope.env"
    profiles_path = _write_profiles(
        tmp_path, '[default]\nhost="from-profile"\nport="abc"\ngame_letter="F"\nhandle="H"\n'
    )
    with pytest.raises(env.EnvResolutionError, match="profiles.toml"):
        env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)
