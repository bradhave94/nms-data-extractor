# NMS Data Extractor

Automated Python system to extract and parse No Man's Sky game data into JSON format. Use for my site [nomansskyrecipes.com]([nomansskyrecipes.com](https://nomansskyrecipes.com/))

## Requirements

Before running the extractor you need:

1. **MBINCompiler**
   - Download the latest release from [monkeyman192/MBINCompiler](https://github.com/monkeyman192/MBINCompiler).
   - Requires [.NET 8](https://dotnet.microsoft.com/download/dotnet/8.0) (choose “Run desktop apps”).
   - Put **MBINCompiler.exe** in the project’s **`tools/`** folder (create `tools/` if it doesn’t exist).

2. **Python Dependencies**
   - Install all required dependencies with: `pip install -r requirements.txt`
   - This includes **hgpaktool** (PAK file extraction) and **zstandard** (compression support)

3. **Optional: ImageMagick** (for icon extraction)
   - Download from [imagemagick.org](https://imagemagick.org/)
   - Used to convert DDS textures to PNG format
   - If not installed, icon extraction will output `.dds` files instead

## Quick Start

### Extract All Data (One Command)
```bash
python extract.py
```

This will:
1. Extract all data from MXML files
2. Categorize into output JSON files

**Output:** JSON files in `data/json/`

Duplicate `Id` entries are automatically deduplicated by default (no flags needed).
`Food.json` keeps merge-style dedupe; other files use keep-first dedupe to avoid cross-schema field contamination.

Strict validation is enabled by default and fails the run on smoke-check errors (including duplicate IDs).  
If you need to bypass strict checks temporarily:

```bash
python extract.py --no-strict
```

### Full refresh (new game version)

To rebuild everything from the latest game files (clean → extract MBINs → convert → extract JSON) in one go:

```bash
# Use default PCBANKS path:
python extract.py --refresh

# Or pass a custom path:
python extract.py --pcbanks "X:\...\PCBANKS"
```

Requires **hgpaktool** library and **MBINCompiler.exe** in `tools/`.

### Extract item icons (images)

To unpack game textures and export one PNG per item (for CDN or app use):

```bash
# Reuse existing EXTRACTED folder:
python extract.py --images --extracted "C:\path\to\EXTRACTED"

# Or extract textures from game files then generate images:
python extract.py --images --pcbanks "X:\...\PCBANKS"
```

`--images` runs image extraction only (it does not run JSON extraction).  
This will run `utils.images` to produce **`data/images/{id}.png`** (or `.dds` if ImageMagick is not installed).  
If `--extracted` is not provided, textures are unpacked from game files first.

- **Requires:** hgpaktool library (installed via requirements.txt); **optional:** [ImageMagick](https://imagemagick.org/) (`magick`) for DDS→PNG.

### Smoke checks

Run lightweight validation on extracted JSON output:

```bash
# Default: validates file existence/JSON structure; duplicate IDs are warnings
python -m utils.smoke

# Strict: duplicate IDs are treated as errors
python -m utils.smoke --strict-duplicates
```

### Generated Files

| File | Description |
|------|-------------|
| **Refinery.json** | Refinery recipes |
| **NutrientProcessor.json** | Cooking recipes |
| **Products.json** | Craftable products |
| **RawMaterials.json** | Mineable substances |
| **Technology.json** | Installable technologies |
| **Buildings.json** | Base building parts |
| **Food.json** | Edible items & ingredients |
| **Corvette.json** | Corvette parts |
| **Fish.json** | Catchable fish |
| **Trade.json** | Trade goods & smuggled items |
| **ConstructedTechnology.json** | Buildable tech items |
| **TechnologyModule.json** | Upgrade modules |
| **Curiosities.json** | Salvaged items & relics |
| **Others.json** | Misc items (charts, cosmetics, etc.) |

## Project Structure

```
nms-data-extractor/
├── data/
│   ├── mbin/                # MXML files (converted from MBIN; gitignored)
│   ├── json/                # Final JSON output
│   ├── EXTRACTED/           # Game textures (from extract.py --images; gitignored)
│   └── images/              # Item icons {id}.png (from extract.py --images; gitignored)
├── parsers/
│   ├── __init__.py
│   ├── base_parser.py       # Shared utilities & translation
│   ├── base_parts.py
│   ├── buildings.py
│   ├── cooking.py
│   ├── fish.py
│   ├── procedural_tech.py
│   ├── products.py
│   ├── rawmaterials.py
│   ├── refinery.py
│   ├── ship_components.py
│   ├── technology.py
│   └── trade.py
├── utils/
│   ├── __init__.py
│   ├── categorization.py    # Categorization rules
│   ├── clean.py             # Wipe data/ for full refresh
│   ├── mbin.py              # Copy MBINs into data/mbin, remove metadata/language
│   ├── images.py            # EXTRACTED → data/images/{id}.png (used by extract.py)
│   ├── localization.py      # Localization merger
│   ├── report.py            # Refresh report generation
│   └── smoke.py             # Post-extraction validation checks
├── extract.py               # Single entrypoint (json extraction, refresh, images)
└── tools/                   # gitignored
    └── MBINCompiler.exe     # Not included in the repo
```

## How It Works

1. **Extraction** (`extract.py`)
   - Rebuilds localization, then extracts from MXML files
   - Parses into base categories and categorizes into output files
   - Full English translation from locale MXMLs

2. **Categorization** (`utils/categorization.py`)
   - Routes items based on `Group` field
   - Splits items into the project output files
   - Automatic icon path assignment

3. **Output**
   - JSON files matching your app structure
   - Game IDs preserved
   - English names included

## Key Features

- ✅ Full English translations from 8 localization files
- ✅ Game IDs preserved (e.g., `CASING`, `NANOTUBES`, `TECHFRAG`)
- ✅ English names included for all items
- ✅ Complete recipe data with input/output details
- ✅ Automatic categorization into output files
- ✅ Fast extraction (~8 seconds total)

## Customization

### Modify Categorization Rules

Edit `utils/categorization.py` to change which items go into which files:

```python
CATEGORIZATION_RULES = {
    'Buildings.json': {
        'keywords': ['Decoration', 'Unlockable', ...],
        'exact': set()
    },
    # ... more rules
}
```

## Files Needed for Fresh Extraction

The pipeline uses **18 MBIN files** from the game: 10 data tables and 8 English localization files. You do not need to extract all 177,974 game files.

### Data tables (10)

| MBIN | Output / use |
|------|------------------|
| `nms_reality_gcproducttable.mbin` | Products, Trade, name/icon lookups |
| `consumableitemtable.mbin` | Food.json |
| `nms_reality_gcrecipetable.mbin` | Refinery.json, NutrientProcessor.json |
| `nms_reality_gctechnologytable.mbin` | Technology.json |
| `basebuildingobjectstable.mbin` | Buildings.json |
| `nms_reality_gcsubstancetable.mbin` | RawMaterials.json |
| `fishdatatable.mbin` | Fish.json |
| `nms_modularcustomisationproducts.mbin` | Others.json (ship components) |
| `nms_basepartproducts.mbin` | Buildings (freighter parts) |
| `nms_reality_gcproceduraltechnologytable.mbin` | ConstructedTechnology, TechnologyModule |

### Localization (8)

`nms_loc1_english.mbin`, `nms_loc4_english.mbin`, `nms_loc5_english.mbin`, `nms_loc6_english.mbin`, `nms_loc7_english.mbin`, `nms_loc8_english.mbin`, `nms_loc9_english.mbin`, `nms_update3_english.mbin` (product/fish names and descriptions come from these).

### Automatic Extraction with HGPAKtool Library

`extract.py --refresh` (default path) and `extract.py --pcbanks ...` (custom path) use hgpaktool as a Python library. The library is included in `requirements.txt` and will automatically extract the required files from your game's PCBANKS folder.

If you want to manually extract with the hgpaktool command-line tool (e.g., for testing), you can do so. Point it at your game `PCBANKS` folder and use filters so only these 18 files are extracted.

**Example; replace the path with your No Man's Sky install:**

```
hgpaktool -U `
  -f="*REALITY/TABLES/nms_reality_gcproducttable.mbin" `
  -f="*REALITY/TABLES/consumableitemtable.mbin" `
  -f="*REALITY/TABLES/nms_reality_gcrecipetable.mbin" `
  -f="*REALITY/TABLES/nms_reality_gctechnologytable.mbin" `
  -f="*REALITY/TABLES/basebuildingobjectstable.mbin" `
  -f="*REALITY/TABLES/nms_reality_gcsubstancetable.mbin" `
  -f="*REALITY/TABLES/fishdatatable.mbin" `
  -f="*REALITY/TABLES/nms_modularcustomisationproducts.mbin" `
  -f="*REALITY/TABLES/nms_basepartproducts.mbin" `
  -f="*REALITY/TABLES/nms_reality_gcproceduraltechnologytable.mbin" `
  -f="*LANGUAGE/nms_loc1_english.mbin" `
  -f="*LANGUAGE/nms_loc4_english.mbin" `
  -f="*LANGUAGE/nms_loc5_english.mbin" `
  -f="*LANGUAGE/nms_loc6_english.mbin" `
  -f="*LANGUAGE/nms_loc7_english.mbin" `
  -f="*LANGUAGE/nms_loc8_english.mbin" `
  -f="*LANGUAGE/nms_loc9_english.mbin" `
  -f="*LANGUAGE/nms_update3_english.mbin" `
  "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"
```

Then convert MBIN → MXML with **MBINCompiler** (e.g. `tools\MBINCompiler.exe` in `data\mbin`), and run:

```bash
python extract.py
```

More detail (optional extraction, paths): `docs/REQUIRED_MBINS.md`.

---

## Workflow: New game version

When a new No Man's Sky update is released, do a full refresh so all JSON comes from the new game data. Follow every step in order.

### 1. Clean the data folder

Remove all generated and extracted data so you start from a clean state.

- Delete everything inside **`data/`** (all subfolders and their contents):
  - `data/EXTRACTED/` (if present)
  - `data/mbin/` (old MBINs and MXMLs)
  - `data/json/` (old output; will be recreated by the script)
  - `data/images/` (optional; only if you want to regenerate icons)

You can delete the folders themselves; the next steps will recreate what’s needed. Keep the **`data/`** directory.

### 2. Run extract.py with --refresh (or --pcbanks)

Run with the default PCBANKS path:

```bash
python extract.py --refresh
```

Or run with a custom path:

```bash
python extract.py --pcbanks "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"
```

The script will:
- Extract the 18 required MBIN files from your game's PAK files
- Consolidate them into `data/mbin/`
- Convert MBIN to MXML with MBINCompiler
- Extract and categorize into output JSON files in `data/json/`

### Checklist (new game version)

| Step | Action |
|------|--------|
| 1 | Install dependencies: `pip install -r requirements.txt` |
| 2 | Delete all contents (or subfolders) of `data/` |
| 3 | Run `python extract.py --refresh` (or `python extract.py --pcbanks "X:\path\to\PCBANKS"`) |

---

## Development

- **Cursor Rules**: `.cursor/rules/nms-extraction.md`

