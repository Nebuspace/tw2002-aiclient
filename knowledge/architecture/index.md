# Architecture

Concepts describing the client's engineering foundation and the trainer's north-star design —
what is built, and what the built system is meant to grow into.

## Vision

- [Trainer Vision — Learn, Then Fly](/architecture/trainer-vision.md) — The AI pilots the game while the client learns profitable loops from demonstration, graduating toward autonomous flight as its learned repertoire grows.

## Systems

- [Session Engine — Daemon, Settle Detection, Classification, and Control Lock](/architecture/session-engine.md) — The built two-process engine (a session daemon plus a one-shot CLI) that gives an LLM a clean, settled screen back in one round trip while a control-lock mode machine governs who may drive it.
- [World Model — the Persisted Sector Database](/architecture/world-model.md) — A per-world, per-sector knowledge store of warps, ports, threats, and landmarks that every exploration, coaching, and routing behavior reads from.
- [Autonomy Loop — Actor Attribution, the Autonomy Ratio, and Session Retro](/architecture/autonomy-loop.md) — Every keystroke is attributed to who or what generated it, feeding a graduation gauge and a retro tool that mines a session for AI decisions worth codifying.
