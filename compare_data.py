#!/usr/bin/env python3
"""
Compare two NMS data directories and print a markdown table report.
Example: python compare_data.py
         python compare_data.py --old "c:/nms/src/data" --new "c:/nms/src/datav2"
"""
import argparse
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))

from utils.compare_data import run


def main():
    parser = argparse.ArgumentParser(
        description="Compare old vs new NMS data dirs; output markdown table report.",
    )
    parser.add_argument(
        "--old",
        type=Path,
        default=Path(r"c:\Users\bradhave\Documents\workspace\nms\src\data"),
        help="Path to old data directory (default: nms/src/data)",
    )
    parser.add_argument(
        "--new",
        type=Path,
        default=Path(r"c:\Users\bradhave\Documents\workspace\nms\src\datav2"),
        help="Path to new data directory (default: nms/src/datav2)",
    )
    parser.add_argument(
        "--no-details",
        action="store_true",
        help="Only print summary table, skip per-file details",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Write report to this file instead of stdout",
    )
    args = parser.parse_args()

    if not args.old.is_dir():
        print(f"Error: --old is not a directory: {args.old}", file=sys.stderr)
        sys.exit(1)
    if not args.new.is_dir():
        print(f"Error: --new is not a directory: {args.new}", file=sys.stderr)
        sys.exit(1)

    report = run(
        args.old,
        args.new,
        details=not args.no_details,
    )

    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
