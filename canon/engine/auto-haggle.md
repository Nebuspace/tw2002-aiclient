---
type: System
title: Auto-Haggle — Deterministic Port Negotiation
description: The no-LLM resolver for the port OFFER sub-dialogue — the archetype of a built-in guarded rule that fires on a taught screen, proves its own result, and STOPS to the human on any desync.
tags: [auto-haggle, guarded-rule, deterministic, no-llm, money-path, send-and-confirm, desync-fallback, port-negotiation, prescriptive]
timestamp: 2026-07-23T20:10:55Z
---

Auto-haggle is the app negotiating a port's price for a single commodity, with **zero AI reasoning
at send time**. It is the cleanest example in the whole trainer of a *built-in guarded rule*: a
narrow, taught screen (the `Your offer [N]?` OFFER prompt) matched by a deterministic parser,
answered by a fixed strategy, every send proven against the next expected screen, and — the moment
the screen stops looking like what the rule was taught — it STOPS, accepts the safe default, and
reports a desync rather than pressing on. It touches real credits, so it is a **money-path** rule:
the bar for "I am sure what is on screen" is higher here than anywhere else in the app, and the
guards that enforce that bar are not optional. This concept is prescriptive — it specifies the
parser, the strategy, and the mandatory guard contract the reborn trainer targets, and records
where today's code diverges (most importantly the verified 78-turn-autopilot money-path misfire).

# Schema

## What auto-haggle owns — and what it does not

Auto-haggle resolves **only** the OFFER sub-dialogue: the caller has already navigated commodity
and quantity selection (that is the trade-path's job, not this rule's) and the session is sitting at
a live `We'll buy/sell them for N credits. Your offer [N]?` prompt. From there the rule opens a
counter, concedes round by round, accepts when the port's price is close enough, and hands back a
`{resolved, outcome, rounds, final_price, direction, fair_value}` result. It never selects *what* to
trade, never decides *whether* to trade, and never navigates the port menu — those are upstream
taught behaviors. Auto-haggle is one guarded reflex in a larger taught flow.

## The transaction parser (E1) — anchored to the current offer line

Detection and reading are deterministic regex over the rendered screen, no LLM:

| Element | What it reads |
|---|---|
| Direction | `buy` (port buys *from* us — we want a **higher** price) vs `sell` (port sells *to* us — we want a **lower** price). Extracted from the same dialogue as the default, so the two never disagree. |
| Baseline | The port's own stated price (`We'll buy/sell them for N credits`) — the reference our opening counter is computed off when no external fair-value is supplied. |
| `current_default` | The number bracketed in the live `Your offer [N]?` prompt — the value a bare Enter would accept. Its **presence is the proof an OFFER dialogue is actually live**; its absence means the dialogue is over (or was never entered). |
| Continue tell | A *fresh* `Your offer [` prompt ⇒ the port countered and the dialogue is still open. |
| Resolution tell | The dialogue landing on a post-deal shape — a main `Command [TL=…]` prompt, or straight into the next commodity's `How many holds?` at the same port (both seen live in one capture). |
| Accept/reject tells | Acceptance phrasing is **not uniform** — the same closed deal shows as "Done, we'll take the lot.", "Cheapskate. Here, take them…", "You insult my intelligence, but we'll buy them anyway.", "You will put me out of business, I'll take your offer." These are recognized as *acceptance context*, never relied on alone to price a deal. |

The load-bearing parser invariant: **every read anchors to the CURRENT (last non-blank) line, not
the first match anywhere on screen.** A cropped 80×25 render routinely still holds a
`Command [TL=…]` or an old `Your offer [` left over from *before* this dialogue — matching it
anywhere is the stale-scrollback trap. Reading the current line is what turns "this shape appears
somewhere" into "this is what is actually showing right now" (the same last-non-blank-line
convention the state parser uses; see [screen-understanding](/engine/screen-understanding.md)).

## The deterministic strategy (E2)

No search, no model — a fixed four-move policy off a reference price (an external fair-value from
[port-economics](/strategy/port-economics.md) when available, else the port's own baseline):

1. **Aggressive-but-plausible open.** Counter one step *favorable* off the reference — above it when
   selling to the port, below it when buying from it (default open aggression ~15%). Plausible, not
   absurd: a real port barely concedes off its stated price, so an extreme opener wins nothing and
   risks nothing.
2. **Concede to the midpoint.** Each round the port re-quotes, move the offer to the midpoint of our
   last ask and the port's counter, and go again.
3. **Accept within threshold.** Once the port's current default is within a small band of the
   reference (default ~5%), accept it — by sending a **blank Enter** to take the shown default rather
   than re-typing the number (the "blank-input-accepts-default" trick, so the app never fights the
   number already on screen).
4. **Round cap (≤4) → safe accept-default fallback.** A real port *can* simply refuse to move
   (live-confirmed). Rather than loop forever, at the cap accept the current default and report
   `round_cap_fallback`. The cap is generous headroom for a stubborn port, not the expected path —
   live deals converged within **2 rounds** regardless of how aggressive the open was.

> **Verification status:** the "converges within ~2 rounds / a port barely moves off its own price"
> behavior is *verified* against a real TWGS server (2026-07-19 live captures, reproduced verbatim by
> the test suite). The strategy *parameters* (open aggression ~15%, accept threshold ~5%, round cap
> 4) are **registry-driven defaults** — authored in `data/haggle/params.json` and loaded by
> `tw2002_aiclient/haggle_params.py` (`load_haggle_params` / `DEFAULT_HAGGLE_PARAMS`; shipped
> `WO-BUILD-HAGGLE-PARAMS-REGISTRY`, #575) — not silent module literals and not canonical server
> constants. Tune per server/economy by editing the registry row. Floor prices and fair-value come
> from [port-economics](/strategy/port-economics.md), not this rule.

# The mandatory guard contract (E3)

Auto-haggle is on a money path, so "the screen went quiet" is **never** enough to act. Three guards
are mandatory and non-negotiable — "on by default" does not mean "unguarded on the money path":

## Guard 1 — fresh-render pre-send gate

Before the very first read (before round 1's counter is even computed), the rule waits for the
render to be *positively settled right now* — rx activity quiet for a debounce window — not merely
"idle sometime during a wait." A caller hands the session over the instant it navigated to the OFFER
prompt; reading before that screen finishes painting would compute a counter off a half-drawn,
transitional render. If the screen never settles inside the freshness budget, the rule refuses to
parse it at all: it STOPS and reports `desync_fallback` rather than gamble on a transitional screen.
This is the read-side application of the send/settle-race discipline
([settle-detection](/architecture/settle-detection.md), `wait_until_settled`).

## Guard 2 — send-and-confirm, never send-and-assume

Every keystroke goes through **send-and-confirm** ([settle-detection](/architecture/settle-detection.md)):
a round advances only on a *positive* match of the next expected screen shape (a new offer prompt,
or a recognized resolution shape) with **genuinely new bytes since the send** — never a bare idle
timeout, and never a match against content that was already on screen before the send. A slow
multi-stage paint can go quiet just long enough to satisfy the debounce mid-transition; an unmatched
lull is discarded and re-polled, and a matched shape is re-checked one beat later to prove it did not
just flash for a frame. This is the reborn **start-anchor + send-and-confirm** invariant made
concrete — the same discipline whose absence produced the −75-alignment colonist scar: we prove the
action landed before we believe it did.

## Guard 3 — a deal is `resolved` only on positive evidence; bare main-command ⇒ `DESYNC_FALLBACK`

The subtle money-path defect: the settle layer's confirm match is a whole-screen `re.search`, so it
matches a `Command [TL=…]` **anywhere** — including one left over in stale scrollback from *before*
the dialogue was ever entered. "The offer prompt is gone" is likewise indistinguishable, by itself,
from a genuine deal closing versus a stray keystroke bouncing back to the main prompt. So the rule
**never** reports `resolved` / a `final_price` on a bare shape match. It requires one of two
independent positive signals:

- **A verified credits delta** consistent with the trade direction — credits *increased* when we
  sold, *decreased* when we bought — reported as the honest transacted amount (the strongest
  signal), **or**
- **The current line is itself a positively-identified resolution shape** *with real acceptance
  context* — a `How many holds?` (unambiguous on its own), or a `Command [TL=…]` **plus** a
  live-captured acceptance phrase or a credits-balance line somewhere on screen.

A bare `Command [TL=…]` as the sole content — no delta, no acceptance context — is **not** a deal.
It is `DESYNC_FALLBACK`: `resolved=False`, `final_price=None`. The guard STOPS and escalates rather
than inventing a price it cannot prove. This is guard-may-STOP-instead-of-fire in its purest form,
on the one path where a false "confirmed" costs real money.

## On-by-default, guarded — the operator ruling

**Auto-haggle ships ON BY DEFAULT** as a built-in guarded rule (operator ruling, RESOLVED
2026-07-23). There is **no off-until-proven gate**. Being a *built-in* rule, it is human-approved by
construction — the operator ruled it on, and that ruling *is* the approval that
[the rule–macro engine](/architecture/rule-macro-engine.md) requires before any rule may fire; a
user-authored or AI-proposed haggle *variant* would still be an inert draft until separately
approved. "On by default" is **not** "unguarded": Guards 1–3 above are mandatory and non-negotiable,
precisely because on-by-default on the money path raises, not lowers, the bar for proof. A user
toggle may disable the rule, but while enabled the guards are not optional and cannot be waived.

# The guarded-resolver contract, generalized

Auto-haggle is the archetype, but the *contract* it embodies — parse a taught screen deterministically,
prove the send landed, report only evidence-backed results, STOP+escalate on anything unrecognized —
is the shared shape of every built-in guarded rule. Its sibling is the **fighter-toll resolver**
(`fighter_toll_policy.py`), which resolves an `Option? (A,D,I,R[,P],S,?)` toll dialogue: Attack when
clearly winnable (few enemies, at least as many fighters aboard), else Retreat, and **never auto-Pay**
(`P` requires an explicit hub GO). It, too, prefers a STOP-safe move over guessing — an unparsed
vs-line Retreats rather than holds forever or attacks blind. Two invariants bind that sibling and
belong on the record here:

- **Combat is NPC-only, human-gated math.** The toll resolver computes fight/flee against *NPC*
  targets only; all player-vs-player combat defers to the alignment ethos and an in-the-moment human
  confirmation — the math lives in [toll-and-defense](/strategy/toll-and-defense.md), the human-gate
  in [control-and-escalation](/architecture/control-and-escalation.md).
- **Never auto-Pay / never auto-destroy.** The same "never fire an unverified or destructive action"
  invariant that keeps auto-haggle from inventing a price keeps the toll rule from paying a toll or
  spending fighters it cannot account for.

The concrete byte-level enforcement of these guards is [action-safety-guards](/doctrine/action-safety-guards.md);
auto-haggle is where the guarded-resolver contract is first made real.

# Examples

```
buy  (port buys from us — we want HIGHER): baseline 2,214 → our ask 2,450 → port re-quote 2,216 → accept  (2 rounds)
sell (port sells to us — we want LOWER):   baseline   758 → our ask   700 → port re-quote   753 → accept  (2 rounds)
```

- Both closed within 2 rounds — the port moved 2cr and 5cr respectively off its own price. The
  strategy's job is mostly to *recognize convergence fast and accept*, not to extract a big discount.
- The accept in each case is a **blank Enter** (take the shown default), then Guard 3 confirms the
  deal: a credits delta of +2,216 (buy) / −753 (sell) is the evidence-backed `final_price`, not the
  number we last typed.

```
DESYNC examples — the rule STOPS, reports desync_fallback, resolved=False, final_price=None:
  · render never settles inside the freshness budget        → Guard 1 refuses to parse
  · send-and-confirm never positively matches the next shape → Guard 2 accepts the safe default, reports desync
  · offer prompt gone, screen shows a bare "Command [TL=…]"  → Guard 3: no delta, no acceptance context ⇒ NOT a deal
```

# Code divergence

**DOCS WIN** — where the current code diverges from the prescriptive contract above, the divergence
is recorded here, never silently reconciled into the doc.

- **The verified 78-turn-autopilot misfire is a real money-path defect (the founding finding).** In
  a live run, auto-haggle reported a resolved deal off a stale `Command [TL=…]` left in scrollback —
  a bare main-command shape misread as a confirmation, with no trade actually behind it. This is the
  money-path failure the whole guard contract exists to close: a false "confirmed" on a screen the
  rule was **not** truly looking at. It is recorded as a real defect (not a hypothetical), and the
  canon states the guarded contract **prescriptively** so the fix is measured against the doc, not
  the other way round. `haggle.py`'s current hardening (`_resolution_evidence()` anchoring to the
  current line, the credits-delta cross-check, the `wait_until_settled` pre-send gate) is the
  in-code closure of exactly this defect; the same stale-`Command[TL=` misfire class is what those
  guards reject. The finding stands on the record as the money-path scar that motivated the mandatory
  guards.

- **Disposition CARRY-WITH-CHANGES — recast from always-on resolver to human-approved built-in rule.**
  The v1/v2 code framed auto-haggle as an always-on autopilot resolver invoked inside the trade path.
  The reborn framing recasts it as a *human-approved built-in guarded rule* under
  [the rule–macro engine](/architecture/rule-macro-engine.md) — functionally on-by-default per the
  operator ruling, but now explicitly *a rule that can be toggled and whose firing is governed by the
  same approval/priority/scope machinery as every other rule*, rather than hardcoded control flow. The
  strategy and guards carry unchanged; the framing is the change.

- **Autopilot's per-cycle EV select vs stop-on-unknown (archive-only — do-not-revive).** The
  surrounding pre-rebirth autopilot run-loop that could pick actions per-cycle by expected value over
  untaught screens lived in `archive/.../twclient/autopilot.py` and is **gone from tip**. Auto-haggle
  itself is correctly STOP-safe (Guards 1–3); this note is only that the historical 78-turn misfire
  surfaced *during* such an archived autopilot run — not that a live EV picker still invokes haggle.
  Full archive disposition: [app-autopilot-model](/architecture/app-autopilot-model.md). The rule's
  guards remain what prevent a desync from becoming a fabricated trade.

# Citations

- Reborn vision (fixed constraints): the human is the sovereign pilot and escalation target; the app
  plays back only taught screens and STOPS on the unknown; a guard may STOP+escalate instead of
  firing; every rule is human-approved before it can fire; never fire an unverified or destructive
  action (start-anchor + send-and-confirm); combat is human-gated, NPC-only math. Live keystroke
  senders are `{app, human}` only.
- Operator ruling (RESOLVED 2026-07-23): auto-haggle ships **on by default** as a guarded rule, the
  fresh-render pre-send gate + `DESYNC_FALLBACK` hardening are **mandatory**, and the verified
  78-turn misfire is recorded as a money-path finding.
- Project canon — [north-star](/architecture/north-star.md) (the human-piloted spine),
  [rule-macro-engine](/architecture/rule-macro-engine.md) (auto-haggle is the archetype built-in
  guarded rule; approval/priority/scope machinery),
  [action-safety-guards](/doctrine/action-safety-guards.md) (the guarded-resolver contract enforced
  at the byte level), [control-and-escalation](/architecture/control-and-escalation.md) (STOP→handoff
  and the human-gate), [port-economics](/strategy/port-economics.md) (fair-value / floor prices this
  rule negotiates around), [toll-and-defense](/strategy/toll-and-defense.md) (the NPC-only fighter
  math the sibling toll rule consumes), [settle-detection](/architecture/settle-detection.md)
  (`wait_until_settled` fresh-render gate + `send_and_confirm` positive-match contract),
  [screen-understanding](/engine/screen-understanding.md) (last-non-blank-line current-prompt
  anchoring), [trace-ledger](/engine/trace-ledger.md) (an auto-haggle fire is an `app` row).
- Internal design history (plain text): DESIGN-v2 §9 (deterministic no-LLM auto-haggle, C8-lite),
  §8 (the send/settle-race fix and the blank-input-accepts-default finding); the TW-01 money-path
  hardening (the three real live-loss defects — stale-`Command[TL=` misfire, prompt-gone-without-
  evidence, and the missing opening freshness gate); the parked WO-FIGHTER-AUTO-R folded into the
  fighter-toll resolver.
- Code modules (plain text): `haggle.py` (parser, strategy, the three guards, `run_haggle` result
  shape), `settle.py` (`wait_until_settled` pre-send gate, `send_and_confirm` positive-match +
  stability re-check), `state_parser.py` (`parse_haggle`, `credits_balance`, `last_nonblank_line` —
  current-line anchoring), `fighter_toll_policy.py` (the sibling guarded resolver: Attack/Retreat,
  never auto-Pay, NPC-only).
