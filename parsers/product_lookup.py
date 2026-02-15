"""Shared product-table lookup helpers for parser modules."""
from pathlib import Path

from .base_parser import EXMLParser, normalize_game_icon_path, unresolved_localization_key_count

_PRODUCT_LOOKUP_CACHE: dict[tuple[str, float, bool, bool], dict[str, dict]] = {}


def parse_product_element(
    *,
    parser: EXMLParser,
    localization: dict,
    item,
    include_requirements: bool,
    include_raw_keys: bool,
    require_icon: bool,
    fallback_id: str = "",
    name_default: str = "",
    group_default: str = "",
    description_default: str = "",
) -> dict | None:
    """
    Parse one product-table row into a normalized intermediate dictionary.
    Returns None when the row should be skipped.
    """
    item_id = parser.get_property_value(item, 'ID', fallback_id)
    if not item_id:
        return None

    name_key = parser.get_property_value(item, 'Name', '')
    subtitle_key = parser.get_property_value(item, 'Subtitle', '')
    description_key = parser.get_property_value(item, 'Description', '')
    if unresolved_localization_key_count(localization, name_key, subtitle_key, description_key) >= 2:
        return None

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
    is_craftable_bool = parser.parse_value(is_craftable)
    is_cooking_bool = parser.parse_value(is_cooking)
    egg_modifier_bool = parser.parse_value(egg_modifier)
    good_for_selling_bool = parser.parse_value(good_for_selling)

    usages = []
    if is_craftable_bool:
        usages.append('HasUsedToCraft')
    if is_cooking_bool:
        usages.append('HasCookingProperties')
    if egg_modifier_bool:
        usages.append('IsEggIngredient')
    if good_for_selling_bool:
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
    if require_icon and not icon_path:
        return None

    row = {
        'Id': item_id,
        'Name': parser.translate(name_key, name_default),
        'Group': parser.translate(subtitle_key, group_default),
        'Description': parser.translate(description_key, description_default),
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
        'CookingIngredient': is_cooking_bool,
        'GoodForSelling': good_for_selling_bool,
        'EggModifierIngredient': egg_modifier_bool,
        'DeploysInto': deploys_into or None,
    }
    if include_raw_keys:
        row['SubtitleKey'] = subtitle_key
        row['NameKey'] = name_key
        row['DescriptionKey'] = description_key
    return row


def load_product_lookup(
    *,
    parser: EXMLParser,
    localization: dict,
    products_mxml_path: str | Path,
    include_requirements: bool = True,
    include_raw_keys: bool = False,
) -> dict[str, dict]:
    """Load product table rows into a normalized lookup keyed by product ID."""
    path = Path(products_mxml_path)
    if not path.exists():
        return {}
    resolved_path = path.resolve()
    cache_key = (
        str(resolved_path),
        resolved_path.stat().st_mtime,
        include_requirements,
        include_raw_keys,
    )
    cached = _PRODUCT_LOOKUP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    root = parser.load_xml(str(path))
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        return {}

    lookup: dict[str, dict] = {}
    for item in table_prop.findall('./Property[@name="Table"]'):
        row = parse_product_element(
            parser=parser,
            localization=localization,
            item=item,
            include_requirements=include_requirements,
            include_raw_keys=include_raw_keys,
            require_icon=False,
            fallback_id="",
            name_default=parser.get_property_value(item, 'ID', ''),
            group_default="",
            description_default="",
        )
        if row is None:
            continue
        lookup[row['Id']] = row

    _PRODUCT_LOOKUP_CACHE[cache_key] = lookup
    return lookup
