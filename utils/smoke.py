#!/usr/bin/env python3
"""Lightweight post-extraction smoke checks."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

EXPECTED_JSON_FILES = [
    "Buildings.json",
    "ConstructedTechnology.json",
    "Corvette.json",
    "Creatures.json",
    "Curiosities.json",
    "EggModifiers.json",
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

# Files whose top-level structure is a dict with section keys, not a flat list.
_DICT_STRUCTURED_FILES = {"Creatures.json"}
_CREATURES_REQUIRED_SECTIONS = {
    "Species",
    "Affinities",
    "BattleMoves",
    "MoveSets",
    "ArenaModes",
    "ArenaLeague",
    "ArenaAIConfigs",
    "ArenaRewards",
    "PetShop",
    "PetAccessories",
    "EggOverrides",
    "Behaviours",
    "CreatureGlobals",
}

_CREATURES_DICT_SECTIONS = {"CreatureGlobals"}

# These are references to a canonical item/species, not independent item IDs.
# Keep the locations explicit: a collision in another section is still an error.
ALLOWED_ID_OVERLAPS = {
    **{key: {"Creatures.json:Species", "Creatures.json:EggOverrides"}
       for key in ("FLYINGSNAKE", "FLYINGLIZARD", "FIEND")},
    **{f"SPEC_PB_EGG{i:02}": {"Creatures.json:PetShop", "Others.json"} for i in range(1, 6)},
}
DISPLAY_FIELDS = {"Name", "Description", "AltDescription", "Hint", "Group", "Text", "Title", "Tip",
                  "PinObjective", "PinObjectiveTip", "PinObjectiveMessage"}


def display_token_errors(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in DISPLAY_FIELDS and isinstance(child, str) and re.search(r"\bFE_[A-Z0-9_]+\b", child):
                yield f"{path}.{key}: unresolved controller token"
            yield from display_token_errors(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from display_token_errors(child, f"{path}[{index}]")


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_smoke_check(
    repo_root: Path,
    *,
    fail_on_duplicate_ids: bool = False,
    fail_on_cross_file_duplicate_ids: bool | None = None,
    baseline_json_dir: Path | None = None,
    check_display_tokens: bool = False,
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
    flat_rows = []
    def check_rows(rows, location):
        if not rows:
            failures.append(f"{location}: empty required dataset")
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("Id"), str) or not row["Id"]:
                failures.append(f"{location}: invalid record or missing Id")
                continue
            item_id = row["Id"]
            if item_id in seen:
                (failures if fail_on_duplicate_ids else warnings).append(f"{location}: duplicate Id {item_id}")
            seen.add(item_id)
            files_by_id.setdefault(item_id, set()).add(location)

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

        if check_display_tokens:
            failures.extend(display_token_errors(data, filename))
        if baseline_json_dir and (baseline_json_dir / filename).is_file():
            previous = _load_json(baseline_json_dir / filename)
            sections = {"items": data} if isinstance(data, list) else data
            old_sections = {"items": previous} if isinstance(previous, list) else previous
            if isinstance(sections, dict) and isinstance(old_sections, dict):
                for section, old_rows in old_sections.items():
                    rows = sections.get(section)
                    if isinstance(rows, list) and isinstance(old_rows, list) and len(rows) < len(old_rows) * 0.8:
                        failures.append(f"{filename}:{section}: count fell more than 20% ({len(old_rows)} -> {len(rows)}); review source coverage")

        if not isinstance(data, list):
            if filename in _DICT_STRUCTURED_FILES:
                if not isinstance(data, dict):
                    failures.append(f"{filename}: expected top-level dict, got {type(data).__name__}")
                    continue
                if filename == "Creatures.json":
                    missing_sections = sorted(_CREATURES_REQUIRED_SECTIONS - set(data.keys()))
                    if missing_sections:
                        failures.append(
                            f"{filename}: missing required sections: {', '.join(missing_sections)}"
                        )
                    for section in sorted(_CREATURES_REQUIRED_SECTIONS & set(data.keys())):
                        section_data = data.get(section)
                        if section in _CREATURES_DICT_SECTIONS:
                            if not isinstance(section_data, dict):
                                failures.append(
                                    f"{filename}: section '{section}' expected dict, got {type(section_data).__name__}"
                                )
                            elif not section_data:
                                failures.append(f"{filename}:{section}: empty required metadata")
                        elif not isinstance(section_data, list):
                            failures.append(
                                f"{filename}: section '{section}' expected list, got {type(section_data).__name__}"
                            )
                        else:
                            check_rows(section_data, f"{filename}:{section}")
                continue
            failures.append(f"{filename}: expected top-level list, got {type(data).__name__}")
            continue

        check_rows(data, filename)
        flat_rows.extend(row for row in data if isinstance(row, dict))

    cross_file_duplicates = {
        item_id: sorted(files)
        for item_id, files in files_by_id.items()
        if len(files) > 1 and files != ALLOWED_ID_OVERLAPS.get(item_id)
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

    flat_ids = {row.get("Id") for row in flat_rows}
    for row in flat_rows:
        references = [*(row.get("RequiredItems") or []), *(row.get("Inputs") or [])]
        if isinstance(row.get("Output"), dict):
            references.append(row["Output"])
        for reference in references:
            if not isinstance(reference, dict) or reference.get("Id") not in flat_ids:
                failures.append(f"{row.get('Id')}: unresolved ingredient/output {reference}")

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
