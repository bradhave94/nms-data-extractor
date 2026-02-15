#!/usr/bin/env python3
"""Consolidate MBIN files into data/mbin and remove staging folders."""
from pathlib import Path
import shutil


def consolidate_mbin(repo_root: Path) -> None:
    data_dir = repo_root / "data"
    mbin_dir = data_dir / "mbin"
    metadata_dir = data_dir / "metadata"
    language_dir = data_dir / "language"

    mbin_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for folder in (metadata_dir, language_dir):
        if not folder.exists():
            continue
        for path in folder.rglob("*.mbin"):
            if path.is_file():
                dest = mbin_dir / path.name
                shutil.copy2(path, dest)
                copied += 1
                print(f"  {path.relative_to(data_dir)} -> mbin/")

    if copied:
        print(f"Copied {copied} .mbin files to data/mbin/")
    else:
        print("No .mbin files found in data/metadata or data/language/")

    for folder in (metadata_dir, language_dir):
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            print(f"Removed data/{folder.name}/")

    print("Done.")


def main() -> None:
    consolidate_mbin(Path(__file__).parent.parent)


if __name__ == "__main__":
    main()
