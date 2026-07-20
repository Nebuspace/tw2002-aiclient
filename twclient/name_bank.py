"""Name bank (WO-MS-4 rider): cosmetic handle/ship_name/planet_name pools
for automated NEW-character registration.

`config/profiles.toml` (see credentials.py) still lets an operator pin an
exact handle/ship_name/planet_name — that always wins. This module exists
for the opposite case: an `allow_register=true` profile that leaves one or
more of those fields unset (the bulk/crawler registration shape), which
draws a fresh value per field from this bank instead. Per-field, not
all-or-nothing: a profile can pin `handle` while still bank-drawing
`ship_name`/`planet_name`, or any other combination.

These are display names only, never a secret — `random.Random` (not the
`secrets` module credentials.generate_password() deliberately uses) is the
right tool here, and it's the injectable one so tests are deterministic.
"""

import random
import tomllib
from pathlib import Path

NAME_BANK_PATH = Path(__file__).resolve().parent / "data" / "name_bank.toml"


class NameBankError(Exception):
    """The bank file is missing, unreadable, or missing an expected
    `[names]` list — never raised for a merely-small bank."""


def load_name_bank(path=None):
    """Returns `{"handles": [...], "ships": [...], "planets": [...]}`.
    Raises NameBankError if the file is absent or malformed rather than
    returning an empty/partial bank silently."""
    bank_path = Path(path) if path is not None else NAME_BANK_PATH
    if not bank_path.exists():
        raise NameBankError(f"name_bank_not_found:{bank_path}")
    with open(bank_path, "rb") as f:
        data = tomllib.load(f)
    names = data.get("names", {})
    missing = [k for k in ("handles", "ships", "planets") if not names.get(k)]
    if missing:
        raise NameBankError(f"name_bank_incomplete:{bank_path}:missing={missing}")
    return {"handles": names["handles"], "ships": names["ships"], "planets": names["planets"]}


def resolve_bank_identity(profile, rng=None, path=None):
    """Returns `(handle, ship_name, planet_name)` for a registration
    attempt: any field the profile explicitly set (per `Profile`'s own
    `*_explicit` flags, set at construction time before defaulting —
    credentials.py) always wins; an unset field is drawn randomly from the
    bank. `rng` is an injectable `random.Random` for deterministic tests;
    defaults to a fresh instance (seeded from OS entropy) when omitted."""
    rng = rng or random.Random()
    bank = load_name_bank(path)

    handle = profile.handle if getattr(profile, "handle_explicit", profile.handle is not None) else rng.choice(bank["handles"])
    ship_name = (
        profile.ship_name if getattr(profile, "ship_name_explicit", profile.ship_name is not None) else rng.choice(bank["ships"])
    )
    planet_name = (
        profile.planet_name
        if getattr(profile, "planet_name_explicit", profile.planet_name is not None)
        else rng.choice(bank["planets"])
    )
    return handle, ship_name, planet_name
