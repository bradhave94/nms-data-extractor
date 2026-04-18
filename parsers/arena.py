"""Parse arena-related game data: move sets, arena modes, medals, pet shop,
pet accessories, egg overrides, pet behaviours, and creature globals."""
from .base_parser import (
    EXMLParser, humanize_id, normalize_game_icon_path, shared_texture_icon_name,
)
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
    localization = parser.load_localization()

    _MODE_LOC_KEYS = {
        "PVP_STANDARD": {"desc": "UI_PB_TUT_DETAIL1"},
        "PETBATTLE_NEXUS_PVE": {"desc": "UI_PB_TUT_END_DETAIL3"},
        "PETBATTLE_SYSTEM_CHAMPION": {"desc": "UI_PB_BOSS_HINT_DESC"},
        "PETBATTLE_PLANET_STANDARD": {"desc": "UI_PB_CHALLENGER_MSG1"},
        "PETBATTLE_SYSTEM_STANDARD": {"desc": "UI_PB_CHALLENGER_MSG1"},
        "PETBATTLE_SETTLEMENT": {"desc": "UI_PB_TUT_BRIDGE_DESC"},
        "PETBATTLE_LARGEBUILDING": {"desc": "UI_PB_CHALLENGER_MSG1"},
        "PETBATTLE_PIRATES": {"desc": "UI_PB_CHALLENGER_MSG1"},
    }

    modes = []

    configs_prop = root.find('.//Property[@name="GameTableConfigs"]')
    config_map = {}
    if configs_prop is not None:
        for cfg in configs_prop.findall('./Property[@name="GameTableConfigs"]'):
            cfg_id = parser.get_property_value(cfg, "Id", "")
            if cfg_id:
                config_map[cfg_id] = {
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
            presets = []
            presets_prop = gc.find('.//Property[@name="PresetAIPlayers"]')
            if presets_prop is not None:
                for p in presets_prop.findall('./Property[@name="PresetAIPlayers"]'):
                    val = p.get("value", "")
                    if val:
                        presets.append(val)
            game_configs[gc_id] = {
                "GameMode": game_mode or None,
                "RewardWin": reward_win,
                "RewardLoss": reward_loss,
                "ExperienceMultiplier": xp_mult,
                "PresetAIPlayers": presets,
            }

    ai_configs_prop = root.find('.//Property[@name="AIPlayerConfigs"]')
    ai_difficulty = {}
    if ai_configs_prop is not None:
        for ai in ai_configs_prop.findall('./Property[@name="AIPlayerConfigs"]'):
            ai_id = ai.get("_id", "")
            if not ai_id:
                continue
            diff = parser.get_nested_enum(ai, "Difficulty", "GameTableAIDifficulty", "")
            if diff:
                ai_difficulty[ai_id] = diff

    for mode_id, cfg_data in config_map.items():
        gc_data = game_configs.get(cfg_data.get("GameConfigId", ""), {})
        game_mode_raw = gc_data.get("GameMode") or ""
        game_mode_label = "Creature Battle" if game_mode_raw == "PetBattler" else (
            "Dice Game" if game_mode_raw == "DiceGame" else game_mode_raw
        )
        difficulty = None
        for preset_id in gc_data.get("PresetAIPlayers", []):
            d = ai_difficulty.get(preset_id)
            if d:
                difficulty = d
                break

        loc_keys = _MODE_LOC_KEYS.get(mode_id, {})
        desc_key = loc_keys.get("desc", "")
        raw_desc = localization.get(desc_key, "") if desc_key else ""
        description = raw_desc.split("\n")[0].strip() if raw_desc else None

        modes.append({
            "Id": mode_id,
            "Name": humanize_id(mode_id),
            "Description": description,
            "GameMode": game_mode_label or None,
            "Difficulty": difficulty,
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

    _MEDAL_LOC = {
        "PB_BOSS_WINS": {"medal": "UI_MEDAL_PB_BOSS_WINS", "wiki_name": "UI_WIKI_PB_BOSS_NAME", "wiki_desc": "UI_WIKI_PB_BOSS_DESC"},
        "PB_WINS": {"medal": "UI_MEDAL_PB_WINS", "medal_desc": "UI_MEDAL_DESC_PB_WINS", "wiki_name": "UI_WIKI_PB_WINS_NAME", "wiki_desc": "UI_WIKI_PB_WINS_DESC"},
        "PB_PETS_MAXED": {"wiki_name": "UI_WIKI_PETS_MAXED_NAME", "wiki_desc": "UI_WIKI_PETS_MAXED_DESC"},
        "PB_D_NEXUS": {"medal": "UI_MEDAL_PB_D_NEXUS", "medal_desc": "UI_MEDAL_DESC_PB_D_NEXUS", "wiki_name": "UI_WIKI_PB_D_NEXUS_NAME", "wiki_desc": "UI_WIKI_PB_D_NEXUS_DESC"},
    }
    for medal in medals:
        loc_keys = _MEDAL_LOC.get(medal["Id"], {})
        medal_name = localization.get(loc_keys.get("medal", ""), "")
        medal_desc = localization.get(loc_keys.get("medal_desc", ""), "")
        wiki_name = localization.get(loc_keys.get("wiki_name", ""), "")
        wiki_desc = localization.get(loc_keys.get("wiki_desc", ""), "")
        if medal_name:
            medal["MedalName"] = medal_name
        if medal_desc:
            medal["MedalDescription"] = medal_desc.split("\n")[0].strip()
        if wiki_name:
            medal["WikiName"] = wiki_name
        if wiki_desc:
            medal["WikiDescription"] = wiki_desc

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
        tip_idx = _ACCESSORY_TIP_INDEX.get(acc["Id"])
        if tip_idx is not None:
            chat_desc = localization.get(f"CHAT_PET_ACCESSORY_{tip_idx}", "")
            if chat_desc:
                acc_copy["Description"] = chat_desc
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

    _BEHAVIOUR_LABEL_MAP = {
        "ScanForResource": "UI_PET_LABEL_MINING",
        "FindResource": "UI_PET_LABEL_MINING",
        "Mine": "UI_PET_LABEL_SEARCHING",
        "Explore": "UI_PET_LABEL_EXPLORE",
        "FindHazards": "UI_PET_LABEL_EXPLORE",
        "FindBuilding": "UI_PET_LABEL_BUILDING",
        "Attack": "UI_PET_LABEL_HUNT",
        "Eat": "UI_PET_LABEL_EATING",
        "Emote": "UI_PET_LABEL_EMOTE",
        "FollowPlayer": "UI_PET_LABEL_DIST_FOLLOW",
        "OrderedToPos": "UI_PET_LABEL_ORDERS",
        "ComeHere": "UI_PET_LABEL_ORDERS",
    }

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

        ui_label_key = _BEHAVIOUR_LABEL_MAP.get(name, "")
        ui_label = localization.get(ui_label_key, "") if ui_label_key else ""

        trait_modifiers = []
        trait_mod_container = row.find('./Property[@name="TraitBehaviourModifiers"]')
        if trait_mod_container is not None:
            for tm in trait_mod_container.findall('./Property[@name="TraitBehaviourModifiers"]'):
                trait_modifiers.append({
                    "Trait": parser.get_nested_enum(tm, "Trait", "PetTrait", ""),
                    "TraitMin": parser.parse_value(parser.get_property_value(tm, "TraitMin", "0")),
                    "TraitMax": parser.parse_value(parser.get_property_value(tm, "TraitMax", "0")),
                    "WeightModifierMin": parser.parse_value(parser.get_property_value(tm, "WeightModifierMin", "0")),
                    "WeightModifierMax": parser.parse_value(parser.get_property_value(tm, "WeightModifierMax", "0")),
                    "CooldownModifierMin": parser.parse_value(parser.get_property_value(tm, "CooldownModifierMin", "0")),
                    "CooldownModifierMax": parser.parse_value(parser.get_property_value(tm, "CooldownModifierMax", "0")),
                })

        mood_modifiers = []
        mood_mod_container = row.find('./Property[@name="MoodBehaviourModifiers"]')
        if mood_mod_container is not None:
            for mm in mood_mod_container.findall('./Property[@name="MoodBehaviourModifiers"]'):
                mood_modifiers.append({
                    "Mood": parser.get_nested_enum(mm, "Mood", "PetMood", ""),
                    "MoodMin": parser.parse_value(parser.get_property_value(mm, "MoodMin", "0")),
                    "MoodMax": parser.parse_value(parser.get_property_value(mm, "MoodMax", "0")),
                    "WeightModifierMin": parser.parse_value(parser.get_property_value(mm, "WeightModifierMin", "0")),
                    "WeightModifierMax": parser.parse_value(parser.get_property_value(mm, "WeightModifierMax", "0")),
                    "CooldownModifierMin": parser.parse_value(parser.get_property_value(mm, "CooldownModifierMin", "0")),
                    "CooldownModifierMax": parser.parse_value(parser.get_property_value(mm, "CooldownModifierMax", "0")),
                })

        follow_ups = []
        follow_up_container = row.find('./Property[@name="FollowUpBehaviours"]')
        if follow_up_container is not None:
            for fu in follow_up_container.findall('./Property[@name="FollowUpBehaviours"]'):
                follow_ups.append({
                    "Behaviour": parser.get_nested_enum(fu, "Behaviour", "PetBehaviour", ""),
                    "TraitBased": parser.parse_value(parser.get_property_value(fu, "TraitBased", "false")),
                    "Trait": parser.get_nested_enum(fu, "Trait", "PetTrait", ""),
                    "TraitMin": parser.parse_value(parser.get_property_value(fu, "TraitMin", "0")),
                    "TraitMax": parser.parse_value(parser.get_property_value(fu, "TraitMax", "0")),
                    "WeightMin": parser.parse_value(parser.get_property_value(fu, "WeightMin", "0")),
                    "WeightMax": parser.parse_value(parser.get_property_value(fu, "WeightMax", "0")),
                })

        mood_on_complete = None
        mood_complete_el = row.find('./Property[@name="MoodModifyOnComplete"]')
        if mood_complete_el is not None:
            hungry = parser.parse_value(parser.get_property_value(mood_complete_el, "Hungry", "0"))
            lonely = parser.parse_value(parser.get_property_value(mood_complete_el, "Lonely", "0"))
            if hungry or lonely:
                mood_on_complete = {"Hungry": hungry, "Lonely": lonely}

        entry = {
            "Id": name,
            "Name": humanize_id(name),
            "Label": label,
            "UILabel": ui_label or None,
            "ReactiveBehaviour": reactive,
            "UsefulBehaviour": useful,
            "Weight": weight,
            "MinPerformTime": min_time,
            "MaxPerformTime": max_time,
            "CooldownTime": cooldown,
            "Validity": validity or None,
        }
        if trait_modifiers:
            entry["TraitModifiers"] = trait_modifiers
        if mood_modifiers:
            entry["MoodModifiers"] = mood_modifiers
        if follow_ups:
            entry["FollowUpBehaviours"] = follow_ups
        if mood_on_complete:
            entry["MoodOnComplete"] = mood_on_complete

        behaviours.append(entry)

    print(f"[OK] Parsed {len(behaviours)} pet behaviours")
    return behaviours


def parse_arena_ai_configs(mxml_path: str) -> list:
    """Parse AIPlayerConfigs from gametablesdatatable.MXML into AI player entries."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    configs = []
    table = root.find('.//Property[@name="AIPlayerConfigs"]')
    if table is None:
        print("Warning: Could not find AIPlayerConfigs in game tables")
        return configs

    for row in table.findall('./Property[@name="AIPlayerConfigs"]'):
        config_id = row.get("_id", "")
        if not config_id:
            continue

        difficulty = parser.get_nested_enum(row, "Difficulty", "GameTableAIDifficulty", "")

        game_config_elem = row.find('./Property[@name="GameConfig"]')
        game_type = None
        team_seed_source = None
        pets = None

        if game_config_elem is not None:
            pet_battler = game_config_elem.find(
                './/Property[@name="GcGameTableAIPlayerConfigPetBattler"]'
            )
            dice_game = game_config_elem.find(
                './/Property[@name="GcGameTableAIPlayerConfigDiceGame"]'
            )

            if pet_battler is not None:
                game_type = "PetBattler"
                team_seed_source = parser.get_property_value(
                    pet_battler, "PetBattleAITeamSeedSource", ""
                ) or None

                pets_container = pet_battler.find('./Property[@name="Pets"]')
                if pets_container is not None:
                    pets = []
                    for pet in pets_container.findall('./Property[@name="Pets"]'):
                        pool = parser.get_property_value(
                            pet, "PetBattlerAIPetPool", ""
                        )
                        min_level = parser.parse_value(
                            parser.get_property_value(pet, "MinLevel", "-1")
                        )
                        max_level = parser.parse_value(
                            parser.get_property_value(pet, "MaxLevel", "-1")
                        )
                        pets.append({
                            "Pool": pool or None,
                            "MinLevel": min_level,
                            "MaxLevel": max_level,
                        })
            elif dice_game is not None:
                game_type = "DiceGame"

        configs.append({
            "Id": config_id,
            "Difficulty": difficulty or None,
            "GameType": game_type,
            "TeamSeedSource": team_seed_source or None,
            "Pets": pets,
        })

    print(f"[OK] Parsed {len(configs)} arena AI player configs")
    return configs


def parse_arena_rewards(mxml_path: str) -> list:
    """Parse R_PB_* reward entries from rewardtable.MXML."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    rewards = []
    all_entries = []
    for section_name in ("GenericTable", "GameTableRewards"):
        section = root.find(f'.//Property[@name="{section_name}"]')
        if section is not None:
            all_entries.extend(section.findall(f'./Property[@name="{section_name}"]'))

    for row in all_entries:
        reward_id = row.get("_id", "") or parser.get_property_value(row, "Id", "")
        if not reward_id or not reward_id.startswith("R_PB_"):
            continue

        list_elem = row.find('./Property[@name="List"]')
        reward_choice = ""
        increment_stat = None
        items = []

        if list_elem is not None:
            reward_choice = parser.get_property_value(list_elem, "RewardChoice", "")
            raw_stat = parser.get_property_value(list_elem, "IncrementStat", "")
            increment_stat = raw_stat if raw_stat else None

            inner_list = list_elem.find('./Property[@name="List"]')
            if inner_list is not None:
                for item_elem in inner_list.findall('./Property[@name="List"]'):
                    chance = parser.parse_value(
                        parser.get_property_value(item_elem, "PercentageChance", "100")
                    )
                    reward_prop = item_elem.find('./Property[@name="Reward"]')
                    if reward_prop is None:
                        continue
                    reward_type_name = reward_prop.get("value", "")
                    item_entry = _parse_reward_item(parser, reward_prop, reward_type_name, chance)
                    if item_entry:
                        items.append(item_entry)

        rewards.append({
            "Id": reward_id,
            "RewardChoice": reward_choice or None,
            "IncrementStat": increment_stat,
            "Items": items if items else None,
        })

    print(f"[OK] Parsed {len(rewards)} arena reward entries")
    return rewards


def _parse_reward_item(parser: EXMLParser, reward_prop, reward_type_name: str, chance: float) -> dict | None:
    """Extract a simplified reward item from a GcReward* property."""
    if "GcRewardMoney" in reward_type_name:
        amount_min = parser.parse_value(parser.get_property_value(reward_prop, "AmountMin", "0"))
        amount_max = parser.parse_value(parser.get_property_value(reward_prop, "AmountMax", "0"))
        if not amount_min and not amount_max:
            amount_min = parser.parse_value(parser.get_property_value(reward_prop, "Amount", "0"))
            amount_max = amount_min
        currency = parser.get_nested_enum(reward_prop, "Currency", "Currency", "")
        return {
            "Type": "Currency",
            "Id": currency or None,
            "AmountMin": amount_min,
            "AmountMax": amount_max,
            "Chance": chance,
        }

    if "GcRewardSpecificProduct" in reward_type_name:
        product_id = parser.get_property_value(reward_prop, "ID", "")
        if not product_id:
            product_id = parser.get_property_value(reward_prop, "Id", "")
        if not product_id:
            product_id = parser.get_property_value(reward_prop, "Default", "")
            if not product_id:
                product_prop = reward_prop.find('.//Property[@name="ProductId"]')
                if product_prop is not None:
                    product_id = product_prop.get("value", "")
        amount = parser.parse_value(parser.get_property_value(reward_prop, "Amount", "1"))
        return {
            "Type": "Product",
            "ProductId": product_id or None,
            "Amount": amount,
            "Chance": chance,
        }

    if "GcRewardStatBoost" in reward_type_name:
        stat_id = parser.get_property_value(reward_prop, "Stat", "")
        amount = parser.parse_value(parser.get_property_value(reward_prop, "Amount", "1"))
        return {
            "Type": "Stat",
            "StatId": stat_id or None,
            "Amount": amount,
            "Chance": chance,
        }

    return {
        "Type": reward_type_name.replace("GcReward", "") if reward_type_name else "Unknown",
        "Chance": chance,
    }


def _build_companion_chat_messages(localization: dict) -> dict:
    """Extract CHAT_PET_* companion chat messages from localization, organized by category."""
    import re

    messages = {}
    pattern = re.compile(r'^CHAT_PET_(.+?)_(\d+)$')

    for key, value in localization.items():
        if not key.startswith('CHAT_PET_') or key.startswith('CHAT_PET_ACCESSORY_'):
            continue
        match = pattern.match(key)
        if not match:
            continue
        category = match.group(1)
        if category not in messages:
            messages[category] = []
        if value and value not in messages[category]:
            messages[category].append(value)

    return {k: sorted(v) for k, v in sorted(messages.items())}


def parse_creature_globals(mxml_path: str) -> dict:
    """Parse gccreatureglobals.MXML into global creature config data."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

    # --- Temperaments (note: game file uses "Temperments") ---
    temperaments = []
    temp_prop = root.find('.//Property[@name="Temperments"]')
    if temp_prop is not None:
        for child in temp_prop.findall('./Property'):
            tid = child.get("name", "")
            if not tid or tid == "None":
                continue
            loc_key = child.get("value", "")
            temperaments.append({
                "Id": tid,
                "LocKey": loc_key,
                "DisplayName": localization.get(loc_key, "") or humanize_id(tid),
            })

    # --- Diets ---
    diets = []
    diet_prop = root.find('.//Property[@name="Diets"]')
    if diet_prop is not None:
        for child in diet_prop.findall('./Property'):
            did = child.get("name", "")
            if not did:
                continue
            loc_key = child.get("value", "")
            diets.append({
                "Id": did,
                "LocKey": loc_key,
                "DisplayName": localization.get(loc_key, "") or humanize_id(did),
            })

    # --- PetEggs ---
    pet_eggs = []
    eggs_prop = root.find('.//Property[@name="PetEggs"]')
    if eggs_prop is not None:
        for egg in eggs_prop.findall('./Property[@name="PetEggs"]'):
            egg_id = parser.get_property_value(egg, "Id", "")
            if not egg_id:
                continue
            icon_raw = parser.get_property_value(
                egg.find('.//Property[@name="IconResource"]'), "Filename", ""
            )
            icon_path = normalize_game_icon_path(icon_raw) if icon_raw else ""
            icon_name = shared_texture_icon_name(icon_path) or ""

            egg_res_elem = egg.find('.//Property[@name="EggResource"]')
            egg_model = ""
            if egg_res_elem is not None:
                egg_model = parser.get_property_value(egg_res_elem, "Filename", "")

            hatch_scale = parser.parse_value(
                parser.get_property_value(egg, "HatchScale", "0")
            )
            hatch_offset = parser.parse_value(
                parser.get_property_value(egg, "HatchOffset", "0")
            )
            pet_eggs.append({
                "Id": egg_id,
                "Icon": icon_name,
                "IconPath": icon_path,
                "EggModel": egg_model,
                "HatchScale": hatch_scale,
                "HatchOffset": hatch_offset,
            })

    # --- Enrich Temperaments with description strings ---
    _TEMP_LOC_MAP = {
        "Predator": ("TEMPERAMENT_PREDATOR", 15),
        "PlayerPredator": ("TEMPERAMENT_PLAYERPREDATOR", 10),
        "Prey": ("TEMPERAMENT_PREY", 17),
        "Passive": ("TEMPERAMENT_PASSIVE", 17),
        "Bird": ("TEMPERAMENT_BIRD", 15),
        "FishPrey": ("TEMPERAMENT_FISH", 25),
    }
    for temp in temperaments:
        temp_id = temp["Id"]
        loc_info = _TEMP_LOC_MAP.get(temp_id)
        if loc_info:
            prefix, count = loc_info
            descs = [localization.get(f"{prefix}{i}", "") for i in range(1, count + 1)]
            temp["Descriptions"] = [d for d in descs if d]

    # --- Egg Sequencer Constants ---
    int_keys = [
        "PetEggLayingInterval", "PetEggFirstEggDelay",
        "PetEggModificationTime", "PetEggModificationItemLimit",
    ]
    float_keys = [
        "PetEggSubstanceModifier", "PetEggScaleRangeModifier",
        "PetEggScaleRangeMax", "PetEggTraitRangeModifier",
        "PetEggTraitRangeMax", "PetEggOverdosageModifier",
        "PetEggMaxOverdosage", "PetEggMaxTopDescriptorChangeChance",
        "PetEggAccessoryChanceModifier", "PetEggMaxAccessoriesChangeChance",
    ]
    string_keys = ["PetEggMaxChangeProduct"]

    egg_constants: dict = {}
    for key in int_keys:
        raw = parser.get_property_value(root, key, "0")
        egg_constants[key] = int(parser.parse_value(raw))
    for key in float_keys:
        raw = parser.get_property_value(root, key, "0")
        egg_constants[key] = float(parser.parse_value(raw))
    for key in string_keys:
        egg_constants[key] = parser.get_property_value(root, key, "")

    # --- TrustConstants ---
    trust_props = [
        "PetTrustOnAdoption", "PetTrustOnHatch", "PetTrustIncreaseStep",
        "PetTrustDecreaseStep", "PetTrustIncreaseThreshold", "PetTrustDecreaseThreshold",
        "PetMinTrust", "PetTrustChangeInterval",
    ]
    trust_constants = {}
    for prop_name in trust_props:
        val = parser.get_property_value(root, prop_name, "")
        if val:
            trust_constants[prop_name] = parser.parse_value(val)

    # --- FeedingConstants ---
    feeding_props = [
        "FeedingTaskAmount", "FeedingFollowTime", "FeedingNoticeTime",
        "FeedingNoticeDistance", "PetInteractBaseRange", "PetTickleChatChance",
        "PetTreatChatChance", "PetChatCooldown", "PetChatUseTraitTemplateChance",
    ]
    feeding_constants = {}
    for prop_name in feeding_props:
        val = parser.get_property_value(root, prop_name, "")
        if val:
            feeding_constants[prop_name] = parser.parse_value(val)

    # --- MovementConstants ---
    movement_props = [
        "PetAnimSpeedBoostSmallerThan", "PetAnimSpeedBoostStrength",
        "PetAnimSpeedMax", "PetAnimSpeedMin",
        "PetMinSummonDistance", "PetMaxSummonDistance",
        "PetFollowRunPlayerDistance", "PetPlayerSpeedSmoothTime",
    ]
    movement_constants = {}
    for prop_name in movement_props:
        val = parser.get_property_value(root, prop_name, "")
        if val:
            movement_constants[prop_name] = parser.parse_value(val)

    # --- AffinityLabels ---
    affinity_labels = {}
    _AFF_LOC_MAP = {
        "Normal": "NONE", "Lush": "LUSH", "Fire": "HOT", "Cold": "COLD",
        "Toxic": "TOX", "Barren": "DUST", "Radioactive": "RADIO",
        "Weird": "WEIRD", "Mech": "MECH",
    }
    for game_id, loc_suffix in _AFF_LOC_MAP.items():
        label = localization.get(f"UI_PB_AFFINITY_{loc_suffix}_L", "")
        if label:
            affinity_labels[game_id] = label

    # --- BattleStats ---
    battle_stats = {}
    for key_suffix, field in [("BUDGET", "CombatEffectiveness"), ("SPEED", "Agility"),
                               ("HEALTH", "Health"), ("DODGE", "DodgeChance"),
                               ("CRIT", "CriticalHitChance"), ("HIT", "Accuracy"),
                               ("SHIELD", "DefensiveStrength")]:
        header = localization.get(f"UI_PB_STAT_HEADER_{key_suffix}", "")
        label = localization.get(f"UI_PB_STAT_{key_suffix}", "")
        if header or label:
            battle_stats[field] = {"Header": header or None, "Label": label or None}

    # --- ClimateLabels ---
    climate_labels = {}
    for suffix in ["HOT", "FROZEN", "SWAMP", "LAVA", "TOXIC", "RADIO",
                    "LUSH", "DUST", "WEIRD", "DEAD", "WATER", "GAS"]:
        val = localization.get(f"UI_PET_CLIMATE_{suffix}", "")
        if val:
            climate_labels[suffix] = val

    # --- TraitClasses ---
    trait_classes = {}
    for trait_key, trait_name in [("AGGRESSIVE", "Aggression"), ("HELPFUL", "Helpfulness"),
                                   ("GENTLE", "Gentleness"), ("PLAYFUL", "Playfulness"),
                                   ("INDEPENDENT", "Independence"), ("DEVOTED", "Devotion")]:
        classes = {}
        for tier in ["S", "A", "B", "C"]:
            val = localization.get(f"UI_PET_{trait_key}_CLASS_{tier}", "")
            if val:
                classes[tier] = val
        rating = (localization.get(f"UI_PET_{trait_name.upper()}_RATING", "")
                  or localization.get(f"UI_PET_{trait_key}_RATING", ""))
        if classes:
            trait_classes[trait_name] = {"Rating": rating or trait_name, "Classes": classes}

    fiend_traits = {}
    for trait_key, trait_name in [("AGG", "Aggression"), ("HEL", "Helpfulness"),
                                   ("GEN", "Gentleness"), ("PLA", "Playfulness"),
                                   ("IND", "Independence"), ("DEV", "Devotion")]:
        classes = {}
        for tier in ["S", "A", "B", "C"]:
            val = localization.get(f"UI_PET_FIEND_{trait_key}_CLASS_{tier}", "")
            if val:
                classes[tier] = val
        if classes:
            fiend_traits[trait_name] = classes

    # --- EggLabels ---
    egg_labels = {
        "TraitWords": {},
        "SizeWords": {},
        "TypeNames": {},
        "Requirements": {},
    }
    for key, field in [("AGG", "aggressive"), ("DEV", "devoted"), ("GEN", "gentle"),
                        ("HEL", "industrious"), ("IND", "independent"), ("PLA", "playful")]:
        val = localization.get(f"UI_PET_EGG_{key}", "")
        if val:
            egg_labels["TraitWords"][key] = val
    for key in ["SMALL", "MED", "LARGE", "XL"]:
        val = localization.get(f"UI_PET_EGG_{key}", "")
        if val:
            egg_labels["SizeWords"][key] = val
    for key in [("NAME", "Default"), ("QUAD_NAME", "Quad"), ("FIEND_NAME", "Fiend")]:
        val = localization.get(f"UI_PET_EGG_{key[0]}", "")
        if val:
            egg_labels["TypeNames"][key[1]] = val
    for key in ["AGE", "BIOME", "HUNGRY", "LONELY", "PENDING", "SLOTS", "TIME", "TREAT"]:
        val = localization.get(f"UI_PET_EGG_COST_{key}", "")
        if val:
            egg_labels["Requirements"][key] = val

    # --- MoodStrings ---
    mood_strings = {"Good": [], "Hungry": [], "Lonely": []}
    for i in range(1, 60):
        for mood in ["GOOD", "HUNGRY", "LONELY"]:
            val = localization.get(f"PET_MOOD_{mood}_{i}", "")
            if val:
                mood_strings[mood.capitalize()].append(val)

    # --- ArenaGuild ---
    arena_guild = {
        "Name": localization.get("PET_GUILD_NAME", "Arena League"),
        "Description": localization.get("PET_GUILD_DESC", ""),
    }

    # --- BattleUI labels ---
    battle_ui = {}
    for key in ["MAIN_HEADER", "FINISH_WON", "FINISH_LOST", "FINISH_ABANDONED", "FINISH",
                "MISS", "DODGE", "BLOCK", "CLEANSE", "WEAK", "STRONG", "VS",
                "REST_DESC", "SWITCH_DESC", "BEGIN_BUTTON", "TURN_LABEL",
                "BATTLE_STAT", "TRAITS_HEADER", "STATS_HEADER", "LEVEL_SUB"]:
        val = localization.get(f"UI_PB_{key}", "")
        if val:
            battle_ui[key] = val.strip()

    # --- SpecialCreatureNames ---
    special_names = {}
    for prefix, creature_id in [("UI_HERMITCRAB_PET", "WALKER_CRAB"),
                                 ("UI_FISHBOWL3_PET", "FISHBOWL_PET3"),
                                 ("UI_LANDSQUID_PET", "LANDSQUID_PET"),
                                 ("UI_SPIDERQUAD_PET", "SPIDERQUAD_PET"),
                                 ("UI_HORROR_PET", "HORROR_PET"),
                                 ("UI_HOVERPET", "HOVER_PET")]:
        name = localization.get(f"{prefix}_NAME", "")
        species = localization.get(f"{prefix}_SPECIES", "")
        trait = localization.get(f"{prefix}_TRAIT", "")
        if name:
            entry = {"Name": name}
            if species:
                entry["Species"] = species
            if trait:
                entry["Trait"] = trait
            special_names[creature_id] = entry

    # --- AccessorySlotLabels ---
    slot_labels = {}
    for slot in ["FRONT", "BACK", "LEFT", "RIGHT"]:
        val = localization.get(f"UI_CUSTOM_PET_ACCESSORY_{slot}", "")
        if val:
            slot_labels[slot] = val

    # --- WonderRecords ---
    wonder_records = []
    _WONDER_KEYS = [
        ("WONDER_CREAT_HERB_MAX", "Largest Herbivore"),
        ("WONDER_CREAT_HERB_MIN", "Smallest Herbivore"),
        ("WONDER_CREAT_CARN_MAX", "Largest Carnivore"),
        ("WONDER_CREAT_CARN_MIN", "Smallest Carnivore"),
        ("WONDER_CREAT_INT", "Most Intelligent Being"),
        ("WONDER_CREAT_VIS", "Most Vicious Hunter"),
        ("WONDER_CREAT_COLD", "Greatest Freeze Tolerance"),
        ("WONDER_CREAT_HOT", "Highest Body Temperature"),
        ("WONDER_CREAT_TOX", "Most Corrosive Blood"),
        ("WONDER_CREAT_RAD", "Most Radiation Resistant"),
        ("WONDER_CREAT_WEIRD", "Strongest Psionic Field"),
        ("WONDER_CREAT_WATER", "Largest Aquatic Lifeform"),
        ("WONDER_CREAT_ROBOT", "Convergence Potential"),
        ("WONDER_CREAT_CAVE", "Most Pressure Resistant"),
        ("WONDER_CREAT_FLY", "Heaviest Flying Lifeform"),
    ]
    for loc_key, fallback in _WONDER_KEYS:
        name = localization.get(loc_key, "") or fallback
        num_key = f"{loc_key}_NUM"
        measurement = localization.get(num_key, "")
        wonder_records.append({"Id": loc_key, "Name": name, "Measurement": measurement or None})

    # --- CompanionChat ---
    companion_chat = _build_companion_chat_messages(localization)

    # --- BiomeChat ---
    import re
    biome_chat = {}
    biome_pattern = re.compile(r'^CHAT_PET_BIOME_(.+?)_(\d+)$')
    for key, value in localization.items():
        if not key.startswith('CHAT_PET_BIOME_'):
            continue
        match = biome_pattern.match(key)
        if match:
            biome = match.group(1)
            if biome not in biome_chat:
                biome_chat[biome] = []
            if value and value not in biome_chat[biome]:
                biome_chat[biome].append(value)
        elif key == 'CHAT_PET_BIOME_STATION':
            biome_chat.setdefault('STATION', [])
            if value:
                biome_chat['STATION'].append(value)

    result = {
        "Temperaments": temperaments,
        "Diets": diets,
        "PetEggTypes": pet_eggs,
        "EggSequencerConstants": egg_constants,
        "TrustConstants": trust_constants,
        "FeedingConstants": feeding_constants,
        "MovementConstants": movement_constants,
        "AffinityLabels": affinity_labels,
        "BattleStats": battle_stats,
        "ClimateLabels": climate_labels,
        "TraitClasses": trait_classes,
        "FiendTraitClasses": fiend_traits,
        "EggLabels": egg_labels,
        "MoodStrings": mood_strings,
        "ArenaGuild": arena_guild,
        "BattleUI": battle_ui,
        "SpecialCreatureNames": special_names,
        "AccessorySlotLabels": slot_labels,
        "WonderRecords": wonder_records,
        "CompanionChat": companion_chat,
        "BiomeChat": biome_chat,
    }
    chat_count = sum(len(v) for v in companion_chat.values())
    biome_count = sum(len(v) for v in biome_chat.values())
    print(f"[OK] Parsed creature globals: {len(temperaments)} temperaments, "
          f"{len(diets)} diets, {len(pet_eggs)} pet egg types, "
          f"{len(affinity_labels)} affinity labels, {len(battle_stats)} battle stats, "
          f"{len(climate_labels)} climate labels, {len(trait_classes)} trait classes, "
          f"{len(fiend_traits)} fiend trait classes, {len(battle_ui)} battle UI strings, "
          f"{len(special_names)} special creature names, {len(slot_labels)} accessory slot labels, "
          f"{len(wonder_records)} wonder records, "
          f"{len(companion_chat)} chat categories ({chat_count} messages), "
          f"{len(biome_chat)} biome chat groups ({biome_count} words)")
    return result
