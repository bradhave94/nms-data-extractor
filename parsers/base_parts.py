"""Parser for base building part products (freighter rooms, etc.)."""
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
    parts = parse_products(mxml_path, include_subtitle_key=True)

    # Override Group based on subtitle key and known freighter IDs.
    for part in parts:
        part_id = part.get('Id', '')
        subtitle_key = part.get('SubtitleKey', '')
        if (
            isinstance(subtitle_key, str)
            and 'SPACE' in subtitle_key
        ) or (
            isinstance(part_id, str)
            and 'FREI' in part_id
        ):
            part['Group'] = 'Freighter Interior Module'
        if 'SubtitleKey' in part:
            del part['SubtitleKey']

    print(f"[OK] Parsed {len(parts)} base building parts")
    return parts
