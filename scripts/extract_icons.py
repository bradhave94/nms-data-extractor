#!/usr/bin/env python3
"""
Extract all item icons from data/EXTRACTED into {id}.png for CDN upload.
Output goes to data/images by default.

Reads Id + Icon from the extracted JSON files, finds the source .dds under
data/EXTRACTED/, and outputs one PNG per item as {id}.png (e.g. CHART_SETTLE.png).

Requires ImageMagick (magick) for DDS->PNG conversion. If not found, copies as .dds.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


# JSON files that contain items with id + icon (skip Refinery, localization, none)
ICON_JSON_FILES = [
    "Buildings.json",
    "ConstructedTechnology.json",
    "Cooking.json",
    "Curiosities.json",
    "Fish.json",
    "NutrientProcessor.json",
    "Others.json",
    "Products.json",
    "RawMaterials.json",
    "Technology.json",
    "TechnologyModule.json",
    "Trade.json",
]


def sanitize_filename(id_str: str) -> str:
    """Make id safe for filenames: replace invalid chars with underscore."""
    if not id_str:
        return "unknown"
    # Windows / Linux invalid: \ / : * ? " < > |
    return re.sub(r'[\\/:*?"<>|]', "_", str(id_str)).strip() or "unknown"


def collect_id_icon_pairs(json_dir: Path) -> list[tuple[str, str]]:
    """Load all JSON files and collect (id, icon) from each item. First occurrence wins per id."""
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
            icon_val = item.get("icon") or item.get("Icon") or ""
            if not id_val or not icon_val:
                continue
            if id_val in seen_ids:
                continue
            seen_ids.add(id_val)
            pairs.append((id_val, icon_val))
    return pairs


def dds_to_png_imagemagick(source: Path, dest: Path) -> bool:
    """Convert DDS to PNG using ImageMagick. Returns True on success."""
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
) -> tuple[int, int, bool]:
    """Extract icons. Returns (success_count, skip_count, used_imagemagick)."""
    pairs = collect_id_icon_pairs(json_dir)
    if not pairs:
        print("[WARN] No id+icon pairs found in JSON files.")
        return 0, 0, False

    print(f"[INFO] Found {len(pairs)} items with icons")
    output_dir.mkdir(parents=True, exist_ok=True)
    success = 0
    skipped = 0
    # Probe ImageMagick once
    try:
        subprocess.run(["magick", "-version"], capture_output=True, check=True, timeout=5)
        has_magick = True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        has_magick = False
        if copy_dds_if_no_magick:
            print("[INFO] ImageMagick not found. Will copy .dds files; convert to PNG separately.")
        else:
            print("[WARN] ImageMagick not found. Install it for PNG output, or use --copy-dds.")

    for id_val, icon_path in pairs:
        # Icon path is relative to EXTRACTED, e.g. textures/ui/frontend/icons/...
        source = extracted_root / icon_path
        if not source.exists():
            skipped += 1
            continue
        safe_id = sanitize_filename(id_val)
        if has_magick:
            dest = output_dir / f"{safe_id}.png"
            if dds_to_png_imagemagick(source, dest):
                success += 1
            else:
                skipped += 1
        elif copy_dds_if_no_magick:
            dest = output_dir / f"{safe_id}.dds"
            shutil.copy2(source, dest)
            success += 1
        else:
            skipped += 1

    # When we produced PNGs, remove any leftover .dds from a previous run
    if has_magick and output_dir.is_dir():
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


def main():
    parser = argparse.ArgumentParser(
        description="Extract item icons from EXTRACTED as {id}.png for CDN upload."
    )
    root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=root / "data" / "json",
        help="Directory containing extracted JSON files",
    )
    parser.add_argument(
        "--extracted",
        type=Path,
        default=root / "data" / "EXTRACTED",
        help="Root path of EXTRACTED game files (where icon paths resolve)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=root / "data" / "images",
        help="Output directory for PNG (or DDS if no ImageMagick)",
    )
    parser.add_argument(
        "--no-copy-dds",
        action="store_true",
        help="Do not copy .dds when ImageMagick is missing (skip instead)",
    )
    parser.add_argument(
        "--delete-dds-only",
        action="store_true",
        help="Only delete .dds files in output directory, then exit (no extraction)",
    )
    args = parser.parse_args()

    if args.delete_dds_only:
        output_dir = args.output
        if not output_dir.is_dir():
            print(f"[WARN] Output directory does not exist: {output_dir}")
            return 0
        removed = 0
        for dds_file in output_dir.glob("*.dds"):
            try:
                dds_file.unlink()
                removed += 1
            except OSError as e:
                print(f"[WARN] Could not remove {dds_file}: {e}")
        print(f"[OK] Removed {removed} .dds files from {output_dir}")
        return 0

    if not args.extracted.is_dir():
        print(f"[ERROR] EXTRACTED path not found: {args.extracted}")
        sys.exit(1)

    print(f"JSON dir:    {args.json_dir}")
    print(f"EXTRACTED:   {args.extracted}")
    print(f"Output:      {args.output}")
    print()

    success, skipped, used_imagemagick = extract_icons(
        args.json_dir,
        args.extracted,
        args.output,
        copy_dds_if_no_magick=not args.no_copy_dds,
    )
    print(f"[OK] Extracted: {success}")
    if skipped:
        print(f"[SKIP] Missing source or failed: {skipped}")
    print(f"Output: {args.output}")
    if success and not used_imagemagick and not args.no_copy_dds:
        print("[TIP] Install ImageMagick (magick) and re-run to get .png instead of .dds")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
