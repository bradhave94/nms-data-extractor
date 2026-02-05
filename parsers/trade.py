"""Parse Trade goods from Products table"""
import xml.etree.ElementTree as ET
from .base_parser import EXMLParser, normalize_game_icon_path
from pathlib import Path


def parse_trade(mxml_path: str) -> list:
    """
    Parse Trade goods from nms_reality_gcproducttable.MXML.

    Trade items are products with TradeCategory set.
    Note: mxml_path is ignored - we read from Products table directly.
    """
    parser = EXMLParser()
    parser.load_localization()

    # Read from Products table
    products_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'
    root = parser.load_xml(str(products_path))

    trade_items = []
    trade_counter = 1

    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return trade_items

    for item_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            # Check if this is a trade item OR smuggled goods
            trade_cat_prop = item_elem.find('.//Property[@name="TradeCategory"]//Property[@name="TradeCategory"]')
            trade_category = ''

            if trade_cat_prop is not None:
                trade_category = trade_cat_prop.get('value', '')

            # Extract basic info to check subtitle
            item_id = parser.get_property_value(item_elem, 'ID', '')
            name_key = parser.get_property_value(item_elem, 'Name', '')
            subtitle_key = parser.get_property_value(item_elem, 'Subtitle', '')
            description_key = parser.get_property_value(item_elem, 'Description', '')

            # Translate to English
            name = parser.translate(name_key, item_id)
            subtitle = parser.translate(subtitle_key, '')
            description = parser.translate(description_key, '')

            # Filter: Only include items with "Trade Goods" or "Smuggled Goods" in subtitle
            is_trade_goods = subtitle.startswith('Trade Goods')
            is_smuggled_goods = subtitle.startswith('Smuggled Goods')

            if not (is_trade_goods or is_smuggled_goods):
                continue

            # Skip if trade goods but no TradeCategory (this shouldn't happen but just in case)
            if is_trade_goods and (not trade_category or trade_category == 'None'):
                continue

            # Extract Icon path from game (matches data/EXTRACTED/textures/...)
            icon_prop = item_elem.find('.//Property[@name="Icon"]')
            icon_filename = parser.get_property_value(icon_prop, 'Filename', '') if icon_prop is not None else ''
            icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''
            if not icon_path:
                continue

            # Extract color
            colour_elem = item_elem.find('.//Property[@name="Colour"]')
            colour = parser.parse_colour(colour_elem)

            # Extract numeric values
            base_value = parser.parse_value(parser.get_property_value(item_elem, 'BaseValue', '0'))
            stack_mult = parser.parse_value(parser.get_property_value(item_elem, 'StackMultiplier', '1'))

            # Create trade item entry
            trade_item = {
                'Id': item_id,
                'Icon': f"{item_id}.png",
                'IconPath': icon_path,
                'Name': name,
                'Group': subtitle if subtitle else f'Trade Goods ({trade_category})',
                'Description': description,
                'BaseValueUnits': base_value,
                'CurrencyType': 'Credits',
                'MaxStackSize': stack_mult,
                'Colour': colour,
                'CdnUrl': '',  # Build from Icon path: baseUrl + icon (e.g. EXTRACTED or your CDN)
                'Usages': [],
                'BlueprintCost': 1,
                'BlueprintCostType': 'None',
                'BlueprintSource': 0,
                'RequiredItems': [],
                'StatBonuses': [],
                'ConsumableRewardTexts': []
            }

            trade_items.append(trade_item)
            trade_counter += 1

        except Exception as e:
            print(f"Warning: Skipped trade item due to error: {e}")
            continue

    print(f"[OK] Parsed {len(trade_items)} trade items")
    return trade_items
