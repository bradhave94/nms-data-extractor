"""Parse Products from MXML to JSON"""
from .base_parser import EXMLParser
from .product_lookup import parse_product_element


def parse_products(mxml_path: str, *, include_subtitle_key: bool = False) -> list:
    """
    Parse nms_reality_gcproducttable.MXML to Products.json format.

    Target JSON structure:
    Icon is the item ID. IconPath is the game texture path (matches data/EXTRACTED/textures/...).
    {
        "Id": "prod1",
        "Icon": "prod1",
        "IconPath": "textures/ui/frontend/icons/u4products/product.casing.dds",
        "Name": "Antimatter",
        "Group": "Crafted Technology Component",
        "Description": "...",
        "BaseValueUnits": 5233.0,
        "CurrencyType": "Credits",
        "MaxStackSize": 10.0,
        "Colour": "C01746",
        "CdnUrl": "",
        "Usages": [],
        "BlueprintCost": 1,
        "BlueprintCostType": "None",
        "BlueprintSource": 0,
        "RequiredItems": [{"Id": "raw2", "Quantity": 20}],
        "StatBonuses": [],
        "ConsumableRewardTexts": []
    }

    Args:
        mxml_path: Path to the MXML file

    Returns:
        List of product dictionaries
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    # Load localization for name translations
    localization = parser.load_localization()

    products = []
    product_counter = 1

    # Navigate to Table property
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return products

    # Each product is a Property element with value="GcProductData"
    for product_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            fallback_id = f'PRODUCT_{product_counter}'
            name_key = parser.get_property_value(product_elem, 'Name', '')
            subtitle_key = parser.get_property_value(product_elem, 'Subtitle', '')
            description_key = parser.get_property_value(product_elem, 'Description', '')
            row = parse_product_element(
                parser=parser,
                localization=localization,
                item=product_elem,
                include_requirements=True,
                include_raw_keys=include_subtitle_key,
                require_icon=True,
                fallback_id=fallback_id,
                name_default=name_key,
                group_default=subtitle_key,
                description_default=description_key,
            )
            if row is None:
                continue
            product_id = row['Id']

            # Create product entry
            product = {
                'Id': product_id,  # Use actual game ID
                'Icon': f"{product_id}.png",
                'IconPath': row['IconPath'],
                'Name': row['Name'],
                'Group': row['Group'],
                'Description': row['Description'],
                'BaseValueUnits': row['BaseValueUnits'],
                'CurrencyType': 'Credits',  # Default to Credits
                'MaxStackSize': row['MaxStackSize'],
                'Colour': row['Colour'],
                'CdnUrl': '',  # Build from Icon path: baseUrl + icon (e.g. EXTRACTED or your CDN)
                'Usages': row['Usages'],
                'BlueprintCost': row['BlueprintCost'],
                'BlueprintCostType': 'None',  # May need to extract this
                'BlueprintSource': 0,  # May need to extract this
                'RequiredItems': row['RequiredItems'],
                'StatBonuses': [],  # May need to extract this
                'ConsumableRewardTexts': [],  # May need to extract this
                'Rarity': row['Rarity'],
                'Legality': row['Legality'],
                'TradeCategory': row['TradeCategory'],
                'WikiCategory': row['WikiCategory'],
                'Consumable': row['Consumable'],
                'CookingIngredient': row['CookingIngredient'],
                'GoodForSelling': row['GoodForSelling'],
                'EggModifierIngredient': row['EggModifierIngredient'],
                'DeploysInto': row['DeploysInto'],
            }
            if include_subtitle_key:
                product['SubtitleKey'] = row.get('SubtitleKey', subtitle_key)

            products.append(product)
            product_counter += 1

        except Exception as e:
            print(f"Warning: Skipped product due to error: {e}")
            continue

    print(f"[OK] Parsed {len(products)} products")
    return products
