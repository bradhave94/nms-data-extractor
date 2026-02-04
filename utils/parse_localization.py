"""Parse localization file to create English translation dictionary"""
import xml.etree.ElementTree as ET
import json
from pathlib import Path

# Conjunctions/articles that stay lowercase in title case
_LOWERCASE_WORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'of', 'in', 'on', 'at', 'to', 'for',
    'with', 'by', 'as', 'from', 'into', 'onto', 'upon', 'nor', 'so', 'yet',
})


def title_case_name(s: str) -> str:
    """
    Title-case a name with conjunctions/articles kept lowercase.
    e.g. "CAKE OF GLASS" -> "Cake of Glass", not "Cake Of Glass".
    """
    if not s or not s.strip():
        return s
    words = s.strip().split()
    if not words:
        return s
    result = []
    for i, word in enumerate(words):
        lower = word.lower()
        is_first = i == 0
        is_last = i == len(words) - 1
        if is_first or is_last or lower not in _LOWERCASE_WORDS:
            result.append(word.capitalize())
        else:
            result.append(lower)
    return ' '.join(result)


def parse_localization(mxml_path: str) -> dict:
    """
    Parse nms_loc1_english.MXML to create a lookup dictionary.

    Args:
        mxml_path: Path to the localization MXML file

    Returns:
        Dictionary mapping localization keys to English text
    """
    tree = ET.parse(mxml_path)
    root = tree.getroot()

    translations = {}

    # Navigate to Table property
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in localization MXML")
        return translations

    # Each entry is a TkLocalisationEntry
    for entry in table_prop.findall('./Property[@name="Table"]'):
        # Get the ID (localization key)
        loc_id = entry.get('_id', '')
        if not loc_id:
            # Try property element
            id_prop = entry.find('.//Property[@name="Id"]')
            if id_prop is not None:
                loc_id = id_prop.get('value', '')

        # Get the English translation
        english_prop = entry.find('.//Property[@name="English"]')
        if english_prop is not None:
            english_text = english_prop.get('value', '')
            if loc_id and english_text:
                # Apply title case with lowercase conjunctions for name keys
                if loc_id.endswith('_NAME'):
                    english_text = title_case_name(english_text)
                translations[loc_id] = english_text

    print(f"[OK] Parsed {len(translations)} translations")
    return translations


if __name__ == '__main__':
    # Parse all English localization files and merge them
    mxml_files = [
        'nms_loc1_english.MXML',
        'nms_loc4_english.MXML',
        'nms_loc5_english.MXML',
        'nms_loc6_english.MXML',
        'nms_loc7_english.MXML',
        'nms_update3_english.MXML'
    ]

    print("=" * 60)
    print("Testing Localization Parser")
    print("=" * 60)

    all_translations = {}

    for mxml_file in mxml_files:
        mxml_path = Path(__file__).parent / 'data' / 'mbin' / mxml_file
        if not mxml_path.exists():
            print(f"[SKIP] {mxml_file} not found")
            continue

        print(f"\nParsing: {mxml_file}")
        translations = parse_localization(str(mxml_path))

        # Merge into all_translations
        all_translations.update(translations)

    # Save combined translations to JSON
    output_path = Path(__file__).parent / 'data' / 'json' / 'localization.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_translations, f, indent='\t', ensure_ascii=False)

    print(f"\n[OK] Combined total: {len(all_translations)} translations")
    print(f"[OK] Saved to {output_path.name}")
    print(f"[OK] File size: {output_path.stat().st_size / 1024:.1f} KB\n")

    # Test a few lookups
    test_keys = ['TECH_FRAGMENT_NAME', 'BP_SALVAGE_NAME', 'CASING_NAME', 'PROTECT_NAME']
    print("Sample translations:")
    for key in test_keys:
        value = all_translations.get(key, 'NOT FOUND')
        print(f"  {key} = {value}")
