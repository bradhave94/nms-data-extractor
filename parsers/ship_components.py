"""Parser for modular ship customization components."""
from .base_parser import EXMLParser, normalize_game_icon_path

# Manual mapping of subtitle keys to ship component groups
SUBTITLE_TO_GROUP = {
    'UI_DROPSHIP_PART_SUB': 'Hauler Starship Component',
    'UI_FIGHTER_PART_SUB': 'Fighter Starship Component',
    'UI_SAIL_PART_SUB': 'Solar Starship Component',
    'UI_SCIENTIFIC_PART_SUB': 'Explorer Starship Component',
    'UI_FOS_BI_BODY_SUB': 'Living Ship Component',
    'UI_FOS_BI_TAIL_SUB': 'Living Ship Component',
    'UI_FOS_HEAD_SUB': 'Living Ship Component',
    'UI_FOS_LIMBS_SUB': 'Living Ship Component',
    'UI_SHIP_CORE_A_SUB': 'Starship Core Component',
    'UI_SHIP_CORE_B_SUB': 'Starship Core Component',
    'UI_SHIP_CORE_C_SUB': 'Starship Core Component',
    'UI_SHIP_CORE_S_SUB': 'Starship Core Component',
}

def parse_ship_components(mxml_path: str) -> list:
    """Parse modular ship customization components from MXML file.

    Args:
        mxml_path: Path to nms_modularcustomisationproducts.MXML

    Returns:
        List of ship component dictionaries with translated names and groups
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    # Load localization
    parser.load_localization()

    components = []

    # Navigate to Table property
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return components

    # Each product is a Property element with value="GcProductData"
    for product_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            # Extract basic info
            item_id = parser.get_property_value(product_elem, 'ID', '')
            name_key = parser.get_property_value(product_elem, 'Name', '')
            subtitle_key = parser.get_property_value(product_elem, 'Subtitle', '')
            desc_key = parser.get_property_value(product_elem, 'Description', '')
            base_value = int(parser.get_property_value(product_elem, 'BaseValue', '0'))

            # Get icon path from game (matches data/EXTRACTED/textures/...)
            icon_elem = product_elem.find('.//Property[@name="Icon"]/Property[@name="Filename"]')
            icon_raw = icon_elem.get('value', '') if icon_elem is not None else ''
            icon_path = normalize_game_icon_path(icon_raw) if icon_raw else ''

            # Map subtitle to group
            group = SUBTITLE_TO_GROUP.get(subtitle_key, 'Starship Component')

            # Translate name and description
            name = parser.translate(name_key) or name_key
            description = parser.translate(desc_key) or ''

            # Build component dict
            component = {
                'Id': item_id,
                'Name': name,
                'Group': group,
                'Description': description,
                'BaseValue': base_value,
                'Icon': icon_path,
            }

            components.append(component)

        except Exception as e:
            print(f"Warning: Error parsing ship component: {e}")
            continue

    print(f"[OK] Parsed {len(components)} ship components")
    return components
