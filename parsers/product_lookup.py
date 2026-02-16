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
    name_lower_key = parser.get_property_value(item, 'NameLower', '')
    alt_description_key = parser.get_property_value(item, 'AltDescription', '')
    hint_key = parser.get_property_value(item, 'Hint', '')
    if unresolved_localization_key_count(localization, name_key, subtitle_key, description_key) >= 2:
        return None

    base_value = parser.parse_value(parser.get_property_value(item, 'BaseValue', '0'))
    stack_mult = parser.parse_value(parser.get_property_value(item, 'StackMultiplier', '1'))
    level = parser.parse_value(parser.get_property_value(item, 'Level', '0'))
    charge_value = parser.parse_value(parser.get_property_value(item, 'ChargeValue', '0'))
    default_craft_amount = parser.parse_value(parser.get_property_value(item, 'DefaultCraftAmount', '1'))
    craft_amount_step_size = parser.parse_value(parser.get_property_value(item, 'CraftAmountStepSize', '1'))
    craft_amount_multiplier = parser.parse_value(parser.get_property_value(item, 'CraftAmountMultiplier', '1'))
    recipe_cost = parser.parse_value(parser.get_property_value(item, 'RecipeCost', '0'))
    cooking_value = parser.parse_value(parser.get_property_value(item, 'CookingValue', '0'))
    specific_charge_only = parser.parse_value(parser.get_property_value(item, 'SpecificChargeOnly', 'false'))
    normalized_value_on_world = parser.parse_value(parser.get_property_value(item, 'NormalisedValueOnWorld', '0'))
    normalized_value_off_world = parser.parse_value(parser.get_property_value(item, 'NormalisedValueOffWorld', '0'))
    economy_influence_multiplier = parser.parse_value(
        parser.get_property_value(item, 'EconomyInfluenceMultiplier', '0')
    )

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
    product_category = parser.get_nested_enum(item, 'Type', 'ProductCategory', '')
    substance_category = parser.get_nested_enum(item, 'Category', 'SubstanceCategory', '')
    wiki_category = parser.get_property_value(item, 'WikiCategory', '')
    wiki_enabled = parser.parse_value(parser.get_property_value(item, 'WikiEnabled', 'false'))
    fossil_category = parser.get_property_value(item, 'FossilCategory', '')
    corvette_part_category = parser.get_nested_enum(item, 'CorvettePartCategory', 'CorvettePartCategory', '')
    corvette_reward_frequency = parser.parse_value(parser.get_property_value(item, 'CorvetteRewardFrequency', '0'))
    consumable = parser.parse_value(parser.get_property_value(item, 'Consumable', 'false'))
    deploys_into = parser.get_property_value(item, 'DeploysInto', '')
    pin_objective = parser.get_property_value(item, 'PinObjective', '')
    pin_objective_tip = parser.get_property_value(item, 'PinObjectiveTip', '')
    pin_objective_message = parser.get_property_value(item, 'PinObjectiveMessage', '')
    pin_objective_scannable_type = parser.get_nested_enum(
        item, 'PinObjectiveScannableType', 'ScanIconType', ''
    )
    pin_objective_easy_to_refine = parser.parse_value(
        parser.get_property_value(item, 'PinObjectiveEasyToRefine', 'false')
    )
    never_pinnable = parser.parse_value(parser.get_property_value(item, 'NeverPinnable', 'false'))
    is_techbox = parser.parse_value(parser.get_property_value(item, 'IsTechbox', 'false'))
    can_send_to_other_players = parser.parse_value(parser.get_property_value(item, 'CanSendToOtherPlayers', 'true'))
    buildable_ship_tech_id = parser.get_property_value(item, 'BuildableShipTechID', '')
    group_id = parser.get_property_value(item, 'GroupID', '')
    give_reward_on_special_purchase = parser.get_property_value(item, 'GiveRewardOnSpecialPurchase', '')
    food_bonus_stat = parser.get_nested_enum(item, 'FoodBonusStat', 'ConsumableBonusStat', '')
    food_bonus_stat_amount = parser.parse_value(parser.get_property_value(item, 'FoodBonusStatAmount', '0'))

    colour_elem = item.find('.//Property[@name="Colour"]')
    colour = parser.parse_colour(colour_elem)
    world_colour_elem = item.find('.//Property[@name="WorldColour"]')
    world_colour = parser.parse_colour(world_colour_elem) if world_colour_elem is not None else None

    icon_prop = item.find('.//Property[@name="Icon"]')
    icon_filename = parser.get_property_value(icon_prop, 'Filename', '') if icon_prop is not None else ''
    icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''
    hero_icon_prop = item.find('.//Property[@name="HeroIcon"]')
    hero_icon_filename = parser.get_property_value(hero_icon_prop, 'Filename', '') if hero_icon_prop is not None else ''
    hero_icon_path = normalize_game_icon_path(hero_icon_filename) if hero_icon_filename else ''
    if require_icon and not icon_path:
        return None

    cost_prop = item.find('.//Property[@name="Cost"]')
    price_modifiers = None
    if cost_prop is not None:
        price_modifiers = {
            'SpaceStationMarkup': parser.parse_value(parser.get_property_value(cost_prop, 'SpaceStationMarkup', '0')),
            'LowPriceMod': parser.parse_value(parser.get_property_value(cost_prop, 'LowPriceMod', '0')),
            'HighPriceMod': parser.parse_value(parser.get_property_value(cost_prop, 'HighPriceMod', '0')),
            'BuyBaseMarkup': parser.parse_value(parser.get_property_value(cost_prop, 'BuyBaseMarkup', '0')),
            'BuyMarkupMod': parser.parse_value(parser.get_property_value(cost_prop, 'BuyMarkupMod', '0')),
        }

    row = {
        'Id': item_id,
        'Name': parser.translate(name_key, name_default),
        'NameLower': parser.translate(name_lower_key, name_lower_key) if name_lower_key else None,
        'Group': parser.translate(subtitle_key, group_default),
        'Description': parser.translate(description_key, description_default),
        'AltDescription': parser.translate(alt_description_key, alt_description_key) if alt_description_key else None,
        'Hint': parser.translate(hint_key, hint_key) if hint_key else None,
        'IconPath': icon_path,
        'HeroIconPath': hero_icon_path or None,
        'BaseValueUnits': base_value,
        'Level': level,
        'ChargeValue': charge_value,
        'MaxStackSize': stack_mult,
        'DefaultCraftAmount': default_craft_amount,
        'CraftAmountStepSize': craft_amount_step_size,
        'CraftAmountMultiplier': craft_amount_multiplier,
        'BlueprintCost': recipe_cost,
        'CookingValue': cooking_value,
        'SpecificChargeOnly': specific_charge_only,
        'Colour': colour,
        'WorldColour': world_colour,
        'PriceModifiers': price_modifiers,
        'NormalisedValueOnWorld': normalized_value_on_world,
        'NormalisedValueOffWorld': normalized_value_off_world,
        'EconomyInfluenceMultiplier': economy_influence_multiplier,
        'Usages': usages,
        'RequiredItems': required_items,
        'Rarity': rarity or None,
        'Legality': legality or None,
        'TradeCategory': trade_category or None,
        'ProductCategory': product_category or None,
        'SubstanceCategory': substance_category or None,
        'WikiCategory': wiki_category or None,
        'WikiEnabled': wiki_enabled,
        'FossilCategory': fossil_category or None,
        'CorvettePartCategory': corvette_part_category or None,
        'CorvetteRewardFrequency': corvette_reward_frequency,
        'Consumable': consumable,
        'CookingIngredient': is_cooking_bool,
        'GoodForSelling': good_for_selling_bool,
        'EggModifierIngredient': egg_modifier_bool,
        'DeploysInto': deploys_into or None,
        'BuildableShipTechID': buildable_ship_tech_id or None,
        'GroupID': group_id or None,
        'PinObjective': pin_objective or None,
        'PinObjectiveTip': pin_objective_tip or None,
        'PinObjectiveMessage': pin_objective_message or None,
        'PinObjectiveScannableType': pin_objective_scannable_type or None,
        'PinObjectiveEasyToRefine': pin_objective_easy_to_refine,
        'NeverPinnable': never_pinnable,
        'GiveRewardOnSpecialPurchase': give_reward_on_special_purchase or None,
        'FoodBonusStat': food_bonus_stat or None,
        'FoodBonusStatAmount': food_bonus_stat_amount,
        'IsTechbox': is_techbox,
        'CanSendToOtherPlayers': can_send_to_other_players,
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
