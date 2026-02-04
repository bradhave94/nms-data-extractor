#!/usr/bin/env python3
"""
Clean the data folder: remove all contents, keep data/, create data/json.
Use before a full refresh (e.g. new game version) so HGPAKtool and extract_all.py have a clean slate.

Run from repo root: python -m utils.clean_data
"""
import shutil
from pathlib import Path


def main():
    repo_root = Path(__file__).parent.parent
    data_dir = repo_root / "data"
    data_json = data_dir / "json"

    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        print("Created data/")
    else:
        for child in data_dir.iterdir():
            path = data_dir / child.name
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                print(f"Removed data/{child.name}/")
            else:
                path.unlink(missing_ok=True)
                print(f"Removed data/{child.name}")

    data_json.mkdir(parents=True, exist_ok=True)
    print("Created data/json/")
    print("Done. data/ is clean and data/json/ exists.")


if __name__ == "__main__":
    main()
