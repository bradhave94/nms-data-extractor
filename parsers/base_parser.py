"""Base XML Parser for EXML/MXML files"""
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional, Callable
import json
from pathlib import Path

# Words that stay lowercase in title case (conjunctions, articles, short prepositions)
_LOWERCASE_WORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'of', 'in', 'on', 'at', 'to', 'for',
    'with', 'by', 'as', 'from', 'into', 'onto', 'upon', 'nor', 'so', 'yet',
})


def strip_markup_tags(text: str) -> str:
    """
    Remove game markup tags from text, e.g. <TECHNOLOGY>...</>, <>, <IMG>...</>.
    """
    if not text or not isinstance(text, str):
        return text
    return re.sub(r'<[^>]*>', '', text)


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


class EXMLParser:
    """Base class for EXML/MXML parsing with common utilities"""

    _localization = None  # Cache for localization data

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
    def translate(cls, key: str, default: str = None) -> str:
        """
        Translate a localization key to English.

        Args:
            key: Localization key (e.g., "TECH_FRAGMENT_NAME")
            default: Default value if translation not found (uses key if None)

        Returns:
            English translation or default/key if not found
        """
        loc = cls.load_localization()
        if default is None:
            default = key
        translation = loc.get(key, default)

        # If no translation found and it looks like a key, make it readable
        if translation == key and '_' in key:
            # Convert TECH_FRAGMENT_NAME -> Tech Fragment Name
            words = key.replace('_NAME', '').replace('_DESC', '').replace('_SUBTITLE', '').split('_')
            translation = ' '.join(word.capitalize() for word in words if word)

        # Apply title case with lowercase conjunctions for name keys
        if key.endswith('_NAME') and isinstance(translation, str):
            translation = title_case_name(translation)

        # Remove game markup tags (<TECHNOLOGY>, <>, etc.) so output is plain text
        translation = strip_markup_tags(translation)

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
        tree = ET.parse(filepath)
        return tree.getroot()
