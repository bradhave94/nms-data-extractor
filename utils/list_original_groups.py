"""
Utility script to analyze and list all unique Group values from original data files.
This helps identify which groups should be categorized into which JSON files.
"""

import json
import os
from pathlib import Path

def list_groups_from_file(filepath):
    """Extract all unique Group values from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        groups = set()
        for item in data:
            group = item.get('Group', '')
            if group:
                groups.add(group)

        return sorted(groups)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

def analyze_original_data(original_data_path):
    """Analyze all JSON files in the original data directory."""
    original_path = Path(original_data_path)

    if not original_path.exists():
        print(f"Original data path not found: {original_data_path}")
        return

    results = {}

    # Find all JSON files
    json_files = sorted(original_path.glob('*.json'))

    for json_file in json_files:
        filename = json_file.name
        groups = list_groups_from_file(json_file)
        results[filename] = groups

        print(f"\n{'='*80}")
        print(f"{filename} - {len(groups)} unique groups")
        print('='*80)
        for group in groups:
            print(f"  '{group}',")

    return results

if __name__ == '__main__':
    # Path to original data files
    original_data_path = r'c:\Users\bradhave\Documents\workspace\nms\src\data'

    print("Analyzing original data files for unique Group values...")
    analyze_original_data(original_data_path)
