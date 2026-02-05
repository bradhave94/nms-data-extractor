# NMS Data Extractor

Automated Python system to extract and parse No Man's Sky game data into JSON format.

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
python extract_all.py
```

This will:
1. Extract all data from MXML files
2. Categorize into 13 required JSON files

**Output:** All 13 JSON files in `data/json/`

### Full refresh (new game version)

To rebuild everything from the latest game files (clean → extract MBINs → convert → extract JSON) in one go:

```bash
# Set your game path once (Windows: set NMS_PCBANKS=... ; macOS/Linux: export NMS_PCBANKS=...)
# Or pass it: python full_refresh.py "X:\...\PCBANKS"
python full_refresh.py
```

Requires **hgpaktool** library and **MBINCompiler.exe** in `tools/`.

### Extract item icons (images)

To unpack game textures and export one PNG per item (for CDN or app use):

```bash
# Same game path as full_refresh (NMS_PCBANKS or pass as argument)
python extract_all_images.py
```

This will: (1) unpack `*TEXTURES/*` from the game into `data/`, (2) normalize to `data/EXTRACTED/textures/`, (3) run `utils.extract_images` to produce **`data/images/{id}.png`** (or `.dds` if ImageMagick is not installed).

- **Requires:** hgpaktool library (installed via requirements.txt); **optional:** [ImageMagick](https://imagemagick.org/) (`magick`) for DDS→PNG.
- If you already have `data/EXTRACTED` (e.g. from a previous run), you can skip unpacking and only extract icons:
  `python -m utils.extract_images`
  (uses `data/json/` and `data/EXTRACTED/`, writes to `data/images/`).

### Generated Files

| File | Description |
|------|-------------|
| **Refinery.json** | Refinery recipes |
| **NutrientProcessor.json** | Cooking recipes |
| **Products.json** | Craftable products |
| **RawMaterials.json** | Mineable substances |
| **Technology.json** | Installable technologies |
| **Buildings.json** | Base building parts |
| **Cooking.json** | Edible items & ingredients |
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
│   ├── json/                # Final JSON output (13 category files + localization)
│   ├── EXTRACTED/           # Game textures (from extract_all_images.py; gitignored)
│   └── images/              # Item icons {id}.png (from extract_all_images.py; gitignored)
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
│   ├── clean_data.py        # Wipe data/ for full refresh
│   ├── compare_data.py      # Compare two data dirs (used by compare_data.py CLI)
│   ├── consolidate_mbin.py  # Copy MBINs into data/mbin, remove metadata/language
│   ├── extract_images.py    # EXTRACTED → data/images/{id}.png (used by extract_all_images.py)
│   └── parse_localization.py  # Localization merger
├── extract_all.py           # Main pipeline (run this)
├── extract_all_images.py    # Unpack textures + extract item icons to data/images/
├── full_refresh.py          # Clean + HGPAKtool + MBINCompiler + extract_all
├── compare_data.py          # Compare two data dirs (e.g. old vs new) → markdown table report
└── tools/                   # gitignored
    └── MBINCompiler.exe     # Not included in the repo
```

## How It Works

1. **Extraction** (`extract_all.py`)
   - Rebuilds localization, then extracts from MXML files
   - Parses into base categories and categorizes into 13 files
   - Full English translation from locale MXMLs

2. **Categorization** (`utils/categorization.py`)
   - Routes items based on `Group` field
   - Splits into 13 required files
   - Automatic icon path assignment

3. **Output**
   - 13 JSON files matching your app structure
   - Game IDs preserved
   - English names included

### Compare data (old vs new)

Use `compare_data.py` to diff two data directories (e.g. previous vs current extract) and get a markdown table report:

```bash
# Default: old = nms/src/data, new = nms/src/datav2
python compare_data.py

# Custom paths
python compare_data.py --old "path/to/old/data" --new "path/to/new/data"

# Summary table only
python compare_data.py --no-details

# Write report to file
python compare_data.py -o comparison_report.md
```

Report columns: **Added** (IDs only in new), **Removed** (IDs only in old), **Changed** (same ID, different fields). `CdnUrl` and `Icon` are ignored when detecting changes.

## Key Features

- ✅ Full English translations from 8 localization files
- ✅ Game IDs preserved (e.g., `CASING`, `NANOTUBES`, `TECHFRAG`)
- ✅ English names included for all items
- ✅ Complete recipe data with input/output details
- ✅ Automatic categorization into 13 files
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
| `consumableitemtable.mbin` | Cooking.json |
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

The `full_refresh.py` script uses hgpaktool as a Python library. The library is included in `requirements.txt` and will automatically extract the required files from your game's PCBANKS folder.

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
python extract_all.py
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

### 2. Run full_refresh.py

Run the script with your game's PCBANKS path:

```bash
python full_refresh.py "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"
```

The script will:
- Extract the 18 required MBIN files from your game's PAK files
- Consolidate them into `data/mbin/`
- Convert MBIN to MXML with MBINCompiler
- Extract and categorize into 13 JSON files in `data/json/`

### Checklist (new game version)

| Step | Action |
|------|--------|
| 1 | Install dependencies: `pip install -r requirements.txt` |
| 2 | Delete all contents (or subfolders) of `data/` |
| 3 | Run `python full_refresh.py "X:\path\to\PCBANKS"` (script handles extraction, conversion, and JSON generation automatically) |

---

## Development

- **Cursor Rules**: `.cursor/rules/nms-extraction.md`

