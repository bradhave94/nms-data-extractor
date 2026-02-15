#!/usr/bin/env python3
"""Builds per-run refresh reports and snapshots for extraction runs."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

IGNORED_REPORT_FILES = {"localization.json"}


def _sanitize_version(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._-") or "unknown-version"


def detect_version_key(repo_root: Path) -> str:
    import os

    explicit = (os.environ.get("NMS_GAME_VERSION") or os.environ.get("NMS_VERSION") or "").strip()
    if explicit:
        return _sanitize_version(explicit)

    candidate = repo_root / "data" / "mbin" / "nms_reality_gcproducttable.MXML"
    if candidate.exists():
        try:
            with open(candidate, encoding="utf-8") as f:
                for _ in range(6):
                    line = f.readline()
                    if not line:
                        break
                    match = re.search(r"MBINCompiler version \(([^)]+)\)", line)
                    if match:
                        return _sanitize_version(match.group(1))
        except OSError:
            pass
    return "unknown-version"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _is_id_list(data: Any) -> bool:
    if not isinstance(data, list):
        return False
    return all(isinstance(item, dict) and "Id" in item for item in data)


def _index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["Id"]): item for item in items}


def _compare_file(old_data: Any, new_data: Any) -> dict[str, Any]:
    if old_data is None and new_data is None:
        return {
            "old_count": 0,
            "new_count": 0,
            "added_ids": [],
            "removed_ids": [],
            "changed_ids": [],
            "has_changes": False,
            "mode": "missing",
        }

    if _is_id_list(old_data or []) and _is_id_list(new_data or []):
        old_by_id = _index_by_id(old_data or [])
        new_by_id = _index_by_id(new_data or [])
        old_ids = set(old_by_id)
        new_ids = set(new_by_id)
        added_ids = sorted(new_ids - old_ids)
        removed_ids = sorted(old_ids - new_ids)
        changed_ids = sorted(
            iid
            for iid in (old_ids & new_ids)
            if json.dumps(old_by_id[iid], sort_keys=True, ensure_ascii=False)
            != json.dumps(new_by_id[iid], sort_keys=True, ensure_ascii=False)
        )
        return {
            "old_count": len(old_by_id),
            "new_count": len(new_by_id),
            "added_ids": added_ids,
            "removed_ids": removed_ids,
            "changed_ids": changed_ids,
            "has_changes": bool(added_ids or removed_ids or changed_ids),
            "mode": "id-list",
        }

    old_count = len(old_data) if isinstance(old_data, list) else (len(old_data) if isinstance(old_data, dict) else (0 if old_data is None else 1))
    new_count = len(new_data) if isinstance(new_data, list) else (len(new_data) if isinstance(new_data, dict) else (0 if new_data is None else 1))
    return {
        "old_count": old_count,
        "new_count": new_count,
        "added_ids": [],
        "removed_ids": [],
        "changed_ids": [],
        "has_changes": old_data != new_data,
        "mode": "generic",
    }


def _copy_snapshot(source_json_dir: Path, snapshot_dir: Path) -> None:
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for json_file in sorted(source_json_dir.glob("*.json")):
        shutil.copy2(json_file, snapshot_dir / json_file.name)


def _build_markdown(*, version_key: str, generated_at: str, previous_run: dict[str, Any] | None, per_file: dict[str, dict[str, Any]]) -> str:
    old_total = sum(info["old_count"] for info in per_file.values())
    new_total = sum(info["new_count"] for info in per_file.values())
    added_total = sum(len(info["added_ids"]) for info in per_file.values())
    removed_total = sum(len(info["removed_ids"]) for info in per_file.values())
    changed_total = sum(len(info["changed_ids"]) for info in per_file.values())

    lines = [
        "# NMS Full Refresh Report",
        "",
        f"- Generated: `{generated_at}`",
        f"- Version key: `{version_key}`",
    ]
    if previous_run:
        lines.append(f"- Previous run: `{previous_run.get('generated_at', 'unknown')}` ({previous_run.get('version_key', 'unknown')})")
    else:
        lines.append("- Previous run: `none` (first report)")
    lines.extend(
        [
            "",
            "## Totals",
            "",
            f"- Old total items: **{old_total}**",
            f"- New total items: **{new_total}**",
            f"- Added IDs: **{added_total}**",
            f"- Removed IDs: **{removed_total}**",
            f"- Changed IDs: **{changed_total}**",
            "",
            "## Per File",
            "",
            "| File | Old | New | Added | Removed | Changed |",
            "|:-----|----:|----:|------:|--------:|--------:|",
        ]
    )

    for filename in sorted(per_file):
        info = per_file[filename]
        lines.append(f"| {filename} | {info['old_count']} | {info['new_count']} | {len(info['added_ids'])} | {len(info['removed_ids'])} | {len(info['changed_ids'])} |")

    lines.extend(["", "## Net New Highlights", ""])
    changes_found = False
    for filename in sorted(per_file):
        info = per_file[filename]
        if not info["has_changes"]:
            continue
        changes_found = True
        lines.append(f"### {filename}")
        if info["added_ids"]:
            preview = ", ".join(info["added_ids"][:25])
            lines.append(f"- Added ({len(info['added_ids'])}): {preview}")
            if len(info["added_ids"]) > 25:
                lines.append(f"  - ... and {len(info['added_ids']) - 25} more")
        if info["removed_ids"]:
            preview = ", ".join(info["removed_ids"][:25])
            lines.append(f"- Removed ({len(info['removed_ids'])}): {preview}")
            if len(info["removed_ids"]) > 25:
                lines.append(f"  - ... and {len(info['removed_ids']) - 25} more")
        if info["changed_ids"]:
            preview = ", ".join(info["changed_ids"][:25])
            lines.append(f"- Changed ({len(info['changed_ids'])}): {preview}")
            if len(info["changed_ids"]) > 25:
                lines.append(f"  - ... and {len(info['changed_ids']) - 25} more")
        lines.append("")

    if not changes_found:
        lines.append("- No net changes detected versus previous run.")

    lines.append("")
    return "\n".join(lines)


def generate_refresh_report(repo_root: Path) -> dict[str, Any]:
    reports_root = repo_root / "reports"
    latest_snapshot = reports_root / "_latest_snapshot"
    latest_run_meta_path = reports_root / "latest_run.json"
    current_json_dir = repo_root / "data" / "json"

    version_key = detect_version_key(repo_root)
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    run_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    previous_run = None
    if latest_run_meta_path.exists():
        previous_run = _load_json(latest_run_meta_path)
        if not isinstance(previous_run, dict):
            previous_run = None

    current_files = {p.name for p in current_json_dir.glob("*.json") if p.name not in IGNORED_REPORT_FILES}
    previous_files = {p.name for p in latest_snapshot.glob("*.json") if p.name not in IGNORED_REPORT_FILES}
    all_files = sorted(current_files | previous_files)

    per_file: dict[str, dict[str, Any]] = {}
    for filename in all_files:
        old_data = _load_json(latest_snapshot / filename)
        new_data = _load_json(current_json_dir / filename)
        per_file[filename] = _compare_file(old_data, new_data)

    run_dir = reports_root / "by_version" / version_key / run_stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    md_path = run_dir / "report.md"
    json_path = run_dir / "report.json"

    markdown = _build_markdown(
        version_key=version_key,
        generated_at=generated_at,
        previous_run=previous_run,
        per_file=per_file,
    )
    report_payload = {
        "generated_at": generated_at,
        "version_key": version_key,
        "previous_run": previous_run,
        "files": per_file,
    }

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2, ensure_ascii=False)

    reports_root.mkdir(parents=True, exist_ok=True)
    with open(reports_root / "latest_report.md", "w", encoding="utf-8") as f:
        f.write(markdown)

    _copy_snapshot(current_json_dir, latest_snapshot)

    latest_meta = {
        "generated_at": generated_at,
        "version_key": version_key,
        "report_markdown": str(md_path.relative_to(repo_root)),
        "report_json": str(json_path.relative_to(repo_root)),
    }
    with open(latest_run_meta_path, "w", encoding="utf-8") as f:
        json.dump(latest_meta, f, indent=2, ensure_ascii=False)

    totals = {
        "added": sum(len(info["added_ids"]) for info in per_file.values()),
        "removed": sum(len(info["removed_ids"]) for info in per_file.values()),
        "changed": sum(len(info["changed_ids"]) for info in per_file.values()),
    }
    return {
        "version_key": version_key,
        "generated_at": generated_at,
        "report_markdown": md_path,
        "report_json": json_path,
        "totals": totals,
    }
