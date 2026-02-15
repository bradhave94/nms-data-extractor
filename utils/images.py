#!/usr/bin/env python3
"""Extract all item icons from data/EXTRACTED into {id}.png for CDN upload."""
import json
import re
import shutil
import subprocess
from pathlib import Path


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
    "none.json",
]


def sanitize_filename(id_str: str) -> str:
    if not id_str:
        return "unknown"
    return re.sub(r'[\\/:*?"<>|]', "_", str(id_str)).strip() or "unknown"


def collect_id_icon_pairs(json_dir: Path) -> list[tuple[str, str]]:
    seen_ids = set()
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
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            id_val = item.get("id") or item.get("Id") or ""
            icon_val = (
                item.get("iconPath")
                or item.get("IconPath")
                or item.get("icon")
                or item.get("Icon")
                or ""
            )
            if not id_val or not icon_val:
                continue
            if id_val in seen_ids:
                continue
            seen_ids.add(id_val)
            pairs.append((id_val, icon_val))
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
