"""Test script for RawMaterials parser"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.rawmaterials import parse_rawmaterials

def main():
    print("=" * 60)
    print("Testing RawMaterials Parser")
    print("=" * 60)

    mxml_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcsubstancetable.MXML'

    if not mxml_path.exists():
        print(f"[ERROR] {mxml_path} not found!")
        return 1

    print(f"\nParsing: {mxml_path.name}")
    print(f"Size: {mxml_path.stat().st_size / 1024:.1f} KB\n")

    try:
        materials = parse_rawmaterials(str(mxml_path))

        output_path = Path(__file__).parent.parent / 'data' / 'json' / 'RawMaterials.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(materials, f, indent='\t', ensure_ascii=False)

        print(f"[OK] Saved {len(materials)} raw materials to {output_path.name}")
        print(f"[OK] Output size: {output_path.stat().st_size / 1024:.1f} KB\n")

        if materials:
            print("Sample material (first entry):")
            print(json.dumps(materials[0], indent=2))

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
