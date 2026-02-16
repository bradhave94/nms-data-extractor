"""Parsers for pet egg sequencer metadata tables."""
import os
from pathlib import Path

from .base_parser import EXMLParser, normalize_game_icon_path
from .product_lookup import load_product_lookup


_TRAIT_TO_INPUT_TYPE = {
    "Helpfulness": "Neural Calibrator",
    "Aggression": "Neural Calibrator",
    "Independence": "Neural Calibrator",
}


def _load_item_lookup() -> dict[str, dict]:
    """Build lookup from full source tables (not categorized JSON)."""
    repo_root = Path(__file__).parent.parent
    data_dir = repo_root / "data" / "mbin"
    extracted_env = os.environ.get("NMS_EXTRACTED", "").strip()
    extracted_root = Path(extracted_env).expanduser() if extracted_env else None

    parser = EXMLParser()
    localization = parser.load_localization()
    lookup: dict[str, dict] = {}

    substance_candidates = [data_dir / "nms_reality_gcsubstancetable.MXML"]
    if extracted_root:
        substance_candidates.append(extracted_root / "metadata" / "reality" / "tables" / "nms_reality_gcsubstancetable.MXML")
    for path in substance_candidates:
        if not path.exists():
            continue
        try:
            root = parser.load_xml(str(path))
        except Exception:
            continue
        table = root.find('.//Property[@name="Table"]')
        if table is None:
            continue
        for row in table.findall('./Property[@name="Table"]'):
            item_id = parser.get_property_value(row, "ID", "")
            if not item_id:
                continue
            if item_id in lookup:
                continue
            name_key = parser.get_property_value(row, "Name", "")
            subtitle_key = parser.get_property_value(row, "Subtitle", "")
            icon_prop = row.find('.//Property[@name="Icon"]')
            icon_raw = parser.get_property_value(icon_prop, "Filename", "") if icon_prop is not None else ""
            lookup[item_id] = {
                "ItemType": "Substance",
                "Name": parser.translate(name_key, item_id),
                "IconPath": normalize_game_icon_path(icon_raw) if icon_raw else None,
                "Group": parser.translate(subtitle_key, subtitle_key) if subtitle_key else None,
            }
        break

    product_candidates = [data_dir / "nms_reality_gcproducttable.MXML"]
    if extracted_root:
        product_candidates.append(extracted_root / "metadata" / "reality" / "tables" / "nms_reality_gcproducttable.MXML")
    for path in product_candidates:
        if not path.exists():
            continue
        product_lookup = load_product_lookup(
            parser=parser,
            localization=localization,
            products_mxml_path=path,
            include_requirements=False,
        )
        for item_id, product in product_lookup.items():
            if item_id in lookup:
                continue
            lookup[item_id] = {
                "ItemType": "Product",
                "Name": product.get("Name"),
                "IconPath": product.get("IconPath"),
                "Group": product.get("Group"),
            }
        break
    return lookup


def parse_pet_egg_trait_modifiers(mxml_path: str) -> list:
    """
    Parse peteggtraitmodifieroverridetable.MXML into a flattened list.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    item_lookup = _load_item_lookup()

    modifiers = []
    table = root.find('.//Property[@name="TraitModifiers"]')
    if table is None:
        print("Warning: Could not find TraitModifiers property in pet egg table")
        return modifiers

    for row in table.findall('./Property[@name="TraitModifiers"]'):
        product_id = parser.get_property_value(row, "ProductID", "")
        substance_id = parser.get_property_value(row, "SubstanceID", "")
        item_id = product_id or substance_id
        if not item_id:
            continue

        trait = parser.get_nested_enum(row, "Trait", "PetTrait", "")
        increases_trait = parser.parse_value(parser.get_property_value(row, "IncreasesTrait", "false"))
        base_value_override = parser.parse_value(parser.get_property_value(row, "BaseValueOverride", "-1"))
        direction = "Increase" if increases_trait else "Decrease"
        direction_symbol = "+" if increases_trait else "-"
        trait_display = trait or "Unknown"
        effect_label = f"{direction} {trait_display}"
        effect_short = f"{direction_symbol}{trait_display}"

        lookup = item_lookup.get(item_id, {})
        item_type = "Product" if product_id else "Substance"
        if isinstance(lookup.get("ItemType"), str):
            item_type = lookup["ItemType"]

        modifiers.append(
            {
                "Id": f"{item_id}:{trait or 'Unknown'}",
                "ItemId": item_id,
                "ItemType": item_type,
                "Name": lookup.get("Name"),
                "Group": lookup.get("Group"),
                "IconPath": lookup.get("IconPath"),
                "ProductID": product_id or None,
                "SubstanceID": substance_id or None,
                "Trait": trait or None,
                "IncreasesTrait": increases_trait,
                "Direction": direction,
                "DirectionSymbol": direction_symbol,
                "EffectLabel": effect_label,
                "EffectShort": effect_short,
                "InputType": _TRAIT_TO_INPUT_TYPE.get(trait_display, "Neural Calibrator"),
                "BaseValueOverride": base_value_override,
            }
        )

    print(f"[OK] Parsed {len(modifiers)} pet egg trait modifiers")
    return modifiers


def parse_pet_egg_species_overrides(mxml_path: str) -> list:
    """
    Parse peteggspeciesoverridetable.MXML into species constraint rows.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    overrides = []
    table = root.find('.//Property[@name="SpeciesOverrides"]')
    if table is None:
        print("Warning: Could not find SpeciesOverrides property in pet egg table")
        return overrides

    for row in table.findall('./Property[@name="SpeciesOverrides"]'):
        creature_id = parser.get_property_value(row, "CreatureID", "")
        if not creature_id:
            continue
        overrides.append(
            {
                "Id": creature_id,
                "CreatureID": creature_id,
                "CanChangeGrowth": parser.parse_value(parser.get_property_value(row, "CanChangeGrowth", "true")),
                "CanChangeAccessories": parser.parse_value(
                    parser.get_property_value(row, "CanChangeAccessories", "true")
                ),
                "CanChangeColour": parser.parse_value(parser.get_property_value(row, "CanChangeColour", "true")),
                "CanChangeTraits": parser.parse_value(parser.get_property_value(row, "CanChangeTraits", "true")),
                "MinScaleOverride": parser.parse_value(parser.get_property_value(row, "MinScaleOverride", "0")),
                "MaxScaleOverride": parser.parse_value(parser.get_property_value(row, "MaxScaleOverride", "0")),
            }
        )

    print(f"[OK] Parsed {len(overrides)} pet egg species overrides")
    return overrides
