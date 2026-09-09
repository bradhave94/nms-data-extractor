#!/usr/bin/env python3
"""List uncategorized items and Groups missing from CATEGORIZATION_RULES."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from utils.categorization import CATEGORIZATION_RULES  # noqa: E402
NONE_JSON = REPO / "data" / "json" / "none.json"


def all_exact_groups() -> set[str]:
    groups: set[str] = set()
    for rules in CATEGORIZATION_RULES.values():
        groups.update(rules.get("exact", set()))
    return groups


def audit_none(path: Path) -> None:
    items = json.loads(path.read_text(encoding="utf-8"))
    exact = all_exact_groups()

    print(f"none.json: {len(items)} items\n")

    by_group = Counter((i.get("Group") or "(empty)").strip() for i in items)
    print("By Group:")
    for group, count in by_group.most_common():
        mapped = "HAS RULE" if group in exact else "NO EXACT RULE"
        print(f"  {count:3d}  [{mapped}]  {group}")

    no_rule: list[tuple[str, str, str]] = []
    has_rule_still_none: list[tuple[str, str, str]] = []
    for item in items:
        g = (item.get("Group") or "").strip()
        iid = item.get("Id", "")
        name = item.get("Name", "")
        if g and g not in exact:
            no_rule.append((iid, g, name))
        elif g in exact:
            has_rule_still_none.append((iid, g, name))

    print(f"\nNo exact rule ({len(no_rule)} items) — add Group to utils/categorization.py:")
    for iid, g, name in sorted(no_rule, key=lambda x: (x[1], x[0])):
        print(f"  {iid}: {g!r}  ({name!r})")

    print(f"\nHas exact rule but still in none ({len(has_rule_still_none)}) — name/junk filter:")
    for iid, g, name in sorted(has_rule_still_none, key=lambda x: (x[1], x[0]))[:20]:
        print(f"  {iid}: {g!r}  ({name!r})")
    if len(has_rule_still_none) > 20:
        print(f"  ... and {len(has_rule_still_none) - 20} more")


def audit_products_missing_rules(path: Path | None) -> None:
    """Groups present in product table extract but not in any exact rule."""
    if path is None:
        path = REPO / "data" / "mbin" / "nms_reality_gcproducttable.MXML"
    if not path.exists():
        print(f"[skip] product table not found: {path}")
        return

    import xml.etree.ElementTree as ET

    exact = all_exact_groups()
    tree = ET.parse(path)
    root = tree.getroot()
    groups_in_game: Counter[str] = Counter()
    for prop in root.iter("Property"):
        if prop.get("name") != "Id":
            continue
        # walk up to find sibling Group on same product row — simplified: scan all Group props
    for prop in root.iter("Property"):
        if prop.get("name") == "Group":
            val = (prop.get("value") or "").strip()
            if val:
                groups_in_game[val] += 1

    unmapped = [(g, n) for g, n in groups_in_game.items() if g not in exact]
    unmapped.sort(key=lambda x: -x[1])
    print(f"\nProduct table Groups with NO exact rule ({len(unmapped)} distinct):")
    for g, n in unmapped[:40]:
        print(f"  {n:4d}  {g}")
    if len(unmapped) > 40:
        print(f"  ... and {len(unmapped) - 40} more")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--none", type=Path, default=NONE_JSON)
    parser.add_argument("--products", action="store_true", help="Also scan gcproducttable MXML for unmapped Groups")
    args = parser.parse_args()
    if not args.none.exists():
        raise SystemExit(f"Not found: {args.none} (run extract.py first)")
    audit_none(args.none)
    if args.products:
        audit_products_missing_rules(None)


if __name__ == "__main__":
    main()
