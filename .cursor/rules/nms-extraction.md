---
description: NMS Data Extraction development guidelines and patterns
globs:
  - "parsers/**/*.py"
  - "tests/**/*.py"
  - "utils/**/*.py"
  - "scripts/**/*.py"
---

# NMS Data Extraction Rules

## Project Structure
```
nms-data-extractor/
├── extract_all.py             # MAIN SCRIPT (run this)
├── data/
│   ├── mbin/                  # 9 MXML data files + 6 localization files
│   ├── json/                  # 13 output JSON files
│   └── EXTRACTED/             # Raw PAK (can delete after conversion)
├── parsers/                   # 10 modular parsers
│   ├── base_parser.py         # Shared utilities & translation
│   ├── refinery.py            # Refinery & NutrientProcessor
│   ├── products.py
│   ├── rawmaterials.py
│   ├── technology.py
│   ├── buildings.py
│   ├── cooking.py
│   ├── fish.py
│   ├── trade.py
│   └── ship_components.py     # Starship customization parts
├── utils/                     # Helper modules
│   ├── categorization.py      # Item categorization rules
│   └── parse_localization.py  # Localization merger
├── scripts/                   # Analysis & utility scripts
│   ├── compare_extraction.py  # Compare vs reference data
│   └── list_original_groups.py # List groups in reference files
├── tests/                     # Individual parser tests
├── docs/                      # Documentation
└── tools/                     # MBINCompiler.exe
```

## Quick Start

### Single Command Extraction
```bash
python extract_all.py
```

That's it! All 13 JSON files will be in `data/json/`

### What It Does
1. Extracts from 9 MXML game data files
2. Parses into 10 base categories with full English translation
3. Categorizes into 13 required files based on Group field
4. Outputs all files to `data/json/`

### Extraction Time
- ~4-5 seconds for complete extraction

---

## 13 Output Files

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

---

## Manual Extraction Process (for updates)

### 1. Extract Game Files (15 files only)
Use HGPAKtool with filters to extract only needed files:
- 9 data tables from `METADATA/REALITY/TABLES/`
- 6 English localization files from `LANGUAGE/`

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
  -f="*LANGUAGE/nms_loc1_english.mbin" \
  -f="*LANGUAGE/nms_loc4_english.mbin" \
  -f="*LANGUAGE/nms_loc5_english.mbin" \
  -f="*LANGUAGE/nms_loc6_english.mbin" \
  -f="*LANGUAGE/nms_loc7_english.mbin" \
  -f="*LANGUAGE/nms_update3_english.mbin" \
  "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"
```

**Result**: 15 files (~5-10MB) instead of 177,974 files (45GB)

### 2. Convert MBIN to MXML
```bash
cd data/mbin
../../tools/MBINCompiler.exe *.mbin
```

### 3. Run Main Script
```bash
python extract_all.py
```

## Categorization System

### Rules Location
Edit `utils/categorization.py` to modify which items go into which files.

### How It Works
Items are routed based on their `Group` field:
- **Exact matches**: e.g., `"Ship Tech"` → `Technology.json`
- **Keyword matches**: e.g., `"Freighter Tech"` contains "Tech" → `Technology.json`
- **No match**: Item is skipped (not added to any file)

### Categorization Logic
```python
CATEGORIZATION_RULES = {
    'Buildings.json': {
        'keywords': ['Decoration', 'Unlockable', 'Base Building'],
        'exact': {'Planetary Base Building', ...}
    },
    # ... more rules
}
```

### Skip Rules
Items are automatically skipped if:
- Name is missing or broken (starts with `UI_`, `Ui `, etc.)
  - **EXCEPTION**: Ship components are allowed even with `Ui ` names (they use internal keys)
- Name equals the ID (untranslated)
- Group doesn't match any categorization rule
- Group is empty/missing
- Item matches junk keywords (developer placeholders like 'Biggs', 'Basic F', 'Wall Art')

---

## Starship Components (Special Case)

### Source File
**`nms_modularcustomisationproducts.mbin`** - Contains all starship customization parts (427 items)

### Subtitle to Group Mapping
Ship components use subtitle keys instead of standard group names:

| Subtitle Key | Group Name | Count |
|-------------|------------|-------|
| `UI_DROPSHIP_PART_SUB` | Hauler Starship Component | 135 |
| `UI_FIGHTER_PART_SUB` | Fighter Starship Component | 65 |
| `UI_SAIL_PART_SUB` | Solar Starship Component | 39 |
| `UI_SCIENTIFIC_PART_SUB` | Explorer Starship Component | 41 |
| `UI_FOS_HEAD_SUB` | Living Ship Component | 110 |
| `UI_FOS_LIMBS_SUB` | Living Ship Component | 10 |
| `UI_FOS_BI_BODY_SUB` | Living Ship Component | 12 |
| `UI_FOS_BI_TAIL_SUB` | Living Ship Component | 11 |
| `UI_SHIP_CORE_A_SUB` | Starship Core Component | 1 |
| `UI_SHIP_CORE_B_SUB` | Starship Core Component | 1 |
| `UI_SHIP_CORE_C_SUB` | Starship Core Component | 1 |
| `UI_SHIP_CORE_S_SUB` | Starship Core Component | 1 |

### Translation Notes
- Ship component names often don't translate properly (`Ui Dropship Cock A`)
- This is expected - the localization keys aren't in standard language files
- Items are still valid and categorized correctly by Group
- The `categorize_item()` function has a special exception for ship component groups

### Categorization
All ship components go to **Others.json** via exact group matching in `utils/categorization.py`:
```python
'Others.json': {
    'exact': {
        'Hauler Starship Component',
        'Fighter Starship Component',
        'Solar Starship Component',
        'Explorer Starship Component',
        'Living Ship Component',
        'Starship Core Component',
        # ... other groups
    }
}
```

---

## Parser Development Guidelines

### Base Parser Features
- `EXMLParser.load_localization()` - Auto-loads translations
- `EXMLParser.translate(key)` - Translates localization keys to English
- Smart fallback: tries key → BUI_prefix → TRA_prefix → EXP_prefix → readable format

### Name Lookup Pattern
For items referenced in recipes/requirements:
1. Load item tables (Products, Substances)
2. Extract ID and Name key from each item
3. Try multiple translation patterns:
   - Direct key translation (e.g., `TECH_FRAGMENT_NAME`)
   - Prefix patterns (e.g., `BUI_TECHFRAG`)
   - Fallback to formatted ID

### Structure Requirements
- Use game IDs (e.g., `TECHFRAG` not `raw56`)
- Include English names alongside IDs
- Match existing JSON field structure
- Handle missing translations gracefully

## Key Data Mappings

### Refinery/NutrientProcessor
- Both come from `nms_reality_gcrecipetable.mbin`
- Split by `Cooking` flag (false=refinery, true=cooking)
- Include Input/Output names via item lookup

### Products/Substances
- Products: `nms_reality_gcproducttable.mbin`
- Substances: `nms_reality_gcsubstancetable.mbin`
- Used for name lookups in other parsers

## Translation System

### 64,386 English translations from 6 files:
- `nms_loc1_english.mbin` - Core translations (14,731)
- `nms_loc4_english.mbin` - Additional content (10,840)
- `nms_loc5_english.mbin` - Updates (7,074)
- `nms_loc6_english.mbin` - More updates (10,356)
- `nms_loc7_english.mbin` - Recent content (10,099)
- `nms_update3_english.mbin` - Latest updates (11,298)

### Common Translation Patterns:
- Item names: `*_NAME` keys → look for `BUI_*`, `TRA_*`, or `EXP_*` prefixes
- Descriptions: `*_DESC` keys
- Subtitles: `*_SUB` or `*_SUBTITLE` keys

## Testing
Each parser should have a test script:
```python
# tests/test_[parser].py
python tests/test_refinery.py  # Tests and outputs sample
```

## Version Compatibility
- HGPAKtool: For NMS 5.50+ (Worlds Part II onwards)
- MBINCompiler: Version MUST match game version exactly
- Check game version before extracting after updates
