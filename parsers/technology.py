"""Parse Technology from MXML to JSON"""
from .base_parser import (
    EXMLParser,
    format_stat_type_name,
    normalize_game_icon_path,
    unresolved_localization_key_count,
)


def parse_technology(mxml_path: str) -> list:
    """
    Parse nms_reality_gctechnologytable.MXML to Technology.json format.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

    technologies = []
    tech_counter = 1

    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return technologies

    for tech_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            tech_id = parser.get_property_value(tech_elem, 'ID', f'TECH_{tech_counter}')
            name_key = parser.get_property_value(tech_elem, 'Name', '')
            subtitle_key = parser.get_property_value(tech_elem, 'Subtitle', '')
            description_key = parser.get_property_value(tech_elem, 'Description', '')
            name_lower_key = parser.get_property_value(tech_elem, 'NameLower', '')
            hint_start_key = parser.get_property_value(tech_elem, 'HintStart', '')
            hint_end_key = parser.get_property_value(tech_elem, 'HintEnd', '')
            damaged_description_key = parser.get_property_value(tech_elem, 'DamagedDescription', '')
            if unresolved_localization_key_count(localization, name_key, subtitle_key, description_key) >= 2:
                continue

            name = parser.translate(name_key, tech_id)
            name_lower = parser.translate(name_lower_key, name_lower_key) if name_lower_key else ''
            subtitle = parser.translate(subtitle_key, '')
            description = parser.translate(description_key, '')
            hint_start = parser.translate(hint_start_key, hint_start_key) if hint_start_key else ''
            hint_end = parser.translate(hint_end_key, hint_end_key) if hint_end_key else ''
            damaged_description = (
                parser.translate(damaged_description_key, damaged_description_key) if damaged_description_key else ''
            )

            # Extract Icon path from game (matches data/EXTRACTED/textures/...)
            icon_prop = tech_elem.find('.//Property[@name="Icon"]')
            icon_filename = parser.get_property_value(icon_prop, 'Filename', '') if icon_prop is not None else ''
            icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''
            if not icon_path:
                continue

            # Extract color
            colour_elem = tech_elem.find('.//Property[@name="Colour"]')
            colour = parser.parse_colour(colour_elem)

            # Extract values
            base_value = parser.parse_value(parser.get_property_value(tech_elem, 'BaseValue', '1'))
            level = parser.parse_value(parser.get_property_value(tech_elem, 'Level', '0'))
            value = parser.parse_value(parser.get_property_value(tech_elem, 'Value', '0'))
            charge_amount = parser.parse_value(parser.get_property_value(tech_elem, 'ChargeAmount', '0'))
            charge_multiplier = parser.parse_value(parser.get_property_value(tech_elem, 'ChargeMultiplier', '1'))
            build_fully_charged = parser.parse_value(parser.get_property_value(tech_elem, 'BuildFullyCharged', 'false'))
            uses_ammo = parser.parse_value(parser.get_property_value(tech_elem, 'UsesAmmo', 'false'))
            required_level = parser.parse_value(parser.get_property_value(tech_elem, 'RequiredLevel', '0'))
            fragment_cost = parser.parse_value(parser.get_property_value(tech_elem, 'FragmentCost', '0'))
            wiki_enabled = parser.parse_value(parser.get_property_value(tech_elem, 'WikiEnabled', 'false'))
            never_pinnable = parser.parse_value(parser.get_property_value(tech_elem, 'NeverPinnable', 'false'))
            is_template = parser.parse_value(parser.get_property_value(tech_elem, 'IsTemplate', 'false'))
            exclusive_primary_stat = parser.parse_value(
                parser.get_property_value(tech_elem, 'ExclusivePrimaryStat', 'false')
            )

            # Extract requirements
            required_items = []
            requirements_prop = tech_elem.find('.//Property[@name="Requirements"]')
            if requirements_prop is not None:
                for req_elem in requirements_prop.findall('./Property'):
                    req_id = parser.get_property_value(req_elem, 'ID', '')
                    req_amount = parser.get_property_value(req_elem, 'Amount', '1')
                    if req_id:
                        required_items.append({
                            'Id': req_id,
                            'Quantity': parser.parse_value(req_amount)
                        })

            # Extract stat bonuses
            stat_bonuses = []
            stat_bonuses_prop = tech_elem.find('.//Property[@name="StatBonuses"]')
            if stat_bonuses_prop is not None:
                for stat_elem in stat_bonuses_prop.findall('./Property'):
                    stat_type_prop = stat_elem.find('.//Property[@name="Stat"]//Property[@name="StatsType"]')
                    stat_type = stat_type_prop.get('value', '') if stat_type_prop is not None else ''
                    bonus = parser.get_property_value(stat_elem, 'Bonus', '0')

                    if stat_type:
                        # Convert stat type to readable name
                        stat_name = format_stat_type_name(stat_type, strip_prefixes=('Suit_',))
                        stat_bonuses.append({
                            'Name': stat_name,
                            'LocaleKeyTemplate': 'enabled',
                            'Image': stat_type.lower().split('_')[-1] if '_' in stat_type else 'enabled',
                            'Value': str(int(float(bonus)))
                        })

            # Determine usages
            usages = []
            is_chargeable = parser.parse_value(parser.get_property_value(tech_elem, 'Chargeable', 'false'))
            if is_chargeable:
                usages.append('HasChargedBy')
            usages.append('HasDevProperties')

            # Category, Rarity, Chargeable, ChargeBy, Upgrade, Core, ParentTechId, RequiredTech
            tech_category = parser.get_nested_enum(tech_elem, 'Category', 'TechnologyCategory', '')
            tech_rarity = parser.get_nested_enum(tech_elem, 'Rarity', 'TechnologyRarity', '')
            charge_by_list = []
            charge_by_prop = tech_elem.find('.//Property[@name="ChargeBy"]')
            if charge_by_prop is not None:
                for cb in charge_by_prop.findall('./Property[@name="ChargeBy"]'):
                    val = cb.get('value', '')
                    if val:
                        charge_by_list.append(val)
            upgrade = parser.parse_value(parser.get_property_value(tech_elem, 'Upgrade', 'false'))
            core = parser.parse_value(parser.get_property_value(tech_elem, 'Core', 'false'))
            parent_tech_id = parser.get_property_value(tech_elem, 'ParentTechId', '') or None
            required_tech = parser.get_property_value(tech_elem, 'RequiredTech', '') or None
            teach = parser.get_property_value(tech_elem, 'Teach', '') or None
            charge_type = parser.get_nested_enum(tech_elem, 'ChargeType', 'SubstanceCategory', '')
            ammo_id = parser.get_property_value(tech_elem, 'AmmoId', '') or None
            primary_item = parser.get_property_value(tech_elem, 'PrimaryItem', '') or None
            repair_tech = parser.parse_value(parser.get_property_value(tech_elem, 'RepairTech', 'false'))
            procedural = parser.parse_value(parser.get_property_value(tech_elem, 'Procedural', 'false'))
            broken_slot_tech = parser.get_property_value(tech_elem, 'BrokenSlotTech', '') or None
            focus_locator = parser.get_property_value(tech_elem, 'FocusLocator', '') or None
            upgrade_colour = parser.parse_colour(tech_elem.find('.//Property[@name="UpgradeColour"]'))
            link_colour = parser.parse_colour(tech_elem.find('.//Property[@name="LinkColour"]'))
            reward_group = parser.get_property_value(tech_elem, 'RewardGroup', '') or None
            required_rank = parser.parse_value(parser.get_property_value(tech_elem, 'RequiredRank', '0'))
            dispensing_race = parser.get_nested_enum(tech_elem, 'DispensingRace', 'AlienRace', '')
            tech_shop_rarity = parser.get_nested_enum(tech_elem, 'TechShopRarity', 'Rarity', '')

            cost_prop = tech_elem.find('.//Property[@name="Cost"]')
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

            # Create technology entry
            technology = {
                'Id': tech_id,
                'Icon': f"{tech_id}.png",
                'IconPath': icon_path,
                'Name': name,
                'NameLower': name_lower or None,
                'Group': subtitle,
                'Description': description,
                'HintStart': hint_start or None,
                'HintEnd': hint_end or None,
                'DamagedDescription': damaged_description or None,
                'BaseValueUnits': base_value,
                'CurrencyType': 'None',
                'Level': level,
                'Value': value,
                'Colour': colour,
                'Usages': usages,
                'BlueprintCost': 1,
                'BlueprintCostType': 'Nanites',
                'BlueprintSource': 0,
                'RequiredItems': required_items,
                'StatBonuses': stat_bonuses,
                'ConsumableRewardTexts': [],
                'Category': tech_category or None,
                'Rarity': tech_rarity or None,
                'Teach': teach,
                'Chargeable': is_chargeable,
                'ChargeAmount': charge_amount,
                'ChargeType': charge_type or None,
                'ChargeBy': charge_by_list,
                'ChargeMultiplier': charge_multiplier,
                'BuildFullyCharged': build_fully_charged,
                'UsesAmmo': uses_ammo,
                'AmmoId': ammo_id,
                'PrimaryItem': primary_item,
                'Upgrade': upgrade,
                'Core': core,
                'RepairTech': repair_tech,
                'Procedural': procedural,
                'BrokenSlotTech': broken_slot_tech,
                'ParentTechId': parent_tech_id,
                'RequiredTech': required_tech,
                'RequiredLevel': required_level,
                'FocusLocator': focus_locator,
                'UpgradeColour': upgrade_colour,
                'LinkColour': link_colour,
                'RewardGroup': reward_group,
                'PriceModifiers': price_modifiers,
                'RequiredRank': required_rank,
                'DispensingRace': dispensing_race or None,
                'FragmentCost': fragment_cost,
                'TechShopRarity': tech_shop_rarity or None,
                'WikiEnabled': wiki_enabled,
                'NeverPinnable': never_pinnable,
                'IsTemplate': is_template,
                'ExclusivePrimaryStat': exclusive_primary_stat,
            }

            technologies.append(technology)
            tech_counter += 1

        except Exception as e:
            print(f"Warning: Skipped technology due to error: {e}")
            continue

    print(f"[OK] Parsed {len(technologies)} technologies")
    return technologies
