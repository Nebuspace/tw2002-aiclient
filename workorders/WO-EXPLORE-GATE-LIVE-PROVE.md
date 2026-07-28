# WO-EXPLORE-GATE-LIVE-PROVE — Live half of WO-EXPLORE-AUTOMATION-GATE Accept 5

**Status:** OPEN · EXECUTE · HIGH · Cursor (`impl-aiclient-cursor`)  
**Posted:** hub emergency seed (shell wedge recovery)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `70dfdbe` · E1–E4 on tip · CC observability 21:53Z + world_id doctrine 21:55Z  
**Refs:** `WO-EXPLORE-AUTOMATION-GATE` · Max sacrificial GO continues  
**HOLD cleared by:** this HANDOFF

## Goal

Close explore automation gate **live** residual: map growth + ≥1 learned **port.class** + typed halt. Offline E1–E4 DONE — do not re-implement. **Do not require `port.commodities`** (no product writer).

## Accept

1. Tip-check E1–E4 still present.
2. Live map-fill (`min_sectors=0` preferred) on sacrificial profile(s):
   - `tw explore status --json` → `run.distinct_sectors` strictly greater after vs before; typed `run.reason` verbatim
   - ≥1 sector with non-empty **`port.class`** via leak-safe indexed count (script below) — never print world slug / host / handle
   - `tw pairs --world-id <slug>` OK locally; STATUS records **`reason` only**
3. Hosts = catalog **host-key nicknames** only (#201 style).
4. Diversity preferred (≥3 · ≥1 NEW · ≥1 RETURNING); honest SKIP ≠ false `n/a`.
5. Suite green · STATUS · hub `hub-live-prove-check.sh`.

## Leak-safe port.class count (CC-verified)

```python
import json, pathlib
root = pathlib.Path("state/world")
for i, wd in enumerate(sorted(p for p in root.iterdir() if p.is_dir())):
    tot = cls = 0
    for f in sorted((wd / "sectors").glob("*.json")):
        d = json.loads(f.read_text()); tot += 1
        if (d.get("port") or {}).get("class"): cls += 1
    print(f"world[{i}]: sectors={tot} with_port_class={cls}")
```

## Constraints

Confirm-gated arms · no discovered→taught · no hygiene invent · no secrets/handles/FQDNs in committed text.

## Proof

`/tmp/…` audit (no secrets) + hub live-prove success post.
