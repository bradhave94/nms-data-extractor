# Required MBIN Files for Extraction

## Essential Game Data Files (10 files)
Extract from: `GAMEDATA\PCBANKS\` → `METADATA\REALITY\TABLES\`

1. `nms_reality_gcproducttable.mbin` → Products.json + Trade.json
2. `consumableitemtable.mbin` → Cooking.json
3. `nms_reality_gcrecipetable.mbin` → Refinery.json + NutrientProcessor.json
4. `nms_reality_gctechnologytable.mbin` → Technology.json
5. `basebuildingobjectstable.mbin` → Buildings.json
6. `nms_reality_gcsubstancetable.mbin` → RawMaterials.json
7. `fishdatatable.mbin` → Fish.json
8. `tradingclassdatatable.mbin` → Trade.json (metadata)
9. **`nms_modularcustomisationproducts.mbin`** → **Others.json (Ship Components)**
10. **`nms_basepartproducts.mbin`** → **Buildings.json (Freighter Interior)**

## English Localization Files (6 files)
Extract from: `GAMEDATA\PCBANKS\` → `LANGUAGE\`

1. `nms_loc1_english.mbin`
2. `nms_loc4_english.mbin`
3. `nms_loc5_english.mbin`
4. `nms_loc6_english.mbin`
5. `nms_loc7_english.mbin`
6. `nms_update3_english.mbin`

## HGPAKtool Filtered Extraction Command

Instead of extracting all 177,974 files (45GB), use:

```bash
tools\hgpaktool.exe -U \
  -f="*REALITY/TABLES/nms_reality_gcproducttable.mbin" \
  -f="*REALITY/TABLES/consumableitemtable.mbin" \
  -f="*REALITY/TABLES/nms_reality_gcrecipetable.mbin" \
  -f="*REALITY/TABLES/nms_reality_gctechnologytable.mbin" \
  -f="*REALITY/TABLES/basebuildingobjectstable.mbin" \
  -f="*REALITY/TABLES/tradingclassdatatable.mbin" \
  -f="*REALITY/TABLES/nms_reality_gcsubstancetable.mbin" \
  -f="*REALITY/TABLES/fishdatatable.mbin" \
  -f="*REALITY/TABLES/nms_modularcustomisationproducts.mbin" \
  -f="*REALITY/TABLES/nms_basepartproducts.mbin" \
  -f="*LANGUAGE/nms_loc1_english.mbin" \
  -f="*LANGUAGE/nms_loc4_english.mbin" \
  -f="*LANGUAGE/nms_loc5_english.mbin" \
  -f="*LANGUAGE/nms_loc6_english.mbin" \
  -f="*LANGUAGE/nms_loc7_english.mbin" \
  -f="*LANGUAGE/nms_update3_english.mbin" \
  "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"
```

**Result**: 16 files (~6-12MB) instead of 177,974 files (45GB)
**Time**: Seconds instead of 6+ minutes

## Total Files Needed: 16
- 10 data tables
- 6 localization files

## Optional: Extract ALL Reality Tables (58 files)

For access to all game data including rewards, expeditions, unlockables, etc:

```bash
hgpaktool -U -f="*REALITY/TABLES/*.mbin" -O "data/EXTRACTED" "X:\Steam\...\PCBANKS"
```

Then convert all MBINs to MXML:
```bash
cd data/mbin
../../tools/MBINCompiler.exe *.mbin
```
