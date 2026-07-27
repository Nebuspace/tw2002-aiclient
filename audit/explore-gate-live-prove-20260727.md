# WO-EXPLORE-AUTOMATION-GATE — live prove artifact (Accept 5)

**Run:** 2026-07-27T23:03:43Z → 23:03:50Z · **turns spent: 8** (exactly the budget)
**Seat:** `impl-claudecode-aiclient` · **Branch:** `wo/EXPLORE-AUTOMATION-GATE`
**Authorisation:** Max GO for a full explore run on a sacrificial profile; hub GO for the
zero-turn read. Profile `scout_microblaster` (`crawl_sacrificial = true`), registered for this
purpose — **not** `xeno`, which is flagged non-sacrificial.

Host `twgs.microblaster.net:2002` · world `twgs_microblaster_net__A__Pathfind`.

---

## 1. Zero-turn half — the E2 parser against a genuine screen

Every fixture in `tests/test_state_parser_port_flyby.py` is a reconstruction from canon plus one
archived ledger. This is the first time the parser met real bytes. Captured with the read-only
`screen` verb (never sends):

```
Sector  : 1 in The Federation.
Beacon  : FedSpace, FedLaw Enforced
Ports   : Sol, Class 0 (Special)
Planets : (M) Terra
Warps to Sector(s) :  (2) - (3) - (4) - (5) - (6) - (7)
Command [TL=00:00:00]:[1] (?=Help)? :
```

| claim under test | live result |
|---|---|
| the flyby is read at all | `PortRead(observed=True, port={})` |
| `Class 0 (Special)` does **not** invent a class | `class` key absent ✅ |
| status lines are **column-0**, not indented | confirmed ✅ |
| warps still parse from the paren form | `[2, 3, 4, 5, 6, 7]` |
| last-match discipline | screen carried the block **twice** (a `<Re-Display>`); the newest won |

**The column-0 finding matters beyond this run.** Canon's worked example in
`canon/engine/screen-understanding.md` §"Examples" renders the status block **indented**, and
`read_warps_from_sector_status` anchors `^Warps` with no leading-whitespace allowance — so canon's
own example, lifted verbatim as a fixture, would fail against a parser that is correct for the real
game. The archive's live-run ledger (`seraph_run`, 2026-07-19) already showed column-0; this run
confirms it first-hand. Canon's indentation is markdown formatting, not a screen fact. **Worth a
one-line note in that canon example so the next author does not build fixtures from it.**

## 2. Turn-spending half — bounded map-fill

`min_sectors=0` (E1 exhaustive: no sector cap), `turn_budget=8`, `intent=map_fill`.

```json
{
  "world_id": "twgs_microblaster_net__A__Pathfind",
  "outcome": "halted",
  "reason": "explore_exhausted:turn_budget",
  "distinct_sectors": 8,
  "sends_issued": 8,
  "turns_remaining": 0,
  "min_sectors": 0,
  "intent": "map_fill"
}
```

- **E1** — the uncapped run went to the budget and halted with the **typed** reason, not a bare
  stop. Before this WO, `min_sectors` was floored at 1 and a cap always short-circuited the run.
- **E3** — `intent` rides the wire report, so a cockpit can say which goal a run was pursuing.
  Without it, `exhausted` is ambiguous between a filled frontier and an unreachable landmark.
- **E4** — not exercised (no unknown screen appeared in 8 hops). Covered by unit pins:
  `test_explore_halts_on_unknown_screen` and this WO's new
  `test_explore_halts_on_a_never_auto_action_screen`, which additionally asserts **zero sends**
  into a recognised-but-forbidden prompt.

## 3. Map growth + port records (E2 end-to-end)

World model went **0 → 8 sectors**, with **7 port records**:

| sector | warps | port |
|---|---|---|
| 1 | 6 → 2,3,4,5,6,7 | present, **class `—`** (Sol, `Class 0 (Special)`) |
| 2 | 6 → 1,3,7,8,9,10 | **BSS** |
| 3 | 4 → 1,2,4,20568 | **BBS** |
| 4 | 4 → 1,3,5,27494 | **BSS** |
| 5 | 4 → 1,4,6,19902 | **SBB** |
| 6 | 5 → 1,5,7,3591,8467 | **no port** |
| 7 | 5 → 1,2,6,8,20593 | **SBB** |
| 8 | 3 → 2,7,28492 | **SBB** |

Both edge cases behaved as designed, and they are the ones that matter:

- **Sector 1** — a port IS present, but `Class 0 (Special)` is not a buy/sell posture, so the record
  carries **no class** rather than a fabricated `"Special"`. `write_from_state` then preserves any
  class a future CIM report teaches.
- **Sector 6** — the render carried no `Ports :` line, so **nothing** was written for `port`. Not an
  empty record, not a `None` that would clear a future reading — absent, which is the honest state.

Six real buy/sell classes off **8 turns of ordinary map-fill**, with no docking and no trading, is
the thing this gate exists to produce: chain detection can be fed by exploration rather than
needing a second, turn-spending pass.

## 4. Credential handling

`config/secrets.json` was created by the registration path itself — `-rw-------` (0600), gitignored,
containing exactly one entry. No secret passed through argv, a shell command, this file, or the
coordination channel. Per `canon/doctrine/secrets-and-credentials.md` the minted credential is
persisted eagerly so the character survives a crash.

## 5. Defects found by running it

1. **`internal_error:AttributeError` on registration** — `_load_profile` accepted a handle-less
   profile when `allow_register` was set, and `None` reached `connection.send_text`. Fixed on this
   branch (`55705e3`, Max-approved: login is a gated area): a handle is now required
   unconditionally, and `send_text` refuses a non-`str` at the boundary with a named type.
2. **`AF_UNIX path too long`** — a deep `TW_RUN_DIR` kills `twd` at `server_bind` with an unhandled
   `OSError` whose text never mentions the run dir. Banked as `WO-RUN-DIR-AFUNIX-REFUSE` (#124).

Neither was findable by reading; both came from actually driving the product.
