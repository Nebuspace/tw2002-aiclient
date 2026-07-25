"""WO-TWD-PROFILE-STORE-UNREADABLE — an unreadable profile store must reach
the operator as a line, not as a traceback.

``daemon.main`` catches exactly one thing around host/port resolution,
``env.EnvResolutionError``, because that is the contract ``env.py`` publishes.
``env._load_profile_host_port`` is the translator that owes it: it turns
``credentials.py``'s typed ``ProfileConnectionError`` family into either
"absent, fall through" or that one error.

It used to enumerate the LOUD side (``except credentials.ProfileMalformed``),
and the loud side is an OPEN set. ``ProfileStoreUnreadable`` was added as a
direct child of the base — deliberately not a ``ProfileMalformed``, because
nothing was read, so nothing can be called malformed — and it fell straight
through every handler: ``chmod 000 config/profiles.toml`` with no
``--host/--port`` killed ``twd`` at startup with a full traceback.

So the enumeration moved to the ABSENT side, which is the CLOSED one
(``ProfileConnectionError``'s own docstring: *"Absence is never one of
these"*), and everything else is caught at the family BASE. The next family
member then defaults to loud-and-actionable instead of to a traceback.

Three layers, because each proves something the others cannot:

* **A — the daemon's own startup path.** ``daemon.main`` driven for real
  against real ``chmod 000`` conditions; a traceback here is an exception
  escaping ``main``, not a ``SystemExit``, so the assertion is structural.
* **B — the translation itself**, including the two-sided control: a
  genuinely absent store must still fall through as "nothing here". A
  handler that shouts on everything has only moved the collapse.
* **C — the tripwire.** Walk ``ProfileConnectionError.__subclasses__()``
  *recursively* and hold every member to one of the two outcomes. A new
  sibling in ``credentials.py`` then fails HERE, in a fast unit test,
  instead of at a daemon start in front of an operator.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tw2002_aiclient.session import credentials, daemon, env

# chmod-based denial proves nothing as root: the kernel lets root read a 000
# file, so the "denied" branch would never be reached and the test would pass
# for the wrong reason.
_needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses file permissions — the denial can't be provoked",
)

PROFILE = '[default]\nhost = "profile.example.test"\nport = 2323\n'

# The CLOSED absent set, stated here independently of ``env.py``'s own tuple
# rather than imported from it. Two independent statements of the same
# contract: if either side moves, layer C's walk disagrees with reality and
# fails. Held by NAME, not by class identity, because
# ``test_credentials_store_honesty`` / ``test_profile_resolver`` reload
# ``credentials`` in their fixtures — every class object in this file is
# therefore resolved at call time, never captured at import.
CLOSED_ABSENT_NAMES = ("ProfileNotFound", "ProfileIncomplete")


def _closed_absent():
    return tuple(getattr(credentials, name) for name in CLOSED_ABSENT_NAMES)


@pytest.fixture
def store(tmp_path, monkeypatch):
    """An isolated ``config/`` with a good ``profiles.toml``, wired in as the
    one ``credentials`` reads, and every higher tier silenced.

    Higher tiers matter: ``resolve_host_port`` only consults the profile when
    host or port is still unresolved, so a stray ``TW2002_HOST``/``.env`` on
    the machine running the suite would skip the tier under test entirely and
    the test would pass without ever reading the store. ``DOTENV_PATH`` is
    pointed at a path that cannot exist rather than trusting the repo not to
    have a gitignored ``.env``.

    Three containments, none of which the assertions rely on being unnecessary:

    * the ``chmod 000`` lands on a tmp copy — the repo's own ``config/`` is
      never read, written, or chmod-ed, because an operator may be mid-session
      against it;
    * ``TW_RUN_DIR`` is redirected even though ``main`` exits before it reads
      one. If a regression ever let resolution succeed here, the run dir is
      where it would claim a pidfile — that must not be a real ``run/``;
    * the profile's host is in the reserved ``.test`` TLD (RFC 2606, the same
      convention ``conftest.resolve_fake_host_port`` uses), so the connect a
      regression would attempt cannot resolve, let alone reach a live server.

    Restores every mode this file clears before pytest's own tmp cleanup, so
    a ``chmod 000`` can never outlive its test.
    """
    cfg = tmp_path / "config"
    cfg.mkdir()
    path = cfg / "profiles.toml"
    path.write_text(PROFILE, encoding="utf-8")
    monkeypatch.setattr(credentials, "PROFILES_PATH", path)
    monkeypatch.setattr(env, "DOTENV_PATH", tmp_path / "no-such.env")
    monkeypatch.delenv(env.HOST_VAR, raising=False)
    monkeypatch.delenv(env.PORT_VAR, raising=False)
    monkeypatch.setenv(env.RUN_DIR_VAR, str(tmp_path / "run"))
    try:
        yield path
    finally:
        try:
            cfg.chmod(0o755)
            path.chmod(0o644)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Layer A — the daemon's own startup path.
# ---------------------------------------------------------------------------


def _twd_start(capsys):
    """Run ``twd``'s entry point with no ``--host/--port`` and report what the
    operator got: (exit code, stderr).

    Deliberately NOT wrapped in a bare ``except Exception``. An unhandled
    error inside ``main`` must fail the test by propagating out of it — that
    IS the defect being fenced off, and swallowing it here to assert on a
    string would test the wrong thing. ``main`` exits at resolution, so
    nothing downstream (run dir, pidfile, telnet) is reached — and the
    ``store`` fixture redirects those anyway, so this stays true even under a
    regression.
    """
    with pytest.raises(SystemExit) as caught:
        daemon.main([])
    return caught.value.code, capsys.readouterr().err


@_needs_unprivileged
def test_unreadable_profiles_file_is_a_line_not_a_traceback(store, capsys):
    store.chmod(0o000)
    try:
        code, err = _twd_start(capsys)
    finally:
        store.chmod(0o644)
    assert code == 1
    assert "Traceback" not in err
    assert "ProfileStoreUnreadable" not in err
    assert err.startswith("twd: ")
    # Actionable means: which store, why, and what to do instead.
    assert str(store) in err
    assert "Permission denied" in err
    assert env.HOST_VAR in err and env.PORT_VAR in err


@_needs_unprivileged
def test_unreadable_config_directory_is_a_line_not_a_traceback(store, capsys):
    """The containing directory, not the file — a different errno path in
    ``credentials._load_toml_store`` (the file is readable; we cannot get to
    it), and the one that used to be indistinguishable from "no profiles"."""
    cfg = store.parent
    cfg.chmod(0o000)
    try:
        code, err = _twd_start(capsys)
    finally:
        cfg.chmod(0o755)
    assert code == 1
    assert "Traceback" not in err
    assert err.startswith("twd: ")
    # Names the directory to fix, not just the file that is already fine.
    assert str(cfg) in err
    assert "containing directory" in err


def test_a_genuinely_absent_store_still_says_could_not_resolve(store, capsys):
    """The two-sided half. Absence is the one negative this tier is entitled
    to report, and it must still fall through to ``resolve_host_port``'s own
    "pass --host / set TW2002_HOST" message — not to the new loud branch."""
    store.unlink()
    code, err = _twd_start(capsys)
    assert code == 1
    assert "Traceback" not in err
    assert "could not resolve the game server host" in err
    assert "could not be used" not in err


# ---------------------------------------------------------------------------
# Layer B — the translation, and what the message is allowed to claim.
# ---------------------------------------------------------------------------


@_needs_unprivileged
def test_unreadable_store_becomes_env_resolution_error(store):
    store.chmod(0o000)
    try:
        with pytest.raises(env.EnvResolutionError) as caught:
            env._load_profile_host_port("default", store)
    finally:
        store.chmod(0o644)
    assert isinstance(caught.value.__cause__, credentials.ProfileStoreUnreadable)


@_needs_unprivileged
def test_the_message_claims_nothing_about_content(store):
    """A store nobody could read is not "misconfigured" — that word is a claim
    about content, and no content was ever seen. The reason and the store that
    failed both have to survive into the line, because this path also reaches
    the ``servers.toml`` catalog, not just ``profiles.toml``."""
    store.chmod(0o000)
    try:
        with pytest.raises(env.EnvResolutionError) as caught:
            env._load_profile_host_port("default", store)
    finally:
        store.chmod(0o644)
    message = str(caught.value)
    assert "misconfigured" not in message
    assert "invalid" not in message
    assert "Permission denied" in message
    assert str(store) in message


def test_a_broken_value_is_still_loud(tmp_path):
    """The condition the old ``except ProfileMalformed`` branch existed for
    keeps its behaviour: a declared-but-broken ``port`` is not "nothing
    here"."""
    path = tmp_path / "profiles.toml"
    path.write_text('[default]\nhost = "x.example.test"\nport = "abc"\n', encoding="utf-8")
    with pytest.raises(env.EnvResolutionError) as caught:
        env._load_profile_host_port("default", path)
    assert str(path) in str(caught.value)


@pytest.mark.parametrize(
    "body, why",
    [
        ('[other]\nhost = "x.example.test"\nport = 23\n', "no [default] section"),
        ('[default]\ngame_letter = "A"\n', "section with no host/port/server"),
    ],
)
def test_absent_and_incomplete_still_fall_through(tmp_path, body, why):
    path = tmp_path / "profiles.toml"
    path.write_text(body, encoding="utf-8")
    assert env._load_profile_host_port("default", path) == (None, None), why


def test_a_missing_file_still_falls_through(tmp_path):
    assert env._load_profile_host_port("default", tmp_path / "nope.toml") == (None, None)


# ---------------------------------------------------------------------------
# Layer C — the tripwire.
# ---------------------------------------------------------------------------


def _family(root):
    """Every subclass of ``root``, recursively, deduplicated, order-stable.

    ``__subclasses__()`` is one level deep. ``ProfileStoreMalformed`` sits at
    depth 2 (under ``ProfileMalformed``), so a shallow walk would silently
    skip a real family member — see ``test_the_walk_is_recursive``.
    """
    found = {}
    for sub in root.__subclasses__():
        found[sub] = None
        for deeper in _family(sub):
            found[deeper] = None
    return list(found)


def _instantiate(exc_type):
    """Build an instance of a family member without knowing its ``__init__``.

    The two store-read failures take ``(cause, reason, path)`` via the shared
    ``_StoreReadFailure`` payload; the rest take a plain message. Tried by
    arity rather than by ``isinstance`` against a private mixin, so this does
    not need editing when the family grows in the shape it already has. A
    member with some third signature fails loudly here, which is the correct
    outcome: this helper is then genuinely out of date.
    """
    for args in (
        ("tripwire",),
        (credentials.CAUSE_DENIED, "tripwire", Path("/nonexistent/profiles.toml")),
        (),
    ):
        try:
            return exc_type(*args)
        except TypeError:
            continue
    pytest.fail(
        f"{exc_type.__name__} takes an __init__ this tripwire cannot call — "
        f"teach _instantiate its signature rather than dropping it from the walk"
    )


def _outcome(exc_type, tmp_path, monkeypatch):
    """What ``_load_profile_host_port`` does when the resolver raises this
    member: ``("absent", (None, None))``, ``("loud", message)``, or the
    exception itself if it escaped."""
    instance = _instantiate(exc_type)

    def _raiser(profile_name, *, profiles_path=None, servers_path=None):
        raise instance

    monkeypatch.setattr(credentials, "resolve_profile_host_port", _raiser)
    try:
        return "absent", env._load_profile_host_port("default", tmp_path / "profiles.toml")
    except env.EnvResolutionError as e:
        return "loud", str(e)
    except BaseException as e:  # noqa: BLE001 — an escape is exactly the defect
        return "escaped", e


def test_every_family_member_is_either_absent_or_loud(tmp_path, monkeypatch):
    """The tripwire. Every ``ProfileConnectionError`` descendant must resolve
    to one of exactly two outcomes, and membership of the absent side is
    EXACT, not by ``issubclass``.

    Exact membership is the half that catches a loud error wrongly filed under
    absence: a new ``ProfileStoreVanished(ProfileNotFound)`` would inherit the
    silent fall-through and disappear, so it has to be added to
    ``CLOSED_ABSENT_NAMES`` by hand — a review, not an accident. Everything
    that is not absent is caught at the base and is loud by default, so a new
    sibling anywhere else passes this test the day it is written. That
    asymmetry is the design being enforced.
    """
    closed = _closed_absent()
    members = _family(credentials.ProfileConnectionError)
    assert members, "the family walk found nothing — the walk itself is broken"

    problems = []
    for member in members:
        kind, detail = _outcome(member, tmp_path, monkeypatch)
        monkeypatch.undo()
        if kind == "escaped":
            problems.append(
                f"{member.__name__} escaped as {type(detail).__name__} — "
                f"twd would traceback at startup"
            )
        elif kind == "absent" and member not in closed:
            problems.append(
                f"{member.__name__} was swallowed as absent, but the absent set "
                f"is closed ({', '.join(CLOSED_ABSENT_NAMES)}) — either it is a "
                f"genuine absence (add it to CLOSED_ABSENT_NAMES here) or it is "
                f"loud and must not subclass one"
            )
        elif kind == "loud" and member in closed:
            problems.append(f"{member.__name__} is absent but was reported loudly")
    assert not problems, "\n".join(problems)


def test_the_walk_is_recursive(tmp_path, monkeypatch):
    """A shallow ``__subclasses__()`` would miss ``ProfileStoreMalformed``,
    which is exactly the depth a future store-failure sibling would land at.
    Pinned by execution, not by reading the walk."""
    assert credentials.ProfileStoreMalformed not in credentials.ProfileConnectionError.__subclasses__()
    assert credentials.ProfileStoreMalformed in _family(credentials.ProfileConnectionError)


def test_todays_two_store_failures_are_both_loud(tmp_path, monkeypatch):
    """The regression itself, named. ``ProfileStoreUnreadable`` is the member
    that escaped; ``ProfileStoreMalformed`` is the one that never did (it is a
    ``ProfileMalformed``). Both must be loud now."""
    for member in (credentials.ProfileStoreUnreadable, credentials.ProfileStoreMalformed):
        kind, detail = _outcome(member, tmp_path, monkeypatch)
        monkeypatch.undo()
        assert kind == "loud", f"{member.__name__}: {kind} ({detail})"


def test_a_new_family_member_is_loud_by_default(tmp_path, monkeypatch):
    """Inject a member that did not exist when the handler was written.

    Defined inside the test so it cannot leak into the walk above, and
    subclassing the base rather than editing ``credentials.py`` (secrets lane,
    read-only here). This is the property the base-catch buys: no edit to
    ``env.py`` is needed for this class to reach the operator as a line.
    """

    class ProfileStoreFromTheFuture(credentials.ProfileConnectionError):
        pass

    assert ProfileStoreFromTheFuture in _family(credentials.ProfileConnectionError)
    kind, detail = _outcome(ProfileStoreFromTheFuture, tmp_path, monkeypatch)
    monkeypatch.undo()
    assert kind == "loud", f"a new sibling escaped: {kind} ({detail})"
    assert "could not be used" in detail
