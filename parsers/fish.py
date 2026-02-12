"""Parse Fish from MXML to JSON.

Fish names/descriptions come from the product table (nms_reality_gcproducttable) and
localization (LANGUAGE/*.mbin). If fish names are missing or wrong, extract additional
locale MBINs from the game, run MBINCompiler to get MXML, then add them to
utils/parse_localization.py and rebuild localization.json.
"""
import re
from .base_parser import (
    EXMLParser,
    normalize_game_icon_path,
    unresolved_localization_key_count,
)
from pathlib import Path


# Cache for product details (from game MXML)
_product_cache = None


def _replace_size_token(text: str, size_word: str) -> str:
    """Replace %SIZE% and preserve spacing if followed by a word."""
    if not isinstance(text, str) or not text:
        return ''
    if not size_word:
        return text.replace('%SIZE%', '').strip()
    # Handle malformed cases like "%SIZE%An ..." by inserting a space.
    text = re.sub(r'%SIZE%(?=[A-Za-z])', f'{size_word} ', text)
    return text.replace('%SIZE%', size_word)


def _build_fish_fallback_description(
    parser: EXMLParser,
    quality: str,
    fish_size: str,
    biomes: list[str],
) -> str:
    """
    Build fish description from generic rarity/biome localization templates.
    """
    loc = parser.load_localization()

    size_suffix = {
        'Small': 'S',
        'Medium': 'M',
        'Large': 'L',
        'ExtraLarge': 'XL',
    }.get(fish_size, 'M')

    rarity_suffix = {
        'Common': 'COM',
        'Rare': 'RARE',
        'Epic': 'EPIC',
        'Legendary': 'EPIC',  # Reuse epic rarity template, then append legend note.
    }.get(quality, '')

    biome_to_suffix = {
        'All': 'ALL',
        'Lush': 'LUSH',
        'Scorched': 'HOT',
        'Lava': 'HOT',
        'Frozen': 'COLD',
        'Radioactive': 'RAD',
        'Toxic': 'TOX',
        'Swamp': 'TOX',
        'Barren': 'DUST',
        'Dead': 'DUST',
        'Weird': 'ODD',
        'Red': 'ODD',
        'Green': 'ODD',
        'Blue': 'ODD',
        'Test': 'ODD',
        'Waterworld': 'DEEP',
        'GasGiant': 'GAS',
    }

    size_word = loc.get(f'UI_FISH_SIZE_{size_suffix}', '').strip()
    rarity_desc = loc.get(f'UI_FISH_RARITY_{rarity_suffix}_{size_suffix}_DESC', '').strip() if rarity_suffix else ''

    biome_desc = ''
    for biome in biomes or []:
        suffix = biome_to_suffix.get(biome)
        if not suffix:
            continue
        candidate = loc.get(f'UI_FISH_BIOME_{suffix}_DESC', '').strip()
        if candidate:
            biome_desc = candidate
            break

    biome_desc = _replace_size_token(biome_desc, size_word).strip()

    parts = [p for p in (biome_desc, rarity_desc) if p]
    if quality == 'Legendary':
        legend = loc.get('UI_FISH_LEGEND_EXTRA', '').strip()
        if legend:
            parts.append(legend)

    return '\n\n'.join(parts).strip()


def _load_product_details():
    """Load product details for fish ProductIDs"""
    global _product_cache
    if _product_cache is not None:
        return _product_cache

    _product_cache = {}
    parser = EXMLParser()
    localization = parser.load_localization()

    # Load from Products table
    products_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'
    if products_path.exists():
        root = parser.load_xml(str(products_path))
        table_prop = root.find('.//Property[@name="Table"]')
        if table_prop:
            for item in table_prop.findall('./Property[@name="Table"]'):
                item_id = parser.get_property_value(item, 'ID', '')
                name_key = parser.get_property_value(item, 'Name', '')
                subtitle_key = parser.get_property_value(item, 'Subtitle', '')
                description_key = parser.get_property_value(item, 'Description', '')
                if unresolved_localization_key_count(localization, name_key, subtitle_key, description_key) >= 2:
                    continue
                base_value = parser.parse_value(parser.get_property_value(item, 'BaseValue', '0'))
                stack_mult = parser.parse_value(parser.get_property_value(item, 'StackMultiplier', '1'))
                cooking_value = parser.parse_value(parser.get_property_value(item, 'CookingValue', '0'))
                rarity = parser.get_nested_enum(item, 'Rarity', 'Rarity', '')
                legality = parser.get_nested_enum(item, 'Legality', 'Legality', '')
                trade_category = parser.get_nested_enum(item, 'TradeCategory', 'TradeCategory', '')
                wiki_category = parser.get_property_value(item, 'WikiCategory', '')
                consumable = parser.parse_value(parser.get_property_value(item, 'Consumable', 'false'))

                # Extract color
                colour_elem = item.find('.//Property[@name="Colour"]')
                colour = parser.parse_colour(colour_elem)

                # Icon path from game (matches data/EXTRACTED/textures/...)
                icon_prop = item.find('.//Property[@name="Icon"]')
                icon_filename = parser.get_property_value(icon_prop, 'Filename', '') if icon_prop is not None else ''
                icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''

                if item_id:
                    name = parser.translate(name_key, item_id)
                    group = parser.translate(subtitle_key, '')
                    description = parser.translate(description_key, '')

                    _product_cache[item_id] = {
                        'IconPath': icon_path,
                        'Name': name,
                        'Group': group,
                        'Description': description,
                        'BaseValueUnits': base_value,
                        'MaxStackSize': stack_mult,
                        'CookingValue': cooking_value,
                        'Colour': colour,
                        'Rarity': rarity or None,
                        'Legality': legality or None,
                        'TradeCategory': trade_category or None,
                        'WikiCategory': wiki_category or None,
                        'Consumable': consumable,
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

            # From fishdatatable: Quality (rarity), Size, Time (fishing time)
            quality = parser.get_nested_enum(fish_elem, 'Quality', 'ItemQuality', '')
            fish_size = parser.get_nested_enum(fish_elem, 'Size', 'FishSize', '')
            fishing_time = parser.get_nested_enum(fish_elem, 'Time', 'FishingTime', '')
            needs_storm = parser.parse_value(parser.get_property_value(fish_elem, 'NeedsStorm', 'false'))
            requires_mission_active = parser.get_property_value(fish_elem, 'RequiresMissionActive', '') or None
            mission_seed = parser.get_property_value(fish_elem, 'MissionSeed', '') or None
            mission_must_also_be_selected = parser.parse_value(
                parser.get_property_value(fish_elem, 'MissionMustAlsoBeSelected', 'false')
            )
            mission_catch_chance_override = parser.parse_value(
                parser.get_property_value(fish_elem, 'MissionCatchChanceOverride', '0')
            )
            catch_increments_stat = parser.get_property_value(fish_elem, 'CatchIncrementsStat', '') or None

            biome_flags = {}
            biome_prop = fish_elem.find('./Property[@name="Biome"]')
            if biome_prop is not None:
                for biome in biome_prop.findall('./Property'):
                    biome_name = biome.get('name')
                    biome_val = biome.get('value', 'false')
                    if biome_name:
                        biome_flags[biome_name] = parser.parse_value(biome_val)
            biomes = [name for name, enabled in biome_flags.items() if enabled]

            # Get product details (name, description, group from product table + localization)
            product_details = products.get(product_id, {})
            if not product_details.get('IconPath'):
                continue

            name = product_details.get('Name', product_id)
            group = product_details.get('Group', '')
            description = product_details.get('Description', '')
            if not (description or '').strip():
                description = _build_fish_fallback_description(
                    parser=parser,
                    quality=quality,
                    fish_size=fish_size,
                    biomes=biomes,
                )
            fish = {
                'Id': product_id,
                'Icon': f"{product_id}.png",
                'IconPath': product_details.get('IconPath', ''),
                'Name': name,
                'Group': group,
                'Description': description,
                'Quality': quality,
                'FishSize': fish_size,
                'FishingTime': fishing_time,
                'Biomes': biomes,
                'NeedsStorm': needs_storm,
                'RequiresMissionActive': requires_mission_active,
                'MissionSeed': mission_seed,
                'MissionMustAlsoBeSelected': mission_must_also_be_selected,
                'MissionCatchChanceOverride': mission_catch_chance_override,
                'CatchIncrementsStat': catch_increments_stat,
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
                'Rarity': product_details.get('Rarity'),
                'Legality': product_details.get('Legality'),
                'TradeCategory': product_details.get('TradeCategory'),
                'WikiCategory': product_details.get('WikiCategory'),
                'Consumable': product_details.get('Consumable'),
            }
            fish_list.append(fish)
            fish_counter += 1

        except Exception as e:
            print(f"Warning: Skipped fish due to error: {e}")
            continue

    print(f"[OK] Parsed {len(fish_list)} fish")
    return fish_list
