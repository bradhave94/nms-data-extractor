#!/usr/bin/env python3
"""
Compare two NMS data directories (e.g. old vs new) and produce summary + per-file tables.
Items are keyed by "Id". Reports: Added (new only), Removed (old only), Changed (same Id, different fields).
"""
import json
from pathlib import Path
from typing import Any


# Category JSON files to compare (exclude localization / non-category files)
CATEGORY_FILES = [
    "Buildings.json",
    "ConstructedTechnology.json",
    "Cooking.json",
    "Curiosities.json",
    "Fish.json",
    "NutrientProcessor.json",
    "Others.json",
    "Products.json",
    "RawMaterials.json",
    "Refinery.json",
    "Technology.json",
    "TechnologyModule.json",
    "Trade.json",
]


def load_json_array(path: Path) -> list[dict[str, Any]]:
    """Load a JSON file; expect a top-level array. Return [] if missing or invalid."""
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index items by their 'Id' field."""
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and "Id" in item:
            out[str(item["Id"])] = item
    return out


def diff_values(old_val: Any, new_val: Any) -> list[tuple[str, Any, Any]]:
    """
    Recursive diff of two JSON-serializable values.
    Returns list of (path, old_value, new_value) for differences.
    Path is dot-separated for nested keys.
    """
    changes: list[tuple[str, Any, Any]] = []

    def _diff(path: str, a: Any, b: Any) -> None:
        if a == b:
            return
        if type(a) != type(b):
            changes.append((path, a, b))
            return
        if isinstance(a, dict):
            all_keys = set(a) | set(b)
            for k in sorted(all_keys):
                p = f"{path}.{k}" if path else k
                if k not in a:
                    _diff(p, None, b[k])
                elif k not in b:
                    _diff(p, a[k], None)
                else:
                    _diff(p, a[k], b[k])
        elif isinstance(a, list):
            # Compare as ordered lists; if lengths differ or any element differs, report whole field
            if len(a) != len(b) or any(
                json.dumps(x, sort_keys=True) != json.dumps(y, sort_keys=True)
                for x, y in zip(a, b)
            ):
                changes.append((path, a, b))
        else:
            changes.append((path, a, b))

    _diff("", old_val, new_val)
    return changes


def compare_file(
    old_path: Path,
    new_path: Path,
    *,
    ignore_keys: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """
    Compare one category file between old and new dirs.
    Returns dict with keys: added (list of Ids), removed (list of Ids), changed (list of dicts with Id, name, changes).
    """
    old_items = load_json_array(old_path)
    new_items = load_json_array(new_path)
    old_by_id = by_id(old_items)
    new_by_id = by_id(new_items)

    old_ids = set(old_by_id)
    new_ids = set(new_by_id)
    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    common = old_ids & new_ids

    changed: list[dict[str, Any]] = []
    for iid in sorted(common):
        old_obj = old_by_id[iid]
        new_obj = new_by_id[iid]
        field_changes = diff_values(old_obj, new_obj)
        # Filter out ignored keys (e.g. CdnUrl, Icon if they always differ)
        field_changes = [
            (p, o, n) for p, o, n in field_changes if p.split(".")[0] not in ignore_keys
        ]
        if field_changes:
            name = old_obj.get("Name") or new_obj.get("Name") or iid
            changed.append(
                {
                    "Id": iid,
                    "Name": name,
                    "changes": field_changes,
                }
            )

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "old_count": len(old_by_id),
        "new_count": len(new_by_id),
    }


def compare_dirs(
    old_dir: Path,
    new_dir: Path,
    *,
    ignore_keys: frozenset[str] = frozenset(),
) -> dict[str, dict[str, Any]]:
    """Compare all category files between old_dir and new_dir. Returns results keyed by filename."""
    results: dict[str, dict[str, Any]] = {}
    for filename in CATEGORY_FILES:
        results[filename] = compare_file(
            old_dir / filename,
            new_dir / filename,
            ignore_keys=ignore_keys,
        )
    return results


def _change_pct(old_n: int, new_n: int) -> str:
    """Net change as percentage of old count. Returns e.g. '+17.2%', '-5.0%', '0%', or '—'."""
    if old_n == 0:
        return "—" if new_n == 0 else "new"
    pct = (new_n - old_n) / old_n * 100
    if pct == 0:
        return "0%"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def format_summary_table(results: dict[str, dict[str, Any]]) -> str:
    """Markdown table with right-aligned numbers and a Change % column. Padded for terminal readability."""
    # Column widths for padding (so table aligns in terminal and markdown)
    w_file, w_a, w_b, w_c, w_old, w_new, w_pct = 28, 6, 7, 7, 9, 9, 8
    lines = [
        f"| {'File':<{w_file}} | {'Added':>{w_a}} | {'Removed':>{w_b}} | {'Changed':>{w_c}} | {'Old total':>{w_old}} | {'New total':>{w_new}} | {'Change %':>{w_pct}} |",
        "|:" + "-" * w_file + "|------:|------:|------:|----------:|----------:|---------:|",
    ]
    for filename in CATEGORY_FILES:
        r = results.get(filename, {})
        a = len(r.get("added", []))
        b = len(r.get("removed", []))
        c = len(r.get("changed", []))
        old_n = r.get("old_count", 0)
        new_n = r.get("new_count", 0)
        pct = _change_pct(old_n, new_n)
        line = (
            f"| {filename:<{w_file}} | {a:>{w_a}} | {b:>{w_b}} | {c:>{w_c}} | {old_n:>{w_old}} | {new_n:>{w_new}} | {pct:>{w_pct}} |"
        )
        lines.append(line)
    return "\n".join(lines)


def format_details(results: dict[str, dict[str, Any]], max_changes_per_item: int = 10) -> str:
    """Per-file details: added/removed IDs and changed items with field diffs."""
    sections: list[str] = []
    for filename in CATEGORY_FILES:
        r = results.get(filename, {})
        added = r.get("added", [])
        removed = r.get("removed", [])
        changed = r.get("changed", [])

        if not added and not removed and not changed:
            continue

        parts = [f"### {filename}\n"]
        if added:
            parts.append(f"- **Added** ({len(added)}): {', '.join(added[:30])}")
            if len(added) > 30:
                parts.append(f"  ... and {len(added) - 30} more")
            parts.append("")
        if removed:
            parts.append(f"- **Removed** ({len(removed)}): {', '.join(removed[:30])}")
            if len(removed) > 30:
                parts.append(f"  ... and {len(removed) - 30} more")
            parts.append("")
        if changed:
            parts.append(f"- **Changed** ({len(changed)}):")
            for entry in changed[:20]:  # cap changed items shown
                name = entry.get("Name", entry.get("Id", "?"))
                ch = entry.get("changes", [])[:max_changes_per_item]
                parts.append(f"  - `{entry.get('Id')}` ({name})")
                for path, old_v, new_v in ch:
                    old_s = json.dumps(old_v, ensure_ascii=False)[:60]
                    new_s = json.dumps(new_v, ensure_ascii=False)[:60]
                    if len(json.dumps(old_v)) > 60 or len(json.dumps(new_v)) > 60:
                        old_s += "…"
                        new_s += "…"
                    parts.append(f"    - `{path}`: {old_s} → {new_s}")
                if len(entry.get("changes", [])) > max_changes_per_item:
                    parts.append(f"    - ... and {len(entry['changes']) - max_changes_per_item} more fields")
            if len(changed) > 20:
                parts.append(f"  ... and {len(changed) - 20} more changed items")
        sections.append("\n".join(parts))
    return "\n".join(sections)


def run(
    old_dir: Path,
    new_dir: Path,
    *,
    ignore_keys: frozenset[str] = frozenset({"CdnUrl", "Icon"}),
    details: bool = True,
) -> str:
    """
    Run comparison and return a single markdown report.
    """
    results = compare_dirs(old_dir, new_dir, ignore_keys=ignore_keys)
    report = [
        "# NMS Data Comparison",
        "",
        f"- **Old:** `{old_dir}`",
        f"- **New:** `{new_dir}`",
        "",
        "## Summary",
        "",
        format_summary_table(results),
        "",
    ]
    if details:
        report.append("## Details")
        report.append("")
        report.append(format_details(results))
    return "\n".join(report)
