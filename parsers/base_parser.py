"""Base XML Parser for EXML/MXML files"""
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional, Callable
import json
import os
from pathlib import Path

# Words that stay lowercase in title case (conjunctions, articles, short prepositions)
_LOWERCASE_WORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'of', 'in', 'on', 'at', 'to', 'for',
    'with', 'by', 'as', 'from', 'into', 'onto', 'upon', 'nor', 'so', 'yet',
})

# Hand-tuned fallbacks for known missing localization keys in current game data.
_MISSING_LOCALIZATION_OVERRIDES = {
    'UI_BRIDGECONNECT_NAME': 'Bridge Connector',
}

_MARKUP_TAG_RE = re.compile(r'<[^>]*>')
_FE_TOKEN_RE = re.compile(r'\bFE_[A-Z0-9_]+\b')


def strip_markup_tags(text: str) -> str:
    """
    Remove game markup tags from text, e.g. <TECHNOLOGY>...</>, <>, <IMG>...</>.
    """
    if not text or not isinstance(text, str):
        return text
    if '<' not in text:
        return text
    return _MARKUP_TAG_RE.sub('', text)


def normalize_control_tokens(text: str) -> str:
    """
    Convert control placeholders like FE_ALT1 into readable labels.
    Example: "Use FE_ALT1" -> "Use [ALT 1]"
    """
    if not text or not isinstance(text, str):
        return text

    mode = (os.environ.get("NMS_FE_TOKEN_MODE") or "resolved").strip().lower()
    if mode in {"raw", "off", "disabled"}:
        return text
    if "FE_" not in text:
        return text

    lookup = EXMLParser.load_controller_lookup()
    platform = (os.environ.get("NMS_INPUT_PLATFORM") or "Win").strip()
    token_map = lookup.get(platform, {})

    def _icon_to_readable(icon_path: str) -> str:
        if not icon_path:
            return ""
        upper = icon_path.upper()
        if upper.startswith("KEYBOARD/"):
            filename = Path(icon_path).name
            stem = Path(filename).stem  # e.g. INTERACT.E or KEYWIDE.TAB
            key = stem.split(".")[-1]
            return key.upper()
        if upper.startswith("MOUSE/KEY.MOUSELEFT"):
            return "LMB"
        if upper.startswith("MOUSE/KEY.MOUSERIGHT"):
            return "RMB"
        return ""

    def _token_label(match: re.Match[str]) -> str:
        token = match.group(0)
        icon_path = token_map.get(token, "")
        readable = _icon_to_readable(icon_path)
        if readable:
            return f"[{readable}]"
        return token

    return _FE_TOKEN_RE.sub(_token_label, text)


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


def normalize_game_icon_path(game_path: str) -> str:
    """
    Normalize a game texture path to match data/EXTRACTED layout.
    Use this for Icon so your app can load from EXTRACTED or build CDN URLs.

    Example: TEXTURES/UI/FRONTEND/ICONS/U4PRODUCTS/PRODUCT.CASING.DDS
         -> textures/ui/frontend/icons/u4products/product.casing.dds
    """
    if not game_path or not game_path.strip():
        return ''
    # Lowercase, forward slashes (game uses backslashes or forward)
    normalized = game_path.strip().replace('\\', '/').lower()
    return normalized


def looks_like_localization_key(value: str) -> bool:
    """
    Heuristic for unresolved loc keys like UP_CRUI4_SUB or UI_FOO_NAME.
    """
    if not value or not isinstance(value, str):
        return False
    if '_' not in value:
        return False
    return bool(re.fullmatch(r'[A-Z0-9_]+', value))


def unresolved_localization_key_count(localization: dict, *keys: str) -> int:
    """Count key-like localization tokens that are missing from localization data."""
    return sum(
        1
        for key in keys
        if looks_like_localization_key(key) and key not in localization
    )


def format_stat_type_name(stat_type: str, strip_prefixes: tuple[str, ...] = ()) -> str:
    """
    Convert stat enums into human-readable labels.
    Examples:
    - Weapon_Projectile_BurstCap -> Weapon Projectile Burst Cap
    - Weapon_Projectile_BurstCooldown -> Weapon Projectile Burst Cooldown
    """
    if not stat_type or not isinstance(stat_type, str):
        return ''

    cleaned = stat_type
    for prefix in strip_prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]

    words = []
    for token in cleaned.split('_'):
        if not token:
            continue
        # Split CamelCase chunks so BurstCap -> Burst Cap.
        token = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', token)
        token = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', token)
        words.append(token)

    return ' '.join(words).title()


class EXMLParser:
    """Base class for EXML/MXML parsing with common utilities"""

    _localization = None  # Cache for localization data
    _controller_lookup = None  # Cache for FE token -> icon lookups
    _xml_cache: dict[str, tuple[float, ET.Element]] = {}

    @classmethod
    def load_localization(cls) -> dict:
        """Load and cache the English localization dictionary"""
        if cls._localization is None:
            loc_path = Path(__file__).parent.parent / 'data' / 'json' / 'localization.json'
            if loc_path.exists():
                with open(loc_path, 'r', encoding='utf-8') as f:
                    cls._localization = json.load(f)
                print(f"[OK] Loaded {len(cls._localization)} translations")
            else:
                cls._localization = {}
                print("[WARN] localization.json not found")
        return cls._localization

    @classmethod
    def load_controller_lookup(cls) -> dict[str, dict[str, str]]:
        """Load token->icon mappings by platform from generated lookup JSON."""
        if cls._controller_lookup is None:
            lookup_path = Path(__file__).parent.parent / "data" / "json" / "controllerLookup.generated.json"
            if not lookup_path.exists():
                cls._controller_lookup = {}
                return cls._controller_lookup
            try:
                with open(lookup_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                parsed: dict[str, dict[str, str]] = {}
                for platform, rows in (raw or {}).items():
                    if not isinstance(platform, str) or not isinstance(rows, list):
                        continue
                    platform_map: dict[str, str] = {}
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        key = row.get("Key")
                        icon = row.get("Icon")
                        if isinstance(key, str) and isinstance(icon, str):
                            platform_map[key] = icon
                    parsed[platform] = platform_map
                cls._controller_lookup = parsed
            except (OSError, json.JSONDecodeError):
                cls._controller_lookup = {}
        return cls._controller_lookup

    @classmethod
    def translate(cls, key: str, default: str = None) -> str:
        """
        Translate a localization key to English. Same lookup is used for all
        items (categorized and none.json). If the key is missing from
        localization.json we fall back to default, or to a title-cased key
        (e.g. UI_STARCHART_BUILDER_NAME -> "Ui Starchart Builder") so names
        are never blank.

        Args:
            key: Localization key (e.g., "TECH_FRAGMENT_NAME")
            default: Default value if translation not found (uses key if None)

        Returns:
            English translation or default/key if not found
        """
        loc = cls.load_localization()
        if default is None:
            default = key
        translation = loc.get(key, _MISSING_LOCALIZATION_OVERRIDES.get(key, default))

        # If no translation found and it looks like a key, make it readable
        if translation == key and '_' in key:
            # Convert TECH_FRAGMENT_NAME -> Tech Fragment Name
            words = key.replace('_NAME', '').replace('_DESC', '').replace('_SUBTITLE', '').split('_')
            # UI_* keys are common internal prefixes; drop them for cleaner fallback names.
            if words and words[0] == 'UI':
                words = words[1:]
            translation = ' '.join(word.capitalize() for word in words if word)

        # Apply title case with lowercase conjunctions for name keys
        if key.endswith('_NAME') and isinstance(translation, str):
            translation = title_case_name(translation)

        # Remove game markup tags (<TECHNOLOGY>, <>, etc.) so output is plain text
        translation = strip_markup_tags(translation)
        # Convert control placeholders to readable labels.
        translation = normalize_control_tokens(translation)

        return translation

    @staticmethod
    def get_property_value(element: ET.Element, name: str, default: str = '') -> str:
        """
        Extract value attribute from a Property element by name.

        Args:
            element: Parent XML element
            name: Property name to find
            default: Default value if not found

        Returns:
            Property value as string, or default if not found
        """
        if element is None:
            return default
        # Fast path: direct child lookup first, then deep search fallback.
        prop = element.find(f'./Property[@name="{name}"]')
        if prop is None:
            prop = element.find(f'.//Property[@name="{name}"]')
        return prop.get('value', default) if prop is not None else default

    @staticmethod
    def get_nested_enum(element: ET.Element, outer_name: str, inner_name: str = None, default: str = '') -> str:
        """
        Get value from nested enum, e.g. <Property name="Rarity" value="GcRarity"><Property name="Rarity" value="Common"/></Property>.
        Returns the inner value (e.g. "Common"). If inner_name is None, uses outer_name for both.
        """
        name = inner_name if inner_name is not None else outer_name
        outer = element.find(f'.//Property[@name="{outer_name}"]')
        if outer is None:
            return default
        inner = outer.find(f'Property[@name="{name}"]')
        return inner.get('value', default) if inner is not None else default

    @staticmethod
    def parse_value(value_str: str) -> Any:
        """
        Parse a string value to appropriate Python type.

        Handles:
        - Booleans: "true"/"false" → bool
        - Integers: "1124" → int
        - Floats: "0.793" or "3.0" → float
        - Strings: Everything else → str

        Args:
            value_str: String value from EXML

        Returns:
            Parsed value in appropriate type
        """
        if not value_str:
            return ''

        # Check for boolean
        if value_str.lower() in ('true', 'false'):
            return value_str.lower() == 'true'

        # Fast skip for obvious non-numeric values to avoid exception-heavy parsing.
        if value_str[0] not in ('-', '+') and not value_str[0].isdigit():
            return value_str

        # Try numeric parsing
        try:
            # Try float first (works for both int and float)
            num = float(value_str)
            # If it's a whole number and has no decimal point, return int
            if '.' not in value_str and num.is_integer():
                return int(num)
            return num
        except ValueError:
            # It's a string
            return value_str

    @staticmethod
    def parse_colour(colour_element: Optional[ET.Element]) -> str:
        """
        Convert RGBA colour to hex string.

        Args:
            colour_element: XML element containing R, G, B, A properties

        Returns:
            Hex colour string (e.g., "FF5733") or "FFFFFF" if None
        """
        if colour_element is None:
            return 'FFFFFF'

        parser = EXMLParser()
        r = int(float(parser.get_property_value(colour_element, 'R', '1')) * 255)
        g = int(float(parser.get_property_value(colour_element, 'G', '1')) * 255)
        b = int(float(parser.get_property_value(colour_element, 'B', '1')) * 255)

        return f"{r:02X}{g:02X}{b:02X}"

    @staticmethod
    def parse_array(parent_element: ET.Element, property_name: str, item_parser: Callable) -> list:
        """
        Parse an array property containing multiple items.

        Args:
            parent_element: Parent XML element
            property_name: Name of the array property
            item_parser: Function to parse each array item

        Returns:
            List of parsed items
        """
        items = []
        array_element = parent_element.find(f'.//Property[@name="{property_name}"]')

        if array_element is not None:
            for item_element in array_element.findall('./Property'):
                parsed_item = item_parser(item_element)
                if parsed_item is not None:
                    items.append(parsed_item)

        return items

    @staticmethod
    def is_template_reference(value: Optional[str]) -> bool:
        """
        Check if a value string is a template reference.

        Args:
            value: Value string from Property element

        Returns:
            True if it's a template reference (ends with .xml or is a Gc* type)
        """
        return value is not None and (value.endswith('.xml') or value.startswith('Gc'))

    @staticmethod
    def load_xml(filepath: str) -> ET.Element:
        """
        Load and parse an XML/MXML file.

        Args:
            filepath: Path to EXML/MXML file

        Returns:
            Root element of the XML tree
        """
        path = Path(filepath)
        key = str(path.resolve())
        mtime = path.stat().st_mtime

        cached = EXMLParser._xml_cache.get(key)
        if cached is not None:
            cached_mtime, cached_root = cached
            if cached_mtime == mtime:
                return cached_root

        tree = ET.parse(filepath)
        root = tree.getroot()
        EXMLParser._xml_cache[key] = (mtime, root)
        return root

    @classmethod
    def clear_xml_cache(cls) -> None:
        """Clear cached XML roots (useful before a fresh extraction run)."""
        cls._xml_cache.clear()
