# TWGS Binary Pattern Findings (Leg B)

String / documentation mining of the three TWGS 2.20b Windows distributions,
for prompt and screen-state patterns useful to `classify.py` and the settle
layer.

**Interoperability research only.** Nothing is redistributed; no bundled
documentation is reproduced; binaries live only in gitignored `research/raw/`.
Quoted strings are short functional literals.

---

## Headline: mostly a negative result, and that is the finding

**The three distributions contain no player-visible game text.** All three are
*installers*. The TWGS server and the TW2002 game engine — the binaries that
actually emit the prompts we care about — are inside a compressed payload that
cannot be opened on this platform.

This is worth stating plainly because the natural assumption ("a 3.4 MB TWGS
binary must be full of prompt strings") is wrong, and acting on it would waste
a future cycle.

### Container chain

| Artifact | What it actually is |
|---|---|
| `TWGS220B.EXE` (3.4 MB) | UPX-packed 7-Zip SFX → `setup.exe` (4.36 MB) |
| `TWGS220-220B.EXE` (493 KB) | UPX-packed 7-Zip SFX → `setup.exe` (604 KB), the 2.20→2.20b patch |
| `TOOLS100.zip` (897 KB) | → `TOOLS100.EXE`, a Delphi SFX wrapping an InstallShield 5 package |

Both `setup.exe` payloads are **InstallShield Express**. Their own strings name
the real payload (`Trade Wars Game Server.msi`, `Data.Cab`) and the flag
`DataCabInSetupExe` — i.e. the cabinet is embedded **and compressed** inside
`setup.exe`. `7z` cannot open it; no `unshield` / `cabextract` is available
here. Signature scans for `MSCF` (CAB), `D0CF11E0` (MSI/OLE), `PK` (zip) and
embedded PE headers across the full 4.36 MB all return **zero hits**,
confirming the payload is compressed rather than merely appended.

`TOOLS100.EXE`'s InstallShield 5 package lists its file table in the clear —
`NameEditor.exe`, `RankEditor.exe`, `infolist.txt`, `license.txt` — but the
file *contents* are likewise compressed. These are sysop-side editors, not
game-text carriers; the payload was judged not worth a custom extractor.

**Reaching the game strings needs a Windows box (or an InstallShield
extractor) to run the installer and mine the installed `TWGS.EXE` / game
module.** That is a different WO. I did not install any new tooling.

### Confirming the negative

Full ASCII + UTF-16LE string dumps of all five readable binaries (~46,000
lines, in gitignored `research/raw/twgs/strings/`) were searched for:

- TW domain vocabulary — `sector`, `warp`, `port`, `planet`, `citadel`,
  `stardock`, `fedspace`, `corporation`, `fighters`, `holds`, `turns`,
  `photon`, `ferrengi`, `genesis`, `density`, `probe`, … → **only** hits are
  the string "InstallShield Software Corporation" matching `corporation`.
- Prompt shapes — any `(Y/N)` variant → **zero hits**. Any line ending in `?`
  → two, both binary noise.

---

## The one finding that touches us

### TWGS ships in three editions, and our `game_select` banner check may not survive two of them (P1)

`TOOLS100.EXE` — which must detect an existing TWGS install — carries all three
product names it knows how to find:

> `Trade Wars 2002 Game Server`
> `Trade Wars 2002 Game Server (Lite)`
> `Trade Wars 2002 Game Server (Unregistered)`

Our non-boxed `game_select` variant
(`_is_twgs_server_banner_game_select_menu`) requires **all three** banner lines,
two of which are brittle against this:

| Anchor | Pattern | Risk |
|---|---|---|
| `_TWGS_BANNER_TITLE_RE` | `trade\s*wars\s+game\s+server` | Does **not** match any name containing `2002` between "Wars" and "Game" — verified below |
| `_TWGS_BANNER_REGISTERED_RE` | `server\s+registered\s+to` | An *unregistered* edition plausibly has no registrant line to print |

Verified against the live regexes:

```
TradeWars Game Server                        -> True    (our captured fixture)
Trade Wars Game Server                       -> True
Trade Wars 2002 Game Server                  -> False
Trade Wars 2002 Game Server (Lite)           -> False
Trade Wars 2002 Game Server (Unregistered)   -> False
```

**Honest framing — this is a hypothesis, not a confirmed break.** The strings
above are Windows *product / registry* names from an installer, **not observed
telnet banner text**. The only banner we have actually captured reads
`TradeWars Game Server` and matches fine. What the strings establish is that
**edition tiers exist**; whether the telnet banner differs per edition is
untested.

It matters because the anchor is a hard 3-of-3 conjunction, so *either*
divergence silently drops the whole screen class — and small hobby servers, the
ones most likely to run Lite or unregistered, are well represented in
`config/servers.toml`.

**Suggested touch:** `classify.py` — widen `_TWGS_BANNER_TITLE_RE` to tolerate
an optional `2002` and a trailing parenthesised edition; consider relaxing the
registrant line from a hard requirement to one of N corroborating signals.
**Cheapest proof is empirical, not a code change:** connect to a listed server
known to be small and capture its banner. Do not widen the regex on this
inference alone — it is a conjunction guarding against stale-scrollback
misfires, and loosening it without evidence trades a real defence for a
hypothetical gain.

---

## Host-admin noise (explicitly *not* player-visible)

Everything else readable is Windows-side sysop surface. Recorded so a future
pass does not re-mine it:

- **Registry / config** — `SOFTWARE\Epic Interactive Strategy\Trade Wars 2002
  Game Server\Configuration`, `…\Tools`; `RegisteredOwner`,
  `RegisteredOrganization`.
- **Installer chrome** — InstallShield/MSI machinery, .NET and J# redistributable
  probes, `RunOnce`/`Uninstall` keys, proxy settings, ~1990s InstallShield
  corporate strings.
- **Sysop-facing UI** — `TWGS Command Center, Tools menu`, `Shutting down TWGS
  before proceeding…`, `Copying TWGS Tools Program files…`, `NameEditor.exe`,
  `RankEditor.exe`.

None of this is ever seen by a connected player. It is not classifier input and
should not become anchor material.

**Licensing internals: out of scope by instruction and by choice.** The
edition tiering is noted *only* because it may change what a player sees on
connect. No registration or licensing mechanism was examined or documented.

---

## Corpus layout (all gitignored)

```
research/raw/twgs/
  TWGS220B.EXE  TWGS220-220B.EXE  TOOLS100.zip   (copies; originals untouched)
  x_twgs220b/setup.exe      x_patch/setup.exe    (SFX payloads)
  tools100/TOOLS100.EXE                          (unpacked zip)
  strings/                                       (ASCII + UTF-16LE dumps)
```

---

## Recommended follow-up

1. **Do not re-mine these installers.** The negative result is solid.
2. **Capture banners empirically** from two or three small listed servers —
   settles the edition question at a fraction of the cost of unpacking a 2012
   InstallShield package (P1).
3. If the installed game binaries are genuinely wanted, that needs a Windows
   environment and its own WO. Judged low value: live capture gives *rendered*
   screens, which is what the classifier consumes, while a binary yields format
   strings still needing assembly.
