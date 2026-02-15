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
            'Group': subtitle if subtitle else f"Trade Goods ({trade_category})",
            'Description': product.get('Description', ''),
            'BaseValueUnits': product.get('BaseValueUnits', 0),
            'CurrencyType': 'Credits',
            'MaxStackSize': product.get('MaxStackSize', 1),
            'Colour': product.get('Colour', 'FFFFFF'),
            'CdnUrl': '',
            'Usages': [],
            'BlueprintCost': 1,
            'BlueprintCostType': 'None',
            'BlueprintSource': 0,
            'RequiredItems': [],
            'StatBonuses': [],
            'ConsumableRewardTexts': [],
        })

    print(f"[OK] Parsed {len(trade_items)} trade items")
    return trade_items
