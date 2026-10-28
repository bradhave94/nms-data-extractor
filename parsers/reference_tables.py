"""Reference tables the site lists but doesn't give item pages: frigate traits, settlement
perks, where items come from, and the research trees that sell blueprints.

Each parser reads one table plus the related tables beside it in the same MXML folder
(globals for numeric effects, the reward and cost tables for exchanges), so a staged run
never reads live data. Localization keys must resolve, as in player_unlocks.
"""
from pathlib import Path

from .base_parser import EXMLParser
from .player_unlocks import _child_value, _field, _text


def _load(path: Path):
    if not path.is_file():
        raise ValueError(f"Required source missing: {path.name}")
    return EXMLParser.load_xml(str(path))


def _enum(element, outer: str, inner: str | None = None) -> str:
    return _child_value(element, f'./Property[@name="{outer}"]/Property[@name="{inner or outer}"]')


def _number(value: str):
    return EXMLParser.parse_value(value or "0")


def _signed(value) -> str:
    text = str(int(value)) if float(value).is_integer() else str(value)
    return text if float(value) < 0 else f"+{text}"


def _require(problems: set[str], what: str) -> None:
    if problems:
        raise ValueError(f"{what} text keys are missing or in an unknown format: {', '.join(sorted(problems))}")


# ---------- frigate traits ----------

# Frigate classes in ChanceOfBeingOffered -> the game's own class name. Normandy and Swarm
# have no class string, so their internal names are kept.
_FRIGATE_CLASS_KEYS = {
    "Combat": "FLEET_UI_TYPE_COMBAT", "Exploration": "FLEET_UI_TYPE_EXPLORE", "Mining": "FLEET_UI_TYPE_MINING",
    "Diplomacy": "FLEET_UI_TYPE_TRADING", "Support": "FLEET_UI_TYPE_SUPPORT", "DeepSpace": "FLEET_UI_TYPE_DEEP_SPACE",
    "DeepSpaceCommon": "FLEET_UI_TYPE_DEEP_SPACE", "Pirate": "FLEET_UI_TYPE_PIRATE", "GhostShip": "FLEET_UI_TYPE_GHOSTSHIP",
}


def _class_label(frigate_class: str, problems: set[str]) -> str:
    key = _FRIGATE_CLASS_KEYS.get(frigate_class)
    label = _text(key, problems) if key else frigate_class
    return label.title() if label and label.isupper() else (label or frigate_class)

def parse_frigate_traits(mxml_path: str) -> list:
    """frigatetraittable.MXML, with each strength's stat change from gcfleetglobals."""
    path = Path(mxml_path)
    rows = _load(path).findall('./Property[@name="Traits"]/Property[@name="Traits"]')
    if not rows:
        raise ValueError("Frigate trait source is empty or incompatible")
    globals_root = _load(path.with_name("gcfleetglobals.global.MXML"))
    stats = globals_root.find('./Property[@name="FrigateTraitStrengths"]/Property[@name="FrigateStatType"]')
    if stats is None:
        raise ValueError("gcfleetglobals has no FrigateTraitStrengths")
    stat_info = {}
    for stat in stats:
        stat_info[stat.get("name")] = {
            "values": {node.get("name"): _number(node.get("value")) for node in stat.findall('./Property[@name="StatAlteration"]/Property')},
            "label_key": _field(stat, "StatLocID"),
            "displays_positive": _field(stat, "StatDisplaysPositive") == "true",
        }
    problems: set[str] = set()
    traits = []
    for row in rows:
        trait_id = _field(row, "ID")
        stat = _enum(row, "FrigateStatType")
        strength = _enum(row, "Strength", "FrigateTraitStrength")
        info = stat_info.get(stat)
        if not trait_id or info is None or strength not in info["values"]:
            raise ValueError(f"Frigate trait {trait_id or '?'} has an unknown stat or strength: {stat}/{strength}")
        value = info["values"][strength]
        # The game shows some stats inverted (a lower fuel cost reads as a negative number).
        shown = value if info["displays_positive"] else -value
        label = _text(info["label_key"], problems)
        traits.append({
            "Id": trait_id,
            "Name": _text(_field(row, "DisplayName"), problems),
            "Stat": stat,
            "Strength": strength,
            "Value": value,
            "Effect": label.replace("%amount%", _signed(shown)) if label else None,
            "Beneficial": not strength.startswith("Negative"),
            # Primary traits have no chances here: the game assigns them by frigate type.
            "OfferedOn": [{"Class": node.get("name"), "Label": _class_label(node.get("name"), problems),
                           "Weight": _number(node.get("value"))}
                          for node in row.findall('./Property[@name="ChanceOfBeingOffered"]/Property')
                          if _number(node.get("value"))],
        })
    _require(problems, "Frigate trait")
    return sorted(traits, key=lambda trait: trait["Id"])


# ---------- settlement perks ----------

# Settlement stats -> the game's stat names (and the capacity wording for MaxPopulation).
_SETTLEMENT_STAT_KEYS = {
    "Happiness": "UI_SETTLEMENT_STAT_MOOD_NAME", "Production": "UI_SETTLEMENT_STAT_PROD_NAME",
    "Upkeep": "UI_SETTLEMENT_STAT_COST_NAME", "Sentinels": "UI_SETTLEMENT_STAT_SENT_NAME",
    "MaxPopulation": "UI_SETTLEMENT_STAT_MAX_POS_FMT",
}

def parse_settlement_perks(mxml_path: str) -> list:
    """settlementperkstable.MXML, with each strength's range from gcsettlementglobals."""
    path = Path(mxml_path)
    rows = _load(path).findall('./Property[@name="Table"]/Property[@name="Table"]')
    if not rows:
        raise ValueError("Settlement perk source is empty or incompatible")
    globals_root = _load(path.with_name("gcsettlementglobals.MXML"))
    ranges = {}
    for stat in globals_root.findall('./Property[@name="PerkStatStrengthValues"]/Property'):
        for strength in stat.findall('./Property[@name="PerkStatStrengthValues"]/Property'):
            ranges[(stat.get("name"), strength.get("name"))] = (
                _number(_field(strength, "AmountMin")), _number(_field(strength, "AmountMax")))
    if not ranges:
        raise ValueError("gcsettlementglobals has no PerkStatStrengthValues")
    problems: set[str] = set()
    perks = []
    for row in rows:
        perk_id = _field(row, "ID")
        effects = []
        for change in row.findall('./Property[@name="StatChanges"]/Property'):
            stat = _enum(change, "Stat", "SettlementStatType")
            strength = _enum(change, "Strength", "SettlementStatStrength")
            if (stat, strength) not in ranges:
                raise ValueError(f"Settlement perk {perk_id} has an unknown stat or strength: {stat}/{strength}")
            low, high = ranges[(stat, strength)]
            label_key = _SETTLEMENT_STAT_KEYS.get(stat)
            label = _text(label_key, problems) if label_key else None
            if label:
                label = label.replace("+%NUM%", "").strip()
                label = label[:1].upper() + label[1:]
            effects.append({"Stat": stat, "Label": label or stat, "Strength": strength, "Min": low, "Max": high,
                            "ChangesPopulation": _field(change, "DirectlyChangePopulation") == "true"})
        perks.append({
            "Id": perk_id,
            "Name": _text(_field(row, "Name"), problems),
            "Description": _text(_field(row, "Description"), problems),
            "IsNegative": _field(row, "IsNegative") == "true",
            "IsStarter": _field(row, "IsStarter") == "true",
            "IsProc": _field(row, "IsProc") == "true",
            "IsJob": _field(row, "IsJob") == "true",
            "IsBlessing": _field(row, "IsBlessing") == "true",
            "Effects": effects,
            "Buildings": sorted(_child_value(node, './Property[@name="BuildingClass"]')
                                for node in row.findall('./Property[@name="AssociatedBuildings"]/Property')),
        })
    if any(not perk["Id"] for perk in perks):
        raise ValueError("Settlement perk has no game ID")
    _require(problems, "Settlement perk")
    return sorted(perks, key=lambda perk: perk["Id"])


# ---------- where items come from ----------

_SPECIFIC_REWARDS = {
    "GcRewardSpecificProduct": ("Product", "ID"),
    "GcRewardSpecificSpecial": ("Product", "ID"),
    "GcRewardSpecificTech": ("Technology", "TechId"),
    "GcRewardSpecificWeapon": ("Weapon", None),
}
_COSTS = {
    "GcCostProduct": "Product",
    "GcCostSubstance": "Substance",
    "GcCostMoney": "Currency",
}


def _reward_grants(reward_root) -> dict[str, list[dict]]:
    """Reward Id -> what it grants, only for rewards that always give every listed item and
    are made entirely of specific items (no random picks, no chances below 100%)."""
    grants = {}
    for table in reward_root:
        for entry in table:
            reward_id = _field(entry, "Id")
            listing = entry.find('./Property[@name="List"]')
            items = entry.findall('./Property[@name="List"]/Property[@name="List"]/Property')
            if not reward_id or not items:
                continue
            if len(items) > 1 and _field(listing, "RewardChoice") not in ("GiveAll", "GiveAllSilent"):
                continue
            if any(_number(_field(item, "PercentageChance")) < 100 for item in items):
                continue
            granted = []
            for item in items:
                reward = item.find('./Property[@name="Reward"]')
                kind = reward.get("value") if reward is not None else ""
                if kind not in _SPECIFIC_REWARDS:
                    granted = None
                    break
                grant_type, id_field = _SPECIFIC_REWARDS[kind]
                body = reward.find(f'./Property[@name="{kind}"]')
                if grant_type == "Weapon":
                    granted.append({"Type": "Weapon", "Id": reward_id,
                                    "NameKey": _child_value(body, './Property[@name="NameOverride"]')})
                    continue
                low = _number(_field(body, "AmountMin") or _field(body, "Amount") or "1")
                high = _number(_field(body, "AmountMax") or "0") or low
                granted.append({"Type": grant_type, "Id": _field(body, id_field), "AmountMin": low, "AmountMax": max(low, high)})
            if granted:
                grants[reward_id] = granted
    return grants


def _exchanges(folder: Path, reward_root, problems: set[str]) -> list[dict]:
    """Dialog options that take a fixed cost and give specific items (e.g. 5 Preserved Grubs for the Larva Cannon)."""
    costs = {}
    for table in _load(folder / "costtable.MXML"):
        for entry in table:
            cost_id = _field(entry, "Id")
            cost = entry.find('./Property[@name="Cost"]')
            if not cost_id or cost is None or cost.get("value") not in _COSTS:
                continue
            # Only real, fixed prices: not costs that are shown but never charged, or whose
            # item or amount comes from elsewhere (season data, a default product).
            if _field(entry, "DontCharge") == "true":
                continue
            kind_name = cost.get("value")
            body = cost.find(f'./Property[@name="{kind_name}"]')
            if any(_field(body, flag) == "true" for flag in ("UseDefaultAmount", "TakeIDFromSeasonData", "TakeAmountFromSeasonData")):
                continue
            if _child_value(body, './Property[@name="Default"]/Property') not in ("", "None"):
                continue
            # Substance costs can be local to a planet or scan event; only plain ones are fixed prices.
            if kind_name == "GcCostSubstance" and any(
                    flag.get("name", "").startswith("Use") and flag.get("value") == "true" for flag in body):
                continue
            kind = _COSTS[cost.get("value")]
            if kind == "Currency":
                costs[cost_id] = {"Type": "Currency", "Id": _enum(body, "CostCurrency", "Currency"),
                                  "Amount": _number(_field(body, "Cost"))}
            else:
                costs[cost_id] = {"Type": kind, "Id": _field(body, "Id"), "Amount": _number(_field(body, "Amount"))}
    grants = _reward_grants(reward_root)
    exchanges = {}
    for entry in _load(folder / "nms_dialog_gcalienpuzzletable.MXML").findall('./Property[@name="Table"]/Property'):
        puzzle = _field(entry, "Id")
        # The same dialog Id exists once per alien race; the race is part of the exchange's identity.
        race = _enum(entry, "Race", "AlienRace")
        context = {"Race": race, "Interaction": _enum(entry, "Type", "InteractionType"),
                   "Category": _enum(entry, "Category", "AlienPuzzleCategory")}
        for index, option in enumerate(entry.findall('./Property[@name="Options"]/Property')):
            cost = costs.get(_field(option, "Cost"))
            rewards = [node.get("value") for node in option.findall('./Property[@name="Rewards"]/Property')]
            if not cost or not cost["Id"] or not rewards or not all(reward in grants for reward in rewards):
                continue
            gives = []
            for reward in rewards:
                for grant in grants[reward]:
                    if grant["Type"] == "Weapon":
                        gives.append({"Type": "Weapon", "Id": grant["Id"], "Name": _text(grant["NameKey"], problems)})
                        continue
                    # A give-all reward can list the same item twice; the player gets both.
                    same = next((given for given in gives if given["Type"] == grant["Type"] and given["Id"] == grant["Id"]), None)
                    if same:
                        same["AmountMin"] += grant["AmountMin"]
                        same["AmountMax"] += grant["AmountMax"]
                    else:
                        gives.append(dict(grant))
            exchange = {"Id": f"{puzzle}@{race}#{index}", "Puzzle": puzzle, **context,
                        "Option": _text(_field(option, "Name"), problems), "Cost": cost, "Gives": gives}
            previous = exchanges.get(exchange["Id"])
            if previous is not None and previous != exchange:
                raise ValueError(f"Two different exchanges share the identity {exchange['Id']}")
            exchanges[exchange["Id"]] = exchange
    return [exchanges[key] for key in sorted(exchanges)]


def parse_item_sources(mxml_path: str) -> dict:
    """unlockableseasonrewards.MXML plus the Twitch, platform, Quicksilver shop, expedition
    and exchange tables beside it, keyed by the item each one hands out."""
    folder = Path(mxml_path).parent
    problems: set[str] = set()
    items: dict[str, list[dict]] = {}

    def add(item_id: str, source: dict) -> None:
        if not item_id:
            raise ValueError(f"Item source without an item ID: {source}")
        items.setdefault(item_id, []).append(source)

    for row in _load(Path(mxml_path)).findall('./Property[@name="Table"]/Property'):
        seasons = [int(_number(node.get("value"))) for node in row.findall('./Property[@name="SeasonIds"]/Property')]
        stages = [int(_number(node.get("value"))) for node in row.findall('./Property[@name="StageIds"]/Property')]
        add(_field(row, "ID"), {"Type": "Expedition", "Expeditions": seasons, "Phases": stages,
                                "SwitchExclusive": _field(row, "SwitchExclusive") == "true"})
    for row in _load(folder / "unlockabletwitchrewards.MXML").findall('./Property[@name="Table"]/Property'):
        add(_field(row, "ProductId"), {"Type": "Twitch", "Drop": _field(row, "TwitchId")})
    for row in _load(folder / "unlockableplatformrewards.MXML").findall('./Property[@name="Table"]/Property'):
        add(_field(row, "ProductId"), {"Type": "Platform", "Reward": _field(row, "RewardId")})
    for row in _load(folder / "purchaseablespecials.MXML").findall('./Property[@name="Table"]/Property'):
        add(_field(row, "ID"), {"Type": "Quicksilver", "Shop": int(_number(_field(row, "ShopNumber"))),
                                "MissionTier": int(_number(_field(row, "MissionTier")))})

    expeditions = []
    for row in _load(folder / "historicalseasondatatable.MXML").findall('./Property[@name="Table"]/Property'):
        expeditions.append({
            "Number": int(_number(_field(row, "SeasonNumber"))),
            "Remix": int(_number(_field(row, "RemixNumber"))),
            "DisplayNumber": int(_number(_field(row, "DisplayNumber"))),
            "Name": _text(_field(row, "SeasonName"), problems),
        })

    shown_numbers = {row["DisplayNumber"] for row in expeditions}
    unknown = sorted({number for sources in items.values() for source in sources if source["Type"] == "Expedition"
                      for number in source["Expeditions"] if number not in shown_numbers})
    if unknown:
        # Rewards for an upcoming expedition can ship before its history row.
        print(f"  [WARN] Item sources name expeditions with no history row: {', '.join(map(str, unknown))}")

    reward_root = _load(folder / "rewardtable.MXML")
    exchanges = _exchanges(folder, reward_root, problems)
    for exchange in exchanges:
        for grant in exchange["Gives"]:
            if grant["Type"] != "Weapon":
                add(grant["Id"], {"Type": "Exchange", "Exchange": exchange["Id"]})
    _require(problems, "Item source")
    if not items or not expeditions:
        raise ValueError("Item source tables are empty or incompatible")
    for sources in items.values():
        sources.sort(key=lambda source: (source["Type"], str(sorted(source.items()))))
    return {
        "Expeditions": sorted(expeditions, key=lambda row: (row["Number"], row["Remix"])),
        "Exchanges": exchanges,
        "Items": dict(sorted(items.items())),
    }


# ---------- research trees ----------

def parse_research_trees(mxml_path: str) -> dict:
    """unlockableitemtrees.MXML: each station's trees, their currency and node order.
    A node's Price is the game's RecipeCost (products, base parts) or FragmentCost
    (technology), paid in the tree's currency."""
    root = _load(Path(mxml_path))
    folder = Path(mxml_path).parent
    # A blueprint's price: RecipeCost for products and base parts, FragmentCost for technology.
    prices = {}
    for table, field in (("nms_reality_gcproducttable.MXML", "RecipeCost"), ("nms_basepartproducts.MXML", "RecipeCost"),
                         ("nms_reality_gctechnologytable.MXML", "FragmentCost")):
        for row in _load(folder / table).findall('./Property[@name="Table"]/Property'):
            row_id = _field(row, "ID") or _field(row, "Id")
            if row_id and _field(row, field):
                prices.setdefault(row_id, _number(_field(row, field)))
    problems: set[str] = set()
    cost_types = {}
    for row in root.findall('./Property[@name="CostTypes"]/Property'):
        cost_type = _field(row, "TypeOfCost")
        cost_types[_field(row, "CostTypeID")] = {
            "Type": cost_type,
            "Id": _enum(row, "CurrencyType", "Currency") if cost_type == "Currency" else _field(row, "TypeID"),
        }
    groups = []
    trees_root = root.find('./Property[@name="Trees"]')
    for group in (trees_root if trees_root is not None else []):
        key = group.get("name")
        if key == "Test":
            continue
        trees = []
        for tree in group.findall('./Property[@name="Trees"]/Property'):
            nodes = []

            def walk(node, parent):
                item_id = _field(node, "Unlockable")
                if item_id:
                    nodes.append({"Id": item_id, "Parent": parent, "Price": prices.get(item_id)})
                for child in node.findall('./Property[@name="Children"]/Property'):
                    walk(child, item_id or parent)

            walk(tree.find('./Property[@name="Root"]'), None)
            cost_id = _field(tree, "CostTypeID")
            if cost_id and cost_id not in cost_types:
                raise ValueError(f"Research tree in {key} uses an unknown cost type: {cost_id}")
            trees.append({"Name": _text(_field(tree, "Title"), problems),
                          "Cost": cost_types.get(cost_id), "Nodes": nodes})
        # Station names are framed by an inline bullet image, which localization flattens to its name.
        name = _text(_field(group, "Title"), problems)
        name = " ".join(name.replace("DIAMONDBULLET", " ").split()) if name else name
        groups.append({"Id": key, "Name": name,
                       "Trees": [tree for tree in trees if tree["Nodes"]]})
    _require(problems, "Research tree")
    if not groups:
        raise ValueError("Research tree source is empty or incompatible")
    return {"Groups": groups}
