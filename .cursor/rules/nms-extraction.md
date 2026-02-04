---
description: NMS Data Extraction — always include this rule when working on the nms-data-extractor app. Development guidelines, pipeline, and categorization.
globs:
  - "parsers/**/*.py"
  - "utils/**/*.py"
  - "extract_all.py"
  - "docs/**/*.md"
  - "README.md"
---

# NMS Data Extraction Rules

**Always include this rule** when working on the nms-data-extractor app (parsers, categorization, extraction pipeline or docs).

---

## Project Structure

```
nms-data-extractor/
├── extract_all.py             # MAIN SCRIPT (run this)
├── data/
│   ├── mbin/                  # MXML data files + localization (convert from MBIN)
│   ├── json/                  # 13 output JSON files + none.json (uncategorized)
│   └── EXTRACTED/             # Raw PAK output (optional; can delete after conversion)
├── parsers/                   # 12 modular parsers
│   ├── base_parser.py         # Shared utilities & translation
│   ├── refinery.py            # Refinery & NutrientProcessor
│   ├── products.py
│   ├── rawmaterials.py
│   ├── technology.py
│   ├── buildings.py
│   ├── cooking.py
│   ├── fish.py
│   ├── trade.py
│   ├── ship_components.py     # Starship customization parts
│   ├── base_parts.py          # Base/freighter building parts
│   └── procedural_tech.py     # Procedural upgrade modules
├── utils/
│   ├── categorization.py     # Item categorization rules (Group → file)
│   ├── list_original_groups.py # List unique Group values from original data
│   └── parse_localization.py # Localization merger
├── docs/
├── tools/                     # MBINCompiler.exe (not in repo)
└── README.md
```

---

## Pipeline (extract_all.py)

### Step 0: Rebuild localization
- Builds `data/json/localization.json` from locale MXML files in `data/mbin/`.
- Parsers use this for English names/descriptions.

### Step 1: Extract base data (12 parsers)
Reads MXML from `data/mbin/` and populates `base_data`:

| Parser            | Source MXML                                      | Output / use                    |
|-------------------|--------------------------------------------------|---------------------------------|
| Refinery          | nms_reality_gcrecipetable.MXML                   | Refinery.json                   |
| NutrientProcessor | nms_reality_gcrecipetable.MXML                   | NutrientProcessor.json          |
| Products          | nms_reality_gcproducttable.MXML                  | Categorized + name lookups     |
| RawMaterials      | nms_reality_gcsubstancetable.MXML                | RawMaterials.json               |
| Technology        | nms_reality_gctechnologytable.MXML                | Categorized                     |
| Buildings         | basebuildingobjectstable.MXML                     | Categorized                     |
| Cooking           | consumableitemtable.MXML                          | Categorized                     |
| Fish              | fishdatatable.MXML                                | Fish.json                       |
| Trade             | nms_reality_gcproducttable.MXML                   | Trade.json                      |
| ShipComponents    | nms_modularcustomisationproducts.MXML            | Categorized → Others            |
| BaseParts         | nms_basepartproducts.MXML                         | Categorized                     |
| ProceduralTech    | nms_reality_gcproceduraltechnologytable.MXML     | Categorized                     |

### Step 2: Categorize into 13 files
- **Kept as-is (no categorization):** Refinery, NutrientProcessor, Fish, Trade, RawMaterials.
- **Categorized:** Items from Products, Technology, Buildings, Cooking, ShipComponents, BaseParts, ProceduralTech are routed by `Group` via `utils/categorization.py`.
- **Order matters:** First matching file wins (e.g. ConstructedTechnology before Technology).
- **Uncategorized items** are written to `data/json/none.json` for review.

### Step 3: Save
- Writes 13 JSON files (+ `none.json` when there are uncategorized items) to `data/json/`.

### Run
```bash
python extract_all.py
```
- Typical run: ~4–8 seconds.

---

## 13 Output Files

| File | Description |
|------|-------------|
| Refinery.json | Refinery recipes |
| NutrientProcessor.json | Cooking recipes |
| Products.json | Craftable products (by Group) |
| RawMaterials.json | Mineable substances |
| Technology.json | Installable technologies |
| Buildings.json | Base building parts |
| Cooking.json | Edible items & ingredients |
| Fish.json | Catchable fish |
| Trade.json | Trade goods & smuggled items |
| ConstructedTechnology.json | Buildable tech items |
| TechnologyModule.json | Upgrade modules |
| Curiosities.json | Salvaged items & relics |
| Others.json | Misc (charts, cosmetics, ship components, etc.) |

---

## Categorization System (utils/categorization.py)

### Rules
- **Exact match only:** Each file has an `exact` set of `Group` values. No keyword/substring matching.
- **Rule order:** First matching file wins. ConstructedTechnology and TechnologyModule are ordered before Technology.

### How it works
- `categorize_item(item)` reads `item.get('Group', '').strip()` and returns the target filename or `None`.
- If `None`, the item is skipped and written to **none.json**.

### Skip rules (return None)
- Group is empty or missing.
- **Name filter:** Name missing, or starts with `UI_` / `Ui `, or equals Id, or matches other untranslated patterns.
  - **Exceptions:** `ship_component_groups` (e.g. Hauler Starship Component) and `name_filter_exempt_groups` (e.g. Edible Product, Exclusive Spacecraft, Unlockable Armour, …) bypass the name filter.
- **Junk keywords:** Group or name contains developer placeholders (e.g. `Biggs`, `Basic F`, `Wall Art`, `Planet Tech`, `Base Tech`, `Rooms`).
- Group not in any `CATEGORIZATION_RULES` exact set.

### Adding or moving groups
- Edit `CATEGORIZATION_RULES` in `utils/categorization.py`.
- To move a group from one file to another, remove it from the first file’s `exact` set and add it to the target file’s set (order matters).
- To allow untranslated names for a group, add it to `name_filter_exempt_groups` in `categorize_item()`.

---

## Starship Components (Special Case)

- **Source:** `nms_modularcustomisationproducts.MXML` (427 items).
- **Group** comes from subtitle keys (e.g. `UI_DROPSHIP_PART_SUB` → Hauler Starship Component).
- All ship component groups are in **Others.json** (exact match).
- **Name filter exception:** Ship component groups are in `ship_component_groups` so items are kept even when names look untranslated (`Ui …`).

---

## Parser Guidelines

- Use **game IDs** (e.g. `CASING`, `NANOTUBES`), not synthetic IDs like `prod1`.
- Use `EXMLParser.load_localization()` and `translate(key)` for English names/descriptions.
- Match existing JSON field structure; handle missing translations gracefully.
- Refinery/NutrientProcessor: both from `nms_reality_gcrecipetable.MXML`; split by Cooking flag.

---

## Key Data Mappings

- **Refinery / NutrientProcessor:** same table; split by `Cooking` flag.
- **Products / Substances:** used for name and icon lookups in other parsers.
- **Localization:** built from locale MXMLs in `data/mbin/` (e.g. nms_loc1_english.MXML, nms_update3_english.MXML).

---

## Version Compatibility

- **HGPAKtool:** NMS 5.50+ (Worlds Part II onwards).
- **MBINCompiler:** Version must match game version.
- After a game update: re-extract MBINs, convert to MXML, run `python extract_all.py`. See README “Workflow: New game version” and `.cursor/skills/new-game-version/` if present.
