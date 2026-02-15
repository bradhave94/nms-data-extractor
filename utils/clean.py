#!/usr/bin/env python3
"""Clean the data folder and recreate data/json."""
from pathlib import Path
import shutil


def clean_data(repo_root: Path) -> None:
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


def main() -> None:
    clean_data(Path(__file__).parent.parent)


if __name__ == "__main__":
    main()
