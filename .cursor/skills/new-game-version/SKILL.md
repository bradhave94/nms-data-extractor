---
name: new-game-version
description: Full refresh workflow when a new No Man's Sky update is released using extract.py.
---

# New game version – full refresh

When a new No Man's Sky update is released, do a full refresh so all JSON comes from the new game data.

**One-shot (no LLM needed):** From repo root:

```bash
python extract.py --pcbanks "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"
```

This runs: clean → HGPAKtool → consolidate_mbin → MBINCompiler → extract_all.

**If using an LLM** to run steps for you: you must execute every step yourself; do not tell the user to run HGPAKtool or other steps manually.

## When to use

- User says "new game version", "new NMS update", "full refresh", or "update for new patch".
- User wants to re-extract all data from the latest game files.

## Game path (needed for Step 2)

- Game path is `X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS`

---

## Step 1: Run the unified extraction script

**Execute:** From repo root:

```bash
python extract.py --pcbanks "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"
```

This produces the JSON files in `data/json/`.

---

## Checklist (you do all)

| Step | You run |
|------|--------|
| 1 | Run `python extract.py --pcbanks "X:\path\to\PCBANKS"` |
