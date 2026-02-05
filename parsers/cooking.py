"""Parse Cooking from MXML to JSON"""
import xml.etree.ElementTree as ET
from .base_parser import EXMLParser, normalize_game_icon_path
from pathlib import Path


def parse_cooking(mxml_path: str) -> list:
    """
    Parse consumableitemtable.MXML to Cooking.json format.

    This references product IDs from the Products table.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    parser.load_localization()

    # Load product details from Products table to get names/descriptions
    products_lookup = {}
    products_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'
    if products_path.exists():
        prod_root = parser.load_xml(str(products_path))
        table_prop = prod_root.find('.//Property[@name="Table"]')
        if table_prop:
            counter = 1
            for item in table_prop.findall('./Property[@name="Table"]'):
                item_id = parser.get_property_value(item, 'ID', '')
                name_key = parser.get_property_value(item, 'Name', '')
                subtitle_key = parser.get_property_value(item, 'Subtitle', '')
                description_key = parser.get_property_value(item, 'Description', '')
                base_value = parser.parse_value(parser.get_property_value(item, 'BaseValue', '0'))
                stack_mult = parser.parse_value(parser.get_property_value(item, 'StackMultiplier', '1'))
                cooking_value = parser.parse_value(parser.get_property_value(item, 'CookingValue', '0'))

                colour_elem = item.find('.//Property[@name="Colour"]')
                colour = parser.parse_colour(colour_elem)

                # Icon path from game (matches data/EXTRACTED/textures/...)
                icon_prop = item.find('.//Property[@name="Icon"]')
                icon_filename = parser.get_property_value(icon_prop, 'Filename', '') if icon_prop is not None else ''
                icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''

                if item_id:
                    products_lookup[item_id] = {
                        'counter': counter,
                        'IconPath': icon_path,
                        'Name': parser.translate(name_key, item_id),
                        'Group': parser.translate(subtitle_key, ''),
                        'Description': parser.translate(description_key, ''),
                        'BaseValueUnits': base_value,
                        'MaxStackSize': stack_mult,
                        'CookingValue': cooking_value,
                        'Colour': colour
                    }
                    counter += 1

    print(f"[OK] Loaded {len(products_lookup)} products for lookup")

    cooking_items = []

    # Navigate to Table property
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return cooking_items

    # Get all consumable IDs
    for item_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            item_id = parser.get_property_value(item_elem, 'ID', '')
            if not item_id:
                continue

            # Look up in products
            product_info = products_lookup.get(item_id)
            if not product_info:
                continue  # Skip if not a food product
            if not product_info.get('IconPath'):
                continue

            # Create cooking entry from product info (Icon from game path)
            cooking = {
                'Id': item_id,
                'Icon': f"{item_id}.png",
                'IconPath': product_info.get('IconPath', ''),
                'Name': product_info['Name'],
                'Group': product_info['Group'],
                'Description': product_info['Description'],
                'BaseValueUnits': product_info['BaseValueUnits'],
                'CurrencyType': 'Credits',
                'MaxStackSize': product_info['MaxStackSize'],
                'Colour': product_info['Colour'],
                'CookingValue': product_info['CookingValue'],
                'CdnUrl': '',  # Build from Icon path: baseUrl + icon (e.g. EXTRACTED or your CDN)
                'Usages': [],
                'BlueprintCost': 0,
                'BlueprintCostType': 'None',
                'BlueprintSource': 0,
                'RequiredItems': [],
                'StatBonuses': [],
                'ConsumableRewardTexts': []
            }

            cooking_items.append(cooking)

        except Exception as e:
            print(f"Warning: Skipped cooking item due to error: {e}")
            continue

    print(f"[OK] Parsed {len(cooking_items)} cooking items")
    return cooking_items
