"""Parse creature species data from creaturedatatable.MXML."""
from .base_parser import (
    EXMLParser,
    affinity_display_name,
    canonical_pet_affinity,
    humanize_id,
    normalize_game_icon_path,
    shared_texture_icon_name,
)

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

_DEFAULT_NEUTRAL_CREATURE_ICON_PATH = "TEXTURES/UI/HUD/ICONS/CREATUREINTERACTION.DDS"

_AFFINITY_ORDER = [
    "Lush",
    "Cold",
    "Fire",
    "Toxic",
    "Barren",
    "Radioactive",
    "Weird",
    "Mech",
]

_MANUAL_NORMAL_AFFINITY_GUESSES = {
    # Biologically themed fauna; biased toward tropical/desert spread.
    "ANTELOPE": "Lush",
    "TWOLEGANTELOPE": "Barren",
    "COW": "Lush",
    "SIXLEGCOW": "Lush",
    "CAT": "Lush",
    "SIXLEGCAT": "Lush",
    "RODENT": "Barren",
    "TRICERATOPS": "Barren",
    # Predatory/hostile silhouettes.
    "TREX": "Fire",
    "SPIDER": "Toxic",
    "ARTHROPOD": "Toxic",
    "GRUNT": "Toxic",
    # Aquatic / aerial specialty guesses.
    "CRAB": "Cold",
    "SHARK": "Cold",
    "FLYINGLIZARD": "Fire",
    "LARGEBUTTERFLY": "Lush",
    "FLYINGBEETLE": "Lush",
    # Proto / anomalous family guesses.
    "BLOB": "Radioactive",
    "FLOATSPIDER": "Weird",
    "PROTOROLLER": "Fire",
    "WEIRDROLL": "Weird",
    "WEIRDFLOAT": "Weird",
    "WEIRDCRYSTAL": "Weird",
    # Radiant/charged visual variants.
    "STRIDER": "Radioactive",
    "STRIDERGLOW": "Radioactive",
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


def _build_tag_affinity_hints(rows: list[dict]) -> dict[str, str]:
    """
    Build a PetTag -> affinity hint map from species that already have explicit affinities.
    Only keep tags that map to a single unambiguous affinity.
    """
    tag_to_affinities: dict[str, set[str]] = {}
    for row in rows:
        if not row.get("CanBeUsedInBattle"):
            continue
        affinity = row.get("CanonicalForcedAffinity")
        pet_tag = row.get("BattlePetTag")
        if not affinity or not pet_tag or pet_tag == "None":
            continue
        tag_to_affinities.setdefault(pet_tag, set()).add(affinity)

    return {
        tag: next(iter(affinities))
        for tag, affinities in tag_to_affinities.items()
        if len(affinities) == 1
    }


def _resolve_battle_affinity(
    *,
    creature_id: str,
    can_battle: bool,
    raw_affinity: str | None,
    canonical_forced_affinity: str | None,
    pet_tag: str | None,
    tag_affinity_hints: dict[str, str],
) -> tuple[str | None, str | None, str | None]:
    if not can_battle:
        return None, None, None
    if canonical_forced_affinity:
        return canonical_forced_affinity, "Forced", "Explicit PetBattlerForcedAffinity in creature table"
    if pet_tag and pet_tag != "None" and pet_tag in tag_affinity_hints:
        return (
            tag_affinity_hints[pet_tag],
            "PetTagHint",
            "Inferred from shared PetTag with explicit-affinity species",
        )
    manual_guess = _MANUAL_NORMAL_AFFINITY_GUESSES.get(creature_id)
    if manual_guess:
        return manual_guess, "ManualGuess", "Species-level heuristic guess for Normal affinity"
    return None, "Unknown", "No reliable source beyond raw Normal/None"


def build_affinity_icon_catalog() -> list[dict]:
    """
    Build a stable list of Pet Battler affinities and their icon assets.
    Includes the eight elemental affinities used by Xeno Arena.
    """
    catalog: list[dict] = []
    for affinity in _AFFINITY_ORDER:
        icon_path = normalize_game_icon_path(_AFFINITY_ICON_MAP.get(affinity, ""))
        if not icon_path:
            continue
        catalog.append({
            "Id": affinity,
            "DisplayName": affinity_display_name(affinity) or affinity,
            "Icon": shared_texture_icon_name(icon_path),
            "IconPath": icon_path,
        })
    return catalog


def _select_creature_icon_path(
    *,
    can_battle: bool,
    affinity_icon_path: str | None,
) -> str:
    if can_battle and affinity_icon_path:
        return affinity_icon_path
    return normalize_game_icon_path(_DEFAULT_NEUTRAL_CREATURE_ICON_PATH)


def parse_creatures(mxml_path: str) -> list:
    """
    Parse creaturedatatable.MXML into a list of creature species entries,
    including battle eligibility, forced affinity, and move set assignments.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

    parsed_rows: list[dict] = []
    table = root.find('.//Property[@name="Table"]')
    if table is None:
        print("Warning: Could not find Table property in creature data table")
        return parsed_rows

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
        canonical_forced_affinity = canonical_pet_affinity(forced_affinity)
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

        parsed_rows.append({
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
            "BattleForcedAffinityRaw": forced_affinity if can_battle else None,
            "CanonicalForcedAffinity": canonical_forced_affinity if can_battle else None,
            "BattlePetTag": pet_tag or None,
            "BattleSwellOnAttack": swell_on_attack if can_battle else None,
            "BattleFlyerExtraOffset": flyer_offset if can_battle else None,
            "MoveSets": move_sets if move_sets else None,
        })

    tag_affinity_hints = _build_tag_affinity_hints(parsed_rows)
    creatures = []
    for row in parsed_rows:
        creature_id = row["Id"]
        can_battle = bool(row.get("CanBeUsedInBattle"))
        raw_affinity = row.get("BattleForcedAffinityRaw")
        canonical_forced_affinity = row.get("CanonicalForcedAffinity")
        pet_tag = row.get("BattlePetTag")
        resolved_affinity, affinity_source, affinity_reason = _resolve_battle_affinity(
            creature_id=creature_id,
            can_battle=can_battle,
            raw_affinity=raw_affinity,
            canonical_forced_affinity=canonical_forced_affinity,
            pet_tag=pet_tag,
            tag_affinity_hints=tag_affinity_hints,
        )
        affinity_icon = (
            normalize_game_icon_path(_AFFINITY_ICON_MAP.get(resolved_affinity, ""))
            or None
            if can_battle and resolved_affinity
            else None
        )
        icon_path = _select_creature_icon_path(
            can_battle=can_battle,
            affinity_icon_path=affinity_icon,
        )
        row["BattleForcedAffinity"] = resolved_affinity if can_battle else None
        row["BattleForcedAffinityDisplay"] = (
            affinity_display_name(resolved_affinity or "None") if can_battle else None
        )
        row["BattleAffinityIcon"] = shared_texture_icon_name(affinity_icon) if affinity_icon else None
        row["BattleAffinityIconPath"] = affinity_icon
        row["BattleAffinitySource"] = affinity_source if can_battle else None
        row["BattleAffinityReason"] = affinity_reason if can_battle else None
        row["Icon"] = f"{creature_id}.png"
        row["IconPath"] = icon_path
        row.pop("CanonicalForcedAffinity", None)
        creatures.append(row)

    print(f"[OK] Parsed {len(creatures)} creature species")
    return creatures


def parse_creature_filenames(mxml_path: str) -> list:
    """
    Parse creaturefilenametable.MXML into scene model path mappings.

    These scene paths are the authoritative source for creature visual models,
    and can be used later to generate per-species thumbnails.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    mappings = []
    table = root.find('.//Property[@name="Table"]')
    if table is None:
        print("Warning: Could not find Table property in creature filename table")
        return mappings

    for row in table.findall('./Property[@name="Table"]'):
        creature_id = parser.get_property_value(row, "ID", "")
        if not creature_id:
            continue

        model_scene = parser.get_property_value(row, "Filename", "")
        extra_scene = parser.get_property_value(row, "ExtraFilename", "")

        mappings.append({
            "Id": creature_id,
            "ModelScenePath": model_scene or None,
            "ExtraModelScenePath": extra_scene or None,
        })

    print(f"[OK] Parsed {len(mappings)} creature model filename mappings")
    return mappings
