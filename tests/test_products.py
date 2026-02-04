"""Test script for Products parser"""
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.products import parse_products

def main():
    print("=" * 60)
    print("Testing Products Parser")
    print("=" * 60)

    mxml_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'

    if not mxml_path.exists():
        print(f"[ERROR] {mxml_path} not found!")
        return 1

    print(f"\nParsing: {mxml_path.name}")
    print(f"Size: {mxml_path.stat().st_size / 1024:.1f} KB\n")

    try:
        # Parse the MXML file
        products = parse_products(str(mxml_path))

        # Save to JSON
        output_path = Path(__file__).parent.parent / 'data' / 'json' / 'Products.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent='\t', ensure_ascii=False)

        print(f"[OK] Saved {len(products)} products to {output_path.name}")
        print(f"[OK] Output size: {output_path.stat().st_size / 1024:.1f} KB\n")

        # Show first product as sample
        if products:
            print("Sample product (first entry):")
            print(json.dumps(products[0], indent=2))

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
