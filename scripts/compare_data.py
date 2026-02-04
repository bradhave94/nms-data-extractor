import json
from pathlib import Path

print("=" * 80)
print("COMPARISON: Original vs Generated Data")
print("=" * 80)

original_dir = Path(r"c:\Users\bradhave\Documents\workspace\nms\src\data")
generated_dir = Path(r"c:\Users\bradhave\Documents\workspace\nms-data-extractor\data\json")

files = [
    'Refinery.json',
    'NutrientProcessor.json',
    'Products.json',
    'RawMaterials.json',
    'Technology.json',
    'Buildings.json',
    'Cooking.json',
    'Fish.json',
    'Trade.json'
]

print(f"\n{'File':<25} {'Original':<12} {'Generated':<12} {'Difference':<12} {'Match?'}")
print("-" * 80)

for filename in files:
    orig_path = original_dir / filename
    gen_path = generated_dir / filename

    if orig_path.exists() and gen_path.exists():
        orig_data = json.load(open(orig_path, encoding='utf-8'))
        gen_data = json.load(open(gen_path, encoding='utf-8'))

        orig_count = len(orig_data)
        gen_count = len(gen_data)
        diff = gen_count - orig_count
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        match = "[OK]" if abs(diff) <= 5 else "[DIFF]"

        print(f"{filename:<25} {orig_count:<12} {gen_count:<12} {diff_str:<12} {match}")
    else:
        status = "MISSING ORIG" if not orig_path.exists() else "MISSING GEN"
        print(f"{filename:<25} {status}")

print("\n" + "=" * 80)

# Check for additional files in original
print("\nAdditional files in original:")
all_orig = [f.name for f in original_dir.glob("*.json")]
for f in all_orig:
    if f not in files:
        count = len(json.load(open(original_dir / f, encoding='utf-8')))
        print(f"  - {f:<30} {count:>5} items")
