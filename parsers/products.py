"""Parse Products from MXML to JSON"""
import xml.etree.ElementTree as ET
from .base_parser import EXMLParser, normalize_game_icon_path


def parse_products(mxml_path: str) -> list:
    """
    Parse nms_reality_gcproducttable.MXML to Products.json format.

    Target JSON structure:
    Icon is the item ID. IconPath is the game texture path (matches data/EXTRACTED/textures/...).
    {
        "Id": "prod1",
        "Icon": "prod1",
        "IconPath": "textures/ui/frontend/icons/u4products/product.casing.dds",
        "Name": "Antimatter",
        "Group": "Crafted Technology Component",
        "Description": "...",
        "BaseValueUnits": 5233.0,
        "CurrencyType": "Credits",
        "MaxStackSize": 10.0,
        "Colour": "C01746",
        "CdnUrl": "",
        "Usages": [],
        "BlueprintCost": 1,
        "BlueprintCostType": "None",
        "BlueprintSource": 0,
        "RequiredItems": [{"Id": "raw2", "Quantity": 20}],
        "StatBonuses": [],
        "ConsumableRewardTexts": []
    }

    Args:
        mxml_path: Path to the MXML file

    Returns:
        List of product dictionaries
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    # Load localization for name translations
    parser.load_localization()

    products = []
    product_counter = 1

    # Navigate to Table property
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return products

    # Each product is a Property element with value="GcProductData"
    for product_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            # Extract basic info
            product_id = parser.get_property_value(product_elem, 'ID', f'PRODUCT_{product_counter}')
            name_key = parser.get_property_value(product_elem, 'Name', '')
            subtitle_key = parser.get_property_value(product_elem, 'Subtitle', '')
            description_key = parser.get_property_value(product_elem, 'Description', '')

            # Translate to English
            name = parser.translate(name_key, name_key)
            subtitle = parser.translate(subtitle_key, subtitle_key)
            description = parser.translate(description_key, description_key)

            # Extract Icon path from game (matches data/EXTRACTED/textures/...)
            icon_prop = product_elem.find('.//Property[@name="Icon"]')
            icon_filename = ''
            if icon_prop is not None:
                icon_filename = parser.get_property_value(icon_prop, 'Filename', '')
            icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''
            if not icon_path:
                continue

            # Extract color
            colour_elem = product_elem.find('.//Property[@name="Colour"]')
            colour = parser.parse_colour(colour_elem)

            # Extract numeric values
            base_value = parser.parse_value(parser.get_property_value(product_elem, 'BaseValue', '0'))
            stack_multiplier = parser.parse_value(parser.get_property_value(product_elem, 'StackMultiplier', '1'))
            recipe_cost = parser.parse_value(parser.get_property_value(product_elem, 'RecipeCost', '0'))

            # Extract requirements
            required_items = []
            requirements_prop = product_elem.find('.//Property[@name="Requirements"]')
            if requirements_prop is not None:
                for req_elem in requirements_prop.findall('./Property'):
                    req_id = parser.get_property_value(req_elem, 'ID', '')
                    req_amount = parser.get_property_value(req_elem, 'Amount', '1')
                    if req_id:
                        required_items.append({
                            'Id': req_id,
                            'Quantity': parser.parse_value(req_amount)
                        })

            # Determine usages (based on boolean properties)
            usages = []
            is_craftable = parser.get_property_value(product_elem, 'IsCraftable', 'false')
            is_cooking = parser.get_property_value(product_elem, 'CookingIngredient', 'false')
            egg_modifier = parser.get_property_value(product_elem, 'EggModifierIngredient', 'false')
            good_for_selling = parser.get_property_value(product_elem, 'GoodForSelling', 'false')

            if parser.parse_value(is_craftable):
                usages.append('HasUsedToCraft')
            if parser.parse_value(is_cooking):
                usages.append('HasCookingProperties')
            if parser.parse_value(egg_modifier):
                usages.append('IsEggIngredient')
            if parser.parse_value(good_for_selling):
                usages.append('HasDevProperties')

            # Nested enums and extra fields
            rarity = parser.get_nested_enum(product_elem, 'Rarity', 'Rarity', '')
            legality = parser.get_nested_enum(product_elem, 'Legality', 'Legality', '')
            trade_category = parser.get_nested_enum(product_elem, 'TradeCategory', 'TradeCategory', '')
            wiki_category = parser.get_property_value(product_elem, 'WikiCategory', '')
            consumable = parser.parse_value(parser.get_property_value(product_elem, 'Consumable', 'false'))

            # Create product entry
            product = {
                'Id': product_id,  # Use actual game ID
                'Icon': f"{product_id}.png",
                'IconPath': icon_path,
                'Name': name,
                'Group': subtitle,
                'Description': description,
                'BaseValueUnits': base_value,
                'CurrencyType': 'Credits',  # Default to Credits
                'MaxStackSize': stack_multiplier,
                'Colour': colour,
                'CdnUrl': '',  # Build from Icon path: baseUrl + icon (e.g. EXTRACTED or your CDN)
                'Usages': usages,
                'BlueprintCost': recipe_cost,
                'BlueprintCostType': 'None',  # May need to extract this
                'BlueprintSource': 0,  # May need to extract this
                'RequiredItems': required_items,
                'StatBonuses': [],  # May need to extract this
                'ConsumableRewardTexts': [],  # May need to extract this
                'Rarity': rarity or None,
                'Legality': legality or None,
                'TradeCategory': trade_category or None,
                'WikiCategory': wiki_category or None,
                'Consumable': consumable,
                'CookingIngredient': parser.parse_value(is_cooking),
                'GoodForSelling': parser.parse_value(good_for_selling),
                'EggModifierIngredient': parser.parse_value(egg_modifier),
            }

            products.append(product)
            product_counter += 1

        except Exception as e:
            print(f"Warning: Skipped product due to error: {e}")
            continue

    print(f"[OK] Parsed {len(products)} products")
    return products
