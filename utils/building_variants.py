"""Read explicit space-base product overrides from the game's building table."""
from pathlib import Path
import xml.etree.ElementTree as ET


def load_space_base_variants(data_dir: Path) -> dict[str, list[str]]:
    source = data_dir / "basebuildingobjectstable.MXML"
    if not source.exists():
        return {}
    root = ET.parse(source).getroot()
    variants: dict[str, set[str]] = {}
    for entry in root.findall('.//Property[@name="Objects"]/Property[@name="Objects"]'):
        fields = {prop.get("name"): prop.get("value") for prop in entry.findall("Property")}
        original = fields.get("ID")
        override = fields.get("OverrideProductID")
        if fields.get("UseProductIDOverrideInSpace") == "true" and original and override and original != override:
            variants.setdefault(override, set()).add(original)
    return {iid: sorted(originals) for iid, originals in variants.items()}


def enrich_space_base_variants(final_files: dict, data_dir: Path) -> int:
    variants = load_space_base_variants(data_dir)
    enriched = 0
    for filename, items in final_files.items():
        if filename in {"new.json", "localization.json"} or not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item.pop("SpaceBaseVariantOf", None)
            if item.get("Id") in variants:
                item["SpaceBaseVariantOf"] = variants[item["Id"]]
                enriched += 1
    return enriched
