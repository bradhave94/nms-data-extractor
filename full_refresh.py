#!/usr/bin/env python3
r"""
Full refresh: clean data, extract 18 MBINs (HGPAKtool), consolidate, convert to MXML (MBINCompiler), run extract_all.

  python full_refresh.py
  python full_refresh.py "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"

Game path: set NMS_PCBANKS env var, or pass as the only argument.
"""
import os
import subprocess
import sys
from pathlib import Path
from hgpaktool.api import HGPAKFile, InvalidFileException
from utils.refresh_report import generate_refresh_report

REPO_ROOT = Path(__file__).resolve().parent

# 18 MBIN filters for HGPAKtool
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
    "*LANGUAGE/nms_loc1_english.mbin",
    "*LANGUAGE/nms_loc4_english.mbin",
    "*LANGUAGE/nms_loc5_english.mbin",
    "*LANGUAGE/nms_loc6_english.mbin",
    "*LANGUAGE/nms_loc7_english.mbin",
    "*LANGUAGE/nms_loc8_english.mbin",
    "*LANGUAGE/nms_loc9_english.mbin",
    "*LANGUAGE/nms_update3_english.mbin",
]


def get_game_path():
    if len(sys.argv) >= 2:
        return sys.argv[1].strip()
    path = os.environ.get("NMS_PCBANKS", "").strip()
    if path:
        return path
    print("Game path required. Set NMS_PCBANKS or run: python full_refresh.py \"X:\\...\\No Man's Sky\\GAMEDATA\\PCBANKS\"")
    sys.exit(1)


def run(cmd, check=True, **kwargs):
    subprocess.run(cmd, check=check, cwd=REPO_ROOT, **kwargs)


def extract_mbins_with_hgpaktool(pcbanks: str, output_dir: Path, filters: list[str]) -> int:
    """Extract MBINs using hgpaktool library directly."""
    output_dir.mkdir(parents=True, exist_ok=True)
    file_count = 0

    # Iterate over .pak files in PCBANKS directory
    for fname in os.listdir(pcbanks):
        if not fname.lower().endswith(".pak"):
            continue
        pak_path = os.path.join(pcbanks, fname)
        try:
            print(f"  Reading {fname}...")
            with HGPAKFile(pak_path) as pak:
                file_count += pak.unpack(str(output_dir), filters, upper=False, write_manifest=False)
        except InvalidFileException:
            # Skip invalid pak files silently
            continue
        except Exception as e:
            print(f"  Warning: Failed to extract from {fname}: {e}")
            continue

    return file_count


def main():
    pcbanks = get_game_path()
    if not Path(pcbanks).exists():
        print(f"Game path does not exist: {pcbanks}")
        sys.exit(1)

    print("\n--- Step 1: Clean data ---")
    from utils.clean_data import main as clean_main
    clean_main()

    print("\n--- Step 2: Extract MBINs (HGPAKtool) ---")
    data_dir = REPO_ROOT / "data"
    file_count = extract_mbins_with_hgpaktool(pcbanks, data_dir, MBIN_FILTERS)
    print(f"  Extracted {file_count} files from PCBANKS")

    print("\n--- Step 2b: Consolidate MBINs into data/mbin, remove metadata/language ---")
    from utils.consolidate_mbin import main as consolidate_main
    consolidate_main()

    print("\n--- Step 3: Convert MBIN -> MXML (MBINCompiler) ---")
    mbin_dir = REPO_ROOT / "data" / "mbin"
    compiler = REPO_ROOT / "tools" / "MBINCompiler.exe"
    if not compiler.exists():
        print(f"MBINCompiler not found: {compiler}")
        sys.exit(1)
    for mbin in sorted(mbin_dir.glob("*.mbin")):
        run([str(compiler), str(mbin)])

    print("\n--- Step 4: Extract JSON (extract_all) ---")
    from extract_all import main as extract_all_main
    extract_all_main()

    print("\n--- Step 5: Build run report (net new vs previous run) ---")
    report = generate_refresh_report(REPO_ROOT)
    totals = report["totals"]
    print(f"  Version key: {report['version_key']}")
    print(f"  Added: {totals['added']}  Removed: {totals['removed']}  Changed: {totals['changed']}")
    print(f"  Markdown: {report['report_markdown']}")
    print(f"  JSON: {report['report_json']}")

    print("\n--- Full refresh complete ---\n")


if __name__ == "__main__":
    main()
