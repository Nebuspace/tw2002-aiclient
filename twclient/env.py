"""Pure-stdlib `.env` loader + host/port resolution order.

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
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"

HOST_VAR = "TW2002_HOST"
PORT_VAR = "TW2002_PORT"


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
        from . import credentials
        try:
            profile = credentials.load_profile(profile_name, profiles_path=profiles_path)
        except credentials.CredentialError:
            profile = None
        except ValueError as e:
            raise EnvResolutionError(
                f"config/profiles.toml's [{profile_name}] port is not a "
                f"valid integer ({e}) -- fix it in profiles.toml, or set "
                f"{PORT_VAR} to override it."
            )
        if profile is not None:
            if host is None:
                host = profile.host
            if port is None:
                port = profile.port

    if host is None:
        raise EnvResolutionError(
            f"could not resolve the game server host: pass --host, set "
            f"{HOST_VAR} in the environment or .env, or add a [default] "
            f"host in config/profiles.toml."
        )
    if port is None:
        raise EnvResolutionError(
            f"could not resolve the game server port: pass --port, set "
            f"{PORT_VAR} in the environment or .env, or add a [default] "
            f"port in config/profiles.toml."
        )
    return host, port
