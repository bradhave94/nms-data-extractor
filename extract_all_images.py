#!/usr/bin/env python3
r"""
Unpack game textures to data/EXTRACTED, then run utils.extract_images to produce
data/images/{id}.png (or .dds if ImageMagick is not installed).

Requires: hgpaktool on PATH, NMS_PCBANKS env or one argument (game PCBANKS path).
Optional: ImageMagick (magick) for DDS->PNG. Run from repo root.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DATA = REPO_ROOT / "data"
EXTRACTED = DATA / "EXTRACTED"
TEXTURES_SOURCE = DATA / "TEXTURES"  # HGPAKtool may create this with uppercase


def get_game_path():
    if len(sys.argv) >= 2:
        return sys.argv[1].strip()
    path = os.environ.get("NMS_PCBANKS", "").strip()
    if path:
        return path
    print("Game path required. Set NMS_PCBANKS or run: python extract_all_images.py \"X:\\...\\PCBANKS\"")
    sys.exit(1)


def unpack_textures(pcbanks: str) -> bool:
    """Run HGPAKtool to unpack *TEXTURES/* into data/. Returns True if something was unpacked."""
    DATA.mkdir(parents=True, exist_ok=True)
    cmd = [
        "hgpaktool", "-U",
        "-f=*TEXTURES/*",
        "-O", str(DATA),
        pcbanks,
    ]
    print("[1/4] Unpacking game textures (HGPAKtool)...")
    try:
        subprocess.run(cmd, check=True, cwd=REPO_ROOT)
    except FileNotFoundError:
        print("[ERROR] hgpaktool not found. Install it (e.g. pip install hgpaktool) and ensure it's on PATH.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] HGPAKtool failed: {e}")
        sys.exit(1)
    return TEXTURES_SOURCE.exists() or (DATA / "textures").exists()


def normalize_to_extracted():
    """
    Copy data/TEXTURES (or data/textures) -> data/EXTRACTED/textures (lowercase) so that
    paths in JSON (e.g. textures/ui/frontend/icons/...) resolve on all platforms.
    """
    src_dir = TEXTURES_SOURCE if TEXTURES_SOURCE.exists() else DATA / "textures"
    if not src_dir.exists():
        print("[WARN] No data/TEXTURES or data/textures found after unpack. Skipping copy.")
        return
    print("[2/4] Copying textures to data/EXTRACTED/textures/ (lowercase paths)...")
    dest_textures = EXTRACTED / "textures"
    if dest_textures.exists():
        shutil.rmtree(dest_textures, ignore_errors=True)
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
    if src_dir.exists():
        shutil.rmtree(src_dir, ignore_errors=True)


def run_extract_images():
    print("[3/4] Extracting icons to data/images/...")
    from utils.extract_images import extract_icons
    json_dir = DATA / "json"
    output_dir = DATA / "images"
    if not EXTRACTED.is_dir():
        print("[ERROR] data/EXTRACTED not found. Run texture unpack first.")
        sys.exit(1)
    success, skipped, used_magick = extract_icons(
        json_dir, EXTRACTED, output_dir, copy_dds_if_no_magick=True
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
    pcbanks = get_game_path()
    if not Path(pcbanks).exists():
        print(f"Game path does not exist: {pcbanks}")
        sys.exit(1)

    unpack_textures(pcbanks)
    normalize_to_extracted()
    run_extract_images()
    cleanup_data_folders()
    print("\nDone.")


if __name__ == "__main__":
    main()
