---
type: Doctrine
title: Secrets & Credential Handling
description: The non-negotiable discipline for storing, resolving, redacting, and rotating the operator's game passwords and credentials — secrets never touch logs, argv, history, or the repo.
tags: [doctrine, secrets, credentials, security, redaction, public-repo]
timestamp: 2026-07-24T21:56:00Z
---

A game password belongs to **the operator**, and to the operator alone. Nothing in this system —
not the App autopilot, not the on-demand AI teacher, not a transcript log, not a coordination
file, not the public git tree — ever holds, echoes, or transmits that secret except the one
narrow path that must, at the one moment it must, and only after routing it through a redaction
sink. This is a *doctrine*, not a feature: a set of non-negotiable invariants every other concept
inherits without restating. The [Session Engine](/architecture/session-engine.md) and the
[Login Automaton](/architecture/login-automaton.md) are the substrate that sends credentials on
the wire; the [entry & profile-selection surface](/surfaces/entry-and-profile-selection.md) is
what the operator uses to choose which credential; this concept is the discipline all three obey.

# The Five Invariants

1. **Secrets never touch logs, argv, shell history, or the repo.** A password is never a
   command-line argument (it would land in the process table and the shell history), never printed
   to a CLI response, never written to a transcript log, never committed. The two on-disk homes
   below are the *only* places a secret is permitted to rest.

   **Operator hazard (tip honesty · 2026-07-25):** `tw attach --keys …` *does* place its payload on
   argv / shell history by design (scripted/non-TTY automation). That flag is therefore **not a
   credential channel** — never put a password or PIN in `--keys`. Prefer interactive attach (secret
   prompts hit the redaction sink) or env / chmod-600 `secrets.json`. Draft argparse help copy for
   product (no `.py` in this docs tick):
   `scripted keystrokes then detach (unicode-escape; no TTY). NEVER a password — lands in argv/history.`

2. **Every password send routes through the redaction sink.** A keystroke that carries a secret
   is logged as a redaction marker, never as its bytes — and never with a byte count, since a
   length is itself a leak. There is exactly one redaction primitive
   ([`log_redacted()`](/architecture/session-engine.md)) and every secret-bearing send on every
   channel uses it.

3. **Resolution precedence is environment-first, then the out-of-band store.** A password is
   looked up as `TW2002_PASSWORD_<PROFILE>` in the environment first; only if that is absent is
   the chmod-600 secrets file consulted. This lets an operator or CI supply a throwaway credential
   without ever writing it to disk. **Absence is not an error** — a profile with no credential
   anywhere is the normal state of a character that has never been registered.

4. **Only non-secret shape is tracked; the secret store is gitignored and chmod-600.** The
   public repo tracks exactly two config files: the profile *shape* template and the public
   server catalog. The real profile table (non-secret) and the secrets file (secret) are both
   local-only and never committed. The secrets file is created and re-asserted at mode `0600` on
   every write.

5. **The public-repo leak gate precedes every push.** This repository is public, and public is
   forever. No real personal name, handle, fully-qualified domain, or username appears in canon
   or code — the operator is *"the operator"* / *"the human."* The leak gate runs before every
   push; private journals and the `.samantha/` and `.claude/` trees are gitignored so
   coordination chatter and design history never reach the public tree.

# The Two On-Disk Homes

A credential system has exactly two files, and they are deliberately kept apart so that the
non-secret shape can be freely read, printed, and logged while the secret itself stays sealed:

- **The profile table** (`config/profiles.toml`, gitignored) — the non-secret *shape* per
  profile: host, port, game letter, handle, and optional ship/planet-name overrides, plus the
  opt-in policy gates (`allow_register`, `crawl_sacrificial`, `autopilot`). It is safe to read,
  print, and log because **it has no password field at all** — the credential object built from
  it structurally cannot carry a secret.
- **The secrets file** (`config/secrets.json`, gitignored, chmod-600) — the *only* on-disk home
  for a password. Written atomically (temp file → `chmod 600` → atomic replace → re-assert
  `600`), so a reader never sees a half-written file and the file never widens its mode. Passwords
  are written here and only here; the persistence path never touches the environment, because the
  environment is a read-only, caller-managed override.

The public tree tracks only `config/profiles.toml.example` (the shape template) and
`config/servers.toml` (the public game-server catalog). Everything real under `config/` is local.

# Redaction: the send path, and its one honest boundary

The reliability core of this doctrine is that redaction is decided **fresh, at send time, from
the current screen** — never pre-computed and never trusted from a stale earlier decision. A
broad, deliberately over-inclusive secret-prompt detector classifies the live prompt the send is
answering; if it looks like a password prompt, the send is redacted. This covers not only the
scripted login automaton's `--secret` sends but also a raw human keystroke typed into an
interactive attach session that happens to land on a password prompt — the same redaction
contract, applied identically on both the encoded-text and raw-byte send channels.

The **TX (send) channel** is redacted by design. The **RX (receive) channel is transcribed
verbatim** — see [Code Divergence](#code-divergence) — so the no-leak guarantee on the receive
side rests on the standard telnet property that a password prompt suppresses local echo and the
server does not echo the typed secret back. That boundary is stated here honestly rather than
papered over.

# The Credential Bank — metadata only (TW-31)

To multiply the game's daily turn allotment, an operator may run several **independent**
characters and rotate between them. The **credential bank** is the client-side bookkeeping for
this: it tracks *which* characters exist (each entry links back to a profile by name) plus simple
rotation state (who played last, remaining turns) so a rotation driver can pick who is up next.

The bank stores **metadata only, by structural design** — it is built from the non-secret
credential object, which has no password field, so there is *nothing in it that could leak a
secret*. Password resolution stays entirely inside the environment-first store, invoked at
use-time by whoever actually drives a login, never by the bank. The one place free-form caller
data enters the bank — a per-character `notes` dict — is guarded in depth anyway: values are
restricted to scalars (no nested containers to smuggle a secret a level down), string values are
length-capped, and keys are checked against a broadened, case-insensitive
password/secret/token/credential-alias denylist. A refused key is never echoed verbatim into an
error, only truncated — so even a secret-*shaped* key name cannot land in a traceback.

**The hard boundary on the bank:** it exists to run *independent* players in parallel and multiply
turns, **never to enable collusion or resource transfer between them.** Cross-account
coordination — funneling credits, cargo, or combat advantage from one owned character to another —
is out of bounds. That conduct rule is owned by [alignment & conduct](/doctrine/alignment-and-conduct.md);
this concept names the boundary and defers to it as the single source.

# Schema

Resolution precedence for a profile's password (first hit wins; a miss is a legitimate *absent*,
not an error):

| Order | Source | Written by whom | Persists to disk? |
|---|---|---|---|
| 1 | `TW2002_PASSWORD_<PROFILE>` environment variable | operator / CI (out-of-band) | No — caller-managed, never written by this system |
| 2 | `config/secrets.json` entry (chmod-600) | the persistence path only | Yes — atomic write, mode re-asserted `0600` |
| — | *(neither present)* | — | Returns *absent* — the normal state of an unregistered character |

Redaction sinks (a secret-bearing send uses one; none logs a byte count):

| Channel | Carrier | Redacted? |
|---|---|---|
| TX encoded-text send (scripted login) | `--secret` send | Yes — redaction marker only |
| TX raw-byte send (interactive attach keystroke) | live secret-prompt detection | Yes — same contract, decided fresh at send time |
| RX receive transcript | server output | **No — verbatim** (see Code Divergence) |

# Examples

- **Env override for a throwaway test character.** Export `TW2002_PASSWORD_SCRATCH=…` and connect
  with profile `scratch`; the password is resolved from the environment, never written to
  `secrets.json`, and vanishes with the shell.
- **A registered character survives a crash.** The moment a credential is minted it is persisted
  to the chmod-600 secrets file eagerly, so the character remains recoverable even if a later step
  in the same run fails. It is written to the secrets file only — never the environment.
- **A password typed into a live attach session.** The operator lands on a password prompt in an
  interactive attach; the raw keystrokes are classified as secret at send time and logged as a
  redaction marker, not as bytes — identical to the scripted path.
- **A public push.** Before the push, the leak gate scans for real names, handles, FQDNs, and
  usernames; the private journals and `.samantha/`/`.claude/` trees are already gitignored, so the
  only config files that can reach the public tree are the shape template and the server catalog.

# Code Divergence

*(DOCS WIN: canon is prescriptive; these record where the current implementation diverges from,
or falls short of, the reborn target. They are documentation findings — this concept edits no
code.)*

1. **RX transcript is unredacted (TX-only redaction) — and the same class can leave via the
   live status verb.** Redaction is enforced on the *send* side; the receive-side reader logs
   every received frame verbatim. The no-leak guarantee on the RX channel therefore relies on the
   standard telnet behavior that a password prompt suppresses local echo and the server does not
   echo the secret. This holds for conventional TW2002 login flows, but the invariant "secrets
   never touch logs" is *structurally* enforced only on TX; a server that ever echoed a typed
   password back would capture it into the RX transcript.

   **Status-verb wire (Mack PoC, P3-041):** the same root cause is not limited to the on-disk
   transcript log file. `status["prompt"]` (and any other response field that mirrors the live
   pyte tail / last row) is built from the unredacted receive buffer (`session/protocol.py` /
   `build_response`). An echoing server can therefore put secret bytes onto the **live status
   JSON** consumed by cockpit / `tw status` / subscribers — even when TX redaction and the LOGS
   ring (`log_tail`, redact-at-insert) are airtight. `fake_twgs` never echoes, so green e2e against
   it does **not** prove this boundary. Recorded here as the honest scope of Code-Divergence #1;
   a harden WO (redact-or-omit sensitive status fields) is **out of scope** for docs-only
   touch-ups — this paragraph is the DOC-GAP close for naming.

   **RESOLVED 2026-07-26** (`DECISIONS.md` §C.2 / §C.2.1 / §C.2.2 — Max carte blanche). The
   harden WOs landed, and the family is now split **by whether the mirror leaves the session**:

   - **`ensure` failure payloads — CLOSED.** Both carriers. The error text no longer interpolates
     the observed prompt (`LoginStalled` is structurally incapable of holding screen text,
     `297abc1`), and the failure answer is built by `_login_failure_response`, which never calls
     `build_response` — so there is no `screen` / `prompt` / `color` mirror to forget to redact
     (`0150838`).
   - **`tw status` JSON — OMITTED.** `_status_response` carries `classification` and
     `prompt_withheld`, never the painted line (`a2e42d4`). The omission is **unconditional**:
     recognition-gating it fails OPEN, because an echoing server *replaces* the word `password`
     with the credential, so both `is_probable_secret_prompt` and `classify_screen` answer
     "not a secret prompt" about a line that is nothing but a secret.
   - **`tw watch --json` — CARVED OUT (§C.2.2).** It is the live-paint export *by purpose*, so it
     may carry `screen`. Live TUI paint of the telnet stream is the human's own eyes on their own
     game; what must redact is a **structured mirror that leaves the session**.

   Still open, and named rather than implied: a future world-identity strip must deliver the
   current sector as a **bounded daemon-side integer**, never a raw line for a client to
   re-parse — the archive derived it by re-parsing `status["prompt"]`, which is exactly how this
   carrier would come back.

2. **The App can mint and persist a credential without a human typing it.** When a profile opts
   into automated NEW-character registration, the login automaton generates a password (CSPRNG,
   short alnum) and persists it to the secrets file itself, before the human ever sees it. This is
   safe-by-omission (the gate defaults off and every legacy profile is unaffected) and the secret
   still only ever rests in the chmod-600 store — but it is a place where the *App*, not the
   operator, originates a credential, which sits in tension with the operator-sovereignty framing.
   Recorded so the tension is visible rather than silently normalized; the flow itself is owned by
   the [login automaton](/architecture/login-automaton.md).

# Citations

[1] twclient/credentials.py (profile shape, env-first `get_password()`, atomic chmod-600
`save_password()`, CSPRNG `generate_password()`, `allow_register` gate)
[2] twclient/logging_util.py (`log_redacted()` — redaction marker, no byte count)
[3] twclient/connection.py + twclient/session.py (fresh-at-send-time secret detection; TX-side
redaction on both send channels; unredacted RX reader loop)
[4] twclient/player_bank.py (TW-31 credential bank — metadata-only by construction, notes-key
denylist, scalar-only value guard)
[5] CLAUDE.md — Hard rules (secrets never touch logs/argv/history/repo; single-connection
pidfile; gitignored `config/`/`run/`/`state/`/`logs/`; only `profiles.toml.example` +
`servers.toml` tracked)
[6] CLAUDE.local.md — public-repo posture and the leak gate that precedes every push
