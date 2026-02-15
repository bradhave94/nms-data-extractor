#!/usr/bin/env python3
"""Lightweight post-extraction smoke checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_JSON_FILES = [
    "Buildings.json",
    "ConstructedTechnology.json",
    "Corvette.json",
    "Curiosities.json",
    "Exocraft.json",
    "Fish.json",
    "Food.json",
    "NutrientProcessor.json",
    "Others.json",
    "Products.json",
    "RawMaterials.json",
    "Refinery.json",
    "Starships.json",
    "Technology.json",
    "TechnologyModule.json",
    "Trade.json",
    "Upgrades.json",
]


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_smoke_check(
    repo_root: Path,
    *,
    fail_on_duplicate_ids: bool = False,
    fail_on_cross_file_duplicate_ids: bool | None = None,
) -> int:
    json_dir = repo_root / "data" / "json"
    failures: list[str] = []
    warnings: list[str] = []
    if fail_on_cross_file_duplicate_ids is None:
        fail_on_cross_file_duplicate_ids = fail_on_duplicate_ids

    if not json_dir.exists():
        print(f"[ERROR] Missing directory: {json_dir}")
        return 1

    files_by_id: dict[str, set[str]] = {}
    for filename in EXPECTED_JSON_FILES:
        path = json_dir / filename
        if not path.exists():
            failures.append(f"{filename}: file missing")
            continue

        try:
            data = _load_json(path)
        except (OSError, json.JSONDecodeError) as e:
            failures.append(f"{filename}: invalid JSON ({e})")
            continue

        if not isinstance(data, list):
            failures.append(f"{filename}: expected top-level list, got {type(data).__name__}")
            continue

        seen_ids: set[str] = set()
        duplicate_ids: set[str] = set()
        for row in data:
            if not isinstance(row, dict):
                continue
            item_id = row.get("Id")
            if not isinstance(item_id, str) or not item_id:
                continue
            if item_id in seen_ids:
                duplicate_ids.add(item_id)
            else:
                seen_ids.add(item_id)
            files_by_id.setdefault(item_id, set()).add(filename)

        if duplicate_ids:
            preview = ", ".join(sorted(duplicate_ids)[:10])
            suffix = " ..." if len(duplicate_ids) > 10 else ""
            message = f"{filename}: duplicate Id values ({len(duplicate_ids)}): {preview}{suffix}"
            if fail_on_duplicate_ids:
                failures.append(message)
            else:
                warnings.append(message)

    cross_file_duplicates = {
        item_id: sorted(files)
        for item_id, files in files_by_id.items()
        if len(files) > 1
    }
    if cross_file_duplicates:
        preview_rows = []
        for item_id, files in sorted(cross_file_duplicates.items())[:10]:
            preview_rows.append(f"{item_id} ({', '.join(files)})")
        preview = "; ".join(preview_rows)
        suffix = " ..." if len(cross_file_duplicates) > 10 else ""
        message = (
            f"Cross-file duplicate Id values ({len(cross_file_duplicates)}): "
            f"{preview}{suffix}"
        )
        if fail_on_cross_file_duplicate_ids:
            failures.append(message)
        else:
            warnings.append(message)

    if failures:
        print("[FAIL] Smoke checks failed:")
        for issue in failures:
            print(f"  - {issue}")
        if warnings:
            print("[WARN] Additional warnings:")
            for issue in warnings:
                print(f"  - {issue}")
        return 1

    if warnings:
        print("[OK] Smoke checks passed with warnings.")
        for issue in warnings:
            print(f"[WARN] {issue}")
    else:
        print("[OK] Smoke checks passed.")

    print(f"Checked {len(EXPECTED_JSON_FILES)} JSON files in {json_dir}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lightweight post-extraction smoke checks.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root path (default: current project root).",
    )
    parser.add_argument(
        "--strict-duplicates",
        action="store_true",
        help="Treat duplicate Id values as errors (includes cross-file duplicates).",
    )
    parser.add_argument(
        "--strict-global-duplicates",
        action="store_true",
        help="Treat cross-file duplicate Id values as errors.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_smoke_check(
        args.repo_root.resolve(),
        fail_on_duplicate_ids=args.strict_duplicates,
        fail_on_cross_file_duplicate_ids=(args.strict_duplicates or args.strict_global_duplicates),
    )


if __name__ == "__main__":
    raise SystemExit(main())
