"""Shared product-table lookup helpers for parser modules."""
from pathlib import Path

from utils.workspace import workspace_root

from .base_parser import EXMLParser, normalize_game_icon_path, unresolved_localization_key_count

_PRODUCT_LOOKUP_CACHE: dict[tuple[str, float, bool, bool], dict[str, dict]] = {}



def base_food_duration() -> float | None:
    """BaseFoodDuration (seconds) from gcgameplayglobals.global.MXML, or None when that file is absent.

    The Nutrient Ingestor runs one unit of food for BaseFoodDuration x the product's CookingValue
    (600 s in 7.10; e.g. CookingValue 0.66 gives 6:36, matching the in-game timer)."""
    path = workspace_root() / 'data' / 'mbin' / 'gcgameplayglobals.global.MXML'
    if not path.exists():
        return None
    key = (str(path), path.stat().st_mtime)
    if key not in _BASE_FOOD_DURATION_CACHE:
        root = EXMLParser.load_xml(str(path))
        prop = root.find('./Property[@name="BaseFoodDuration"]')
        value = float(prop.get('value')) if prop is not None and prop.get('value') else None
        _BASE_FOOD_DURATION_CACHE.clear()
        _BASE_FOOD_DURATION_CACHE[key] = value if value and value > 0 else None
    return _BASE_FOOD_DURATION_CACHE[key]


_BASE_FOOD_DURATION_CACHE: dict = {}

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
    # MXML nests the stat as <Property name="FoodBonusStat" value="GcStatsTypes"><Property name="StatsType" .../>.
    # "Unspecified" means the item gives no Nutrient Ingestor bonus.
    food_bonus_stat = parser.get_nested_enum(item, 'FoodBonusStat', 'StatsType', '')
    if food_bonus_stat == 'Unspecified':
        food_bonus_stat = ''
    food_bonus_stat_name = localization.get(food_bonus_stat.upper()) if food_bonus_stat else None
    food_base_duration = base_food_duration() if food_bonus_stat else None
    food_bonus_duration = (
        round(food_base_duration * cooking_value, 1)
        if food_base_duration and isinstance(cooking_value, (int, float)) and cooking_value > 0
        else None
    )
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
        'FoodBonusStatName': food_bonus_stat_name,
        'FoodBonusDurationSeconds': food_bonus_duration,
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
