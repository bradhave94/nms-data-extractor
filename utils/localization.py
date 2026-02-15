"""Parse localization MXML files into data/json/localization.json."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

_LOWERCASE_WORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'of', 'in', 'on', 'at', 'to', 'for',
    'with', 'by', 'as', 'from', 'into', 'onto', 'upon', 'nor', 'so', 'yet',
})


def strip_markup_tags(text: str) -> str:
    if not text:
        return text
    return re.sub(r'<[^>]*>', '', text)


def _capitalize_word(word: str, force_capitalize: bool) -> str:
    if len(word) >= 3 and word.startswith("'") and word.endswith("'"):
        inner = word[1:-1]
        return "'" + (inner.capitalize() if force_capitalize else inner.lower()) + "'"
    return word.capitalize() if force_capitalize else word.lower()


def title_case_name(s: str) -> str:
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
    tree = ET.parse(mxml_path)
    root = tree.getroot()
    translations = {}

    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in localization MXML")
        return translations

    for entry in table_prop.findall('./Property[@name="Table"]'):
        loc_id = entry.get('_id', '')
        if not loc_id:
            id_prop = entry.find('.//Property[@name="Id"]')
            if id_prop is not None:
                loc_id = id_prop.get('value', '')

        english_prop = entry.find('.//Property[@name="English"]')
        if english_prop is not None:
            english_text = english_prop.get('value', '')
            if loc_id and english_text:
                english_text = strip_markup_tags(english_text)
                if loc_id.endswith('_NAME'):
                    english_text = title_case_name(english_text)
                translations[loc_id] = english_text

    print(f"[OK] Parsed {len(translations)} translations")
    return translations


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


def build_localization_json(base_path: Path | None = None) -> int:
    if base_path is None:
        base_path = Path(__file__).parent.parent
    search_dirs = [base_path / 'data' / 'mbin', base_path / 'data' / 'EXTRACTED' / 'language']
    all_translations = {}

    for mxml_file in LOCALE_MXML_FILES:
        mxml_path = None
        for directory in search_dirs:
            candidate = directory / mxml_file
            if candidate.exists():
                mxml_path = candidate
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
