#!/usr/bin/env python3
"""
NMS Data Extraction - Master Script
Extracts from game files and categorizes into 13 required JSON files
"""
import sys
import os
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from parsers.refinery import parse_refinery, parse_nutrient_processor
from parsers.products import parse_products
from parsers.rawmaterials import parse_rawmaterials
from parsers.fish import parse_fish
from parsers.cooking import parse_cooking
from parsers.trade import parse_trade
from parsers.technology import parse_technology
from parsers.buildings import parse_buildings
from parsers.ship_components import parse_ship_components
from parsers.base_parts import parse_base_parts
from parsers.procedural_tech import parse_procedural_tech
from utils.categorization import categorize_item
from utils.parse_localization import build_localization_json
import json


def save_json(data, filename):
    """Save data to JSON file"""
    output_path = Path(__file__).parent / 'data' / 'json' / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent='\t', ensure_ascii=False)
    file_size = output_path.stat().st_size / 1024
    return file_size


def apply_slugs(final_files: dict) -> None:
    """Add Slug field to items based on output file."""
    slugs = {
        'RawMaterials.json': 'raw/',
        'Products.json': 'products/',
        'Cooking.json': 'cooking/',
        'Curiosities.json': 'curiosities/',
        'Corvette.json': 'corvette/',
        'Fish.json': 'fish/',
        'ConstructedTechnology.json': 'technology/',
        'Technology.json': 'technology/',
        'TechnologyModule.json': 'technology/',
        'Others.json': 'other/',
        'Refinery.json': 'refinery/',
        'NutrientProcessor.json': 'nutrient-processor/',
        'Buildings.json': 'buildings/',
        'Trade.json': 'other/',
    }

    for filename, data in final_files.items():
        prefix = slugs.get(filename)
        if not prefix or not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            item_id = item.get('Id') or item.get('id')
            if not item_id:
                continue
            item['Slug'] = f"{prefix}{item_id}"


def filter_missing_icons(data):
    """Remove items with empty IconPath when present."""
    if not isinstance(data, list):
        return data, 0
    filtered = []
    removed = 0
    for item in data:
        if isinstance(item, dict) and 'IconPath' in item and not item.get('IconPath'):
            removed += 1
            continue
        filtered.append(item)
    return filtered, removed


def main():
    start_time = time.time()

    print("\n" + "=" * 70)
    print("NMS DATA EXTRACTION - FULL PIPELINE")
    print("=" * 70 + "\n")

    repo_root = Path(__file__).parent
    data_dir = repo_root / 'data' / 'mbin'

    # Step 0: Rebuild localization from locale MXML files
    print("STEP 0: Rebuilding localization...")
    print("-" * 70)
    build_localization_json(repo_root)
    # Force parsers to load the fresh localization (clear cache)
    from parsers.base_parser import EXMLParser
    EXMLParser._localization = None

    # Step 1: Extract base data from MXML files
    print("STEP 1: Extracting base data from game files...")
    print("-" * 70 + "\n")

    base_data = {}
    parsers = [
        ('Refinery', 'nms_reality_gcrecipetable.MXML', lambda p: parse_refinery(p, only_refinery=True)),
        ('NutrientProcessor', 'nms_reality_gcrecipetable.MXML', parse_nutrient_processor),
        ('Products', 'nms_reality_gcproducttable.MXML', parse_products),
        ('RawMaterials', 'nms_reality_gcsubstancetable.MXML', parse_rawmaterials),
        ('Technology', 'nms_reality_gctechnologytable.MXML', parse_technology),
        ('Buildings', 'basebuildingobjectstable.MXML', parse_buildings),
        ('Cooking', 'consumableitemtable.MXML', parse_cooking),
        ('Fish', 'fishdatatable.MXML', parse_fish),
        ('Trade', 'nms_reality_gcproducttable.MXML', parse_trade),
        ('ShipComponents', 'nms_modularcustomisationproducts.MXML', parse_ship_components),
        ('BaseParts', 'nms_basepartproducts.MXML', parse_base_parts),
        ('ProceduralTech', 'nms_reality_gcproceduraltechnologytable.MXML', parse_procedural_tech),
    ]

    for i, (name, mxml_file, parser_func) in enumerate(parsers, 1):
        mxml_path = data_dir / mxml_file

        print(f"[{i}/{len(parsers)}] Extracting {name}...")

        if not mxml_path.exists():
            print(f"  [SKIP] {mxml_file} not found\n")
            continue

        try:
            data = parser_func(str(mxml_path))
            base_data[name] = data
            print(f"  [OK] {len(data)} items extracted\n")
        except Exception as e:
            print(f"  [ERROR] Failed: {e}\n")
            import traceback
            traceback.print_exc()

    # Step 2: Categorize into 13 final files
    print("\n" + "=" * 70)
    print("STEP 2: Categorizing into 13 required files...")
    print("-" * 70 + "\n")

    # Files that don't need categorization (keep as-is)
    final_files = {
        'Refinery.json': base_data.get('Refinery', []),
        'NutrientProcessor.json': base_data.get('NutrientProcessor', []),
        'Fish.json': base_data.get('Fish', []),
        'Trade.json': base_data.get('Trade', []),
        'RawMaterials.json': base_data.get('RawMaterials', []),
    }

    # Initialize empty lists for categorized files
    categorized = {
        'Buildings.json': [],
        'ConstructedTechnology.json': [],
        'Cooking.json': [],
        'Corvette.json': [],
        'Curiosities.json': [],
        'Others.json': [],
        'Products.json': [],
        'Technology.json': [],
        'TechnologyModule.json': [],
    }

    # Categorize items from base extractions
    items_to_categorize = []
    items_to_categorize.extend(base_data.get('Products', []))
    items_to_categorize.extend(base_data.get('Technology', []))
    items_to_categorize.extend(base_data.get('Buildings', []))
    items_to_categorize.extend(base_data.get('Cooking', []))
    items_to_categorize.extend(base_data.get('ShipComponents', []))
    items_to_categorize.extend(base_data.get('BaseParts', []))
    items_to_categorize.extend(base_data.get('ProceduralTech', []))

    total_categorized = 0
    total_skipped = 0
    uncategorized_items = []  # Track items that don't match any rules

    for item in items_to_categorize:
        target_file = categorize_item(item)

        if target_file is None:
            total_skipped += 1
            uncategorized_items.append(item)
            continue

        if target_file in categorized:
            categorized[target_file].append(item)
            total_categorized += 1

    print(f"Categorized {total_categorized} items")
    print(f"Skipped {total_skipped} items (saved to none.json for review)\n")

    # Save uncategorized items to none.json for review
    if uncategorized_items:
        uncategorized_items, removed_uncategorized = filter_missing_icons(uncategorized_items)
        if removed_uncategorized:
            print(f"  [FILTER] Removed {removed_uncategorized} items with empty IconPath from none.json")
        uncategorized_file = Path(__file__).parent / 'data' / 'json' / 'none.json'
        with open(uncategorized_file, 'w', encoding='utf-8') as f:
            json.dump(uncategorized_items, f, indent=2, ensure_ascii=False)
        print(f"  [REVIEW] Saved {len(uncategorized_items)} uncategorized items to none.json\n")

    # Merge categorized files with kept files
    final_files.update(categorized)

    # Filter out items that lack icon paths (only when IconPath is present)
    total_removed = 0
    for filename, data in list(final_files.items()):
        filtered, removed = filter_missing_icons(data)
        if removed:
            print(f"  [FILTER] {filename}: removed {removed} items with empty IconPath")
            final_files[filename] = filtered
            total_removed += removed
    if total_removed:
        print(f"  [FILTER] Removed {total_removed} items with empty IconPath total\n")

    # Add slug field based on output file
    apply_slugs(final_files)

    # Step 3: Save all 13 files
    print("STEP 3: Saving final files...")
    print("-" * 70 + "\n")

    results = []
    for filename, data in sorted(final_files.items()):
        if data:  # Only save if we have data
            file_size = save_json(data, filename)
            results.append((filename, len(data), file_size))
            print(f"  {filename:30} {len(data):4} items  {file_size:8.1f} KB")

    # Print summary
    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE!")
    print("=" * 70)
    print(f"\nGenerated {len(results)} files in {elapsed:.1f} seconds:\n")

    total_items = 0
    total_size = 0
    for filename, item_count, file_size in results:
        total_items += item_count
        total_size += file_size

    print(f"  TOTAL: {total_items} items  {total_size:.1f} KB")
    print("\n" + "=" * 70)
    print(f"Output location: {Path(__file__).parent / 'data' / 'json'}")
    print("=" * 70 + "\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
