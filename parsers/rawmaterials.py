"""Parse RawMaterials (Substances) from MXML to JSON"""
from .base_parser import (
    EXMLParser,
    normalize_game_icon_path,
    unresolved_localization_key_count,
)


def parse_rawmaterials(mxml_path: str) -> list:
    """
    Parse nms_reality_gcsubstancetable.MXML to RawMaterials.json format.

    Similar structure to Products.json
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

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
            name_lower_key = parser.get_property_value(item_elem, 'NameLower', '')
            subtitle_key = parser.get_property_value(item_elem, 'Subtitle', '')
            description_key = parser.get_property_value(item_elem, 'Description', '')
            if unresolved_localization_key_count(localization, name_key, subtitle_key, description_key) >= 2:
                continue

            # Translate to English
            name = parser.translate(name_key, name_key)
            name_lower = parser.translate(name_lower_key, name_lower_key) if name_lower_key else ''
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
            charge_value = parser.parse_value(parser.get_property_value(item_elem, 'ChargeValue', '0'))
            stack_multiplier = parser.parse_value(parser.get_property_value(item_elem, 'StackMultiplier', '1'))
            economy_influence_multiplier = parser.parse_value(
                parser.get_property_value(item_elem, 'EconomyInfluenceMultiplier', '0')
            )

            # Category and gameplay attributes
            category = parser.get_nested_enum(item_elem, 'Category', 'SubstanceCategory', '')
            rarity = parser.get_nested_enum(item_elem, 'Rarity', 'Rarity', '')
            legality = parser.get_nested_enum(item_elem, 'Legality', 'Legality', '')
            trade_category = parser.get_nested_enum(item_elem, 'TradeCategory', 'TradeCategory', '')
            cooking_ingredient = parser.parse_value(parser.get_property_value(item_elem, 'CookingIngredient', 'false'))
            good_for_selling = parser.parse_value(parser.get_property_value(item_elem, 'GoodForSelling', 'false'))
            easy_to_refine = parser.parse_value(parser.get_property_value(item_elem, 'EasyToRefine', 'false'))
            egg_modifier_ingredient = parser.parse_value(
                parser.get_property_value(item_elem, 'EggModifierIngredient', 'false')
            )
            wiki_enabled = parser.parse_value(parser.get_property_value(item_elem, 'WikiEnabled', 'false'))
            only_found_in_purple_systems = parser.parse_value(
                parser.get_property_value(item_elem, 'OnlyFoundInPurpleSytems', 'false')
            )

            # Objectives and wiki metadata
            pin_objective_scannable_type = parser.get_nested_enum(
                item_elem, 'PinObjectiveScannableType', 'ScanIconType', ''
            )
            wiki_mission_id = parser.get_property_value(item_elem, 'WikiMissionID', '')

            # Cost modifiers
            cost_prop = item_elem.find('.//Property[@name="Cost"]')
            price_modifiers = None
            if cost_prop is not None:
                price_modifiers = {
                    'SpaceStationMarkup': parser.parse_value(
                        parser.get_property_value(cost_prop, 'SpaceStationMarkup', '0')
                    ),
                    'LowPriceMod': parser.parse_value(parser.get_property_value(cost_prop, 'LowPriceMod', '0')),
                    'HighPriceMod': parser.parse_value(parser.get_property_value(cost_prop, 'HighPriceMod', '0')),
                    'BuyBaseMarkup': parser.parse_value(parser.get_property_value(cost_prop, 'BuyBaseMarkup', '0')),
                    'BuyMarkupMod': parser.parse_value(parser.get_property_value(cost_prop, 'BuyMarkupMod', '0')),
                }

            # Symbol text and key
            symbol_key = parser.get_property_value(item_elem, 'Symbol', '')
            symbol = parser.translate(symbol_key, '') if symbol_key else ''

            usages = []
            if cooking_ingredient:
                usages.append('HasCookingProperties')
            if good_for_selling:
                usages.append('HasDevProperties')
            if easy_to_refine:
                usages.append('HasRefinerProperties')
            if egg_modifier_ingredient:
                usages.append('IsEggIngredient')

            # Create material entry
            material = {
                'Id': item_id,
                'Icon': f"{item_id}.png",
                'IconPath': icon_path,
                'Name': name,
                'NameLower': name_lower or None,
                'Group': subtitle,
                'Description': description,
                'BaseValueUnits': base_value,
                'CurrencyType': 'Credits',
                'Colour': colour,
                'CdnUrl': '',  # Build from Icon path: baseUrl + icon (e.g. EXTRACTED or your CDN)
                'Usages': usages,
                'BlueprintCost': 0,
                'BlueprintCostType': 'None',
                'BlueprintSource': 0,
                'RequiredItems': [],
                'StatBonuses': [],
                'ConsumableRewardTexts': [],
                'Category': category or None,
                'Rarity': rarity or None,
                'Legality': legality or None,
                'TradeCategory': trade_category or None,
                'CookingIngredient': cooking_ingredient,
                'GoodForSelling': good_for_selling,
                'EasyToRefine': easy_to_refine,
                'EggModifierIngredient': egg_modifier_ingredient,
                'WikiEnabled': wiki_enabled,
                'OnlyFoundInPurpleSystems': only_found_in_purple_systems,
                'OnlyFoundInPurpleSytems': only_found_in_purple_systems,
                'ChargeValue': charge_value,
                'MaxStackSize': stack_multiplier,
                'EconomyInfluenceMultiplier': economy_influence_multiplier,
                'PriceModifiers': price_modifiers,
                'PinObjectiveScannableType': pin_objective_scannable_type or None,
                'WikiMissionID': wiki_mission_id or None,
                'Symbol': symbol or None,
            }

            materials.append(material)
            material_counter += 1

        except Exception as e:
            print(f"Warning: Skipped material due to error: {e}")
            continue

    print(f"[OK] Parsed {len(materials)} raw materials")
    return materials
