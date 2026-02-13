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
            base_value = parser.parse_value(parser.get_property_value(product_elem, 'BaseValue', '0'))

            # Get icon path from game (matches data/EXTRACTED/textures/...)
            icon_elem = product_elem.find('.//Property[@name="Icon"]/Property[@name="Filename"]')
            icon_raw = icon_elem.get('value', '') if icon_elem is not None else ''
            icon_path = normalize_game_icon_path(icon_raw) if icon_raw else ''
            if not icon_path:
                continue

            # Map subtitle to group
            group = SUBTITLE_TO_GROUP.get(subtitle_key, 'Starship Component')

            # Translate name and description
            name = parser.translate(name_key) or name_key
            description = parser.translate(desc_key) or ''

            # Enriched product metadata
            hero_icon_raw = parser.get_property_value(
                product_elem.find('.//Property[@name="HeroIcon"]'),
                'Filename',
                '',
            )
            hero_icon_path = normalize_game_icon_path(hero_icon_raw) if hero_icon_raw else ''

            colour_elem = product_elem.find('.//Property[@name="Colour"]')
            colour = parser.parse_colour(colour_elem)

            rarity = parser.get_nested_enum(product_elem, 'Rarity', 'Rarity', '')
            legality = parser.get_nested_enum(product_elem, 'Legality', 'Legality', '')
            trade_category = parser.get_nested_enum(product_elem, 'TradeCategory', 'TradeCategory', '')
            product_category = parser.get_nested_enum(product_elem, 'Type', 'ProductCategory', '')
            substance_category = parser.get_nested_enum(product_elem, 'Category', 'SubstanceCategory', '')
            pin_scannable = parser.get_nested_enum(
                product_elem,
                'PinObjectiveScannableType',
                'ScanIconType',
                '',
            )

            # Build component dict
            component = {
                'Id': item_id,
                'Name': name,
                'Group': group,
                'Description': description,
                'BaseValue': base_value,
                'BaseValueUnits': base_value,
                'CurrencyType': 'Credits',
                'Icon': f"{item_id}.png",
                'IconPath': icon_path,
                'HeroIconPath': hero_icon_path or None,
                'BuildableShipTechID': parser.get_property_value(product_elem, 'BuildableShipTechID', '') or None,
                'GroupID': parser.get_property_value(product_elem, 'GroupID', '') or None,
                'Colour': colour,
                'Rarity': rarity or None,
                'Legality': legality or None,
                'TradeCategory': trade_category or None,
                'WikiCategory': parser.get_property_value(product_elem, 'WikiCategory', '') or None,
                'SubstanceCategory': substance_category or None,
                'ProductCategory': product_category or None,
                'MaxStackSize': parser.parse_value(parser.get_property_value(product_elem, 'StackMultiplier', '1')),
                'BlueprintCost': parser.parse_value(parser.get_property_value(product_elem, 'RecipeCost', '0')),
                'ChargeValue': parser.parse_value(parser.get_property_value(product_elem, 'ChargeValue', '0')),
                'DefaultCraftAmount': parser.parse_value(
                    parser.get_property_value(product_elem, 'DefaultCraftAmount', '1')
                ),
                'CraftAmountStepSize': parser.parse_value(
                    parser.get_property_value(product_elem, 'CraftAmountStepSize', '1')
                ),
                'CraftAmountMultiplier': parser.parse_value(
                    parser.get_property_value(product_elem, 'CraftAmountMultiplier', '1')
                ),
                'SpecificChargeOnly': parser.parse_value(
                    parser.get_property_value(product_elem, 'SpecificChargeOnly', 'false')
                ),
                'NormalisedValueOnWorld': parser.parse_value(
                    parser.get_property_value(product_elem, 'NormalisedValueOnWorld', '0')
                ),
                'NormalisedValueOffWorld': parser.parse_value(
                    parser.get_property_value(product_elem, 'NormalisedValueOffWorld', '0')
                ),
                'EconomyInfluenceMultiplier': parser.parse_value(
                    parser.get_property_value(product_elem, 'EconomyInfluenceMultiplier', '0')
                ),
                'IsCraftable': parser.parse_value(parser.get_property_value(product_elem, 'IsCraftable', 'false')),
                'DeploysInto': parser.get_property_value(product_elem, 'DeploysInto', '') or None,
                'PinObjective': parser.get_property_value(product_elem, 'PinObjective', '') or None,
                'PinObjectiveTip': parser.get_property_value(product_elem, 'PinObjectiveTip', '') or None,
                'PinObjectiveMessage': parser.get_property_value(product_elem, 'PinObjectiveMessage', '') or None,
                'PinObjectiveScannableType': pin_scannable or None,
                'PinObjectiveEasyToRefine': parser.parse_value(
                    parser.get_property_value(product_elem, 'PinObjectiveEasyToRefine', 'false')
                ),
                'NeverPinnable': parser.parse_value(parser.get_property_value(product_elem, 'NeverPinnable', 'false')),
                'CanSendToOtherPlayers': parser.parse_value(
                    parser.get_property_value(product_elem, 'CanSendToOtherPlayers', 'true')
                ),
            }

            components.append(component)

        except Exception as e:
            print(f"Warning: Error parsing ship component: {e}")
            continue

    print(f"[OK] Parsed {len(components)} ship components")
    return components
