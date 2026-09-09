#!/usr/bin/env python3
"""Rebuild ``data/json/new.json`` from an archived report release.

The normal path uses only the baseline/current JSON and building MXML recorded
by ``report.json``.  ``--bootstrap`` is an explicit migration helper for the
pre-manifest ``reports/_latest_snapshot`` layout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from utils.report import (  # noqa: E402
    SnapshotIntegrityError,
    bootstrap_release,
    build_new_json_document,
    resolve_report_archive,
    write_new_json,
)


def _building_dir(path: Path | None, fallback: Path) -> Path:
    if path is None:
        return fallback
    return path.parent if path.is_file() else path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report",
        type=Path,
        nargs="?",
        help="Path to an archived reports/by_version/.../report.json",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO,
        help="Repository root whose data/json/new.json is written (default: extractor root).",
    )
    parser.add_argument(
        "--baseline-snapshot",
        type=Path,
        help="Explicit archived baseline directory for a legacy report or bootstrap.",
    )
    parser.add_argument(
        "--current-snapshot",
        type=Path,
        help="Explicit archived/current JSON directory for a legacy report or bootstrap.",
    )
    parser.add_argument(
        "--building-mxml",
        type=Path,
        help="Archived building MXML file (or its directory) for a legacy report/bootstrap.",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create the immutable release archive; requires --release-version.",
    )
    parser.add_argument(
        "--release-version",
        help="Explicit numeric game release key for --bootstrap.",
    )
    parser.add_argument(
        "--previous-version",
        help="Optional previous release key recorded by --bootstrap.",
    )
    return parser


def _run_bootstrap(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.release_version:
        parser.error("--bootstrap requires --release-version")
    repo_root = args.repo_root.resolve()
    try:
        archive = bootstrap_release(
            repo_root,
            version_key=args.release_version,
            baseline_snapshot_dir=args.baseline_snapshot,
            current_json_dir=args.current_snapshot,
            building_mxml_path=args.building_mxml,
            previous_version_key=args.previous_version,
        )
    except (OSError, SnapshotIntegrityError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"Release {archive['version_key']} archive "
        f"({'created' if archive['created'] else 'already exists'}): "
        f"{archive['release_dir']}"
    )
    return 0


def _legacy_archive_args(
    args: argparse.Namespace,
    report_path: Path,
    parser: argparse.ArgumentParser,
) -> dict[str, Path]:
    if args.baseline_snapshot is None or args.current_snapshot is None:
        parser.error(
            "This report has no archive references; supply both "
            "--baseline-snapshot and --current-snapshot archived directories"
        )
    if not (args.baseline_snapshot / "manifest.json").is_file():
        parser.error(f"Legacy rebuild baseline must have a manifest: {args.baseline_snapshot}")
    if not (args.current_snapshot / "manifest.json").is_file():
        parser.error(f"Legacy rebuild current snapshot must have a manifest: {args.current_snapshot}")
    building = _building_dir(args.building_mxml, report_path.parent / "building")
    return {
        "baseline_snapshot_dir": args.baseline_snapshot.resolve(),
        "current_snapshot_dir": args.current_snapshot.resolve(),
        "building_mxml_dir": building.resolve(),
    }


def _run_rebuild(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.report is None:
        parser.error("a report path is required unless --bootstrap is used")
    repo_root = args.repo_root.resolve()
    report_path = args.report.resolve()
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"Cannot read report JSON {report_path}: {exc}")
    if not isinstance(report, dict):
        parser.error(f"Report JSON is invalid: {report_path}")

    try:
        if isinstance(report.get("archive"), dict):
            sources = resolve_report_archive(report_path, repo_root=repo_root)
            source_args = {
                "baseline_snapshot_dir": sources["baseline_snapshot_dir"],
                "current_snapshot_dir": sources["current_snapshot_dir"],
                "building_mxml_dir": sources["building_mxml_dir"],
            }
        else:
            source_args = _legacy_archive_args(args, report_path, parser)
        doc = build_new_json_document(
            repo_root,
            version_key=str(report["version_key"]),
            previous_run=report.get("previous_run"),
            generated_at=report.get("generated_at"),
            **source_args,
        )
        write_new_json(repo_root, doc)
    except (OSError, KeyError, SnapshotIntegrityError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"Wrote {repo_root / 'data/json/new.json'}: "
        f"{doc['Summary']['Added']} added, {doc['Summary']['Changed']} changed"
    )
    return 0


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if args.bootstrap:
        return _run_bootstrap(args, parser)
    return _run_rebuild(args, parser)


if __name__ == "__main__":
    raise SystemExit(main())
