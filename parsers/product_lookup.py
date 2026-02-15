"""Shared product-table lookup helpers for parser modules."""
from pathlib import Path

from .base_parser import EXMLParser, normalize_game_icon_path, unresolved_localization_key_count


def load_product_lookup(
    *,
    parser: EXMLParser,
    localization: dict,
    products_mxml_path: str | Path,
    include_requirements: bool = True,
) -> dict[str, dict]:
    """Load product table rows into a normalized lookup keyed by product ID."""
    path = Path(products_mxml_path)
    if not path.exists():
        return {}

    root = parser.load_xml(str(path))
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        return {}

    lookup: dict[str, dict] = {}
    for item in table_prop.findall('./Property[@name="Table"]'):
        item_id = parser.get_property_value(item, 'ID', '')
        name_key = parser.get_property_value(item, 'Name', '')
        subtitle_key = parser.get_property_value(item, 'Subtitle', '')
        description_key = parser.get_property_value(item, 'Description', '')
        if unresolved_localization_key_count(localization, name_key, subtitle_key, description_key) >= 2:
            continue

        base_value = parser.parse_value(parser.get_property_value(item, 'BaseValue', '0'))
        stack_mult = parser.parse_value(parser.get_property_value(item, 'StackMultiplier', '1'))
        recipe_cost = parser.parse_value(parser.get_property_value(item, 'RecipeCost', '0'))
        cooking_value = parser.parse_value(parser.get_property_value(item, 'CookingValue', '0'))

        required_items = []
        if include_requirements:
            requirements_prop = item.find('.//Property[@name="Requirements"]')
            if requirements_prop is not None:
                for req_elem in requirements_prop.findall('./Property'):
                    req_id = parser.get_property_value(req_elem, 'ID', '')
                    req_amount = parser.get_property_value(req_elem, 'Amount', '1')
                    if req_id:
                        required_items.append({
                            'Id': req_id,
                            'Quantity': parser.parse_value(req_amount),
                        })

        is_craftable = parser.get_property_value(item, 'IsCraftable', 'false')
        is_cooking = parser.get_property_value(item, 'CookingIngredient', 'false')
        egg_modifier = parser.get_property_value(item, 'EggModifierIngredient', 'false')
        good_for_selling = parser.get_property_value(item, 'GoodForSelling', 'false')
        usages = []
        if parser.parse_value(is_craftable):
            usages.append('HasUsedToCraft')
        if parser.parse_value(is_cooking):
            usages.append('HasCookingProperties')
        if parser.parse_value(egg_modifier):
            usages.append('IsEggIngredient')
        if parser.parse_value(good_for_selling):
            usages.append('HasDevProperties')

        rarity = parser.get_nested_enum(item, 'Rarity', 'Rarity', '')
        legality = parser.get_nested_enum(item, 'Legality', 'Legality', '')
        trade_category = parser.get_nested_enum(item, 'TradeCategory', 'TradeCategory', '')
        wiki_category = parser.get_property_value(item, 'WikiCategory', '')
        consumable = parser.parse_value(parser.get_property_value(item, 'Consumable', 'false'))
        deploys_into = parser.get_property_value(item, 'DeploysInto', '')

        colour_elem = item.find('.//Property[@name="Colour"]')
        colour = parser.parse_colour(colour_elem)

        icon_prop = item.find('.//Property[@name="Icon"]')
        icon_filename = parser.get_property_value(icon_prop, 'Filename', '') if icon_prop is not None else ''
        icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''

        if item_id:
            lookup[item_id] = {
                'Id': item_id,
                'Name': parser.translate(name_key, item_id),
                'Group': parser.translate(subtitle_key, ''),
                'Description': parser.translate(description_key, ''),
                'IconPath': icon_path,
                'BaseValueUnits': base_value,
                'MaxStackSize': stack_mult,
                'BlueprintCost': recipe_cost,
                'CookingValue': cooking_value,
                'Colour': colour,
                'Usages': usages,
                'RequiredItems': required_items,
                'Rarity': rarity or None,
                'Legality': legality or None,
                'TradeCategory': trade_category or None,
                'WikiCategory': wiki_category or None,
                'Consumable': consumable,
                'CookingIngredient': parser.parse_value(is_cooking),
                'GoodForSelling': parser.parse_value(good_for_selling),
                'EggModifierIngredient': parser.parse_value(egg_modifier),
                'DeploysInto': deploys_into or None,
            }

    return lookup
