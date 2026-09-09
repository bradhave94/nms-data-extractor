"""Explicit coverage of building objects that are not catalog products.

The listed 7.00 objects have no published product or icon override. They are kept
out of item cards rather than inventing names, icons, or recipes. New omissions
must be reviewed explicitly; an object gaining an icon override must be reviewed
again. This is an extraction exception list, not a claim about in-game unlocks.
"""
from pathlib import Path
from parsers.base_parser import EXMLParser

KNOWN_OBJECT_ONLY_IDS = frozenset("""
B_CANOPY_WALL1 B_CANOPY_WALL2 B_WALL_SUPPORTS SET_CLASS_S SET_CLASS_A SET_CLASS_B
SET_CONSTRUCT SET_MAYORTERM SET_GROUNDDECAL SET_SFXCONST_S0 SET_MONUMENT
SET_MONUMENT_FA SET_B_MONU SET_B_MONU_FA SET_T_MONU SET_T_MONU_FA SET_F_MONU
SET_F_MONU_FA SET_FISHPOND B_ROBOTARM S_TOWER S_TOWER_C S_TOWER_B S_TOWER_FA
S_TOWER_B_FA B_TOWER B_TOWER_C B_TOWER_B SET_INT_SHIPSAL SET_INT_SUMMARY
SET_WEAPONBOX SET_STAFFBUILD CHECKPOINT SET_BYTEBEAT GAMETABLE BIGGSCONNECTOR
FREIGHTER_CORE AIRLCKCONNECTOR BASE_ROOT BUILDLOCKER_ABA TURRET_ABAND DECALPATH
STATION_CORE U_PARAGON B_HOP_A B_MAG_1X2 STACONNECT
""".split())


def validate_building_coverage(data_dir: Path, final_files: dict) -> dict:
    published = {row["Id"] for rows in final_files.values() if isinstance(rows, list)
                 for row in rows if isinstance(row, dict) and row.get("Id")}
    root = EXMLParser.load_xml(str(data_dir / "basebuildingobjectstable.MXML"))
    rows = root.findall('./Property[@name="Objects"]/Property[@name="Objects"]')
    if not rows:
        raise ValueError("Building object source is empty or incompatible")
    excluded, missing = [], []
    for row in rows:
        item_id = EXMLParser.get_property_value(row, "ID", "")
        override = EXMLParser.get_property_value(row, "IconOverrideProductID", "")
        if not item_id:
            raise ValueError("Building object has no game ID")
        if item_id in published:
            continue
        if item_id in KNOWN_OBJECT_ONLY_IDS and not override:
            excluded.append(item_id)
        else:
            missing.append(item_id)
    if missing:
        raise ValueError(f"Uncovered building objects (add real catalog data or review an explicit exception): {', '.join(missing)}")
    return {"sourceObjects": len(rows), "reviewedObjectOnlyIds": sorted(excluded)}
