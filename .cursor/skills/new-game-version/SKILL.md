---
name: new-game-version
description: Full refresh workflow when a new No Man's Sky update is released—clean data, extract 18 MBINs, convert to MXML, run extract_all.py.
---

# New game version – full refresh

When a new No Man's Sky update is released, do a full refresh so all JSON comes from the new game data.

**One-shot (no LLM needed):** From repo root, set the game path once then run:

```bash
set NMS_PCBANKS=X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS
python full_refresh.py
```

Or pass the path: `python full_refresh.py "X:\...\PCBANKS"`. The script runs: clean → HGPAKtool → consolidate_mbin → MBINCompiler → extract_all.

**If using an LLM** to run steps for you: you must execute every step yourself; do not tell the user to run HGPAKtool or other steps manually.

## When to use

- User says "new game version", "new NMS update", "full refresh", or "update for new patch".
- User wants to re-extract all data from the latest game files.

## Game path (needed for Step 2)

- Game path is `X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS`

---

## Step 1: Clean the data folder

**Execute:** Run the clean script (from repo root):

```bash
python -m utils.clean_data
```

This removes everything inside `data/` (EXTRACTED, mbin, json, images, etc.), keeps `data/`, and creates `data/json/`.

## Step 2: Get the 18 MBINs with HGPAKtool

**Execute:** Run HGPAKtool from the repo root with the 18-file filters and `-O data` (game path: `X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS`). Then run the consolidate script so all MBINs end up in `data/mbin/` and `data/metadata/` and `data/language/` are removed:

```bash
hgpaktool -U \
  -f="*REALITY/TABLES/nms_reality_gcproducttable.mbin" \
  -f="*REALITY/TABLES/consumableitemtable.mbin" \
  -f="*REALITY/TABLES/nms_reality_gcrecipetable.mbin" \
  -f="*REALITY/TABLES/nms_reality_gctechnologytable.mbin" \
  -f="*REALITY/TABLES/basebuildingobjectstable.mbin" \
  -f="*REALITY/TABLES/nms_reality_gcsubstancetable.mbin" \
  -f="*REALITY/TABLES/fishdatatable.mbin" \
  -f="*REALITY/TABLES/nms_modularcustomisationproducts.mbin" \
  -f="*REALITY/TABLES/nms_basepartproducts.mbin" \
  -f="*REALITY/TABLES/nms_reality_gcproceduraltechnologytable.mbin" \
  -f="*LANGUAGE/nms_loc1_english.mbin" \
  -f="*LANGUAGE/nms_loc4_english.mbin" \
  -f="*LANGUAGE/nms_loc5_english.mbin" \
  -f="*LANGUAGE/nms_loc6_english.mbin" \
  -f="*LANGUAGE/nms_loc7_english.mbin" \
  -f="*LANGUAGE/nms_loc8_english.mbin" \
  -f="*LANGUAGE/nms_loc9_english.mbin" \
  -f="*LANGUAGE/nms_update3_english.mbin" \
  -O data \
  "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"

python -m utils.consolidate_mbin
```

The consolidate script copies every `.mbin` from `data/metadata` and `data/language` into `data/mbin/`, creates `data/mbin/` if needed, then deletes `data/metadata/` and `data/language/`.

## Step 3: Convert MBIN → MXML with MBINCompiler

**Execute:** Run MBINCompiler on every `.mbin` in `data/mbin/`. The tool takes one file at a time; loop over `data/mbin/*.mbin` (e.g. `for f in data/mbin/*.mbin; do tools/MBINCompiler.exe "$f"; done` or equivalent). Ensure every `.mbin` has a matching `.MXML`.

## Step 4: Run the extraction script

**Execute:** From repo root:

```bash
python extract_all.py
```

This produces the 13 JSON files in `data/json/`.

---

## Checklist (you do all)

| Step | You run |
|------|--------|
| 1 | Run `python -m utils.clean_data` |
| 2 | Run HGPAKtool; then `python -m utils.consolidate_mbin` |
| 3 | Run MBINCompiler on each `data/mbin/*.mbin` |
| 4 | Run `python extract_all.py` |
