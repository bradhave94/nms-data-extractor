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
    # Use the products parser since it's the same format
    parts = parse_products(mxml_path)

    # Override the Group field based on Subtitle
    # Most items in this file are freighter parts
    for part in parts:
        # The Subtitle field typically contains UI_SPACE_*_SUB keys
        # which translate to "Freighter Interior Module" or similar
        subtitle = part.get('Subtitle', '')
        if 'SPACE' in subtitle or 'FREI' in part.get('Id', ''):
            part['Group'] = 'Freighter Interior Module'

    print(f"[OK] Parsed {len(parts)} base building parts")
    return parts
