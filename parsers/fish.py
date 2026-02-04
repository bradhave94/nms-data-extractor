"""Parse Fish from MXML to JSON"""
import xml.etree.ElementTree as ET
import re
from .base_parser import EXMLParser, normalize_game_icon_path, title_case_name
from pathlib import Path


# Cache for product details
_product_cache = None


def _readable_fallback_from_id(item_id: str) -> str:
    """When localization is missing, derive a readable name from ID (e.g. F_JELLYCHILD -> Jellychild)."""
    if not item_id:
        return ''
    # Strip common prefixes (F_, S15_, etc.) then replace _ with space and title-case
    s = item_id.strip()
    for prefix in ('F_', 'S15_', 'S19_', 'S10_'):
        if s.upper().startswith(prefix.upper()):
            s = s[len(prefix):]
            break
    s = re.sub(r'_+', ' ', s).strip()
    return title_case_name(s) if s else item_id


def _is_likely_untranslated(name: str, item_id: str) -> bool:
    """True if name looks like the fallback (title-cased ID) when the locale key is missing."""
    if not name or not item_id:
        return False
    # When key is missing, translate() returns default then title_case_name() is applied -> "F_JELLYCHILD" -> "F_jellychild"
    default_name = title_case_name(item_id)
    return name == default_name or name == item_id


def _load_product_details():
    """Load product details for fish ProductIDs"""
    global _product_cache
    if _product_cache is not None:
        return _product_cache

    _product_cache = {}
    parser = EXMLParser()
    parser.load_localization()

    # Load from Products table
    products_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'
    if products_path.exists():
        root = parser.load_xml(str(products_path))
        table_prop = root.find('.//Property[@name="Table"]')
        if table_prop:
            for item in table_prop.findall('./Property[@name="Table"]'):
                item_id = parser.get_property_value(item, 'ID', '')
                name_key = parser.get_property_value(item, 'Name', '')
                name_lower_key = parser.get_property_value(item, 'NameLower', '')
                subtitle_key = parser.get_property_value(item, 'Subtitle', '')
                description_key = parser.get_property_value(item, 'Description', '')
                base_value = parser.parse_value(parser.get_property_value(item, 'BaseValue', '0'))
                stack_mult = parser.parse_value(parser.get_property_value(item, 'StackMultiplier', '1'))
                cooking_value = parser.parse_value(parser.get_property_value(item, 'CookingValue', '0'))

                # Extract color
                colour_elem = item.find('.//Property[@name="Colour"]')
                colour = parser.parse_colour(colour_elem)

                # Icon path from game (matches data/EXTRACTED/textures/...)
                icon_prop = item.find('.//Property[@name="Icon"]')
                icon_filename = parser.get_property_value(icon_prop, 'Filename', '') if icon_prop is not None else ''
                icon = normalize_game_icon_path(icon_filename) if icon_filename else ''

                if item_id:
                    name = parser.translate(name_key, item_id)
                    if _is_likely_untranslated(name, item_id) and name_lower_key:
                        name = parser.translate(name_lower_key, name)
                    if _is_likely_untranslated(name, item_id):
                        name = _readable_fallback_from_id(item_id)

                    group = parser.translate(subtitle_key, '')
                    description = parser.translate(description_key, '')

                    _product_cache[item_id] = {
                        'Icon': icon,
                        'Name': name,
                        'Group': group,
                        'Description': description,
                        'BaseValueUnits': base_value,
                        'MaxStackSize': stack_mult,
                        'CookingValue': cooking_value,
                        'Colour': colour
                    }

    print(f"[OK] Loaded {len(_product_cache)} product details for lookup")
    return _product_cache


def parse_fish(mxml_path: str) -> list:
    """
    Parse fishdatatable.MXML to Fish.json format.

    Fish table references ProductIDs that need to be looked up in Products table.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    parser.load_localization()

    # Load product details
    products = _load_product_details()

    fish_list = []
    fish_counter = 1

    # Navigate to Fish property
    fish_prop = root.find('.//Property[@name="Fish"]')
    if fish_prop is None:
        print("Warning: Could not find Fish property in MXML")
        return fish_list

    for fish_elem in fish_prop.findall('./Property[@name="Fish"]'):
        try:
            # Get ProductID to look up details
            product_id = parser.get_property_value(fish_elem, 'ProductID', '')
            if not product_id:
                continue

            # Get product details
            product_details = products.get(product_id, {})

            # Create fish entry (Icon from product game path, or fallback)
            icon = product_details.get('Icon', '') or f"curiosities/{fish_counter}.png"
            name = product_details.get('Name', product_id)
            group = product_details.get('Group', '') or 'Fish'
            fish = {
                'Id': product_id,  # Use product ID as fish ID
                'Icon': icon,
                'Name': name,
                'Group': group,
                'Description': product_details.get('Description', ''),
                'BaseValueUnits': product_details.get('BaseValueUnits', 0),
                'CurrencyType': 'Credits',
                'MaxStackSize': product_details.get('MaxStackSize', 1),
                'Colour': product_details.get('Colour', 'FFFFFF'),
                'CookingValue': product_details.get('CookingValue', 0),
                'Usages': [],
                'BlueprintCost': 0,
                'BlueprintCostType': 'None',
                'BlueprintSource': 0,
                'RequiredItems': [],
                'StatBonuses': [],
                'ConsumableRewardTexts': [],
                'fishId': f'fish{fish_counter}'
            }

            fish_list.append(fish)
            fish_counter += 1

        except Exception as e:
            print(f"Warning: Skipped fish due to error: {e}")
            continue

    print(f"[OK] Parsed {len(fish_list)} fish")
    return fish_list
