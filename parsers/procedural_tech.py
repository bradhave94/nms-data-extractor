"""Parser for procedural technology upgrades (upgrade modules)."""
from pathlib import Path
from .base_parser import EXMLParser, format_stat_type_name, normalize_game_icon_path

# Mapping of procedural tech categories to groups
# These are upgrade modules that go into TechnologyModule or ConstructedTechnology
QUALITY_PREFIX = {
    'Normal': 'C-Class',
    'Rare': 'B-Class',
    'Epic': 'A-Class',
    'Legendary': 'S-Class',
}


def _parse_procedural_stat_levels(parser: EXMLParser, tech_elem) -> list[dict]:
    """Extract procedural roll ranges from StatLevels."""
    stat_levels = []
    stat_levels_prop = tech_elem.find('.//Property[@name="StatLevels"]')
    if stat_levels_prop is None:
        return stat_levels

    for stat_elem in stat_levels_prop.findall('./Property[@name="StatLevels"]'):
        stat_type = parser.get_nested_enum(stat_elem, 'Stat', 'StatsType', '')
        value_min = parser.parse_value(parser.get_property_value(stat_elem, 'ValueMin', '0'))
        value_max = parser.parse_value(parser.get_property_value(stat_elem, 'ValueMax', '0'))
        weighting_curve = parser.get_nested_enum(stat_elem, 'WeightingCurve', 'WeightingCurve', '')
        always_choose = parser.parse_value(parser.get_property_value(stat_elem, 'AlwaysChoose', 'false'))

        if not stat_type:
            continue

        stat_levels.append({
            'StatType': stat_type,
            'Name': format_stat_type_name(stat_type),
            'ValueMin': value_min,
            'ValueMax': value_max,
            'WeightingCurve': weighting_curve,
            'AlwaysChoose': always_choose,
        })

    return stat_levels


def _load_template_icon_map(procedural_mxml_path: str) -> dict[str, str]:
    """Build a map of template ID -> normalized icon path from technology table."""
    technology_table_path = (
        Path(procedural_mxml_path).resolve().parent / 'nms_reality_gctechnologytable.MXML'
    )
    if not technology_table_path.exists():
        print(f"[WARN] Technology table not found for template icons: {technology_table_path}")
        return {}

    try:
        tech_root = EXMLParser.load_xml(str(technology_table_path))
    except Exception as e:
        print(f"[WARN] Failed to load technology table for template icons: {e}")
        return {}

    parser = EXMLParser()
    template_icons: dict[str, str] = {}

    table_prop = tech_root.find('.//Property[@name="Table"]')
    if table_prop is None:
        return template_icons

    for tech_elem in table_prop.findall('./Property[@name="Table"]'):
        template_id = parser.get_property_value(tech_elem, 'ID', '')
        if not template_id:
            continue
        icon_prop = tech_elem.find('.//Property[@name="Icon"]')
        icon_filename = (
            parser.get_property_value(icon_prop, 'Filename', '')
            if icon_prop is not None
            else ''
        )
        icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''
        if icon_path:
            template_icons[template_id] = icon_path

    return template_icons


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
    localization = parser.load_localization()

    technologies = []

    template_icon_map = _load_template_icon_map(mxml_path)

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
            desc_key = parser.get_property_value(tech_elem, 'Description', '')
            template_id = parser.get_property_value(tech_elem, 'Template', '')
            quality = parser.get_property_value(tech_elem, 'Quality', 'Normal')
            num_stats_min = parser.parse_value(parser.get_property_value(tech_elem, 'NumStatsMin', '0'))
            num_stats_max = parser.parse_value(parser.get_property_value(tech_elem, 'NumStatsMax', '0'))
            weighting_curve = parser.get_nested_enum(tech_elem, 'WeightingCurve', 'WeightingCurve', '')
            stat_levels = _parse_procedural_stat_levels(parser, tech_elem)

            # Translate name and description
            has_name_translation = bool(name_key and name_key in localization)
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

            # For internal keys without localization (e.g. AP_HYPERDRIVE), prefer
            # readable translated group names over fallback key prettification.
            if not has_name_translation and group_name and group_name != tech_id:
                name = group_name

            # Prefer direct icon from procedural entry; fallback to template icon.
            icon_prop = tech_elem.find('.//Property[@name="Icon"]')
            icon_filename = (
                parser.get_property_value(icon_prop, 'Filename', '')
                if icon_prop is not None
                else ''
            )
            icon_path = normalize_game_icon_path(icon_filename) if icon_filename else ''
            if not icon_path and template_id:
                icon_path = template_icon_map.get(template_id, '')

            # Build technology dict
            technology = {
                'Id': tech_id,
                'Icon': f'{tech_id}.png',
                'IconPath': icon_path,
                'Name': name,
                'Group': group,
                'Description': description,
                'Quality': quality,
                'NumStatsMin': num_stats_min,
                'NumStatsMax': num_stats_max,
                'WeightingCurve': weighting_curve,
                'StatLevels': stat_levels,
            }

            technologies.append(technology)

        except Exception as e:
            print(f"Warning: Error parsing procedural tech: {e}")
            continue

    print(f"[OK] Parsed {len(technologies)} procedural technology upgrades")
    return technologies
