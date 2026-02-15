#!/usr/bin/env python3
"""Lightweight post-extraction smoke checks."""
from __future__ import annotations

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


def run_smoke_check(repo_root: Path, *, fail_on_duplicate_ids: bool = False) -> int:
    json_dir = repo_root / "data" / "json"
    failures: list[str] = []
    warnings: list[str] = []

    if not json_dir.exists():
        print(f"[ERROR] Missing directory: {json_dir}")
        return 1

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

        if duplicate_ids:
            preview = ", ".join(sorted(duplicate_ids)[:10])
            suffix = " ..." if len(duplicate_ids) > 10 else ""
            message = f"{filename}: duplicate Id values ({len(duplicate_ids)}): {preview}{suffix}"
            if fail_on_duplicate_ids:
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
