"""Test script for Refinery parser"""
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.refinery import parse_refinery

def main():
    print("=" * 60)
    print("Testing Refinery Parser")
    print("=" * 60)

    mxml_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcrecipetable.MXML'

    if not mxml_path.exists():
        print(f"[ERROR] {mxml_path} not found!")
        return 1

    print(f"\nParsing: {mxml_path.name}")
    print(f"Size: {mxml_path.stat().st_size / 1024:.1f} KB\n")

    try:
        # Parse the MXML file
        recipes = parse_refinery(str(mxml_path))

        # Save to JSON
        output_path = Path(__file__).parent.parent / 'data' / 'json' / 'Refinery.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(recipes, f, indent='\t', ensure_ascii=False)

        print(f"[OK] Saved {len(recipes)} recipes to {output_path.name}")
        print(f"[OK] Output size: {output_path.stat().st_size / 1024:.1f} KB\n")

        # Show first recipe as sample
        if recipes:
            print("Sample recipe (first entry):")
            print(json.dumps(recipes[0], indent=2))

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
