"""Parse RawMaterials (Substances) from MXML to JSON"""
import xml.etree.ElementTree as ET
from .base_parser import EXMLParser, normalize_game_icon_path


def parse_rawmaterials(mxml_path: str) -> list:
    """
    Parse nms_reality_gcsubstancetable.MXML to RawMaterials.json format.

    Similar structure to Products.json
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    parser.load_localization()

    materials = []
    material_counter = 1

    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return materials

    for item_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            # Extract basic info
            item_id = parser.get_property_value(item_elem, 'ID', f'SUBSTANCE_{material_counter}')
            name_key = parser.get_property_value(item_elem, 'Name', '')
            subtitle_key = parser.get_property_value(item_elem, 'Subtitle', '')
            description_key = parser.get_property_value(item_elem, 'Description', '')

            # Translate to English
            name = parser.translate(name_key, name_key)
            subtitle = parser.translate(subtitle_key, subtitle_key)
            description = parser.translate(description_key, description_key)

            # Extract Icon path from game (matches data/EXTRACTED/textures/...)
            icon_prop = item_elem.find('.//Property[@name="Icon"]')
            icon_filename = ''
            if icon_prop is not None:
                icon_filename = parser.get_property_value(icon_prop, 'Filename', '')
            icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''
            if not icon_path:
                continue

            # Extract color
            colour_elem = item_elem.find('.//Property[@name="Colour"]')
            colour = parser.parse_colour(colour_elem)

            # Extract numeric values
            base_value = parser.parse_value(parser.get_property_value(item_elem, 'BaseValue', '0'))

            # Category (SubstanceCategory), Rarity, CookingIngredient, Symbol
            category = parser.get_nested_enum(item_elem, 'Category', 'SubstanceCategory', '')
            rarity = parser.get_nested_enum(item_elem, 'Rarity', 'Rarity', '')
            cooking_ingredient = parser.parse_value(parser.get_property_value(item_elem, 'CookingIngredient', 'false'))
            symbol_key = parser.get_property_value(item_elem, 'Symbol', '')
            symbol = parser.translate(symbol_key, '') if symbol_key else ''

            # Create material entry
            material = {
                'Id': item_id,
                'Icon': f"{item_id}.png",
                'IconPath': icon_path,
                'Name': name,
                'Group': subtitle,
                'Description': description,
                'BaseValueUnits': base_value,
                'CurrencyType': 'Credits',
                'Colour': colour,
                'CdnUrl': '',  # Build from Icon path: baseUrl + icon (e.g. EXTRACTED or your CDN)
                'Usages': [],
                'BlueprintCost': 0,
                'BlueprintCostType': 'None',
                'BlueprintSource': 0,
                'RequiredItems': [],
                'StatBonuses': [],
                'ConsumableRewardTexts': [],
                'Category': category or None,
                'Rarity': rarity or None,
                'CookingIngredient': cooking_ingredient,
                'Symbol': symbol or None,
            }

            materials.append(material)
            material_counter += 1

        except Exception as e:
            print(f"Warning: Skipped material due to error: {e}")
            continue

    print(f"[OK] Parsed {len(materials)} raw materials")
    return materials
