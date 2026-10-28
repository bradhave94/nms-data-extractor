"""Progression and economy tables the site shows on its Reference pages: milestone ladders
and Journey ranks, starship and Multi-Tool inventory limits and class odds, and trading.

Like reference_tables, each parser reads one table and the related tables beside it in the
same MXML folder, and localization keys must resolve.
"""
from pathlib import Path

from .player_unlocks import _child_value, _field, _text
from .reference_tables import _enum, _load, _number, _require

_CLASSES = ("C", "B", "A", "S")


def _by_class(element, what: str) -> dict:
    """{C, B, A, S} -> number, for the per-class blocks the inventory table uses."""
    if element is None:
        raise ValueError(f"inventorytable has no {what}")
    values = {node.get("name"): _number(node.get("value")) for node in element}
    if set(values) != set(_CLASSES):
        raise ValueError(f"Expected C/B/A/S values, got {sorted(values)}")
    return {grade: values[grade] for grade in _CLASSES}


# ---------- milestones and ranks ----------

def _stat_value(level) -> float | int:
    """A level's threshold: the stat's int or float value (never both; no ratio stats)."""
    value = level.find('./Property[@name="Value"]')
    integer = _number(_field(value, "IntValue"))
    real = _number(_field(value, "FloatValue"))
    if integer and real:
        raise ValueError(f"Stat level sets both IntValue {integer} and FloatValue {real}")
    if _number(_field(value, "Denominator")):
        raise ValueError("Stat level is a ratio (non-zero Denominator), which is not supported")
    return real or integer


def parse_milestones(mxml_path: str) -> dict:
    """leveledstatstable.MXML: every ladder's level names and thresholds, plus the Journey
    ranks from journeymilestonetable.MXML beside it."""
    path = Path(mxml_path)
    problems: set[str] = set()
    hidden_missing: set[str] = set()
    ladders = []
    for row in _load(path).findall('./Property[@name="LeveledStatTable"]/Property'):
        stat_id = _field(row, "StatId")
        if not stat_id:
            raise ValueError("Leveled stat has no StatId")
        shown = _field(row, "ShowInTerminal") == "true"
        use_rank = _field(row, "UseRankNotStats") == "true"
        # Ladders the game never shows in its terminal can lack English text (10 titles and a
        # tutorial level in 7.10). Missing text on a shown ladder or a rank ladder (race, guild
        # and Outlaw standing, which the site lists) still stops the run; the rest is reported.
        texts = problems if shown or use_rank else hidden_missing
        levels = [{
            "Name": _text(_field(level, "LevelName"), texts),
            "Value": _stat_value(level),
            "Trophy": _field(level, "TrophyToUnlock") or None,
        } for level in row.findall('./Property[@name="StatLevels"]/Property')]
        ladders.append({
            "Id": stat_id,
            "Title": _text(_field(row, "StatTitle"), texts),
            # What the ladder counts, in the game's words ("Discovered all species on %STAT% planets").
            "Notify": _text(_field(row, "NotifyMessage"), texts),
            "ShowInTerminal": shown,
            # Ladders that count ranks (standing) rather than a raw stat.
            "UseRank": use_rank,
            "Levels": levels,
        })
    journey = [{
        "Id": _field(row, "JourneyMilestoneId"),
        "Name": _text(_field(row, "JourneyMilestoneTitleLower"), problems),
        "Points": _number(_field(row, "PointsToUnlock")),
    } for row in _load(path.with_name("journeymilestonetable.MXML")).findall('./Property[@name="JourneyMilestoneTable"]/Property')]
    _require(problems, "Milestone")
    if hidden_missing:
        print(f"  [WARN] Hidden milestone ladders without English text: {', '.join(sorted(hidden_missing))}")
    if not ladders or not journey:
        raise ValueError("Milestone tables are empty or incompatible")
    return {"Ladders": ladders, "Journey": journey}


# ---------- inventory limits, class odds and base stats ----------

# The game's own names for ship and Multi-Tool types (its base-stats screen strings).
# Types with no string (freighters, the Atlas variants) are named by the site.
_SHIP_LABEL_KEYS = {
    "Dropship": "BASESTATS_DROPSHIP_L", "Fighter": "BASESTATS_FIGHTER_L", "Scientific": "BASESTATS_SCIENTIFIC_L",
    "Shuttle": "BASESTATS_SHUTTLE_L", "Royal": "BASESTATS_ROYAL_L", "Alien": "BASESTATS_ALIENSHIP",
    "Sail": "BASESTATS_SAIL_L", "Robot": "BASESTATS_ROBOTSHIP_L", "Corvette": "BASESTATS_CORVETTE_L",
    "SwarmDrone": "BASESTATS_SWARMDRONE_L",
}
_WEAPON_LABEL_KEYS = {
    "Pistol": "BASESTATS_PISTOL_L", "Rifle": "BASESTATS_RIFLE_L", "Pristine": "BASESTATS_PRISTINE_L",
    "Alien": "BASESTATS_ALIEN_L", "Royal": "BASESTATS_ROYAL_L", "Robot": "BASESTATS_ROBOGUN_L",
    "Atlas": "BASESTATS_ATLASGUN_L", "Staff": "BASESTATS_STAFFGUN_L",
}

def _base_stats(block) -> dict:
    """GcInventoryGenerationBaseStatData -> {class: [{Stat, Min, Max}]}."""
    result = {}
    for grade in block.findall('./Property[@name="BaseStatsPerClass"]/Property'):
        result[grade.get("name")] = [{
            "Stat": _field(stat, "BaseStatID"),
            "Min": _number(_field(stat, "Min")),
            "Max": _number(_field(stat, "Max")),
        } for stat in grade.findall('./Property[@name="BaseStats"]/Property')]
    return result


def parse_inventory(mxml_path: str) -> dict:
    """inventorytable.MXML: the most slots each ship type and the Multi-Tool can be upgraded
    to by class, the class odds by system wealth, and base stat ranges by class."""
    root = _load(Path(mxml_path))

    def section(name):
        node = root.find(f'./Property[@name="{name}"]')
        if node is None:
            raise ValueError(f"inventorytable has no {name}")
        return node

    max_slots = {}
    for ship in section("ShipInventoryMaxUpgradeSize"):
        max_slots[ship.get("name")] = {
            "General": _by_class(ship.find('./Property[@name="MaxInventoryCapacity"]'), f"{ship.get('name')} MaxInventoryCapacity"),
            "Tech": _by_class(ship.find('./Property[@name="MaxTechInventoryCapacity"]'), f"{ship.get('name')} MaxTechInventoryCapacity"),
            "Cargo": _by_class(ship.find('./Property[@name="MaxCargoInventoryCapacity"]'), f"{ship.get('name')} MaxCargoInventoryCapacity"),
        }
    weapon_max = _by_class(section("WeaponInventoryMaxUpgradeSize").find('./Property[@name="MaxInventoryCapacity"]'),
                           "Multi-Tool MaxInventoryCapacity")
    class_odds = {wealth.get("name"): _by_class(wealth.find('./Property[@name="ClassProbabilities"]'),
                                                f"{wealth.get('name')} ClassProbabilities")
                  for wealth in section("ClassProbabilityData")}
    base_stats = {
        "Ships": {ship.get("name"): _base_stats(ship) for ship in section("ShipBaseStatsData")},
        "Weapons": {weapon.get("name"): _base_stats(weapon) for weapon in section("WeaponBaseStatsData")},
    }
    if not max_slots or not class_odds:
        raise ValueError("inventorytable is empty or incompatible")
    problems: set[str] = set()
    labels = {
        "Ships": {kind: _text(key, problems) for kind, key in _SHIP_LABEL_KEYS.items()},
        "Weapons": {kind: _text(key, problems) for kind, key in _WEAPON_LABEL_KEYS.items()},
    }
    _require(problems, "Inventory")
    return {"MaxSlots": max_slots, "MultiToolMaxSlots": weapon_max, "ClassOdds": class_odds,
            "BaseStats": base_stats, "Labels": labels}


# ---------- trading ----------

# Economy types -> the game's four map names for each (UI_ECON_CLASS_<key>_1..4).
_ECONOMY_NAME_KEYS = {
    "Mining": "MINING", "HighTech": "TECH", "Trading": "TRADE", "Manufacturing": "MANUFACT",
    "Fusion": "ALLOY", "Scientific": "SCIENCE", "PowerGeneration": "POWER",
}

def parse_trading(mxml_path: str) -> dict:
    """tradingclassdatatable.MXML: what each economy type sells and needs, its price
    multipliers, and how fast prices move per 100 sold."""
    path = Path(mxml_path)
    root = _load(path)
    problems: set[str] = set()
    economies = []
    for economy in root.findall('./Property[@name="TradingClassesData"]/Property'):
        key = _ECONOMY_NAME_KEYS.get(economy.get("name"))
        if key is None:
            raise ValueError(f"Unknown economy type {economy.get('name')}; map its UI_ECON_CLASS_* names")
        economies.append({
            "Id": economy.get("name"),
            "Names": [_text(f"UI_ECON_CLASS_{key}_{index}", problems) for index in range(1, 5)],
            "Sells": _enum(economy, "Sells", "TradeCategory"),
            "Needs": _enum(economy, "Needs", "TradeCategory"),
            **{key: _number(_field(economy, key)) for key in (
                "MinSellingPriceMultiplier", "MaxSellingPriceMultiplier", "MinBuyingPriceMultiplier",
                "MaxBuyingPriceMultiplier", "MinBuyingPriceMultiplierSurge", "MaxBuyingPriceMultiplierSurge")},
        })
    categories = {}
    for category in root.findall('./Property[@name="CategoryData"]/Property'):
        # "None" (uncategorised goods) has real price rates but a name key with no text.
        categories[category.get("name")] = {
            "Name": None if category.get("name") == "None" else _text(_field(category, "Name"), problems),
            "ProductMultiplierChangePer100": _number(_field(category, "ProductMultiplierChangePer100")),
            "SubstanceMultiplierChangePer100": _number(_field(category, "SubstanceMultiplierChangePer100")),
        }
    unknown = sorted({e[key] for e in economies for key in ("Sells", "Needs")} - set(categories))
    if unknown:
        raise ValueError(f"Economies trade categories with no category data: {', '.join(unknown)}")
    _require(problems, "Trading")
    if not economies or not categories:
        raise ValueError("Trading table is empty or incompatible")
    return {
        "Economies": economies,
        "Categories": categories,
        "MinTradingMultiplier": _number(_field(root, "MinTradingMultiplier")),
        "MaxTradingMultiplier": _number(_field(root, "MaxTradingMultiplier")),
    }
