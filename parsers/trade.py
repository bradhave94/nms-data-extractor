"""Parse Trade goods from Products table"""
from .base_parser import (
    EXMLParser,
)
from .product_lookup import load_product_lookup


def parse_trade(mxml_path: str) -> list:
    """
    Parse Trade goods from nms_reality_gcproducttable.MXML.

    Trade items are products with TradeCategory set.
    """
    parser = EXMLParser()
    localization = parser.load_localization()

    products_lookup = load_product_lookup(
        parser=parser,
        localization=localization,
        products_mxml_path=mxml_path,
        include_requirements=False,
    )

    trade_items = []
    for item_id, product in products_lookup.items():
        subtitle = product.get('Group', '') or ''
        trade_category = product.get('TradeCategory')
        is_trade_goods = subtitle.startswith('Trade Goods')
        is_smuggled_goods = subtitle.startswith('Smuggled Goods')
        if not (is_trade_goods or is_smuggled_goods):
            continue
        if is_trade_goods and (not trade_category or trade_category == 'None'):
            continue

        icon_path = product.get('IconPath', '')
        if not icon_path:
            continue

        trade_items.append({
            'Id': item_id,
            'Icon': f"{item_id}.png",
            'IconPath': icon_path,
            'Name': product.get('Name', item_id),
            'NameLower': product.get('NameLower'),
            'Group': subtitle if subtitle else f"Trade Goods ({trade_category})",
            'Description': product.get('Description', ''),
            'AltDescription': product.get('AltDescription'),
            'Hint': product.get('Hint'),
            'BaseValueUnits': product.get('BaseValueUnits', 0),
            'CurrencyType': 'Credits',
            'Level': product.get('Level', 0),
            'ChargeValue': product.get('ChargeValue', 0),
            'MaxStackSize': product.get('MaxStackSize', 1),
            'DefaultCraftAmount': product.get('DefaultCraftAmount', 1),
            'CraftAmountStepSize': product.get('CraftAmountStepSize', 1),
            'CraftAmountMultiplier': product.get('CraftAmountMultiplier', 1),
            'Colour': product.get('Colour', 'FFFFFF'),
            'WorldColour': product.get('WorldColour'),
            'CdnUrl': '',
            'Usages': product.get('Usages', []),
            'BlueprintCost': product.get('BlueprintCost', 0),
            'BlueprintCostType': 'None',
            'BlueprintSource': 0,
            'RequiredItems': product.get('RequiredItems', []),
            'StatBonuses': [],
            'ConsumableRewardTexts': [],
            'HeroIconPath': product.get('HeroIconPath'),
            'PriceModifiers': product.get('PriceModifiers'),
            'SpecificChargeOnly': product.get('SpecificChargeOnly', False),
            'NormalisedValueOnWorld': product.get('NormalisedValueOnWorld', 0),
            'NormalisedValueOffWorld': product.get('NormalisedValueOffWorld', 0),
            'EconomyInfluenceMultiplier': product.get('EconomyInfluenceMultiplier', 0),
            'Rarity': product.get('Rarity'),
            'Legality': product.get('Legality'),
            'TradeCategory': product.get('TradeCategory'),
            'ProductCategory': product.get('ProductCategory'),
            'SubstanceCategory': product.get('SubstanceCategory'),
            'WikiCategory': product.get('WikiCategory'),
            'WikiEnabled': product.get('WikiEnabled', False),
            'FossilCategory': product.get('FossilCategory'),
            'CorvettePartCategory': product.get('CorvettePartCategory'),
            'CorvetteRewardFrequency': product.get('CorvetteRewardFrequency', 0),
            'Consumable': product.get('Consumable', False),
            'CookingIngredient': product.get('CookingIngredient', False),
            'GoodForSelling': product.get('GoodForSelling', False),
            'EggModifierIngredient': product.get('EggModifierIngredient', False),
            'DeploysInto': product.get('DeploysInto'),
            'BuildableShipTechID': product.get('BuildableShipTechID'),
            'GroupID': product.get('GroupID'),
            'PinObjective': product.get('PinObjective'),
            'PinObjectiveTip': product.get('PinObjectiveTip'),
            'PinObjectiveMessage': product.get('PinObjectiveMessage'),
            'PinObjectiveScannableType': product.get('PinObjectiveScannableType'),
            'PinObjectiveEasyToRefine': product.get('PinObjectiveEasyToRefine', False),
            'NeverPinnable': product.get('NeverPinnable', False),
            'GiveRewardOnSpecialPurchase': product.get('GiveRewardOnSpecialPurchase'),
            'FoodBonusStat': product.get('FoodBonusStat'),
            'FoodBonusStatAmount': product.get('FoodBonusStatAmount', 0),
            'IsTechbox': product.get('IsTechbox', False),
            'CanSendToOtherPlayers': product.get('CanSendToOtherPlayers', True),
        })

    print(f"[OK] Parsed {len(trade_items)} trade items")
    return trade_items
