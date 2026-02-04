# NMS Data Extraction - Complete

## ✅ Status: COMPLETE

All 13 required JSON files successfully generated and categorized!

### Final Output (as of 2026-02-03)

| File | Items | Size |
|------|-------|------|
| **Refinery.json** | 357 | 127 KB |
| **NutrientProcessor.json** | 1,323 | 491 KB |
| **Products.json** | 61 | 49 KB |
| **RawMaterials.json** | 113 | 70 KB |
| **Technology.json** | 164 | 152 KB |
| **Buildings.json** | 779 | 448 KB |
| **Cooking.json** | 763 | 547 KB |
| **Fish.json** | 226 | 101 KB |
| **Trade.json** | 86 | 65 KB |
| **ConstructedTechnology.json** | 16 | 13 KB |
| **TechnologyModule.json** | 255 | 222 KB |
| **Curiosities.json** | 49 | 38 KB |
| **Others.json** | 2,735 | 1.5 MB |

**Total: 6,927 items in ~4.3 MB**

---

## Complete Extraction Pipeline

### Single Command
```bash
python extract_and_categorize.py
```

### What It Does
1. **Extracts** from 8 MXML game data files
2. **Parses** into 9 base categories with full English translation
3. **Categorizes** into 13 required files based on Group field
4. **Outputs** all files to `data/json/`

### Extraction Time
- **~4-5 seconds** for complete extraction and categorization

---

## System Architecture

### Phase 1: Base Extraction
9 parsers extract from MXML files:
- `refinery.py` → Refinery & NutrientProcessor recipes
- `products.py` → All products
- `rawmaterials.py` → Substances
- `technology.py` → Technologies
- `buildings.py` → Building parts
- `cooking.py` → Food items
- `fish.py` → Fish species
- `trade.py` → Trade goods

### Phase 2: Categorization
`categorization.py` routes items to 13 final files based on `Group` field:
- **Buildings** ← Decorations, cosmetics
- **ConstructedTechnology** ← Buildable tech
- **Cooking** ← Edible items, ingredients
- **Curiosities** ← Relics, salvaged items
- **Fish** ← Fish (kept as-is)
- **NutrientProcessor** ← Cooking recipes (kept as-is)
- **Others** ← Catch-all (charts, cosmetics, etc.)
- **Products** ← Craftable products
- **RawMaterials** ← Mineable substances
- **Refinery** ← Refinery recipes (kept as-is)
- **Technology** ← Installable tech
- **TechnologyModule** ← Upgrade modules
- **Trade** ← Trade goods (kept as-is)

---

## Key Features Implemented

### ✅ Complete English Translation
- 64,386 translation entries from 6 localization files
- Automatic fallback for missing translations
- Smart name inference (e.g., "TECH_FRAGMENT_NAME" → "Tech Fragment Name")

### ✅ Game IDs Preserved
- Uses actual game IDs (e.g., `CASING`, `NANOTUBES`, `TECHFRAG`)
- English names included alongside IDs
- Compatible with game updates

### ✅ Complete Recipe Data
- Input/output items with quantities
- English names for all ingredients
- Operation names translated
- Processing times included

### ✅ Automatic Categorization
- Rule-based routing via `categorization.py`
- Customizable keyword matching
- Icon paths auto-assigned per category

### ✅ Modular & Maintainable
- Separate parser for each data type
- Shared base parser for common operations
- Easy to add new categories or modify rules

---

## Project Structure

```
nms-data-extractor/
├── data/
│   ├── mbin/                    # 8 MXML files + 6 localization MXML
│   └── json/                    # 13 output JSON files + localization.json
├── parsers/                     # 9 modular parsers
│   ├── base_parser.py           # Shared utilities & translation
│   ├── refinery.py
│   ├── products.py
│   ├── rawmaterials.py
│   ├── technology.py
│   ├── buildings.py
│   ├── cooking.py
│   ├── fish.py
│   └── trade.py
├── tests/                       # Individual test scripts for each parser
├── scripts/                     # Analysis & utility scripts
├── tools/
│   └── MBINCompiler.exe
├── .cursor/rules/
│   └── nms-extraction.md        # Development guidelines
├── extract_and_categorize.py    # Main pipeline (ENTRY POINT)
├── categorization.py            # Categorization rules
├── recategorize_all.py          # Re-categorization engine
├── parse_localization.py        # Localization merger
├── README.md                    # User documentation
├── PROGRESS.md                  # This file
└── REQUIRED_MBINS.md            # List of files needed for extraction
```

---

## Next Steps

### For Website Integration
1. Copy all 13 JSON files from `data/json/` to your website
2. Test data loading and display
3. Verify all features work with new data structure

### For Future Updates
1. Run `python extract_and_categorize.py` with new game data
2. Adjust categorization rules in `categorization.py` if needed
3. Re-deploy to website

### Customization
- Modify `categorization.py` to change item routing
- Edit individual parsers for specific data transformations
- Adjust icon paths in `recategorize_all.py`

---

## Completed Milestones

- ✅ **Phase 1**: File extraction (177,974 files)
- ✅ **Phase 2**: MXML conversion (8 data files + 6 localization files)
- ✅ **Phase 3**: Localization merge (64,386 translations)
- ✅ **Phase 4**: Base parsers (9 files created)
- ✅ **Phase 5**: Translation integration
- ✅ **Phase 6**: Categorization system
- ✅ **Phase 7**: 13-file output pipeline
- ✅ **Phase 8**: Cleanup & documentation

---

## Success Metrics

✅ All 13 required JSON files generated
✅ Full English translations (no game keys remaining)
✅ Game IDs preserved
✅ Fast extraction (~4 seconds)
✅ Modular, maintainable codebase
✅ Complete documentation
✅ Ready for website integration

**Status: PRODUCTION READY** 🎉
