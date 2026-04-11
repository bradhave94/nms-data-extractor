#!/usr/bin/env python3
"""Extract all item icons from data/EXTRACTED into {id}.png for CDN upload."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parsers.base_parser import shared_texture_icon_name


ICON_JSON_FILES = [
    "Buildings.json",
    "ConstructedTechnology.json",
    "Food.json",
    "Corvette.json",
    "Curiosities.json",
    "Exocraft.json",
    "Fish.json",
    "NutrientProcessor.json",
    "Others.json",
    "Products.json",
    "RawMaterials.json",
    "Starships.json",
    "Technology.json",
    "TechnologyModule.json",
    "Trade.json",
    "Upgrades.json",
    "Creatures.json",
    "none.json",
]

_STANDARD_ICON_FIELDS = ("IconPath", "iconPath", "Icon", "icon")

_EXTRA_ICON_PATH_FIELDS = (
    "CategoryIconPath", "CategoryBgIconPath",
    "BuffIconPath", "DebuffIconPath",
    "BattleAffinityIconPath", "BattleAffinityBinocsIconPath",
)


def sanitize_filename(id_str: str) -> str:
    if not id_str:
        return "unknown"
    return re.sub(r'[\\/:*?"<>|]', "_", str(id_str)).strip() or "unknown"


def _dds_output_name(dds_path: str) -> str:
    """Derive a stable output name for a shared texture asset.

    Delegates to shared_texture_icon_name and strips the .png suffix
    since extract_icons appends the extension itself.
    """
    icon_name = shared_texture_icon_name(dds_path)
    if icon_name and icon_name.endswith(".png"):
        return icon_name[:-4]
    return icon_name or "unknown"


def _iter_item_lists(data) -> list[list]:
    """Yield all item lists from either a flat list or a dict of lists."""
    if isinstance(data, list):
        return [data]
    if isinstance(data, dict):
        return [v for v in data.values() if isinstance(v, list)]
    return []


def collect_id_icon_pairs(json_dir: Path) -> list[tuple[str, str]]:
    """Collect (output_name, source_dds_path) pairs from all JSON files.

    Standard IconPath fields → output name is the item Id.
    Extra *IconPath fields (shared textures) → output name is the DDS filename stem.
    """
    seen_ids = set()
    seen_texture_stems = set()
    pairs = []

    for filename in ICON_JSON_FILES:
        path = json_dir / filename
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Skip {filename}: {e}")
            continue

        for item_list in _iter_item_lists(data):
            for item in item_list:
                if not isinstance(item, dict):
                    continue
                id_val = item.get("id") or item.get("Id") or ""

                # Standard per-item icon: {Id}.png → source DDS
                if id_val and id_val not in seen_ids:
                    icon_val = ""
                    for field in _STANDARD_ICON_FIELDS:
                        icon_val = item.get(field, "") or ""
                        if icon_val:
                            break
                    if icon_val:
                        seen_ids.add(id_val)
                        pairs.append((id_val, icon_val))

                # Shared texture assets: {dds_stem}.png → source DDS
                for field in _EXTRA_ICON_PATH_FIELDS:
                    dds_path = item.get(field, "") or ""
                    if not dds_path:
                        continue
                    stem = _dds_output_name(dds_path)
                    if stem not in seen_texture_stems:
                        seen_texture_stems.add(stem)
                        pairs.append((stem, dds_path))

    return pairs


def dds_to_png(source: Path, dest: Path) -> bool:
    try:
        subprocess.run(
            ["magick", str(source), str(dest)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def extract_icons(
    json_dir: Path,
    extracted_root: Path,
    output_dir: Path,
    copy_dds_if_no_magick: bool = True,
    keep_dds: bool = False,
) -> tuple[int, int, bool]:
    pairs = collect_id_icon_pairs(json_dir)
    if not pairs:
        print("[WARN] No id+icon pairs found in JSON files.")
        return 0, 0, False

    total = len(pairs)
    print(f"[INFO] Found {total} items with icons")
    output_dir.mkdir(parents=True, exist_ok=True)
    success = 0
    skipped = 0

    try:
        subprocess.run(["magick", "-version"], capture_output=True, check=True, timeout=5)
        has_magick = True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        has_magick = False
        if copy_dds_if_no_magick:
            print("[INFO] ImageMagick not found. Will copy .dds files; convert to PNG separately.")
        else:
            print("[WARN] ImageMagick not found. Install it for PNG output.")

    progress_interval = max(1, min(100, total // 20)) if total else 100
    for idx, (id_val, icon_path) in enumerate(pairs, start=1):
        if idx % progress_interval == 0 or idx == total:
            print(f"[INFO] Converting {idx}/{total} ...", flush=True)

        source = extracted_root / icon_path
        if not source.exists():
            skipped += 1
            continue
        safe_id = sanitize_filename(id_val)
        if has_magick:
            dest = output_dir / f"{safe_id}.png"
            if dds_to_png(source, dest):
                success += 1
            else:
                skipped += 1
        elif copy_dds_if_no_magick:
            dest = output_dir / f"{safe_id}.dds"
            shutil.copy2(source, dest)
            success += 1
        else:
            skipped += 1

    if has_magick and output_dir.is_dir() and not keep_dds:
        removed = 0
        for dds_file in output_dir.glob("*.dds"):
            try:
                dds_file.unlink()
                removed += 1
            except OSError:
                pass
        if removed:
            print(f"[OK] Removed {removed} leftover .dds files from output")

    return success, skipped, has_magick
