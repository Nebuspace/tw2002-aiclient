"""Minimal password resolver (WO-P0-005).

Implements the read-only half of the doctrine's resolution precedence
(see canon/doctrine/secrets-and-credentials.md, "Schema"):

    1. `TW2002_PASSWORD_<PROFILE>` environment variable (caller/CI-managed,
       never written by this module).
    2. `config/secrets.json` entry (gitignored, chmod-600 — the only
       on-disk home for a password).
    3. Neither present -> absent is legitimate, NOT an error: returns
       None. This is the normal state of a profile whose character has
       never been registered.

A password is never logged here, and neither is its length — a byte
count is itself a leak (doctrine Invariant 2).

DEFERRED to a later WO (out of scope here): the write path
(`save_password()`), CSPRNG password generation (`generate_password()`),
and the `allow_register` NEW-character-registration gate — see doctrine
Citation [1] and Code Divergence #2. IF a future writer creates
`config/secrets.json`, it MUST be created (and re-asserted on every
write) at mode 0600 — plaintext-but-sealed, per the doctrine's "Two
On-Disk Homes" section.
"""

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
SECRETS_PATH = CONFIG_DIR / "secrets.json"


def _env_var_name(profile: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in profile.upper())
    return f"TW2002_PASSWORD_{safe}"


def get_password(profile: str) -> str | None:
    """Resolve `profile`'s password: env-first, then the secrets file.

    Never raises for a merely-absent credential -- returns None, which is
    the expected state for a profile that has no stored/overridden
    password anywhere.
    """
    env_val = os.environ.get(_env_var_name(profile))
    if env_val:
        return env_val

    if not SECRETS_PATH.exists():
        return None
    with open(SECRETS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    entry = data.get(profile)
    if isinstance(entry, dict) and entry.get("password"):
        return entry["password"]
    return None
