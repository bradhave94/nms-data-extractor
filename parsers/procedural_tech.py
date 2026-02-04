"""Parser for procedural technology upgrades (upgrade modules)."""
import xml.etree.ElementTree as ET
from .base_parser import EXMLParser

# Mapping of procedural tech categories to groups
# These are upgrade modules that go into TechnologyModule or ConstructedTechnology
QUALITY_PREFIX = {
    'Normal': 'C-Class',
    'Rare': 'B-Class',
    'Epic': 'A-Class',
    'Legendary': 'S-Class',
}

def parse_procedural_tech(mxml_path: str) -> list:
    """
    Parse nms_reality_gcproceduraltechnologytable.MXML to extract upgrade modules.

    This includes all procedurally-generated upgrade modules:
    - Weapon upgrades (Multi-tool)
    - Ship upgrades (Hyperdrive, Shield, Weapons)
    - Exocraft upgrades
    - Minotaur upgrades
    - Exosuit upgrades

    Args:
        mxml_path: Path to nms_reality_gcproceduraltechnologytable.MXML

    Returns:
        List of procedural technology dictionaries
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()

    # Load localization
    parser.load_localization()

    technologies = []

    # Navigate to Table property
    table_prop = root.find('.//Property[@name="Table"]')
    if table_prop is None:
        print("Warning: Could not find Table property in MXML")
        return technologies

    # Each tech is a Property element with value="GcProceduralTechnologyData"
    for tech_elem in table_prop.findall('./Property[@name="Table"]'):
        try:
            # Extract basic info
            tech_id = parser.get_property_value(tech_elem, 'ID', '')
            group_key = parser.get_property_value(tech_elem, 'Group', '')
            name_key = parser.get_property_value(tech_elem, 'Name', '')
            subtitle_key = parser.get_property_value(tech_elem, 'Subtitle', '')
            desc_key = parser.get_property_value(tech_elem, 'Description', '')
            quality = parser.get_property_value(tech_elem, 'Quality', 'Normal')

            # Translate name and description
            name = parser.translate(name_key) or name_key
            description = parser.translate(desc_key) or ''

            # Get the base group/name from Group key
            group_name = parser.translate(group_key) or tech_id

            # Build the full group with quality prefix for the specific tech type
            quality_prefix = QUALITY_PREFIX.get(quality, quality)
            full_group = f'{quality_prefix} {group_name}'

            # Add "Upgrade" or "Node" suffix based on name pattern
            if 'Node' in group_name or any(x in group_name for x in ['Eyes', 'Assembly', 'Heart', 'Suppressor', 'Cortex', 'Vents']):
                group = f'{full_group} Node'
            else:
                group = f'{full_group} Upgrade'

            # Build technology dict
            technology = {
                'Id': tech_id,
                'Name': name,
                'Group': group,
                'Description': description,
                'Quality': quality,
            }

            technologies.append(technology)

        except Exception as e:
            print(f"Warning: Error parsing procedural tech: {e}")
            continue

    print(f"[OK] Parsed {len(technologies)} procedural technology upgrades")
    return technologies
