#!/usr/bin/env python3
"""
NMS Data Extraction - Master Script
Extracts from game files and categorizes into final JSON files
"""
import sys
import os
import time
import re
import argparse
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
from utils.generate_controller_lookup import main as generate_controller_lookup_main
from utils.refresh_report import generate_refresh_report
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
        'Food.json': 'food/',
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
        'Exocraft.json': 'exocraft/',
        'Starships.json': 'starships/',
        'Upgrades.json': 'upgrades/',
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


def dedupe_items_by_id(items: list, *, merge_missing_fields: bool = True) -> tuple[list, int]:
    """
    Remove duplicate item IDs while preserving order.
    Optionally merge missing fields from later entries into the first-seen
    record (disabled for schema-sensitive files).
    """
    if not isinstance(items, list):
        return items, 0

    deduped = []
    first_by_id = {}
    removed = 0

    for item in items:
        if not isinstance(item, dict):
            deduped.append(item)
            continue

        item_id = item.get('Id')
        if not isinstance(item_id, str) or not item_id:
            deduped.append(item)
            continue

        existing = first_by_id.get(item_id)
        if existing is None:
            first_by_id[item_id] = item
            deduped.append(item)
            continue

        if merge_missing_fields:
            # Merge only missing-ish values into the first-seen canonical record.
            for key, value in item.items():
                if key not in existing or existing.get(key) in (None, '', []):
                    existing[key] = value
        removed += 1

    return deduped, removed


def dedupe_all_files_by_id(final_files: dict) -> tuple[int, dict[str, int]]:
    """
    Deduplicate every list-based output file by Id while preserving order.
    Returns total duplicates removed and per-file removal counts.
    """
    total_removed = 0
    removed_by_file: dict[str, int] = {}
    for filename, data in list(final_files.items()):
        if not isinstance(data, list):
            continue
        # Keep first item only; do not merge fields across duplicate IDs because
        # same IDs can represent different schema variants in some outputs.
        deduped, removed = dedupe_items_by_id(data, merge_missing_fields=False)
        if removed:
            final_files[filename] = deduped
            removed_by_file[filename] = removed
            total_removed += removed
    return total_removed, removed_by_file


def _has_stats(item: dict) -> bool:
    """True when an item already carries any stat data."""
    if not isinstance(item, dict):
        return False
    if item.get('StatBonuses'):
        return True
    if item.get('StatLevels'):
        return True
    if item.get('NumStatsMin') is not None and item.get('NumStatsMax') is not None:
        return True
    return False


def _copy_stats_fields(target: dict, source: dict) -> bool:
    """
    Copy stat-related fields from source to target when target is missing them.
    Returns True when at least one field was copied.
    """
    copied = False
    for field in ('StatBonuses', 'StatLevels', 'NumStatsMin', 'NumStatsMax', 'WeightingCurve'):
        src_val = source.get(field)
        if src_val in (None, '', []):
            continue
        tgt_val = target.get(field)
        if tgt_val in (None, '', []):
            target[field] = src_val
            copied = True
    return copied


def enrich_upgrade_stats(final_files: dict, base_data: dict) -> int:
    """
    Backfill stats in Upgrades.json from available sources.

    Priority:
    1) Same ID match from parsed Technology/ProceduralTech data.
    2) Product wrapper DeploysInto target (e.g. U_EXO_SUB3 -> UP_EXSUB3).
    """
    upgrades = final_files.get('Upgrades.json')
    if not isinstance(upgrades, list) or not upgrades:
        return 0

    # Source index from parsers that actually expose stats.
    source_by_id = {}
    for key in ('Technology', 'ProceduralTech'):
        for item in base_data.get(key, []):
            if not isinstance(item, dict):
                continue
            item_id = item.get('Id')
            if isinstance(item_id, str) and item_id and _has_stats(item):
                source_by_id[item_id] = item

    # Also index already-built upgrade items with stats (for DeploysInto linking).
    upgrades_by_id = {}
    for item in upgrades:
        item_id = item.get('Id')
        if isinstance(item_id, str) and item_id:
            upgrades_by_id[item_id] = item

    enriched = 0
    for item in upgrades:
        if not isinstance(item, dict) or _has_stats(item):
            continue

        item_id = item.get('Id')
        if not isinstance(item_id, str) or not item_id:
            continue

        # 1) Direct same-ID source match.
        source = source_by_id.get(item_id)
        if source and _copy_stats_fields(item, source):
            enriched += 1
            continue

        # 2) Product wrapper -> deploy target source match.
        deploy_target = item.get('DeploysInto')
        if isinstance(deploy_target, str) and deploy_target:
            source = source_by_id.get(deploy_target) or upgrades_by_id.get(deploy_target)
            if source and _copy_stats_fields(item, source):
                enriched += 1

    return enriched


def normalize_upgrade_display_names(final_files: dict) -> int:
    """
    For upgrade entries, prefer the specific group label as display name.
    Example: Name "Analysis Visor" + Group "C-Class Analysis Visor Upgrade"
    becomes Name "C-Class Analysis Visor Upgrade".
    """
    upgrades = final_files.get('Upgrades.json')
    if not isinstance(upgrades, list) or not upgrades:
        return 0

    changed = 0
    for item in upgrades:
        if not isinstance(item, dict):
            continue
        group = item.get('Group')
        if not isinstance(group, str) or not group:
            continue
        # Only rewrite true upgrade-style groups.
        if 'upgrade' not in group.lower():
            continue
        if item.get('Name') != group:
            item['Name'] = group
            changed += 1
    return changed


def move_exocraft_upgrades(final_files: dict) -> int:
    """
    Ensure Exocraft.json contains only non-upgrade entries.
    Any exocraft item with upgrade-like group/name is moved to Upgrades.json.
    """
    exocraft = final_files.get('Exocraft.json')
    upgrades = final_files.get('Upgrades.json')
    if not isinstance(exocraft, list) or not isinstance(upgrades, list):
        return 0

    keep = []
    moved = 0
    for item in exocraft:
        if not isinstance(item, dict):
            keep.append(item)
            continue
        name = (item.get('Name') or '')
        group = (item.get('Group') or '')
        if 'upgrade' in name.lower() or 'upgrade' in group.lower():
            upgrades.append(item)
            moved += 1
        else:
            keep.append(item)

    final_files['Exocraft.json'] = keep
    return moved


def _is_placeholder_upgrade_description(text: str) -> bool:
    """Detect procedural fallback text like 'Up Boost3'."""
    if not isinstance(text, str):
        return False
    value = text.strip()
    if not value:
        return False
    return bool(
        re.fullmatch(r'Up [A-Za-z0-9_]+', value)
        or re.fullmatch(r'Ut Cr [A-Za-z0-9_]+', value)
    )


def _build_upgrade_description_from_group(item: dict) -> str:
    """Build a readable fallback description when localization is missing."""
    group = (item.get('Group') or '').strip()
    quality = (item.get('Quality') or '').strip()
    if not group:
        return ''

    # Strip common class prefix/suffix from groups for better sentence flow.
    target = re.sub(r'^[CBSA]-Class\s+', '', group, flags=re.IGNORECASE)
    target = re.sub(r'\s+Upgrade$', '', target, flags=re.IGNORECASE).strip()
    if not target:
        target = group

    strength_by_quality = {
        'Normal': 'moderate',
        'Rare': 'significant',
        'Epic': 'extremely powerful',
        'Legendary': 'supremely powerful',
        'Illegal': 'highly unstable',
    }
    strength = strength_by_quality.get(quality, 'powerful')

    return (
        f"A {strength} upgrade for the {target}. Use [E] to begin upgrade installation process.\n\n"
        "The module is flexible, and exact upgrade statistics are unknown until installation is complete."
    )


def enrich_upgrade_descriptions(final_files: dict) -> int:
    """
    Replace placeholder upgrade descriptions with translated wrapper descriptions
    using DeploysInto links (e.g. U_EXOBOOST3 -> UP_BOOST3).
    """
    upgrades = final_files.get('Upgrades.json')
    if not isinstance(upgrades, list) or not upgrades:
        return 0

    by_id = {}
    wrappers_by_target = {}
    for item in upgrades:
        if not isinstance(item, dict):
            continue
        item_id = item.get('Id')
        if isinstance(item_id, str) and item_id:
            by_id[item_id] = item
        deploy = item.get('DeploysInto')
        if isinstance(deploy, str) and deploy and isinstance(item_id, str):
            wrappers_by_target.setdefault(deploy, []).append(item_id)

    updated = 0
    for target_id, wrapper_ids in wrappers_by_target.items():
        target = by_id.get(target_id)
        if not isinstance(target, dict):
            continue
        if not _is_placeholder_upgrade_description(target.get('Description')):
            continue

        replacement = None
        for wrapper_id in wrapper_ids:
            wrapper = by_id.get(wrapper_id)
            if not isinstance(wrapper, dict):
                continue
            wrapper_desc = wrapper.get('Description')
            if isinstance(wrapper_desc, str) and wrapper_desc.strip() and not _is_placeholder_upgrade_description(wrapper_desc):
                replacement = wrapper_desc
                break

        if replacement:
            target['Description'] = replacement
            updated += 1
            continue

        # If there is no wrapper text to copy, synthesize a readable fallback.
        generated = _build_upgrade_description_from_group(target)
        if generated:
            target['Description'] = generated
            updated += 1

    # Also handle standalone upgrades that have placeholder descriptions but no wrapper.
    for item in upgrades:
        if not isinstance(item, dict):
            continue
        if not _is_placeholder_upgrade_description(item.get('Description')):
            continue
        generated = _build_upgrade_description_from_group(item)
        if generated:
            item['Description'] = generated
            updated += 1

    return updated


def enrich_corvette_metadata(final_files: dict, data_dir: Path) -> int:
    """
    Add Corvette-specific metadata from source product tables without
    inflating every other output JSON.
    """
    corvette_items = final_files.get('Corvette.json')
    if not isinstance(corvette_items, list) or not corvette_items:
        return 0

    from parsers.base_parser import EXMLParser, normalize_game_icon_path

    parser = EXMLParser()
    source_tables = [
        data_dir / 'nms_basepartproducts.MXML',
        data_dir / 'nms_modularcustomisationproducts.MXML',
    ]

    metadata_by_id: dict[str, dict] = {}
    for mxml_path in source_tables:
        if not mxml_path.exists():
            continue
        try:
            root = parser.load_xml(str(mxml_path))
        except Exception:
            continue
        table_prop = root.find('.//Property[@name="Table"]')
        if table_prop is None:
            continue

        for product_elem in table_prop.findall('./Property[@name="Table"]'):
            item_id = parser.get_property_value(product_elem, 'ID', '')
            if not item_id:
                continue

            hero_icon_raw = parser.get_property_value(
                product_elem.find('.//Property[@name="HeroIcon"]'),
                'Filename',
                '',
            )
            hero_icon = normalize_game_icon_path(hero_icon_raw) if hero_icon_raw else ''

            metadata_by_id[item_id] = {
                'HeroIconPath': hero_icon or None,
                'BuildableShipTechID': parser.get_property_value(product_elem, 'BuildableShipTechID', '') or None,
                'GroupID': parser.get_property_value(product_elem, 'GroupID', '') or None,
                'SubstanceCategory': parser.get_nested_enum(product_elem, 'Category', 'SubstanceCategory', '') or None,
                'ProductCategory': parser.get_nested_enum(product_elem, 'Type', 'ProductCategory', '') or None,
                'Level': parser.parse_value(parser.get_property_value(product_elem, 'Level', '0')),
                'ChargeValue': parser.parse_value(parser.get_property_value(product_elem, 'ChargeValue', '0')),
                'DefaultCraftAmount': parser.parse_value(parser.get_property_value(product_elem, 'DefaultCraftAmount', '1')),
                'CraftAmountStepSize': parser.parse_value(parser.get_property_value(product_elem, 'CraftAmountStepSize', '1')),
                'CraftAmountMultiplier': parser.parse_value(parser.get_property_value(product_elem, 'CraftAmountMultiplier', '1')),
                'SpecificChargeOnly': parser.parse_value(parser.get_property_value(product_elem, 'SpecificChargeOnly', 'false')),
                'NormalisedValueOnWorld': parser.parse_value(parser.get_property_value(product_elem, 'NormalisedValueOnWorld', '0')),
                'NormalisedValueOffWorld': parser.parse_value(parser.get_property_value(product_elem, 'NormalisedValueOffWorld', '0')),
                'CorvettePartCategory': parser.get_nested_enum(product_elem, 'CorvettePartCategory', 'CorvettePartCategory', '') or None,
                'CorvetteRewardFrequency': parser.parse_value(parser.get_property_value(product_elem, 'CorvetteRewardFrequency', '0')),
                'IsCraftable': parser.parse_value(parser.get_property_value(product_elem, 'IsCraftable', 'false')),
                'PinObjective': parser.get_property_value(product_elem, 'PinObjective', '') or None,
                'PinObjectiveTip': parser.get_property_value(product_elem, 'PinObjectiveTip', '') or None,
                'PinObjectiveMessage': parser.get_property_value(product_elem, 'PinObjectiveMessage', '') or None,
                'PinObjectiveScannableType': parser.get_nested_enum(
                    product_elem,
                    'PinObjectiveScannableType',
                    'ScanIconType',
                    '',
                ) or None,
                'PinObjectiveEasyToRefine': parser.parse_value(
                    parser.get_property_value(product_elem, 'PinObjectiveEasyToRefine', 'false')
                ),
                'NeverPinnable': parser.parse_value(parser.get_property_value(product_elem, 'NeverPinnable', 'false')),
                'CanSendToOtherPlayers': parser.parse_value(
                    parser.get_property_value(product_elem, 'CanSendToOtherPlayers', 'true')
                ),
            }

    enriched = 0
    for item in corvette_items:
        if not isinstance(item, dict):
            continue
        item_id = item.get('Id')
        if not isinstance(item_id, str):
            continue
        extra = metadata_by_id.get(item_id)
        if not extra:
            continue
        for key, value in extra.items():
            item[key] = value
        enriched += 1

    return enriched


def enrich_corvette_buildable_tech_labels(final_files: dict) -> int:
    """
    Add translated labels for BuildableShipTechID by linking to Upgrades.json IDs.
    """
    corvette_items = final_files.get('Corvette.json')
    upgrades = final_files.get('Upgrades.json')
    if not isinstance(corvette_items, list) or not isinstance(upgrades, list):
        return 0

    upgrades_by_id = {}
    for item in upgrades:
        if not isinstance(item, dict):
            continue
        item_id = item.get('Id')
        if isinstance(item_id, str) and item_id:
            upgrades_by_id[item_id] = item

    enriched = 0
    for item in corvette_items:
        if not isinstance(item, dict):
            continue
        tech_id = item.get('BuildableShipTechID')
        if not isinstance(tech_id, str) or not tech_id:
            continue
        linked = upgrades_by_id.get(tech_id)
        if not isinstance(linked, dict):
            continue

        item['BuildableShipTechName'] = linked.get('Name') or None
        item['BuildableShipTechGroup'] = linked.get('Group') or None
        item['BuildableShipTechDescription'] = linked.get('Description') or None
        enriched += 1

    return enriched


def enrich_exocraft_metadata(final_files: dict, data_dir: Path) -> int:
    """
    Add extended product metadata to Exocraft.json items from source tables.
    Scoped to Exocraft only to avoid bloating all output files.
    """
    exocraft_items = final_files.get('Exocraft.json')
    if not isinstance(exocraft_items, list) or not exocraft_items:
        return 0

    from parsers.base_parser import EXMLParser, normalize_game_icon_path

    parser = EXMLParser()
    source_tables = [
        data_dir / 'nms_reality_gcproducttable.MXML',
        data_dir / 'nms_basepartproducts.MXML',
    ]

    metadata_by_id: dict[str, dict] = {}
    for mxml_path in source_tables:
        if not mxml_path.exists():
            continue
        try:
            root = parser.load_xml(str(mxml_path))
        except Exception:
            continue
        table_prop = root.find('.//Property[@name="Table"]')
        if table_prop is None:
            continue

        for product_elem in table_prop.findall('./Property[@name="Table"]'):
            item_id = parser.get_property_value(product_elem, 'ID', '')
            if not item_id:
                continue

            hero_icon_raw = parser.get_property_value(
                product_elem.find('.//Property[@name="HeroIcon"]'),
                'Filename',
                '',
            )
            hero_icon = normalize_game_icon_path(hero_icon_raw) if hero_icon_raw else ''

            cost_prop = product_elem.find('.//Property[@name="Cost"]')
            price_modifiers = None
            if cost_prop is not None:
                price_modifiers = {
                    'SpaceStationMarkup': parser.parse_value(parser.get_property_value(cost_prop, 'SpaceStationMarkup', '0')),
                    'LowPriceMod': parser.parse_value(parser.get_property_value(cost_prop, 'LowPriceMod', '0')),
                    'HighPriceMod': parser.parse_value(parser.get_property_value(cost_prop, 'HighPriceMod', '0')),
                    'BuyBaseMarkup': parser.parse_value(parser.get_property_value(cost_prop, 'BuyBaseMarkup', '0')),
                    'BuyMarkupMod': parser.parse_value(parser.get_property_value(cost_prop, 'BuyMarkupMod', '0')),
                }

            metadata_by_id[item_id] = {
                'HeroIconPath': hero_icon or None,
                'BuildableShipTechID': parser.get_property_value(product_elem, 'BuildableShipTechID', '') or None,
                'GroupID': parser.get_property_value(product_elem, 'GroupID', '') or None,
                'SubstanceCategory': parser.get_nested_enum(product_elem, 'Category', 'SubstanceCategory', '') or None,
                'ProductCategory': parser.get_nested_enum(product_elem, 'Type', 'ProductCategory', '') or None,
                'Level': parser.parse_value(parser.get_property_value(product_elem, 'Level', '0')),
                'ChargeValue': parser.parse_value(parser.get_property_value(product_elem, 'ChargeValue', '0')),
                'DefaultCraftAmount': parser.parse_value(parser.get_property_value(product_elem, 'DefaultCraftAmount', '1')),
                'CraftAmountStepSize': parser.parse_value(parser.get_property_value(product_elem, 'CraftAmountStepSize', '1')),
                'CraftAmountMultiplier': parser.parse_value(parser.get_property_value(product_elem, 'CraftAmountMultiplier', '1')),
                'SpecificChargeOnly': parser.parse_value(parser.get_property_value(product_elem, 'SpecificChargeOnly', 'false')),
                'NormalisedValueOnWorld': parser.parse_value(parser.get_property_value(product_elem, 'NormalisedValueOnWorld', '0')),
                'NormalisedValueOffWorld': parser.parse_value(parser.get_property_value(product_elem, 'NormalisedValueOffWorld', '0')),
                'EconomyInfluenceMultiplier': parser.parse_value(
                    parser.get_property_value(product_elem, 'EconomyInfluenceMultiplier', '0')
                ),
                'IsCraftable': parser.parse_value(parser.get_property_value(product_elem, 'IsCraftable', 'false')),
                'PinObjective': parser.get_property_value(product_elem, 'PinObjective', '') or None,
                'PinObjectiveTip': parser.get_property_value(product_elem, 'PinObjectiveTip', '') or None,
                'PinObjectiveMessage': parser.get_property_value(product_elem, 'PinObjectiveMessage', '') or None,
                'PinObjectiveScannableType': parser.get_nested_enum(
                    product_elem,
                    'PinObjectiveScannableType',
                    'ScanIconType',
                    '',
                ) or None,
                'PinObjectiveEasyToRefine': parser.parse_value(
                    parser.get_property_value(product_elem, 'PinObjectiveEasyToRefine', 'false')
                ),
                'NeverPinnable': parser.parse_value(parser.get_property_value(product_elem, 'NeverPinnable', 'false')),
                'CanSendToOtherPlayers': parser.parse_value(
                    parser.get_property_value(product_elem, 'CanSendToOtherPlayers', 'true')
                ),
                'IsTechbox': parser.parse_value(parser.get_property_value(product_elem, 'IsTechbox', 'false')),
                'GiveRewardOnSpecialPurchase': parser.get_property_value(
                    product_elem,
                    'GiveRewardOnSpecialPurchase',
                    '',
                ) or None,
                'PriceModifiers': price_modifiers,
            }

    enriched = 0
    for item in exocraft_items:
        if not isinstance(item, dict):
            continue
        item_id = item.get('Id')
        if not isinstance(item_id, str):
            continue
        extra = metadata_by_id.get(item_id)
        if not extra:
            continue
        for key, value in extra.items():
            item[key] = value
        enriched += 1

    return enriched


def main(argv=None):
    parser = argparse.ArgumentParser(description='NMS full extraction pipeline')
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate refresh report and update reports/_latest_snapshot at end of run',
    )
    parser.add_argument(
        '--no-strict',
        action='store_true',
        help='Skip strict smoke checks after extraction',
    )
    args = parser.parse_args(argv)

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

    # Build FE token lookup for prompt replacement (best effort).
    try:
        print("Building controller lookup...")
        # Pass explicit argv to avoid consuming extract_all.py CLI flags.
        lookup_exit = generate_controller_lookup_main([])
        if lookup_exit != 0:
            print("  [WARN] Could not refresh controller lookup (continuing).")
    except Exception as e:
        print(f"  [WARN] Controller lookup generation failed: {e}")

    # Force parsers to load the fresh localization (clear cache)
    from parsers.base_parser import EXMLParser
    EXMLParser._localization = None
    EXMLParser._controller_lookup = None
    EXMLParser.clear_xml_cache()

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

    # Step 2: Categorize into final files
    print("\n" + "=" * 70)
    print("STEP 2: Categorizing into output files...")
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
        'Food.json': [],
        'Corvette.json': [],
        'Curiosities.json': [],
        'Exocraft.json': [],
        'Starships.json': [],
        'Others.json': [],
        'Products.json': [],
        'Technology.json': [],
        'TechnologyModule.json': [],
        'Upgrades.json': [],
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

    # Enrich Upgrades.json with stats from linked technology entries.
    enriched = enrich_upgrade_stats(final_files, base_data)
    if enriched:
        print(f"  [ENRICH] Upgrades.json: backfilled stats for {enriched} items")

    moved = move_exocraft_upgrades(final_files)
    if moved:
        print(f"  [NORMALIZE] Moved {moved} upgrade items from Exocraft.json to Upgrades.json")

    renamed = normalize_upgrade_display_names(final_files)
    if renamed:
        print(f"  [NORMALIZE] Upgrades.json: set Name from Group for {renamed} upgrade items")

    desc_enriched = enrich_upgrade_descriptions(final_files)
    if desc_enriched:
        print(f"  [ENRICH] Upgrades.json: replaced {desc_enriched} placeholder descriptions")

    corvette_enriched = enrich_corvette_metadata(final_files, data_dir)
    if corvette_enriched:
        print(f"  [ENRICH] Corvette.json: added extended metadata to {corvette_enriched} items")

    corvette_tech_labels = enrich_corvette_buildable_tech_labels(final_files)
    if corvette_tech_labels:
        print(f"  [ENRICH] Corvette.json: linked buildable tech labels for {corvette_tech_labels} items")

    exocraft_enriched = enrich_exocraft_metadata(final_files, data_dir)
    if exocraft_enriched:
        print(f"  [ENRICH] Exocraft.json: added extended metadata to {exocraft_enriched} items")

    # Food gets contributions from both Products and Cooking parsers.
    # Use merge dedupe here to retain richer records.
    food = final_files.get('Food.json')
    if isinstance(food, list):
        deduped_food, removed_food_dupes = dedupe_items_by_id(food, merge_missing_fields=True)
        if removed_food_dupes:
            final_files['Food.json'] = deduped_food
            print(f"  [NORMALIZE] Food.json: removed {removed_food_dupes} duplicate IDs")

    # Normalize all outputs by de-duplicating duplicate Id entries.
    total_dupes_removed, removed_by_file = dedupe_all_files_by_id(final_files)
    if total_dupes_removed:
        for filename in sorted(removed_by_file):
            print(f"  [NORMALIZE] {filename}: removed {removed_by_file[filename]} duplicate IDs")
        print(f"  [NORMALIZE] Removed {total_dupes_removed} duplicate IDs total")

    # Step 3: Save all output files
    print("STEP 3: Saving final files...")
    print("-" * 70 + "\n")

    results = []
    for filename, data in sorted(final_files.items()):
        # Always write each target file so stale data from prior runs cannot linger.
        file_size = save_json(data if data is not None else [], filename)
        item_count = len(data) if isinstance(data, list) else 0
        results.append((filename, item_count, file_size))
        print(f"  {filename:30} {item_count:4} items  {file_size:8.1f} KB")

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

    # Step 4: Strict validation (default).
    if args.no_strict:
        print("[INFO] Strict smoke checks skipped (--no-strict).")
    else:
        print("STEP 4: Running strict smoke checks...")
        print("-" * 70)
        from utils.smoke_check import run_smoke_check
        smoke_exit = run_smoke_check(repo_root, fail_on_duplicate_ids=True)
        if smoke_exit != 0:
            print("[ERROR] Strict smoke checks failed.")
            return 1
        print("[OK] Strict smoke checks passed.\n")

    # Step 5: Optionally generate refresh report + update latest snapshot.
    if args.report:
        try:
            report = generate_refresh_report(Path(__file__).parent)
            report_rel = report["report_markdown"].relative_to(Path(__file__).parent)
            print(f"[OK] Report: {report_rel}")
            print(
                f"[OK] Report totals - added: {report['totals']['added']}, "
                f"removed: {report['totals']['removed']}, changed: {report['totals']['changed']}"
            )
        except Exception as e:
            print(f"[WARN] Report generation failed: {e}")
    else:
        print("[INFO] Report generation skipped (use --report to enable).")

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
