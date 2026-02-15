#!/usr/bin/env python3
r"""
Single entrypoint for all extraction workflows.

Examples:
  # Parse existing data/mbin/*.MXML into data/json
  python extract.py

  # Full refresh from game files, then parse JSON
  python extract.py --pcbanks "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"

  # Extract images only
  python extract.py --images --extracted "C:\path\to\EXTRACTED"

  # Extract images directly from game files
  python extract.py --images --pcbanks "X:\...\PCBANKS"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from parsers.base_parts import parse_base_parts
from parsers.buildings import parse_buildings
from parsers.cooking import parse_cooking
from parsers.fish import parse_fish
from parsers.procedural_tech import parse_procedural_tech
from parsers.products import parse_products
from parsers.rawmaterials import parse_rawmaterials
from parsers.refinery import parse_refinery, parse_nutrient_processor
from parsers.ship_components import parse_ship_components
from parsers.technology import parse_technology
from parsers.trade import parse_trade
from utils.categorization import categorize_item
from utils.clean import clean_data
from utils.generate_controller_lookup import main as generate_controller_lookup_main
from utils.images import extract_icons
from utils.localization import build_localization_json
from utils.mbin import consolidate_mbin
from utils.report import generate_refresh_report
from utils.smoke import run_smoke_check

REPO_ROOT = Path(__file__).resolve().parent
DATA = REPO_ROOT / "data"
EXTRACTED = DATA / "EXTRACTED"
DEFAULT_PCBANKS = r"X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"

MBIN_FILTERS = [
    "*REALITY/TABLES/nms_reality_gcproducttable.mbin",
    "*REALITY/TABLES/consumableitemtable.mbin",
    "*REALITY/TABLES/nms_reality_gcrecipetable.mbin",
    "*REALITY/TABLES/nms_reality_gctechnologytable.mbin",
    "*REALITY/TABLES/basebuildingobjectstable.mbin",
    "*REALITY/TABLES/nms_reality_gcsubstancetable.mbin",
    "*REALITY/TABLES/fishdatatable.mbin",
    "*REALITY/TABLES/nms_modularcustomisationproducts.mbin",
    "*REALITY/TABLES/nms_basepartproducts.mbin",
    "*REALITY/TABLES/nms_reality_gcproceduraltechnologytable.mbin",
    "*REALITY/TABLES/rewardtable.mbin",
    "*LANGUAGE/nms_loc1_english.mbin",
    "*LANGUAGE/nms_loc4_english.mbin",
    "*LANGUAGE/nms_loc5_english.mbin",
    "*LANGUAGE/nms_loc6_english.mbin",
    "*LANGUAGE/nms_loc7_english.mbin",
    "*LANGUAGE/nms_loc8_english.mbin",
    "*LANGUAGE/nms_loc9_english.mbin",
    "*LANGUAGE/nms_update3_english.mbin",
]

EXPECTED_MXML_AFTER_REFRESH = [
    "nms_reality_gcproducttable.MXML",
    "consumableitemtable.MXML",
    "nms_reality_gcrecipetable.MXML",
    "nms_reality_gctechnologytable.MXML",
    "basebuildingobjectstable.MXML",
    "nms_reality_gcsubstancetable.MXML",
    "fishdatatable.MXML",
    "nms_modularcustomisationproducts.MXML",
    "nms_basepartproducts.MXML",
    "nms_reality_gcproceduraltechnologytable.MXML",
    "rewardtable.MXML",
    "nms_loc1_english.MXML",
    "nms_loc4_english.MXML",
    "nms_loc5_english.MXML",
    "nms_loc6_english.MXML",
    "nms_loc7_english.MXML",
    "nms_loc8_english.MXML",
    "nms_loc9_english.MXML",
    "nms_update3_english.MXML",
]


def run(cmd: list[str], **kwargs) -> None:
    subprocess.run(cmd, check=True, cwd=REPO_ROOT, **kwargs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified NMS extraction command")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=f"Run full refresh prep using default PCBANKS path ({DEFAULT_PCBANKS}).",
    )
    parser.add_argument("--pcbanks", default="", help="Path to game PCBANKS. Enables full refresh prep.")
    parser.add_argument("--report", action="store_true", help="Generate refresh report.")
    parser.add_argument("--no-strict", action="store_true", help="Skip strict smoke checks after extraction.")
    parser.add_argument("--images", action="store_true", help="Run only image extraction (skip JSON extraction).")
    parser.add_argument("--extracted", default="", help="Use an existing EXTRACTED folder for image extraction.")
    parser.add_argument("--keep-dds", action="store_true", help="Keep .dds files when PNGs are produced.")
    parser.add_argument("--no-cleanup", action="store_true", help="Do not delete data/EXTRACTED or data/metadata after unpacking textures.")
    return parser.parse_args()


def resolve_game_path(explicit_path: str) -> str:
    if explicit_path.strip():
        return explicit_path.strip()
    env_path = os.environ.get("NMS_PCBANKS", "").strip()
    if env_path:
        return env_path
    raise SystemExit('Game path required. Pass --pcbanks "X:\\...\\PCBANKS" or set NMS_PCBANKS.')


def _load_hgpaktool_api():
    try:
        from hgpaktool.api import HGPAKFile, InvalidFileException
    except ModuleNotFoundError as e:
        raise SystemExit(
            "hgpaktool is required only for --refresh/--pcbanks/--images unpack operations. "
            "Install with: python3 -m pip install -r requirements.txt"
        ) from e
    return HGPAKFile, InvalidFileException


def extract_mbins_with_hgpaktool(pcbanks: str, output_dir: Path, filters: list[str]) -> int:
    HGPAKFile, InvalidFileException = _load_hgpaktool_api()
    output_dir.mkdir(parents=True, exist_ok=True)
    file_count = 0
    for fname in os.listdir(pcbanks):
        if not fname.lower().endswith(".pak"):
            continue
        pak_path = os.path.join(pcbanks, fname)
        try:
            print(f"  Reading {fname}...")
            with HGPAKFile(pak_path) as pak:
                file_count += pak.unpack(str(output_dir), filters, upper=False, write_manifest=False)
        except InvalidFileException:
            continue
        except Exception as e:
            print(f"  [WARN] Failed to extract from {fname}: {e}")
            continue
    return file_count


def run_full_refresh_prep(pcbanks_arg: str) -> None:
    pcbanks = resolve_game_path(pcbanks_arg)
    if not Path(pcbanks).exists():
        raise SystemExit(f"Game path does not exist: {pcbanks}")

    print("\n--- Refresh Prep 1/3: Clean data ---")
    clean_data(REPO_ROOT)

    print("\n--- Refresh Prep 2/3: Extract MBINs ---")
    file_count = extract_mbins_with_hgpaktool(pcbanks, DATA, MBIN_FILTERS)
    print(f"  Extracted {file_count} files from PCBANKS")

    print("\n--- Refresh Prep 2b: Consolidate MBINs ---")
    consolidate_mbin(REPO_ROOT)

    print("\n--- Refresh Prep 3/3: Convert MBIN -> MXML ---")
    mbin_dir = REPO_ROOT / "data" / "mbin"
    compiler = REPO_ROOT / "tools" / "MBINCompiler.exe"
    if not compiler.exists():
        raise SystemExit(f"MBINCompiler not found: {compiler}")

    for mbin in sorted(mbin_dir.glob("*.mbin")):
        run([str(compiler), str(mbin)])

    missing = [name for name in EXPECTED_MXML_AFTER_REFRESH if not (mbin_dir / name).exists()]
    if missing:
        print("[ERROR] Missing expected MXML outputs after conversion:")
        for name in missing:
            print(f"  - {name}")
        raise SystemExit(1)


def normalize_to_extracted(extracted_root: Path) -> None:
    src_dir = extracted_root / "TEXTURES" if (extracted_root / "TEXTURES").exists() else extracted_root / "textures"
    if not src_dir.exists():
        print("[WARN] No TEXTURES or textures folder found in EXTRACTED. Skipping normalize.")
        return
    dest_textures = extracted_root / "textures"
    if src_dir.resolve() == dest_textures.resolve():
        return
    if dest_textures.exists():
        shutil.rmtree(dest_textures, ignore_errors=True)
    print("[INFO] Normalizing to EXTRACTED/textures/ (lowercase paths)...")
    for src_file in src_dir.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        dest_file = dest_textures / Path(*[p.lower() for p in rel.parts])
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
    if src_dir.exists() and src_dir.resolve() != dest_textures.resolve():
        shutil.rmtree(src_dir, ignore_errors=True)


def unpack_all_game_files_to_extracted(pcbanks_arg: str, extracted_root: Path) -> None:
    HGPAKFile, InvalidFileException = _load_hgpaktool_api()
    pcbanks = resolve_game_path(pcbanks_arg)
    if not Path(pcbanks).exists():
        raise SystemExit(f"Game path does not exist: {pcbanks}")
    extracted_root.mkdir(parents=True, exist_ok=True)
    print("[INFO] Unpacking game files to EXTRACTED (no filter; this may take a while)...")
    file_count = 0
    pak_count = 0
    for fname in os.listdir(pcbanks):
        if not fname.lower().endswith(".pak"):
            continue
        pak_path = os.path.join(pcbanks, fname)
        try:
            print(f"  Reading {fname}...")
            with HGPAKFile(pak_path) as pak:
                file_count += pak.unpack(str(extracted_root), None, upper=False, write_manifest=False)
            pak_count += 1
        except InvalidFileException:
            continue
        except Exception as e:
            print(f"  [WARN] Failed to extract from {fname}: {e}")
            continue
    print(f"  Unpacked {file_count} files from {pak_count} .pak files")


def save_json(data, filename: str) -> float:
    output_path = REPO_ROOT / "data" / "json" / filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent="\t", ensure_ascii=False)
    return output_path.stat().st_size / 1024


def apply_slugs(final_files: dict) -> None:
    slugs = {
        'RawMaterials.json': 'raw/', 'Products.json': 'products/', 'Food.json': 'food/',
        'Curiosities.json': 'curiosities/', 'Corvette.json': 'corvette/', 'Fish.json': 'fish/',
        'ConstructedTechnology.json': 'technology/', 'Technology.json': 'technology/',
        'TechnologyModule.json': 'technology/', 'Others.json': 'other/', 'Refinery.json': 'refinery/',
        'NutrientProcessor.json': 'nutrient-processor/', 'Buildings.json': 'buildings/',
        'Trade.json': 'other/', 'Exocraft.json': 'exocraft/', 'Starships.json': 'starships/',
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
            if item_id:
                item['Slug'] = f"{prefix}{item_id}"


def filter_missing_icons(data):
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
            for key, value in item.items():
                if key not in existing or existing.get(key) in (None, '', []):
                    existing[key] = value
        removed += 1
    return deduped, removed


def dedupe_all_files_by_id(final_files: dict) -> tuple[int, dict[str, int]]:
    total_removed = 0
    removed_by_file: dict[str, int] = {}
    for filename, data in list(final_files.items()):
        if not isinstance(data, list):
            continue
        deduped, removed = dedupe_items_by_id(data, merge_missing_fields=False)
        if removed:
            final_files[filename] = deduped
            removed_by_file[filename] = removed
            total_removed += removed
    return total_removed, removed_by_file


def dedupe_ids_across_files(final_files: dict) -> tuple[int, dict[str, int]]:
    """
    Enforce globally unique Id values across all output files.
    Keep the first seen occurrence according to final_files insertion order.
    """
    total_removed = 0
    removed_by_file: dict[str, int] = {}
    owner_by_id: dict[str, str] = {}
    for filename, data in list(final_files.items()):
        if not isinstance(data, list):
            continue
        keep = []
        removed = 0
        for item in data:
            if not isinstance(item, dict):
                keep.append(item)
                continue
            item_id = item.get('Id')
            if not isinstance(item_id, str) or not item_id:
                keep.append(item)
                continue
            owner = owner_by_id.get(item_id)
            if owner is None:
                owner_by_id[item_id] = filename
                keep.append(item)
            else:
                removed += 1
                total_removed += 1
        if removed:
            final_files[filename] = keep
            removed_by_file[filename] = removed
    return total_removed, removed_by_file


def _has_stats(item: dict) -> bool:
    return bool(
        isinstance(item, dict) and (
            item.get('StatBonuses') or item.get('StatLevels')
            or (item.get('NumStatsMin') is not None and item.get('NumStatsMax') is not None)
        )
    )


def _copy_stats_fields(target: dict, source: dict) -> bool:
    copied = False
    for field in ('StatBonuses', 'StatLevels', 'NumStatsMin', 'NumStatsMax', 'WeightingCurve'):
        src_val = source.get(field)
        if src_val in (None, '', []):
            continue
        if target.get(field) in (None, '', []):
            target[field] = src_val
            copied = True
    return copied


def enrich_upgrade_stats(final_files: dict, base_data: dict) -> int:
    upgrades = final_files.get('Upgrades.json')
    if not isinstance(upgrades, list) or not upgrades:
        return 0
    source_by_id = {}
    for key in ('Technology', 'ProceduralTech'):
        for item in base_data.get(key, []):
            if not isinstance(item, dict):
                continue
            item_id = item.get('Id')
            if isinstance(item_id, str) and item_id and _has_stats(item):
                source_by_id[item_id] = item

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
        source = source_by_id.get(item_id)
        if source and _copy_stats_fields(item, source):
            enriched += 1
            continue
        deploy_target = item.get('DeploysInto')
        if isinstance(deploy_target, str) and deploy_target:
            source = source_by_id.get(deploy_target) or upgrades_by_id.get(deploy_target)
            if source and _copy_stats_fields(item, source):
                enriched += 1
    return enriched


def normalize_upgrade_display_names(final_files: dict) -> int:
    upgrades = final_files.get('Upgrades.json')
    if not isinstance(upgrades, list) or not upgrades:
        return 0
    changed = 0
    for item in upgrades:
        if not isinstance(item, dict):
            continue
        group = item.get('Group')
        if not isinstance(group, str) or not group or 'upgrade' not in group.lower():
            continue
        if item.get('Name') != group:
            item['Name'] = group
            changed += 1
    return changed


def move_exocraft_upgrades(final_files: dict) -> int:
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
    if not isinstance(text, str):
        return False
    value = text.strip()
    return bool(value and (
        re.fullmatch(r'Up [A-Za-z0-9_]+', value) or re.fullmatch(r'Ut Cr [A-Za-z0-9_]+', value)
    ))


def _build_upgrade_description_from_group(item: dict) -> str:
    group = (item.get('Group') or '').strip()
    quality = (item.get('Quality') or '').strip()
    if not group:
        return ''
    target = re.sub(r'^[CBSA]-Class\s+', '', group, flags=re.IGNORECASE)
    target = re.sub(r'\s+Upgrade$', '', target, flags=re.IGNORECASE).strip() or group
    strength_by_quality = {
        'Normal': 'moderate', 'Rare': 'significant', 'Epic': 'extremely powerful',
        'Legendary': 'supremely powerful', 'Illegal': 'highly unstable',
    }
    strength = strength_by_quality.get(quality, 'powerful')
    return (
        f"A {strength} upgrade for the {target}. Use [E] to begin upgrade installation process.\n\n"
        "The module is flexible, and exact upgrade statistics are unknown until installation is complete."
    )


def enrich_upgrade_descriptions(final_files: dict) -> int:
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
        if not isinstance(target, dict) or not _is_placeholder_upgrade_description(target.get('Description')):
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
        generated = _build_upgrade_description_from_group(target)
        if generated:
            target['Description'] = generated
            updated += 1

    for item in upgrades:
        if not isinstance(item, dict) or not _is_placeholder_upgrade_description(item.get('Description')):
            continue
        generated = _build_upgrade_description_from_group(item)
        if generated:
            item['Description'] = generated
            updated += 1
    return updated


def enrich_corvette_metadata(final_files: dict, data_dir: Path) -> int:
    corvette_items = final_files.get('Corvette.json')
    if not isinstance(corvette_items, list) or not corvette_items:
        return 0
    from parsers.base_parser import EXMLParser, normalize_game_icon_path
    parser = EXMLParser()
    source_tables = [data_dir / 'nms_basepartproducts.MXML', data_dir / 'nms_modularcustomisationproducts.MXML']
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
            hero_icon_raw = parser.get_property_value(product_elem.find('.//Property[@name="HeroIcon"]'), 'Filename', '')
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
                'PinObjectiveScannableType': parser.get_nested_enum(product_elem, 'PinObjectiveScannableType', 'ScanIconType', '') or None,
                'PinObjectiveEasyToRefine': parser.parse_value(parser.get_property_value(product_elem, 'PinObjectiveEasyToRefine', 'false')),
                'NeverPinnable': parser.parse_value(parser.get_property_value(product_elem, 'NeverPinnable', 'false')),
                'CanSendToOtherPlayers': parser.parse_value(parser.get_property_value(product_elem, 'CanSendToOtherPlayers', 'true')),
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
        item.update(extra)
        enriched += 1
    return enriched


def enrich_corvette_buildable_tech_labels(final_files: dict) -> int:
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
    exocraft_items = final_files.get('Exocraft.json')
    if not isinstance(exocraft_items, list) or not exocraft_items:
        return 0
    from parsers.base_parser import EXMLParser, normalize_game_icon_path
    parser = EXMLParser()
    source_tables = [data_dir / 'nms_reality_gcproducttable.MXML', data_dir / 'nms_basepartproducts.MXML']
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
            hero_icon_raw = parser.get_property_value(product_elem.find('.//Property[@name="HeroIcon"]'), 'Filename', '')
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
                'EconomyInfluenceMultiplier': parser.parse_value(parser.get_property_value(product_elem, 'EconomyInfluenceMultiplier', '0')),
                'IsCraftable': parser.parse_value(parser.get_property_value(product_elem, 'IsCraftable', 'false')),
                'PinObjective': parser.get_property_value(product_elem, 'PinObjective', '') or None,
                'PinObjectiveTip': parser.get_property_value(product_elem, 'PinObjectiveTip', '') or None,
                'PinObjectiveMessage': parser.get_property_value(product_elem, 'PinObjectiveMessage', '') or None,
                'PinObjectiveScannableType': parser.get_nested_enum(product_elem, 'PinObjectiveScannableType', 'ScanIconType', '') or None,
                'PinObjectiveEasyToRefine': parser.parse_value(parser.get_property_value(product_elem, 'PinObjectiveEasyToRefine', 'false')),
                'NeverPinnable': parser.parse_value(parser.get_property_value(product_elem, 'NeverPinnable', 'false')),
                'CanSendToOtherPlayers': parser.parse_value(parser.get_property_value(product_elem, 'CanSendToOtherPlayers', 'true')),
                'IsTechbox': parser.parse_value(parser.get_property_value(product_elem, 'IsTechbox', 'false')),
                'GiveRewardOnSpecialPurchase': parser.get_property_value(product_elem, 'GiveRewardOnSpecialPurchase', '') or None,
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
        item.update(extra)
        enriched += 1
    return enriched


def run_json_extraction(*, report: bool, no_strict: bool) -> int:
    start_time = time.time()
    print("\n" + "=" * 70)
    print("NMS DATA EXTRACTION - FULL PIPELINE")
    print("=" * 70 + "\n")

    data_dir = REPO_ROOT / 'data' / 'mbin'

    print("STEP 0: Rebuilding localization...")
    print("-" * 70)
    build_localization_json(REPO_ROOT)

    try:
        print("Building controller lookup...")
        lookup_exit = generate_controller_lookup_main([])
        if lookup_exit != 0:
            print("  [WARN] Could not refresh controller lookup (continuing).")
    except Exception as e:
        print(f"  [WARN] Controller lookup generation failed: {e}")

    from parsers.base_parser import EXMLParser
    EXMLParser._localization = None
    EXMLParser._controller_lookup = None
    EXMLParser.clear_xml_cache()

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

    print("\n" + "=" * 70)
    print("STEP 2: Categorizing into output files...")
    print("-" * 70 + "\n")

    final_files = {
        'Refinery.json': base_data.get('Refinery', []),
        'NutrientProcessor.json': base_data.get('NutrientProcessor', []),
        'Fish.json': base_data.get('Fish', []),
        'Trade.json': base_data.get('Trade', []),
        'RawMaterials.json': base_data.get('RawMaterials', []),
    }
    categorized = {
        'Buildings.json': [], 'ConstructedTechnology.json': [], 'Food.json': [],
        'Corvette.json': [], 'Curiosities.json': [], 'Exocraft.json': [],
        'Starships.json': [], 'Others.json': [], 'Products.json': [],
        'Technology.json': [], 'TechnologyModule.json': [], 'Upgrades.json': [],
    }

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
    uncategorized_items = []
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

    uncategorized_items, removed_uncategorized = filter_missing_icons(uncategorized_items)
    if removed_uncategorized:
        print(f"  [FILTER] Removed {removed_uncategorized} items with empty IconPath from none.json")
    uncategorized_file = REPO_ROOT / 'data' / 'json' / 'none.json'
    with open(uncategorized_file, 'w', encoding='utf-8') as f:
        json.dump(uncategorized_items, f, indent=2, ensure_ascii=False)
    print(f"  [REVIEW] Saved {len(uncategorized_items)} uncategorized items to none.json\n")

    final_files.update(categorized)
    total_removed = 0
    for filename, data in list(final_files.items()):
        filtered, removed = filter_missing_icons(data)
        if removed:
            print(f"  [FILTER] {filename}: removed {removed} items with empty IconPath")
            final_files[filename] = filtered
            total_removed += removed
    if total_removed:
        print(f"  [FILTER] Removed {total_removed} items with empty IconPath total\n")

    apply_slugs(final_files)

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

    food = final_files.get('Food.json')
    if isinstance(food, list):
        deduped_food, removed_food_dupes = dedupe_items_by_id(food, merge_missing_fields=True)
        if removed_food_dupes:
            final_files['Food.json'] = deduped_food
            print(f"  [NORMALIZE] Food.json: removed {removed_food_dupes} duplicate IDs")

    total_dupes_removed, removed_by_file = dedupe_all_files_by_id(final_files)
    if total_dupes_removed:
        for filename in sorted(removed_by_file):
            print(f"  [NORMALIZE] {filename}: removed {removed_by_file[filename]} duplicate IDs")
        print(f"  [NORMALIZE] Removed {total_dupes_removed} duplicate IDs total")

    total_cross_dupes_removed, cross_removed_by_file = dedupe_ids_across_files(final_files)
    if total_cross_dupes_removed:
        for filename in sorted(cross_removed_by_file):
            print(f"  [NORMALIZE] {filename}: removed {cross_removed_by_file[filename]} cross-file duplicate IDs")
        print(f"  [NORMALIZE] Removed {total_cross_dupes_removed} cross-file duplicate IDs total")

    print("STEP 3: Saving final files...")
    print("-" * 70 + "\n")
    results = []
    for filename, data in sorted(final_files.items()):
        file_size = save_json(data if data is not None else [], filename)
        item_count = len(data) if isinstance(data, list) else 0
        results.append((filename, item_count, file_size))
        print(f"  {filename:30} {item_count:4} items  {file_size:8.1f} KB")

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
    print(f"Output location: {REPO_ROOT / 'data' / 'json'}")
    print("=" * 70 + "\n")

    if no_strict:
        print("[INFO] Strict smoke checks skipped (--no-strict).")
    else:
        print("STEP 4: Running strict smoke checks...")
        print("-" * 70)
        smoke_exit = run_smoke_check(REPO_ROOT, fail_on_duplicate_ids=True)
        if smoke_exit != 0:
            print("[ERROR] Strict smoke checks failed.")
            return 1
        print("[OK] Strict smoke checks passed.\n")

    if report:
        try:
            report_result = generate_refresh_report(REPO_ROOT)
            report_rel = report_result["report_markdown"].relative_to(REPO_ROOT)
            print(f"[OK] Report: {report_rel}")
            print(
                f"[OK] Report totals - added: {report_result['totals']['added']}, "
                f"removed: {report_result['totals']['removed']}, changed: {report_result['totals']['changed']}"
            )
        except Exception as e:
            print(f"[WARN] Report generation failed: {e}")
    else:
        print("[INFO] Report generation skipped (use --report to enable).")
    return 0


def run_image_extraction(
    *,
    pcbanks_arg: str,
    extracted_arg: str,
    keep_dds: bool,
    no_cleanup: bool,
) -> int:
    output_dir = DATA / "images"
    if extracted_arg:
        extracted_root = Path(extracted_arg)
        if extracted_root.name.lower() == "textures":
            extracted_root = extracted_root.parent
    else:
        extracted_root = EXTRACTED
        unpack_all_game_files_to_extracted(pcbanks_arg, extracted_root)
        normalize_to_extracted(extracted_root)

    if not extracted_root.is_dir():
        print(f"[ERROR] EXTRACTED path not found: {extracted_root}")
        return 1

    print("\n--- Image Extraction ---")
    success, skipped, used_magick = extract_icons(
        DATA / "json", extracted_root, output_dir, copy_dds_if_no_magick=True, keep_dds=keep_dds
    )
    print(f"[OK] Extracted: {success}  Skipped: {skipped}")
    if success and not used_magick:
        print("[TIP] Install ImageMagick (magick) and re-run to get .png instead of .dds")
    print(f"Output: {output_dir}")

    if not extracted_arg and not no_cleanup:
        to_remove = [DATA / name for name in ("metadata", "EXTRACTED") if (DATA / name).is_dir()]
        if to_remove:
            print("[INFO] Cleanup: removing data/metadata and data/EXTRACTED...")
            for folder in to_remove:
                shutil.rmtree(folder, ignore_errors=True)
                print(f"  Removed {folder}/")
    return 0 if success else 1


def main() -> int:
    args = parse_args()
    pcbanks_arg_effective = args.pcbanks or (DEFAULT_PCBANKS if args.refresh else "")
    if args.images:
        return run_image_extraction(
            pcbanks_arg=pcbanks_arg_effective,
            extracted_arg=args.extracted,
            keep_dds=args.keep_dds,
            no_cleanup=args.no_cleanup,
        )

    refresh_requested = args.refresh or bool(args.pcbanks)
    if refresh_requested:
        run_full_refresh_prep(pcbanks_arg_effective)

    extract_exit = run_json_extraction(report=args.report, no_strict=args.no_strict)
    if extract_exit != 0:
        return extract_exit

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
