# NMS Data Extractor

Automated Python system to extract and parse No Man's Sky game data into JSON format.

## Quick Start

### Extract All Data (One Command)
```bash
python extract_and_categorize.py
```

This will:
1. Extract all data from MXML files
2. Categorize into 13 required JSON files

**Output:** All 13 JSON files in `data/json/`

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
│   ├── mbin/                # MXML files (converted from MBIN)
│   └── json/                # Final JSON output (13 files)
├── parsers/
│   ├── base_parser.py       # Shared utilities & translation
│   ├── refinery.py          # Refinery & NutrientProcessor
│   ├── products.py
│   ├── rawmaterials.py
│   ├── technology.py
│   ├── buildings.py
│   ├── cooking.py
│   ├── fish.py
│   └── trade.py
├── tests/                   # Individual test scripts
├── scripts/                 # Analysis & utility scripts
├── tools/
│   └── MBINCompiler.exe
├── extract_and_categorize.py  # Main pipeline script
├── categorization.py          # Categorization rules
├── recategorize_all.py        # Re-categorization script
└── parse_localization.py      # Localization merger
```

## How It Works

1. **Extraction** (`extract_and_categorize.py`)
   - Extracts data from 8 MXML files
   - Parses into 9 base categories
   - Full English translation (64,386 entries)

2. **Categorization** (`categorization.py`)
   - Routes items based on `Group` field
   - Splits into 13 required files
   - Automatic icon path assignment

3. **Output**
   - 13 JSON files matching your app structure
   - Game IDs preserved
   - English names included

## Key Features

- ✅ Full English translations (64,386 entries from 6 localization files)
- ✅ Game IDs preserved (e.g., `CASING`, `NANOTUBES`, `TECHFRAG`)
- ✅ English names included for all items
- ✅ Complete recipe data with input/output details
- ✅ Automatic categorization into 13 files
- ✅ Fast extraction (~8 seconds total)

## Customization

### Modify Categorization Rules

Edit `categorization.py` to change which items go into which files:

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

See `REQUIRED_MBINS.md` for the exact 14 files needed from game data (instead of extracting all 177,974 files).

## Development

- **Cursor Rules**: `.cursor/rules/nms-extraction.md`
- **Progress Tracking**: `PROGRESS.md`
- **Analysis Scripts**: `scripts/` directory
