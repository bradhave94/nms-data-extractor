import json
from pathlib import Path

# Load original and extracted data
original_dir = Path(r'c:\Users\bradhave\Documents\workspace\nms\src\data')
extracted_dir = Path(r'c:\Users\bradhave\Documents\workspace\nms-data-extractor\data\json')

files = [
    'Buildings.json',
    'ConstructedTechnology.json',
    'Cooking.json',
    'Curiosities.json',
    'Fish.json',
    'NutrientProcessor.json',
    'Others.json',
    'Products.json',
    'RawMaterials.json',
    'Refinery.json',
    'Technology.json',
    'TechnologyModule.json',
    'Trade.json',
]

print("\n" + "=" * 80)
print(" " * 20 + "EXTRACTION COMPARISON")
print("=" * 80)
print(f"{'File':<30} {'Before':<12} {'After':<12} {'Difference':<16}")
print("-" * 80)

total_before = 0
total_after = 0

for filename in files:
    original_file = original_dir / filename
    extracted_file = extracted_dir / filename

    if original_file.exists():
        with open(original_file, encoding='utf-8') as f:
            before = len(json.load(f))
        total_before += before
    else:
        before = 0

    if extracted_file.exists():
        with open(extracted_file, encoding='utf-8') as f:
            after = len(json.load(f))
        total_after += after
    else:
        after = 0

    diff = after - before
    diff_str = f"{diff:+d}" if diff != 0 else "0"

    print(f"{filename:<30} {before:<12} {after:<12} {diff_str:<16}")

print("-" * 80)
total_diff = total_after - total_before
total_diff_str = f"{total_diff:+d}" if total_diff != 0 else "0"
print(f"{'TOTAL':<30} {total_before:<12} {total_after:<12} {total_diff_str:<16}")
# Show none.json (uncategorized) if present
none_file = extracted_dir / 'none.json'
if none_file.exists():
    with open(none_file, encoding='utf-8') as f:
        none_count = len(json.load(f))
    print("-" * 80)
    print(f"{'none.json (uncategorized)':<30} {'N/A':<12} {none_count:<12} {'(review)':<16}")
print("=" * 80 + "\n")
