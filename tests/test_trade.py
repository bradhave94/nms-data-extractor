"""Test script for Trade parser"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.trade import parse_trade

def main():
    print("=" * 60)
    print("Testing Trade Parser")
    print("=" * 60)

    mxml_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'

    if not mxml_path.exists():
        print(f"[ERROR] {mxml_path} not found!")
        return 1

    print(f"\nParsing: {mxml_path.name}")
    print(f"Size: {mxml_path.stat().st_size / 1024:.1f} KB\n")

    try:
        items = parse_trade(str(mxml_path))

        output_path = Path(__file__).parent.parent / 'data' / 'json' / 'Trade.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent='\t', ensure_ascii=False)

        print(f"[OK] Saved {len(items)} trade classes to {output_path.name}")
        print(f"[OK] Output size: {output_path.stat().st_size / 1024:.1f} KB\n")

        if items:
            print("Sample item (first entry):")
            print(json.dumps(items[0], indent=2))

        print("\n" + "=" * 60)
        print("[SUCCESS] Test complete!")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
