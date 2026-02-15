"""Parse Cooking from MXML to JSON"""
import xml.etree.ElementTree as ET
from .base_parser import (
    EXMLParser,
)
from .product_lookup import load_product_lookup
from pathlib import Path
from typing import Any


def _map_effect_category(reward_id: str) -> str:
    """Map raw RewardID to a friendly effect category."""
    if not isinstance(reward_id, str) or not reward_id:
        return 'Unknown'
    rid = reward_id.upper()
    if rid.startswith('DE_FOOD_JETPACK'):
        return 'Jetpack'
    if rid.startswith('DE_FOOD_HAZ'):
        return 'Hazard Protection'
    if rid.startswith('DE_FOOD_ENERGY'):
        return 'Life Support'
    if rid.startswith('DE_FOOD_HEALTH'):
        return 'Health'
    if rid.startswith('DE_FOOD_STAMINA'):
        return 'Stamina'
    return 'Unknown'


def _flatten_property_leaves(prop_elem, prefix='') -> list[tuple[str, str]]:
    """
    Flatten nested <Property> trees into (path, value) leaves.
    Leaf = Property with a value and no nested Property children.
    """
    if prop_elem is None:
        return []
    name = prop_elem.attrib.get('name', '').strip()
    value = prop_elem.attrib.get('value', '')
    current = f"{prefix}.{name}" if prefix and name else (name or prefix)
    children = prop_elem.findall('./Property')
    if children:
        out: list[tuple[str, str]] = []
        for child in children:
            out.extend(_flatten_property_leaves(child, current))
        return out
    if name:
        return [(current, value)]
    return []


def _extract_reward_effect_stats(parser: EXMLParser, reward_entry) -> dict[str, Any]:
    """
    Extract scalar stat-like fields from a reward entry.
    Keeps numeric/bool leaves on amount/value/chance/duration/multiplier paths.
    """
    leaves = _flatten_property_leaves(reward_entry)
    stats = {}
    used_keys: set[str] = set()
    key_markers = (
        'amount',
        'value',
        'chance',
        'duration',
        'time',
        'bonus',
        'mult',
        'min',
        'max',
    )
    for path, raw_value in leaves:
        if not isinstance(path, str):
            continue
        path_l = path.lower()
        if not any(marker in path_l for marker in key_markers):
            continue
        parsed = parser.parse_value(raw_value)
        if isinstance(parsed, (int, float, bool)):
            # Prefer concise, readable keys over full nested XML paths.
            if '.Reward.' in path:
                short_key = path.split('.Reward.', 1)[1]  # e.g. GcRewardEnergy.Amount
            else:
                short_key = path.split('.')[-1]  # e.g. PercentageChance

            # Ensure uniqueness if the same short key appears multiple times.
            if short_key in used_keys:
                i = 2
                candidate = f"{short_key}_{i}"
                while candidate in used_keys:
                    i += 1
                    candidate = f"{short_key}_{i}"
                short_key = candidate
            used_keys.add(short_key)
            stats[short_key] = parsed
    return stats


def _humanize_reward_effect_stats(stats: dict[str, Any] | None) -> dict[str, Any] | None:
    """Map internal reward stat keys to readable labels."""
    if not isinstance(stats, dict) or not stats:
        return stats

    key_map = {
        'GcRewardEnergy.Amount': 'LifeSupportRechargeAmount',
        'GcRewardRefreshHazProt.Amount': 'HazardProtectionRechargeAmount',
        'GcRewardStamina.Amount': 'StaminaRechargeAmount',
        'GcRewardHealth.Amount': 'HealthRechargeAmount',
    }

    out: dict[str, Any] = {}
    for key, value in stats.items():
        out[key_map.get(key, key)] = value
    return out


def _load_reward_effect_lookup(parser: EXMLParser, repo_root: Path) -> dict[str, dict[str, Any]]:
    """
    Build RewardID -> extracted effect stats from reward table when available.
    Works with either rewardtable.MXML or nms_reality_gcrewardtable.MXML.
    """
    candidate_dirs = [
        repo_root / 'data' / 'mbin',
    ]

    candidate_names = (
        'rewardtable.MXML',
        'nms_reality_gcrewardtable.MXML',
    )
    reward_path = None
    for directory in candidate_dirs:
        if not directory.exists():
            continue
        for name in candidate_names:
            path = directory / name
            if path.exists():
                reward_path = path
                break
        if reward_path is not None:
            break
        # Fallback: recurse for any reward-table-like MXML name.
        wildcard_hits = sorted(directory.glob('**/*reward*table*.MXML'))
        if wildcard_hits:
            reward_path = wildcard_hits[0]
            break
    if reward_path is None:
        return {}

    root = parser.load_xml(str(reward_path))
    table_blocks = []
    for table_name in ('GenericTable', 'DestructionTable', 'Table'):
        table_blocks.extend(root.findall(f'.//Property[@name="{table_name}"]'))
    if not table_blocks:
        return {}

    reward_lookup: dict[str, dict[str, Any]] = {}
    for table_prop in table_blocks:
        for reward_entry in table_prop.findall('./Property'):
            reward_id = (
                parser.get_property_value(reward_entry, 'Id', '')
                or parser.get_property_value(reward_entry, 'ID', '')
            )
            if not reward_id:
                continue
            stats = _extract_reward_effect_stats(parser, reward_entry)
            reward_lookup[reward_id] = {
                'RewardEffectStats': _humanize_reward_effect_stats(stats) if stats else None,
            }
    return reward_lookup


def parse_cooking(mxml_path: str) -> list:
    """
    Parse consumableitemtable.MXML to Food.json format.

    This references product IDs from the Products table.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()
    repo_root = Path(__file__).parent.parent
    reward_effect_lookup = _load_reward_effect_lookup(parser, repo_root)

    products_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'
    products_lookup = load_product_lookup(
        parser=parser,
        localization=localization,
        products_mxml_path=products_path,
        include_requirements=True,
    )

    print(f"[OK] Loaded {len(products_lookup)} products for lookup")

    cooking_items = []

    # Navigate to Table property
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return cooking_items

    # Get all consumable IDs
    for item_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            item_id = parser.get_property_value(item_elem, 'ID', '')
            if not item_id:
                continue

            # Look up in products
            product_info = products_lookup.get(item_id)
            if not product_info:
                continue  # Skip if not a food product
            if not product_info.get('IconPath'):
                continue

            reward_id = parser.get_property_value(item_elem, 'RewardID', '')
            reward_effect = reward_effect_lookup.get(reward_id, {})

            # Create cooking entry from product info (Icon from game path)
            cooking = {
                'Id': item_id,
                'Icon': f"{item_id}.png",
                'IconPath': product_info.get('IconPath', ''),
                'Name': product_info['Name'],
                'Group': product_info['Group'],
                'Description': product_info['Description'],
                'BaseValueUnits': product_info['BaseValueUnits'],
                'CurrencyType': 'Credits',
                'MaxStackSize': product_info['MaxStackSize'],
                'Colour': product_info['Colour'],
                'CookingValue': product_info['CookingValue'],
                'CdnUrl': '',  # Build from Icon path: baseUrl + icon (e.g. EXTRACTED or your CDN)
                'Usages': product_info.get('Usages', []),
                'BlueprintCost': product_info.get('BlueprintCost', 0),
                'BlueprintCostType': 'None',
                'BlueprintSource': 0,
                'RequiredItems': product_info.get('RequiredItems', []),
                'StatBonuses': [],
                'ConsumableRewardTexts': [],
                'Rarity': product_info.get('Rarity'),
                'Legality': product_info.get('Legality'),
                'TradeCategory': product_info.get('TradeCategory'),
                'WikiCategory': product_info.get('WikiCategory'),
                'Consumable': product_info.get('Consumable'),
                'CookingIngredient': product_info.get('CookingIngredient'),
                'GoodForSelling': product_info.get('GoodForSelling'),
                'EggModifierIngredient': product_info.get('EggModifierIngredient'),
                'DeploysInto': product_info.get('DeploysInto'),
                'RewardID': reward_id or None,
                'EffectCategory': _map_effect_category(reward_id),
                'RewardEffectStats': reward_effect.get('RewardEffectStats'),
            }

            cooking_items.append(cooking)

        except Exception as e:
            print(f"Warning: Skipped cooking item due to error: {e}")
            continue

    print(f"[OK] Parsed {len(cooking_items)} cooking items")
    return cooking_items
