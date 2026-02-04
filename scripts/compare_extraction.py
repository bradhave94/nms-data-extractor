"""Compare extracted data against original NMS Assistant files"""
import json
from pathlib import Path

# Original files location
ORIGINAL_DIR = Path(r'c:\Users\bradhave\Documents\workspace\nms\src\data')
EXTRACTED_DIR = Path(r'c:\Users\bradhave\Documents\workspace\nms-data-extractor\data\json')

# Files to compare (ones that exist in both)
COMPARE_FILES = [
    'Products.json',
    'Technology.json',
    'Buildings.json',
    'Cooking.json',
    'Curiosities.json',
    'Fish.json',
    'RawMaterials.json',
    'Trade.json',
    'Refinery.json',
    'NutrientProcessor.json',
]

def compare_files():
    print("=" * 80)
    print("COMPARING EXTRACTED vs ORIGINAL")
    print("=" * 80)

    for filename in COMPARE_FILES:
        original_path = ORIGINAL_DIR / filename
        extracted_path = EXTRACTED_DIR / filename

        if not original_path.exists():
            print(f"\n{filename:30} [ORIGINAL NOT FOUND]")
            continue

        if not extracted_path.exists():
            print(f"\n{filename:30} [EXTRACTED NOT FOUND]")
            continue

        # Load both files
        original = json.load(open(original_path, encoding='utf-8'))
        extracted = json.load(open(extracted_path, encoding='utf-8'))

        # Compare counts
        orig_count = len(original)
        extr_count = len(extracted)
        diff = extr_count - orig_count
        diff_pct = (diff / orig_count * 100) if orig_count > 0 else 0

        status = "[OK]" if diff >= 0 else "[WARN]"
        print(f"\n{filename:30} {status}")
        print(f"  Original: {orig_count:4} items")
        print(f"  Extracted: {extr_count:4} items")
        print(f"  Difference: {diff:+4} items ({diff_pct:+.1f}%)")

        # Sample comparison of first item
        if original and extracted:
            orig_item = original[0]
            extr_item = extracted[0]

            # Compare IDs
            orig_id = orig_item.get('Id', 'N/A')
            extr_id = extr_item.get('Id', 'N/A')

            print(f"  Sample ID: '{orig_id}' vs '{extr_id}'")

            # Compare Names
            orig_name = orig_item.get('Name', 'N/A')
            extr_name = extr_item.get('Name', 'N/A')

            print(f"  Sample Name: '{orig_name}' vs '{extr_name}'")

if __name__ == '__main__':
    compare_files()
