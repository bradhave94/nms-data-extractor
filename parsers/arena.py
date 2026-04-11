"""Parse arena-related game data: move sets, arena modes, medals, pet shop,
pet accessories, egg overrides, and pet behaviours."""
from .base_parser import EXMLParser, humanize_id, normalize_game_icon_path
from .product_lookup import load_product_lookup

_ACCESSORY_TIP_INDEX = {
    "CargoCylinder": 1, "Containers": 2, "ShieldArmour": 3,
    "SolarBattery": 4, "Tank": 5, "WingPanel": 6,
    "TravelPack": 7, "SpacePack": 8, "CargoLong": 9,
    "Antennae": 10, "Computer": 11, "Toolbelt": 12,
    "LeftCanisters": 13, "RightCanisters": 13,
    "LeftEnergyCoil": 14, "RightEnergyCoil": 14,
    "LeftFrigateTurret": 15, "RightFrigateTurret": 15,
    "LeftHeadLights": 16, "RightHeadLights": 16,
    "LeftArmourPlate": 17, "RightArmourPlate": 17,
    "LeftTurret": 18, "RightTurret": 18,
    "LeftSupportSystem": 19, "RightSupportSystem": 19,
    "LeftMechanicalPaw": 21, "RightMechanicalPaw": 21, "MechanicalPaw": 21,
}


def parse_move_sets(mxml_path: str) -> list:
    """Parse petbattlermovesetstable.MXML into move set archetypes."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    move_sets = []
    table = root.find('.//Property[@name="MoveSets"]')
    if table is None:
        print("Warning: Could not find MoveSets in move sets table")
        return move_sets

    slot_names = ["Slot1", "Slot2", "Slot3", "Slot4"]

    for row in table.findall('./Property[@name="MoveSets"]'):
        ms_id = parser.get_property_value(row, "ID", "")
        if not ms_id:
            continue

        slots = []
        for slot_name in slot_names:
            slot_elem = row.find(f'./Property[@name="{slot_name}"]')
            if slot_elem is None:
                continue
            options = []
            allowed = slot_elem.find('.//Property[@name="AllowedMoveTemplates"]')
            if allowed is not None:
                for opt in allowed.findall('./Property[@name="AllowedMoveTemplates"]'):
                    template = parser.get_property_value(opt, "Template", "")
                    if not template:
                        continue
                    options.append({
                        "Template": template,
                        "CooldownMin": parser.parse_value(
                            parser.get_property_value(opt, "CooldownMin", "0")
                        ),
                        "CooldownMax": parser.parse_value(
                            parser.get_property_value(opt, "CooldownMax", "0")
                        ),
                        "Weighting": parser.parse_value(
                            parser.get_property_value(opt, "Weighting", "0")
                        ),
                    })
            if options:
                slots.append({
                    "Slot": slot_name,
                    "Options": options,
                })

        move_sets.append({
            "Id": ms_id,
            "Name": humanize_id(ms_id),
            "Slots": slots if slots else None,
        })

    print(f"[OK] Parsed {len(move_sets)} move set archetypes")
    return move_sets


def parse_arena_modes(mxml_path: str) -> list:
    """Parse gametablesdatatable.MXML into arena battle configurations."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    modes = []

    configs_prop = root.find('.//Property[@name="GameTableConfigs"]')
    config_map = {}
    if configs_prop is not None:
        for cfg in configs_prop.findall('./Property[@name="GameTableConfigs"]'):
            cfg_id = parser.get_property_value(cfg, "Id", "")
            if cfg_id:
                config_map[cfg_id] = {
                    "SpawnDataId": parser.get_property_value(cfg, "SpawnDataId", "") or None,
                    "GameConfigId": parser.get_property_value(cfg, "GameConfigId", "") or None,
                }

    game_config_prop = root.find('.//Property[@name="GameTableGameConfig"]')
    game_configs = {}
    if game_config_prop is not None:
        for gc in game_config_prop.findall('./Property[@name="GameTableGameConfig"]'):
            gc_id = parser.get_property_value(gc, "Id", "")
            if not gc_id:
                continue
            game_mode = parser.get_nested_enum(gc, "ForcedGameMode", "GameTableMode", "")
            reward_win = parser.get_property_value(gc, "RewardIdWin", "") or None
            reward_loss = parser.get_property_value(gc, "RewardIdLoss", "") or None
            xp_mult = parser.parse_value(
                parser.get_property_value(gc, "ExperienceRewardMultiplier", "1")
            )
            game_configs[gc_id] = {
                "GameMode": game_mode or None,
                "RewardWin": reward_win,
                "RewardLoss": reward_loss,
                "ExperienceMultiplier": xp_mult,
            }

    for mode_id, cfg_data in config_map.items():
        gc_data = game_configs.get(cfg_data.get("GameConfigId", ""), {})
        modes.append({
            "Id": mode_id,
            "Name": humanize_id(mode_id),
            "SpawnDataId": cfg_data.get("SpawnDataId"),
            "GameConfigId": cfg_data.get("GameConfigId"),
            "GameMode": gc_data.get("GameMode"),
            "RewardWin": gc_data.get("RewardWin"),
            "RewardLoss": gc_data.get("RewardLoss"),
            "ExperienceMultiplier": gc_data.get("ExperienceMultiplier"),
        })

    print(f"[OK] Parsed {len(modes)} arena modes")
    return modes


def parse_arena_league_medals(mxml_path: str) -> list:
    """Parse PB_* stat tracks from leveledstatstable.MXML into medal progressions."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

    PB_STAT_IDS = {"PB_BOSS_WINS", "PB_WINS", "PB_CHALL_WINS", "PB_PETS_MAXED", "PB_D_NEXUS"}

    medals = []
    table = root.find('.//Property[@name="LeveledStatTable"]')
    if table is None:
        table = root
    for row in (table.findall('./Property[@name="LeveledStatTable"]') or
                root.findall('.//Property[@name="LeveledStatTable"]')):
        stat_id = parser.get_property_value(row, "StatId", "")
        if stat_id not in PB_STAT_IDS:
            continue

        stat_title_key = parser.get_property_value(row, "StatTitle", "")
        stat_title = localization.get(stat_title_key, stat_title_key) if stat_title_key else None

        levels = []
        levels_prop = row.find('.//Property[@name="StatLevels"]')
        if levels_prop is not None:
            for lvl in levels_prop.findall('./Property[@name="StatLevels"]'):
                level_name_key = parser.get_property_value(lvl, "LevelName", "")
                level_name = localization.get(level_name_key, level_name_key) if level_name_key else None
                value_prop = lvl.find('.//Property[@name="Value"]')
                threshold = 0
                if value_prop is not None:
                    threshold = parser.parse_value(
                        parser.get_property_value(value_prop, "IntValue", "0")
                    )
                levels.append({
                    "LevelName": level_name,
                    "LevelNameKey": level_name_key or None,
                    "Threshold": threshold,
                })

        medals.append({
            "Id": stat_id,
            "StatTitle": stat_title,
            "StatTitleKey": stat_title_key or None,
            "Levels": levels if levels else None,
        })

    print(f"[OK] Parsed {len(medals)} arena league medal tracks")
    return medals


def parse_pet_shop(mxml_path: str) -> list:
    """Parse petshopitemstable.MXML into prize creature egg entries,
    enriched with product names/descriptions/icons from the product table."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

    from pathlib import Path
    product_table_path = Path(mxml_path).parent / 'nms_reality_gcproducttable.MXML'
    if not product_table_path.exists():
        product_table_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'
    product_lookup = {}
    if product_table_path.exists():
        product_lookup = load_product_lookup(
            parser=parser, localization=localization,
            products_mxml_path=product_table_path, include_requirements=False,
        )

    items = []
    table = root.find('.//Property[@name="Items"]')
    if table is None:
        print("Warning: Could not find Items in pet shop table")
        return items

    for row in table.findall('./Property[@name="Items"]'):
        product_id = parser.get_property_value(row, "ProductID", "")
        if not product_id:
            continue
        product = product_lookup.get(product_id, {})
        icon_path = product.get("IconPath") or None
        items.append({
            "Id": product_id,
            "ProductID": product_id,
            "Icon": f"{product_id}.png",
            "Name": product.get("Name") or product_id,
            "Group": product.get("Group") or None,
            "Description": product.get("Description") or None,
            "IconPath": icon_path,
            "LinkedRewardID": parser.get_property_value(row, "LinkedRewardID", "") or None,
            "RequiredStat": parser.get_property_value(row, "RequiredStat", "") or None,
            "RequiredStatTier": parser.parse_value(
                parser.get_property_value(row, "RequiredStatTier", "0")
            ),
            "Price": parser.parse_value(
                parser.get_property_value(row, "Price", "0")
            ),
        })

    print(f"[OK] Parsed {len(items)} pet shop items")
    return items


def parse_pet_accessories(mxml_path: str) -> list:
    """Parse petaccessorytable.MXML into accessory entries with slot groups."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

    accessories = []
    acc_prop = root.find('.//Property[@name="Accessories"]')
    if acc_prop is not None:
        for acc in acc_prop.findall('./Property'):
            name = acc.get("name", "")
            if not name or name == "None":
                continue
            descriptor = ""
            inner = acc.find('./Property[@name="Descriptor"]')
            if inner is not None:
                descriptor = inner.get("value", "")
            else:
                descriptor = parser.get_property_value(acc, "Descriptor", "")

            tip_idx = _ACCESSORY_TIP_INDEX.get(name)
            display_name = None
            if tip_idx is not None:
                display_name = localization.get(f"UI_TIP_PET_ACCESSORY_{tip_idx}")
            if not display_name:
                display_name = humanize_id(name)

            accessories.append({
                "Id": name,
                "Name": display_name,
                "Descriptor": descriptor or None,
            })

    groups = []
    groups_prop = root.find('.//Property[@name="AccessoryGroups"]')
    if groups_prop is not None:
        for grp in groups_prop.findall('./Property[@name="AccessoryGroups"]'):
            grp_id = parser.get_property_value(grp, "Id", "")
            if not grp_id:
                continue
            disallowed = []
            dis_prop = grp.find('.//Property[@name="DisallowedAccessories"]')
            if dis_prop is not None:
                for da in dis_prop.findall('./Property[@name="DisallowedAccessories"]'):
                    val = parser.get_nested_enum(da, "PetAccessory", default="")
                    if not val:
                        val = da.get("value", "")
                    if val:
                        disallowed.append(val)
            groups.append({
                "Id": grp_id,
                "DisallowedAccessories": disallowed if disallowed else None,
            })

    result = []
    for acc in accessories:
        acc_copy = dict(acc)
        acc_copy["Groups"] = [
            g["Id"] for g in groups
            if acc["Id"] not in (g.get("DisallowedAccessories") or [])
        ] or None
        result.append(acc_copy)

    print(f"[OK] Parsed {len(result)} pet accessories")
    return result


def parse_pet_behaviours(mxml_path: str) -> list:
    """Parse creaturepetbehaviourtable.MXML into companion behaviour entries."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

    behaviours = []
    table = root.find('.//Property[@name="Behaviours"]')
    if table is None:
        print("Warning: Could not find Behaviours in pet behaviour table")
        return behaviours

    for row in table.findall('./Property'):
        name = row.get("name", "")
        if not name or name == "None":
            continue

        reactive = parser.parse_value(
            parser.get_property_value(row, "ReactiveBehaviour", "false")
        )
        useful = parser.parse_value(
            parser.get_property_value(row, "UsefulBehaviour", "false")
        )
        weight = parser.parse_value(
            parser.get_property_value(row, "Weight", "0")
        )
        min_time = parser.parse_value(
            parser.get_property_value(row, "MinPerformTime", "0")
        )
        max_time = parser.parse_value(
            parser.get_property_value(row, "MaxPerformTime", "0")
        )
        cooldown = parser.parse_value(
            parser.get_property_value(row, "CooldownTime", "0")
        )
        validity = parser.get_property_value(row, "PetBehaviourValidity", "")
        label_key = parser.get_property_value(row, "LabelText", "")
        label = localization.get(label_key, label_key) if label_key else None

        behaviours.append({
            "Id": name,
            "Name": humanize_id(name),
            "Label": label,
            "ReactiveBehaviour": reactive,
            "UsefulBehaviour": useful,
            "Weight": weight,
            "MinPerformTime": min_time,
            "MaxPerformTime": max_time,
            "CooldownTime": cooldown,
            "Validity": validity or None,
        })

    print(f"[OK] Parsed {len(behaviours)} pet behaviours")
    return behaviours
