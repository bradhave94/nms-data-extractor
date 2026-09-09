#!/usr/bin/env python3
"""Rebuild data/json/new.json from a saved report.json (e.g. first --report after a game update)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from utils.report import build_new_json_document, write_new_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report",
        type=Path,
        help="Path to reports/by_version/.../report.json",
    )
    parser.add_argument(
        "--baseline-snapshot",
        type=Path,
        required=True,
        help="Snapshot of the report's previous game version, used for both detection and Previous payloads",
    )
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    baseline_dir = args.baseline_snapshot
    if not baseline_dir.is_dir():
        parser.error(f"Previous-release snapshot does not exist: {baseline_dir}")
    doc = build_new_json_document(
        REPO,
        version_key=report["version_key"],
        previous_run=report.get("previous_run"),
        generated_at=report.get("generated_at"),
        baseline_snapshot_dir=baseline_dir,
    )
    write_new_json(REPO, doc)
    print(
        f"Wrote {REPO / 'data/json/new.json'}: "
        f"{doc['Summary']['Added']} added, {doc['Summary']['Changed']} changed"
    )


if __name__ == "__main__":
    main()
