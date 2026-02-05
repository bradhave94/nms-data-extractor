#!/usr/bin/env python3
r"""
Unpack all game files to data/EXTRACTED (full unpack, no filter), normalize
textures to data/EXTRACTED/textures/, then run utils.extract_images to produce
data/images/{id}.png (or .dds if ImageMagick is not installed).

Requires: hgpaktool library, NMS_PCBANKS env or one argument (game PCBANKS path).
Optional: ImageMagick (magick) for DDS->PNG.
Full unpack can take several minutes and temporarily use significant disk space;
use --no-cleanup to keep data/EXTRACTED for inspection.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path
from hgpaktool.api import HGPAKFile, InvalidFileException

REPO_ROOT = Path(__file__).resolve().parent
DATA = REPO_ROOT / "data"
EXTRACTED = DATA / "EXTRACTED"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Unpack textures, extract icons, and optionally clean up EXTRACTED."
    )
    parser.add_argument(
        "pcbanks",
        nargs="?",
        default="",
        help="Path to PCBANKS (or set NMS_PCBANKS env var)",
    )
    parser.add_argument(
        "--keep-dds",
        action="store_true",
        help="Keep .dds files in output directory even when PNGs are produced",
    )
    parser.add_argument(
        "--extracted",
        default="",
        help="Use an existing EXTRACTED folder (skip unpack).",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output directory for images (defaults to data/images).",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Do not delete data/EXTRACTED or data/metadata after extraction",
    )
    return parser.parse_args()


def get_game_path(pcbanks_arg: str) -> str:
    if pcbanks_arg:
        return pcbanks_arg.strip()
    path = os.environ.get("NMS_PCBANKS", "").strip()
    if path:
        return path
    print(
        "Game path required. Set NMS_PCBANKS or run: "
        "python extract_all_images.py \"X:\\...\\PCBANKS\""
    )
    sys.exit(1)


def unpack_textures(pcbanks: str) -> bool:
    """Use hgpaktool library to unpack all game files into data/EXTRACTED (no filter).
    Full unpack is required so we get all texture paths including buildable icons
    that may not match filtered path patterns."""
    EXTRACTED.mkdir(parents=True, exist_ok=True)

    print("[1/4] Unpacking all game files (HGPAKtool library, no filter – this may take several minutes)...")
    file_count = 0
    pak_count = 0

    try:
        # Iterate over .pak files in PCBANKS directory
        for fname in os.listdir(pcbanks):
            if not fname.lower().endswith(".pak"):
                continue
            pak_path = os.path.join(pcbanks, fname)
            try:
                print(f"  Reading {fname}...")
                with HGPAKFile(pak_path) as pak:
                    file_count += pak.unpack(str(EXTRACTED), None, upper=False, write_manifest=False)
                pak_count += 1
            except InvalidFileException:
                # Skip invalid pak files silently
                continue
            except Exception as e:
                print(f"  Warning: Failed to extract from {fname}: {e}")
                continue

        print(f"  Unpacked {file_count} files from {pak_count} .pak files")
    except Exception as e:
        print(f"[ERROR] HGPAKtool failed: {e}")
        sys.exit(1)

    return EXTRACTED.is_dir()


def normalize_to_extracted():
    """
    Ensure data/EXTRACTED/textures/ exists with lowercase path components so that
    paths in JSON (e.g. textures/ui/frontend/icons/...) resolve on all platforms.
    After full unpack, textures may be at EXTRACTED/TEXTURES or EXTRACTED/textures.
    """
    src_dir = EXTRACTED / "TEXTURES" if (EXTRACTED / "TEXTURES").exists() else EXTRACTED / "textures"
    if not src_dir.exists():
        print("[WARN] No TEXTURES or textures folder found in EXTRACTED. Skipping normalize.")
        return
    dest_textures = EXTRACTED / "textures"
    if src_dir.resolve() == dest_textures.resolve():
        # Same folder (e.g. on case-insensitive FS); ensure we use lowercase name
        return
    if dest_textures.exists():
        shutil.rmtree(dest_textures, ignore_errors=True)
    print("[2/4] Normalizing to data/EXTRACTED/textures/ (lowercase paths)...")
    n = 0
    for src_file in src_dir.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        lower_parts = [p.lower() for p in rel.parts]
        dest_file = dest_textures / Path(*lower_parts)
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        n += 1
    print(f"  -> {dest_textures}/ ({n} files)")
    if src_dir.exists() and src_dir.resolve() != dest_textures.resolve():
        shutil.rmtree(src_dir, ignore_errors=True)


def run_extract_images(keep_dds: bool, extracted_root: Path, output_dir: Path):
    print("[3/4] Extracting icons to data/images/...")
    from utils.extract_images import extract_icons
    json_dir = DATA / "json"
    if not extracted_root.is_dir():
        print(f"[ERROR] EXTRACTED path not found: {extracted_root}")
        sys.exit(1)
    success, skipped, used_magick = extract_icons(
        json_dir,
        extracted_root,
        output_dir,
        copy_dds_if_no_magick=True,
        keep_dds=keep_dds,
    )
    print(f"[OK] Extracted: {success}  Skipped: {skipped}")
    if success and not used_magick:
        print("[TIP] Install ImageMagick (magick) and re-run to get .png instead of .dds")
    print(f"Output: {output_dir}")


def cleanup_data_folders():
    """Remove data/metadata and data/EXTRACTED after extraction to free space."""
    to_remove = [DATA / name for name in ("metadata", "EXTRACTED") if (DATA / name).is_dir()]
    if not to_remove:
        return
    print("[4/4] Cleanup: removing data/metadata and data/EXTRACTED...")
    for folder in to_remove:
        shutil.rmtree(folder, ignore_errors=True)
        print(f"  Removed {folder}/")


def main():
    args = parse_args()
    extracted_root = EXTRACTED
    output_dir = Path(args.output) if args.output else (DATA / "images")

    if args.extracted:
        extracted_candidate = Path(args.extracted)
        # If user points at ...\EXTRACTED\textures, use its parent as root.
        if extracted_candidate.name.lower() == "textures":
            extracted_candidate = extracted_candidate.parent
        extracted_root = extracted_candidate
    else:
        pcbanks = get_game_path(args.pcbanks)
        if not Path(pcbanks).exists():
            print(f"Game path does not exist: {pcbanks}")
            sys.exit(1)
        unpack_textures(pcbanks)
        normalize_to_extracted()

    run_extract_images(args.keep_dds, extracted_root, output_dir)

    if args.extracted:
        print("[4/4] Cleanup skipped (custom EXTRACTED provided).")
    elif args.no_cleanup:
        print("[4/4] Cleanup skipped (keeping data/EXTRACTED and data/metadata).")
    else:
        cleanup_data_folders()
    print("\nDone.")


if __name__ == "__main__":
    main()
