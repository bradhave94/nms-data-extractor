"""Parser for base building part products (freighter rooms, etc.)."""
from .base_parser import EXMLParser
from .products import parse_products

def parse_base_parts(mxml_path: str) -> list:
    """
    Parse nms_basepartproducts.MXML to extract buildable parts.

    This file contains freighter interior modules and other base building parts.
    Uses the same structure as products table (GcProductData).

    All items in this file have Subtitle that maps to "Freighter Interior Module"
    or other building-related groups.

    Args:
        mxml_path: Path to nms_basepartproducts.MXML

    Returns:
        List of building part dictionaries
    """
    # Use the products parser since it's the same format.
    parts = parse_products(mxml_path)

    # Build an ID -> raw Subtitle key map from the source table.
    # parse_products() returns translated Group but not the raw Subtitle key.
    subtitle_by_id: dict[str, str] = {}
    try:
        root = EXMLParser.load_xml(mxml_path)
        parser = EXMLParser()
        table_prop = root.find('.//Property[@name="Table"]')
        if table_prop is not None:
            for item in table_prop.findall('./Property[@name="Table"]'):
                item_id = parser.get_property_value(item, 'ID', '')
                subtitle_key = parser.get_property_value(item, 'Subtitle', '')
                if item_id:
                    subtitle_by_id[item_id] = subtitle_key
    except Exception:
        subtitle_by_id = {}

    # Override Group based on subtitle key and known freighter IDs.
    for part in parts:
        part_id = part.get('Id', '')
        subtitle_key = subtitle_by_id.get(part_id, '')
        if (
            isinstance(subtitle_key, str)
            and 'SPACE' in subtitle_key
        ) or (
            isinstance(part_id, str)
            and 'FREI' in part_id
        ):
            part['Group'] = 'Freighter Interior Module'

    print(f"[OK] Parsed {len(parts)} base building parts")
    return parts
