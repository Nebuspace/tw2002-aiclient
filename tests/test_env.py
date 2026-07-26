""".env loader + host/port + run-dir resolution (no network).

WO-P2-021: prove project-rooted `run/` regardless of CWD, `TW_RUN_DIR`
override, and no silent per-profile splinter under the default.
"""

import os
import re
from pathlib import Path

import pytest

from tw2002_aiclient.session import env


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
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)


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
    assert os.environ["TW2002_HOST"] == "example.com"


def test_load_dotenv_never_overwrites_existing_process_env(tmp_path, monkeypatch):
    monkeypatch.setenv(env.HOST_VAR, "from-real-env")
    p = _write_dotenv(tmp_path, "TW2002_HOST=from-dotenv-file\n")
    env.load_dotenv(p)
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
    _clear_env(monkeypatch)
    dotenv_path = tmp_path / "nope.env"
    profiles_path = _write_profiles(tmp_path, '[other]\nhost="x"\nport=23\ngame_letter="F"\nhandle="H"\n')
    with pytest.raises(env.EnvResolutionError, match=env.HOST_VAR):
        env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)


def test_malformed_env_port_raises_actionable_error_not_a_bare_valueerror(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(env.HOST_VAR, "from-env")
    monkeypatch.setenv(env.PORT_VAR, "abc")
    dotenv_path = tmp_path / "nope.env"
    profiles_path = tmp_path / "nope.toml"
    with pytest.raises(env.EnvResolutionError, match=f"{env.PORT_VAR}.*abc"):
        env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)


def test_malformed_profiles_toml_port_raises_actionable_error_not_a_bare_valueerror(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    dotenv_path = tmp_path / "nope.env"
    profiles_path = _write_profiles(
        tmp_path, '[default]\nhost="from-profile"\nport="abc"\ngame_letter="F"\nhandle="H"\n'
    )
    with pytest.raises(env.EnvResolutionError, match="profiles.toml"):
        env.resolve_host_port(profiles_path=profiles_path, dotenv_path=dotenv_path)


# -- resolve_run_dir (WO-P2-021) --------------------------------------------

def test_resolve_run_dir_defaults_to_project_rooted_run(monkeypatch):
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)
    assert env.resolve_run_dir() == env.PROJECT_ROOT / "run"


def test_resolve_run_dir_independent_of_cwd(monkeypatch, tmp_path):
    """WO-P2-021 Accept: caller CWD must not move the default run/ home."""
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    assert Path.cwd() == tmp_path
    assert env.resolve_run_dir() == env.PROJECT_ROOT / "run"
    assert env.socket_path() == env.PROJECT_ROOT / "run" / env.SOCK_NAME
    assert env.pid_path() == env.PROJECT_ROOT / "run" / env.PID_NAME


def test_resolve_run_dir_honors_absolute_tw_run_dir(monkeypatch, tmp_path):
    alt = tmp_path / "alt-run"
    monkeypatch.setenv(env.RUN_DIR_VAR, str(alt))
    assert env.resolve_run_dir() == alt
    assert env.socket_path() == alt / env.SOCK_NAME
    assert env.pid_path() == alt / env.PID_NAME


def test_resolve_run_dir_honors_relative_tw_run_dir(monkeypatch):
    monkeypatch.setenv(env.RUN_DIR_VAR, "run/alt")
    assert env.resolve_run_dir() == env.PROJECT_ROOT / "run" / "alt"


def test_default_run_dir_is_not_per_profile(monkeypatch):
    """WO-P2-021 Accept: with TW_RUN_DIR unset there is one shared run/,
    never a silent run/<profile> splinter."""
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)
    # resolve_run_dir takes no profile arg -- the API itself forbids splintering
    assert env.resolve_run_dir() == env.PROJECT_ROOT / "run"


# -- resolve_run_dir: refuse a dirty override (WO-RUN-DIR-NORMALISE) -------
#
# A stray leading space makes `Path(" /tmp/x").is_absolute()` return False,
# so an absolute override silently resolves under PROJECT_ROOT instead --
# two callers that believe they share a run/ home land on different
# directories, defeating the Single-Connection Invariant. Refused loudly
# rather than silently repaired (hub-ratified 2026-07-26, overruling the
# audit's own earlier `.strip()` suggestion): see resolve_run_dir's
# docstring for why.

def test_resolve_run_dir_rejects_leading_whitespace(monkeypatch):
    monkeypatch.setenv(env.RUN_DIR_VAR, " /tmp/twrun")
    with pytest.raises(env.EnvResolutionError, match="stray whitespace or a newline"):
        env.resolve_run_dir()


def test_resolve_run_dir_rejects_trailing_whitespace(monkeypatch):
    monkeypatch.setenv(env.RUN_DIR_VAR, "/tmp/twrun ")
    with pytest.raises(env.EnvResolutionError, match="stray whitespace or a newline"):
        env.resolve_run_dir()


def test_resolve_run_dir_rejects_trailing_newline(monkeypatch):
    monkeypatch.setenv(env.RUN_DIR_VAR, "/tmp/twrun\n")
    with pytest.raises(env.EnvResolutionError, match="stray whitespace or a newline"):
        env.resolve_run_dir()


def test_resolve_run_dir_rejects_embedded_newline(monkeypatch):
    """Not just an edge case -- a `\\n` in the MIDDLE of the value (e.g. a
    botched multi-line env-file value) is refused too, since no legitimate
    run-dir path ever contains a raw newline."""
    monkeypatch.setenv(env.RUN_DIR_VAR, "/tmp/tw\nrun")
    with pytest.raises(env.EnvResolutionError, match="stray whitespace or a newline"):
        env.resolve_run_dir()


def test_resolve_run_dir_rejects_embedded_carriage_return(monkeypatch):
    """Same for an embedded `\\r` -- the CRLF-line-ending failure mode, not
    only at the tail of the value."""
    monkeypatch.setenv(env.RUN_DIR_VAR, "/tmp/tw\rrun")
    with pytest.raises(env.EnvResolutionError, match="stray whitespace or a newline"):
        env.resolve_run_dir()


def test_resolve_run_dir_error_names_the_stray_whitespace(monkeypatch):
    """The message must make the invisible visible -- repr(), not the raw
    string, since the audit found the whitespace difference invisible in
    most terminals."""
    monkeypatch.setenv(env.RUN_DIR_VAR, " /tmp/twrun")
    with pytest.raises(env.EnvResolutionError, match=re.escape(repr(" /tmp/twrun"))):
        env.resolve_run_dir()


def test_resolve_run_dir_whitespace_only_is_unset(monkeypatch):
    """E-03's own reasoning extended: a whitespace-only override is
    indistinguishable from "operator cleared it" once stripped, so both
    land on the same safe default rather than raising."""
    monkeypatch.setenv(env.RUN_DIR_VAR, "   ")
    assert env.resolve_run_dir() == env.PROJECT_ROOT / "run"


def test_resolve_run_dir_empty_string_still_unset(monkeypatch):
    """Regression pin: "" must keep behaving as unset after the fix."""
    monkeypatch.setenv(env.RUN_DIR_VAR, "")
    assert env.resolve_run_dir() == env.PROJECT_ROOT / "run"


def test_resolve_run_dir_clean_absolute_path_unaffected(monkeypatch, tmp_path):
    """A well-formed override is untouched by the new whitespace check."""
    alt = tmp_path / "alt-run"
    monkeypatch.setenv(env.RUN_DIR_VAR, str(alt))
    assert env.resolve_run_dir() == alt


def test_resolve_run_dir_internal_space_is_not_flagged(monkeypatch, tmp_path):
    """A plain internal SPACE is a real, supported POSIX path component and
    is left alone -- only edge whitespace and any embedded `\\n`/`\\r` are
    refused (see the embedded-newline/CR pins above)."""
    alt = tmp_path / "alt run"
    monkeypatch.setenv(env.RUN_DIR_VAR, str(alt))
    assert env.resolve_run_dir() == alt
