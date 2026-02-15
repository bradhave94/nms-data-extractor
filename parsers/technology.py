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
            if unresolved_localization_key_count(localization, name_key, subtitle_key, description_key) >= 2:
                continue

            name = parser.translate(name_key, tech_id)
            subtitle = parser.translate(subtitle_key, '')
            description = parser.translate(description_key, '')

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

            # Create technology entry
            technology = {
                'Id': tech_id,
                'Icon': f"{tech_id}.png",
                'IconPath': icon_path,
                'Name': name,
                'Group': subtitle,
                'Description': description,
                'BaseValueUnits': base_value,
                'CurrencyType': 'None',
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
                'Chargeable': is_chargeable,
                'ChargeBy': charge_by_list,
                'Upgrade': upgrade,
                'Core': core,
                'ParentTechId': parent_tech_id,
                'RequiredTech': required_tech,
            }

            technologies.append(technology)
            tech_counter += 1

        except Exception as e:
            print(f"Warning: Skipped technology due to error: {e}")
            continue

    print(f"[OK] Parsed {len(technologies)} technologies")
    return technologies
