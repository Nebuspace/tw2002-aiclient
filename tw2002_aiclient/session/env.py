"""Pure-stdlib `.env` loader + project-rooted path resolution.

Resolution precedence for the game server host/port (highest to lowest):

  1. an explicit CLI arg (e.g. `tw start --host ...`), when actually given
  2. `TW2002_HOST` / `TW2002_PORT` already set in the process environment
  3. `.env` file values (repo-root `.env`, gitignored -- see `.env.example`
     if present, or `config/profiles.toml.example` for the shape)
  4. `config/profiles.toml`'s `[default]` section (host/port only)
  5. no silent fallback host -- raises `EnvResolutionError` naming the
     missing variable

This mirrors the env-first idiom `credentials.py` already uses for
`TW2002_PASSWORD_<PROFILE>` (env checked before the on-disk store), just
applied to host/port instead of the password.

This module is also the project's one home for **project-rooted path
resolution** -- `run/`, `logs/`, `state/`, `config/` all resolve relative
to the repo root regardless of the caller's CWD (see canon's Single-
Connection Invariant, `canon/architecture/session-engine.md`), not
relative to wherever `tw`/`twd` happened to be invoked from.
"""

import os
from pathlib import Path

# session/env.py -> session -> tw2002_aiclient -> repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"
CONFIG_DIR = PROJECT_ROOT / "config"
STATE_DIR = PROJECT_ROOT / "state"
LOG_DIR = PROJECT_ROOT / "logs"
PROFILES_PATH = CONFIG_DIR / "profiles.toml"

HOST_VAR = "TW2002_HOST"
PORT_VAR = "TW2002_PORT"

# The sole documented override for the daemon's run/ home (pidfile +
# socket) -- see the Single-Connection Invariant. Unset by default, so
# every caller lands on the one project-rooted `run/` directory.
RUN_DIR_VAR = "TW_RUN_DIR"

SOCK_NAME = "twd.sock"
PID_NAME = "twd.pid"


class EnvResolutionError(Exception):
    """Raised when host/port cannot be resolved from any source."""


def load_dotenv(path=None):
    """Parse a simple `KEY=VALUE` `.env` file into `os.environ`.

    Blank lines and lines starting with `#` are ignored. Values may
    optionally be wrapped in matching single or double quotes, which are
    stripped. Never overwrites a variable already present in the process
    environment -- a real env var always outranks the file (this is what
    makes the CLI-arg/env/.env precedence chain work: by the time
    `resolve_host_port` reads `os.environ`, a pre-existing process env var
    has already blocked the file's value from landing).

    Returns the dict of key/value pairs found in the file (regardless of
    whether they were actually applied to `os.environ`), so callers can
    inspect what the file itself declared.
    """
    path = path or DOTENV_PATH
    if not path.exists():
        return {}
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not key:
            continue
        values[key] = value
        if key not in os.environ:
            os.environ[key] = value
    return values


def _load_profile_host_port(profile_name, profiles_path):
    """Read `host`/`port` out of one `[profile_name]` table in
    `profiles.toml` -- the simple, catalog-free shape canon specifies for
    env.py's own fallback (a `[default]` section, host/port only). This
    is deliberately narrower than the full profile system (server-catalog
    keys, handle/game_letter validation, `Profile` objects): that richer
    shape belongs to `credentials.py`, which callers needing a *named*
    profile with autopilot/registration policy should use directly. Never
    raises for a missing file or missing section -- only for a malformed
    TOML file or a non-integer `port`, both real misconfigurations.
    """
    path = profiles_path or PROFILES_PATH
    if not path.exists():
        return None, None
    import tomllib

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise EnvResolutionError(
            f"{path} is not valid TOML ({e}) -- fix it or remove it."
        ) from e
    section = data.get(profile_name)
    if not isinstance(section, dict):
        return None, None
    host = section.get("host")
    port = section.get("port")
    if port is not None:
        try:
            port = int(port)
        except (TypeError, ValueError):
            raise EnvResolutionError(
                f"{path}'s [{profile_name}] port is not a valid integer "
                f"({port!r}) -- fix it in profiles.toml, or set "
                f"{PORT_VAR} to override it."
            )
    return host, port


def resolve_host_port(cli_host=None, cli_port=None, profile_name="default",
                       profiles_path=None, dotenv_path=None):
    """Resolve (host, port) per the module's precedence order.

    `cli_host`/`cli_port` should be the parsed argparse values with
    `default=None` -- i.e. only non-None when the caller actually passed
    `--host`/`--port`. Raises `EnvResolutionError` with an actionable
    message (naming the missing env var) if nothing resolves.
    """
    load_dotenv(dotenv_path)

    host = cli_host
    port = cli_port

    if host is None:
        host = os.environ.get(HOST_VAR) or None
    if port is None:
        env_port = os.environ.get(PORT_VAR)
        if env_port:
            try:
                port = int(env_port)
            except ValueError:
                raise EnvResolutionError(
                    f"{PORT_VAR} is set to {env_port!r}, which is not a valid "
                    f"integer port -- fix it in the environment or .env."
                )

    if host is None or port is None:
        profile_host, profile_port = _load_profile_host_port(profile_name, profiles_path)
        if host is None:
            host = profile_host
        if port is None:
            port = profile_port

    if host is None:
        raise EnvResolutionError(
            f"could not resolve the game server host: pass --host, set "
            f"{HOST_VAR} in the environment or .env, or add a [{profile_name}] "
            f"host in config/profiles.toml."
        )
    if port is None:
        raise EnvResolutionError(
            f"could not resolve the game server port: pass --port, set "
            f"{PORT_VAR} in the environment or .env, or add a [{profile_name}] "
            f"port in config/profiles.toml."
        )
    return host, port


def resolve_run_dir():
    """Resolve the project-rooted `run/` directory (pidfile + socket home).

    Honors `TW_RUN_DIR` as the sole override (absolute, or relative to
    `PROJECT_ROOT`); defaults to `PROJECT_ROOT / "run"`. Independent of
    the caller's CWD either way -- `tw`/`twd` invoked from any directory
    resolve to the same `run/` home, per the Single-Connection Invariant.
    """
    override = os.environ.get(RUN_DIR_VAR)
    if not override:
        return PROJECT_ROOT / "run"
    p = Path(override)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def socket_path(run_dir=None):
    """The unix-domain command socket path under `run_dir` (default:
    `resolve_run_dir()`)."""
    return (run_dir or resolve_run_dir()) / SOCK_NAME


def pid_path(run_dir=None):
    """The daemon pidfile path under `run_dir` (default:
    `resolve_run_dir()`)."""
    return (run_dir or resolve_run_dir()) / PID_NAME
