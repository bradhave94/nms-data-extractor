"""Parse localization file to create English translation dictionary"""
import re
import xml.etree.ElementTree as ET
import json
from pathlib import Path

# Conjunctions/articles that stay lowercase in title case
_LOWERCASE_WORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'of', 'in', 'on', 'at', 'to', 'for',
    'with', 'by', 'as', 'from', 'into', 'onto', 'upon', 'nor', 'so', 'yet',
})


def strip_markup_tags(text: str) -> str:
    """
    Remove game markup tags from localized text.
    e.g. "<TECHNOLOGY>freighter's emergency log<>" -> "freighter's emergency log"
    Matches any <...> (including <>, <IMG>...</>, <SPECIAL>...) and removes them.
    """
    if not text:
        return text
    return re.sub(r'<[^>]*>', '', text)


def _capitalize_word(word: str, force_capitalize: bool) -> str:
    """Capitalize a single word, including words in single quotes like 'apple' -> 'Apple'."""
    if len(word) >= 3 and word.startswith("'") and word.endswith("'"):
        inner = word[1:-1]
        return "'" + (inner.capitalize() if force_capitalize else inner.lower()) + "'"
    return word.capitalize() if force_capitalize else word.lower()


def title_case_name(s: str) -> str:
    """
    Title-case a name with conjunctions/articles kept lowercase.
    e.g. "CAKE OF GLASS" -> "Cake of Glass", not "Cake Of Glass".
    Words in single quotes get the first letter inside the quotes capitalized: 'apple' -> 'Apple'.
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
            result.append(_capitalize_word(word, force_capitalize=True))
        else:
            result.append(_capitalize_word(word, force_capitalize=False))
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
                # Remove game markup tags (<TECHNOLOGY>, <>, <IMG>...</>, etc.)
                english_text = strip_markup_tags(english_text)
                # Apply title case with lowercase conjunctions for name keys
                if loc_id.endswith('_NAME'):
                    english_text = title_case_name(english_text)
                translations[loc_id] = english_text

    print(f"[OK] Parsed {len(translations)} translations")
    return translations


# Locale MXML files to merge (data/mbin or data/EXTRACTED/language)
LOCALE_MXML_FILES = [
    'nms_loc1_english.MXML',
    'nms_loc4_english.MXML',
    'nms_loc5_english.MXML',
    'nms_loc6_english.MXML',
    'nms_loc7_english.MXML',
    'nms_loc8_english.MXML',
    'nms_loc9_english.MXML',
    'nms_update3_english.MXML',
]


def build_localization_json(base_path: Path = None) -> int:
    """
    Rebuild data/json/localization.json from all locale MXML files.
    Looks in data/mbin and data/EXTRACTED/language. Returns total translation count.
    """
    if base_path is None:
        base_path = Path(__file__).parent.parent
    search_dirs = [base_path / 'data' / 'mbin', base_path / 'data' / 'EXTRACTED' / 'language']
    all_translations = {}

    for mxml_file in LOCALE_MXML_FILES:
        mxml_path = None
        for d in search_dirs:
            p = d / mxml_file
            if p.exists():
                mxml_path = p
                break
        if not mxml_path or not mxml_path.exists():
            print(f"[SKIP] {mxml_file} not found")
            continue

        print(f"  Parsing: {mxml_file}")
        translations = parse_localization(str(mxml_path))
        all_translations.update(translations)

    output_path = base_path / 'data' / 'json' / 'localization.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_translations, f, indent='\t', ensure_ascii=False)

    print(f"[OK] Localization: {len(all_translations)} translations -> {output_path.name}\n")
    return len(all_translations)


if __name__ == '__main__':
    base = Path(__file__).parent.parent
    print("=" * 60)
    print("Localization Parser (standalone)")
    print("=" * 60 + "\n")
    build_localization_json(base)

    # Test a few lookups
    with open(base / 'data' / 'json' / 'localization.json', encoding='utf-8') as f:
        all_translations = json.load(f)
    test_keys = ['TECH_FRAGMENT_NAME', 'BP_SALVAGE_NAME', 'CASING_NAME', 'PROTECT_NAME']
    print("Sample translations:")
    for key in test_keys:
        value = all_translations.get(key, 'NOT FOUND')
        print(f"  {key} = {value}")
