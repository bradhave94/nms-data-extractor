"""Parse creature battle moves from petbattlermovestable.MXML."""
import re
from .base_parser import (
    EXMLParser,
    affinity_display_name,
    canonical_pet_affinity,
    normalize_game_icon_path,
    shared_texture_icon_name,
)

_AFFINITY_LOC_KEYS = [
    ("Normal", "NONE"),
    ("Lush", "LUSH"),
    ("Fire", "HOT"),
    ("Cold", "COLD"),
    ("Toxic", "TOX"),
    ("Barren", "DUST"),
    ("Radioactive", "RADIO"),
    ("Weird", "WEIRD"),
    ("Mech", "MECH"),
]

_MOVE_ICON_MAP = {
    "Speed": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/MOVE.SPEED.DDS",
    "Power": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/MOVE.POWER.DDS",
    "Heal": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/MOVE.HEALTH.DDS",
    "Accuracy": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/MOVE.ACCURACY.DDS",
    "Stealth": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/MOVE.STEALTH.DDS",
    "Shield": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/MOVE.PET.DEFENCE.DDS",
    "Attack": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/MOVE.PET.ATTACK.DDS",
    "Cooldown": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/MOVE.COOLDOWN.DDS",
}

_MOVE_BG_ICON_MAP = {
    "Speed": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/BUTTONBG/MOVE.SPEED.DDS",
    "Power": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/BUTTONBG/MOVE.POWER.DDS",
    "Heal": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/BUTTONBG/MOVE.HEALTH.DDS",
    "Accuracy": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/BUTTONBG/MOVE.ACCURACY.DDS",
    "Stealth": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/BUTTONBG/MOVE.STEALTH.DDS",
    "Shield": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/BUTTONBG/MOVE.PET.DEFENCE.DDS",
    "Attack": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/BUTTONBG/MOVE.PET.ATTACK.DDS",
    "Cooldown": "TEXTURES/UI/FRONTEND/ICONS/PETS/MOVES/BUTTONBG/MOVE.COOLDOWN.DDS",
}

_BUFF_ICON_MAP = {
    "Speed": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/BUFF.SPEED.DDS",
    "Power": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/BUFF.POWER.DDS",
    "Heal": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/BUFF.HEAL.DDS",
    "Accuracy": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/BUFF.ACCURACY.DDS",
    "Stealth": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/BUFF.STEALTH.DDS",
    "Shield": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/BUFF.DEFENCE.DDS",
    "Attack": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/BUFF.ATTACK.DDS",
    "Cooldown": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/BUFF.COOLDOWN.DDS",
}

_DEBUFF_ICON_MAP = {
    "Speed": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/DEBUFF.SPEED.DDS",
    "Power": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/DEBUFF.POWER.DDS",
    "Heal": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/DEBUFF.HEAL.DDS",
    "Accuracy": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/DEBUFF.ACCURACY.DDS",
    "Stealth": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/DEBUFF.STEALTH.DDS",
    "Shield": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/DEBUFF.DEFENCE.DDS",
    "Attack": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/DEBUFF.ATTACK.DDS",
    "Cooldown": "TEXTURES/UI/FRONTEND/ICONS/PETS/BUFFS/DEBUFF.COOLDOWN.DDS",
}

_PAYLOAD_TYPE_TO_EFFECT_LOC = {
    "DealDamage": "UI_PB_MOVE_EFFECT_DAMAGE",
    "Heal": "UI_PB_MOVE_EFFECT_HEAL",
    "DamageOverTime": "UI_PB_MOVE_EFFECT_DOT",
    "HealOverTime": "UI_PB_MOVE_EFFECT_HOT",
    "Shield": "UI_PB_MOVE_EFFECT_SHIELD",
    "Reflect": "UI_PB_MOVE_EFFECT_REFLECT",
    "Absorb": "UI_PB_MOVE_EFFECT_ABSORB",
    "Stun": "UI_PB_MOVE_EFFECT_STUN",
    "Revive": "UI_PB_MOVE_EFFECT_REVIVE",
    "ResetCooldowns": "UI_PB_MOVE_EFFECT_RESET_CD",
    "SelfDestruct": "UI_PB_MOVE_EFFECT_SELF_DESTRUCT",
    "ForceFlee": "UI_PB_MOVE_EFFECT_SWITCH",
    "DealDamageRamp": "UI_PB_MOVE_EFFECT_DAMRAMP",
    "Ramp": "UI_PB_MOVE_EFFECT_RAMP",
    "StatModify": "UI_PB_MOVE_EFFECT_STAT_MOD",
    "DispelBuffs": "UI_PB_MOVE_EFFECT_DISPEL",
    "LockPet": "UI_PB_MOVE_EFFECT_LOCK_PET",
    "LockMove": "UI_PB_MOVE_EFFECT_LOCK_MOVE",
    "ChangeAffinity": "UI_PB_MOVE_EFFECT_AFFINITY",
    "DelayAttack": "UI_PB_MOVE_EFFECT_DELAY_ATT",
    "DelayHeal": "UI_PB_MOVE_EFFECT_DELAY_HEAL",
    "DeathDamage": "UI_PB_MOVE_EFFECT_DEATH_DAM",
    "DeathHeal": "UI_PB_MOVE_EFFECT_DEATH_HEAL",
}

_PLACEHOLDER_RE = re.compile(r'%[A-Z_]+%')
_MULTI_SPACE_RE = re.compile(r'  +')

_STUB_RE = re.compile(r'\s*-\s*STUB\s+REPLACEMENT\s*', re.IGNORECASE)
_DOUBLE_AFTER_RE = re.compile(r'\bafter\s+after\b', re.IGNORECASE)


def _clean_description(raw: str) -> str:
    """Clean up DebugDescription: fix typos, remove stubs, capitalize."""
    if not raw:
        return raw
    text = _STUB_RE.sub('', raw)
    text = _DOUBLE_AFTER_RE.sub('after', text)
    text = text.strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def _resolve_effect_loc_key(payload: dict) -> str | None:
    """Return the full localization key for a payload's effect description."""
    ptype = payload.get("PayloadType") or ""
    base = _PAYLOAD_TYPE_TO_EFFECT_LOC.get(ptype)
    if not base:
        return None
    if ptype == "StatModify":
        benefit = payload.get("Benefit", "")
        return base + ("_DOWN" if benefit == "Negative" else "_UP")
    if ptype == "DispelBuffs":
        detail = payload.get("PayloadDetail", {})
        is_negative = detail.get("DispelNegativeEffects", False)
        return base + ("_DEBUFF" if is_negative else "_BUFF")
    return base


def _strip_placeholders(template: str) -> str:
    """Remove %PLACEHOLDER% tokens and clean up residual whitespace/punctuation."""
    text = _PLACEHOLDER_RE.sub('', template)
    text = _MULTI_SPACE_RE.sub(' ', text).strip()
    text = text.rstrip(',')
    return text


def _build_effect_description(phases: list, localization: dict) -> str | None:
    """Build a human-readable effect description from all payloads across phases."""
    seen_keys: set[str] = set()
    parts: list[str] = []
    for phase in phases:
        for payload in (phase.get("Payloads") or []):
            if payload.get("IsSilent"):
                continue
            loc_key = _resolve_effect_loc_key(payload)
            if not loc_key or loc_key in seen_keys:
                continue
            seen_keys.add(loc_key)
            template = localization.get(loc_key, "")
            if not template:
                continue
            parts.append(_strip_placeholders(template))
    return "; ".join(parts) if parts else None


def _parse_payload_item(parser: EXMLParser, payload_elem) -> dict:
    """Parse a single payload item from a move phase."""
    benefit = parser.get_nested_enum(payload_elem, "Benefit", "PetBattlerPayloadBenefit", "")
    strength = parser.get_nested_enum(payload_elem, "Strength", "PetPayloadStrength", "")
    override_target = parser.parse_value(
        parser.get_property_value(payload_elem, "ShouldOverrideTarget", "false")
    )
    target_override = ""
    if override_target:
        target_override = parser.get_nested_enum(
            payload_elem, "TargetOverride", "PetBattlerTarget", ""
        )
    is_silent = parser.parse_value(
        parser.get_property_value(payload_elem, "IsSilent", "false")
    )

    payload_prop = payload_elem.find('.//Property[@name="Payload"]')
    payload_type = ""
    payload_detail = {}
    if payload_prop is not None:
        payload_type = payload_prop.get("value", "")
        # Strip the Gc prefix and Data suffix for cleaner type name
        short_type = payload_type
        if short_type.startswith("GcPetBattlerPayload"):
            short_type = short_type[len("GcPetBattlerPayload"):]
        if short_type.endswith("Data"):
            short_type = short_type[:-4]

        inner = payload_prop.find(f'./Property[@name="{payload_type}"]')
        if inner is not None:
            affinity_elem = inner.find('.//Property[@name="Affinity"]')
            if affinity_elem is not None:
                payload_detail["AffinityMode"] = parser.get_nested_enum(
                    affinity_elem, "PetPayloadAffinity", default=""
                ) or parser.get_property_value(affinity_elem, "PetPayloadAffinity", "")
                specific = parser.get_nested_enum(
                    affinity_elem, "SpecificAffinity", "PetBattlerAffinity", ""
                )
                if specific:
                    payload_detail["SpecificAffinity"] = specific

            for field_name in ("DispelNegativeEffects", "HealthFactorCutoff",
                               "StatType", "DamageMultiplier"):
                val = parser.get_property_value(inner, field_name, "")
                if val:
                    payload_detail[field_name] = parser.parse_value(val)

        payload_type = short_type

    result = {
        "Benefit": benefit or None,
        "Strength": strength or None,
        "PayloadType": payload_type or None,
        "IsSilent": is_silent,
    }
    if override_target:
        result["TargetOverride"] = target_override
    if payload_detail:
        result["PayloadDetail"] = payload_detail
    return result


def _parse_phase(parser: EXMLParser, phase_elem) -> dict:
    """Parse a single move phase."""
    strength = parser.get_nested_enum(phase_elem, "Strength", "PetPayloadStrength", "")
    effect = parser.get_nested_enum(phase_elem, "Effect", "PetBattlerMoveEffect", "")
    animation = parser.get_property_value(phase_elem, "Animation", "")

    hit_policy_prop = phase_elem.find('.//Property[@name="HitPolicy"]')
    hit_policy = {}
    if hit_policy_prop is not None:
        inner_name = hit_policy_prop.get("value", "")
        inner = hit_policy_prop.find(f'./Property[@name="{inner_name}"]') if inner_name else None
        if inner is not None:
            miss_mod = parser.get_property_value(inner, "MissChanceModifier", "")
            if miss_mod:
                hit_policy["MissChanceModifier"] = parser.parse_value(miss_mod)
            miss_affects = parser.get_property_value(inner, "MissChanceAffectsPayloadScore", "")
            if miss_affects:
                hit_policy["MissChanceAffectsPayloadScore"] = parser.parse_value(miss_affects)

    payloads = []
    payload_list = phase_elem.find('.//Property[@name="PayloadList"]')
    if payload_list is not None:
        for pl_item in payload_list.findall('./Property[@name="PayloadList"]'):
            payloads.append(_parse_payload_item(parser, pl_item))

    result = {
        "Strength": strength or None,
        "Effect": effect or None,
        "Payloads": payloads if payloads else None,
    }
    if animation:
        result["Animation"] = animation
    if hit_policy:
        result["HitPolicy"] = hit_policy
    return result


def parse_battle_moves(mxml_path: str) -> list:
    """
    Parse petbattlermovestable.MXML into a flat list of battle move definitions.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    localization = parser.load_localization()

    moves = []
    table = root.find('.//Property[@name="Moves"]')
    if table is None:
        print("Warning: Could not find Moves property in pet battler moves table")
        return moves

    for row in table.findall('./Property[@name="Moves"]'):
        move_id = parser.get_property_value(row, "ID", "")
        if not move_id:
            continue

        description = _clean_description(
            parser.get_property_value(row, "DebugDescription", "")
        )
        target = parser.get_nested_enum(row, "PrimaryTarget", "PetBattlerTarget", "")
        multi_turn = parser.parse_value(parser.get_property_value(row, "MultiTurnMove", "false"))
        basic_move = parser.parse_value(parser.get_property_value(row, "BasicMove", "false"))
        icon_style = parser.get_nested_enum(row, "OverrideMoveIcon", "PetBattlerIcon", "")
        name_stub = parser.get_property_value(row, "NameStub", "")

        names_by_affinity = {}
        if name_stub:
            for affinity_label, affinity_loc_key in _AFFINITY_LOC_KEYS:
                loc_key = f"UI_PB_MOVE_{affinity_loc_key}_{name_stub}1"
                resolved = localization.get(loc_key, "")
                if resolved:
                    names_by_affinity[affinity_label] = resolved

        canonical_name = name_stub.replace("_", " ").title() if name_stub else None

        icon_path = normalize_game_icon_path(
            _MOVE_ICON_MAP.get(icon_style, "")
        ) or None if icon_style else None
        bg_icon_path = normalize_game_icon_path(
            _MOVE_BG_ICON_MAP.get(icon_style, "")
        ) or None if icon_style else None
        buff_icon_path = normalize_game_icon_path(
            _BUFF_ICON_MAP.get(icon_style, "")
        ) or None if icon_style else None
        debuff_icon_path = normalize_game_icon_path(
            _DEBUFF_ICON_MAP.get(icon_style, "")
        ) or None if icon_style else None

        phases = []
        phases_prop = row.find('./Property[@name="Phases"]')
        if phases_prop is not None:
            for phase_elem in phases_prop.findall('./Property[@name="Phases"]'):
                phases.append(_parse_phase(parser, phase_elem))

        primary_affinity = None
        for phase in phases:
            for payload in (phase.get("Payloads") or []):
                detail = payload.get("PayloadDetail", {})
                if detail.get("SpecificAffinity"):
                    primary_affinity = detail["SpecificAffinity"]
                    break
                if detail.get("AffinityMode") == "UsePetAffinity":
                    primary_affinity = "UsePetAffinity"
                    break
            if primary_affinity:
                break
        canonical_primary_affinity = (
            primary_affinity
            if primary_affinity == "UsePetAffinity"
            else canonical_pet_affinity(primary_affinity)
        )

        default_display_name = canonical_name
        if canonical_primary_affinity and canonical_primary_affinity in names_by_affinity:
            default_display_name = names_by_affinity[canonical_primary_affinity]
        elif names_by_affinity.get("Normal"):
            default_display_name = names_by_affinity["Normal"]

        effect_description = _build_effect_description(phases, localization)

        moves.append({
            "Id": move_id,
            "Name": canonical_name,
            "DefaultDisplayName": default_display_name,
            "NamesByAffinity": names_by_affinity if names_by_affinity else None,
            "NameStub": name_stub or None,
            "Description": description or None,
            "EffectDescription": effect_description,
            "Target": target or None,
            "AffinityRaw": primary_affinity,
            "Affinity": canonical_primary_affinity,
            "AffinityDisplay": affinity_display_name(canonical_primary_affinity or "None"),
            "Category": icon_style or None,
            "CategoryIcon": shared_texture_icon_name(icon_path) if icon_path else None,
            "CategoryIconPath": icon_path,
            "CategoryBgIcon": shared_texture_icon_name(bg_icon_path) if bg_icon_path else None,
            "CategoryBgIconPath": bg_icon_path,
            "BuffIcon": shared_texture_icon_name(buff_icon_path) if buff_icon_path else None,
            "BuffIconPath": buff_icon_path,
            "DebuffIcon": shared_texture_icon_name(debuff_icon_path) if debuff_icon_path else None,
            "DebuffIconPath": debuff_icon_path,
            "MultiTurn": multi_turn,
            "BasicMove": basic_move,
            "Phases": phases if phases else None,
        })

    print(f"[OK] Parsed {len(moves)} battle moves")
    return moves
