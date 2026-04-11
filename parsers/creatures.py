"""Parse creature species data from creaturedatatable.MXML."""
from .base_parser import EXMLParser, humanize_id, normalize_game_icon_path, shared_texture_icon_name

_AFFINITY_ICON_MAP = {
    "Normal": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVE.PET.ATTACK.DDS",
    "Lush": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/STATS.PLANET.LUSH.DDS",
    "Cold": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/STATS.PLANET.COLD.DDS",
    "Fire": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/STATS.PLANET.FIRE.DDS",
    "Toxic": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/STATS.PLANET.TOXIC.DDS",
    "Barren": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/STATS.PLANET.BARREN.DDS",
    "Radioactive": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/STATS.PLANET.RADIOACTIVE.DDS",
    "Weird": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/STATS.PLANET.WEIRD.DDS",
    "Mech": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/STATS.PLANET.MECH.DDS",
}

_AFFINITY_BINOCS_ICON_MAP = {
    "Lush": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/BINOCS.PLANET.LUSH.DDS",
    "Cold": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/BINOCS.PLANET.COLD.DDS",
    "Fire": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/BINOCS.PLANET.FIRE.DDS",
    "Toxic": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/BINOCS.PLANET.TOXIC.DDS",
    "Barren": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/BINOCS.PLANET.BARREN.DDS",
    "Radioactive": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/BINOCS.PLANET.RADIOACTIVE.DDS",
    "Weird": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/BINOCS.PLANET.WEIRD.DDS",
    "Mech": "TEXTURES/UI/FRONTEND/ICONS/PETS/BIOMES/BINOCS.PLANET.MECH.DDS",
}

_SPECIAL_PET_LOC_PREFIX = {
    "FISHBOWL_PET3": "UI_FISHBOWL3_PET",
    "LANDSQUID_PET": "UI_LANDSQUID_PET",
    "SPIDERQUAD_PET": "UI_SPIDERQUAD_PET",
    "HORROR_PET": "UI_HORROR_PET",
    "HERMITCRAB": "UI_HERMITCRAB_PET",
}


def _resolve_species_name(creature_id: str, localization: dict) -> str:
    """Resolve a creature ID to its best English display name."""
    prefix = _SPECIAL_PET_LOC_PREFIX.get(creature_id)
    if prefix:
        loc_name = localization.get(f"{prefix}_NAME", "")
        if loc_name:
            return loc_name
    return humanize_id(creature_id)


def _resolve_species_subtitle(creature_id: str, localization: dict) -> str | None:
    """Resolve a creature ID to its species subtitle (e.g. 'Abyssal Horror')."""
    prefix = _SPECIAL_PET_LOC_PREFIX.get(creature_id)
    if prefix:
        return localization.get(f"{prefix}_SPECIES") or None
    return None


def parse_creatures(mxml_path: str) -> list:
    """
    Parse creaturedatatable.MXML into a list of creature species entries,
    including battle eligibility, forced affinity, and move set assignments.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

    creatures = []
    table = root.find('.//Property[@name="Table"]')
    if table is None:
        print("Warning: Could not find Table property in creature data table")
        return creatures

    for row in table.findall('./Property[@name="Table"]'):
        creature_id = parser.get_property_value(row, "Id", "")
        if not creature_id:
            continue

        force_type = parser.get_nested_enum(row, "ForceType", "CreatureType", "")
        real_type = parser.get_nested_enum(row, "RealType", "CreatureType", "")
        rarity = parser.get_nested_enum(row, "Rarity", "CreatureRarity", "")
        move_area = parser.get_property_value(row, "MoveArea", "")
        egg_type = parser.get_property_value(row, "EggType", "")

        can_battle = parser.parse_value(
            parser.get_property_value(row, "CanBeUsedInPetBattler", "false")
        )
        forced_affinity = parser.get_nested_enum(
            row, "PetBattlerForcedAffinity", "PetBattlerAffinity", "Normal"
        )
        pet_tag_elem = row.find('.//Property[@name="PetBattlerTags"]')
        pet_tag = ""
        if pet_tag_elem is not None:
            pet_tag = parser.get_property_value(pet_tag_elem, "PetTag", "")

        swell_on_attack = parser.parse_value(
            parser.get_property_value(row, "PetBattlerShouldSwellOnAttack", "false")
        )
        flyer_offset = parser.parse_value(
            parser.get_property_value(row, "PetBattleFlyerExtraOffset", "0")
        )

        move_sets_elem = row.find('.//Property[@name="MoveSets"]')
        move_sets = []
        if move_sets_elem is not None:
            for ms in move_sets_elem.findall('./Property'):
                ms_id = parser.get_property_value(ms, "MoveSet", "")
                if ms_id:
                    move_sets.append(ms_id)

        eco_system = parser.parse_value(
            parser.get_property_value(row, "EcoSystemCreature", "true")
        )
        can_be_female = parser.parse_value(
            parser.get_property_value(row, "CanBeFemale", "false")
        )
        min_scale = parser.parse_value(
            parser.get_property_value(row, "MinScale", "0")
        )
        max_scale = parser.parse_value(
            parser.get_property_value(row, "MaxScale", "0")
        )
        predator_mod = parser.get_nested_enum(
            row, "PredatorProbabilityModifier", "CreatureRoleFrequencyModifier", ""
        )
        herbivore_mod = parser.get_nested_enum(
            row, "HerbivoreProbabilityModifier", "CreatureRoleFrequencyModifier", ""
        )

        affinity_icon = normalize_game_icon_path(
            _AFFINITY_ICON_MAP.get(forced_affinity, "")
        ) or None if can_battle and forced_affinity else None
        binocs_icon = normalize_game_icon_path(
            _AFFINITY_BINOCS_ICON_MAP.get(forced_affinity, "")
        ) or None if can_battle and forced_affinity else None

        creatures.append({
            "Id": creature_id,
            "Name": _resolve_species_name(creature_id, localization),
            "SpeciesSubtitle": _resolve_species_subtitle(creature_id, localization),
            "CreatureType": force_type or None,
            "RealType": real_type or None,
            "MoveArea": move_area or None,
            "Rarity": rarity or None,
            "EcoSystemCreature": eco_system,
            "CanBeFemale": can_be_female,
            "MinScale": min_scale,
            "MaxScale": max_scale,
            "PredatorModifier": predator_mod or None,
            "HerbivoreModifier": herbivore_mod or None,
            "EggType": egg_type or None,
            "CanBeUsedInBattle": can_battle,
            "BattleForcedAffinity": forced_affinity if can_battle else None,
            "BattleAffinityIcon": shared_texture_icon_name(affinity_icon) if affinity_icon else None,
            "BattleAffinityIconPath": affinity_icon,
            "BattleAffinityBinocsIcon": shared_texture_icon_name(binocs_icon) if binocs_icon else None,
            "BattleAffinityBinocsIconPath": binocs_icon,
            "BattlePetTag": pet_tag or None,
            "BattleSwellOnAttack": swell_on_attack if can_battle else None,
            "BattleFlyerExtraOffset": flyer_offset if can_battle else None,
            "MoveSets": move_sets if move_sets else None,
        })

    print(f"[OK] Parsed {len(creatures)} creature species")
    return creatures
