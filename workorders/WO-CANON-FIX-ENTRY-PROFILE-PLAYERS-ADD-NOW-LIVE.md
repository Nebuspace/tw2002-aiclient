# WO-CANON-FIX-ENTRY-PROFILE-PLAYERS-ADD-NOW-LIVE

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** LOW  

## Goal

Tip-true `canon/surfaces/entry-and-profile-selection.md` (and `cli-verbs.md` players row) after PR #691 shipped `tw players add`.

## Accept

- No remaining "no `tw players add`" / TARGET-for-add claim in entry-and-profile-selection.md.
- LIVE bank verbs cited as `{list,next,rotate,add}`; `add` → `credentials.create_profile()`.
- Consolidated launcher / `tw aiclient` still correctly recorded as TARGET / absent.

## Proof

```bash
rg -n 'no.*tw players add|\*\*no\*\* `tw players add`' canon/surfaces/entry-and-profile-selection.md
rg -n 'players \{list,next,rotate,add\}' canon/surfaces/entry-and-profile-selection.md canon/architecture/cli-verbs.md
```

live-prove: n/a (docs-only).
