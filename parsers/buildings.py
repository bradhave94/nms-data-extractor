"""Parse Buildings from MXML to JSON"""
from pathlib import Path
from .base_parser import EXMLParser, normalize_game_icon_path


def _load_product_icon_lookup(parser: EXMLParser) -> dict:
    """Build product ID -> normalized icon path from product table (for IconOverrideProductID)."""
    product_icons = {}
    products_path = Path(__file__).parent.parent / 'data' / 'mbin' / 'nms_reality_gcproducttable.MXML'
    if not products_path.exists():
        return product_icons
    try:
        prod_root = parser.load_xml(str(products_path))
        table_prop = prod_root.find('.//Property[@name="Table"]')
        if table_prop is None:
            return product_icons
        for item in table_prop.findall('./Property[@name="Table"]'):
            pid = parser.get_property_value(item, 'ID', '')
            icon_prop = item.find('.//Property[@name="Icon"]')
            if icon_prop is not None:
                fn = parser.get_property_value(icon_prop, 'Filename', '')
                if fn:
                    product_icons[pid] = normalize_game_icon_path(fn)
    except Exception:
        pass
    return product_icons


def parse_buildings(mxml_path: str) -> list:
    """
    Parse basebuildingobjectstable.MXML to Buildings.json format.
    """
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    parser.load_localization()

    product_icons = _load_product_icon_lookup(parser)

    buildings = []
    building_counter = 1

    # Navigate to Objects property
    objects_prop = root.find('.//Property[@name="Objects"]')
    if objects_prop is None:
        print("Warning: Could not find Objects property in MXML")
        return buildings

    for building_elem in objects_prop.findall('./Property[@name="Objects"]'):
        try:
            building_id = parser.get_property_value(building_elem, 'ID', f'BUILDING_{building_counter}')

            # Buildings don't have direct Name/Description in this table
            name = parser.translate(building_id, building_id.replace('_', ' ').title())

            # Group from first Groups entry; full list for Groups
            group = 'Base Building Part'
            groups_list = []
            groups_prop = building_elem.find('.//Property[@name="Groups"]')
            if groups_prop is not None:
                for grp_elem in groups_prop.findall('./Property[@name="Groups"]'):
                    g = parser.get_property_value(grp_elem, 'Group', '')
                    sub = parser.get_property_value(grp_elem, 'SubGroupName', '')
                    if g:
                        groups_list.append({'Group': g, 'SubGroupName': sub or None})
                if groups_list:
                    first = groups_list[0]
                    group = parser.translate(first['Group'], first['Group'].replace('_', ' ').title())

            # Icon: use IconOverrideProductID if set, else empty path
            icon_override = parser.get_property_value(building_elem, 'IconOverrideProductID', '')
            if icon_override and icon_override in product_icons:
                icon_path = product_icons[icon_override]
            else:
                icon_path = ''
            if not icon_path:
                continue

            def _list_values(prop_name: str) -> list:
                values = []
                prop = building_elem.find(f'./Property[@name="{prop_name}"]')
                if prop is None:
                    return values
                for child in prop.findall('./Property'):
                    v = child.get('value', '')
                    if v:
                        values.append(v)
                return values

            # BuildableOn* booleans
            buildable_planet_base = parser.parse_value(parser.get_property_value(building_elem, 'BuildableOnPlanetBase', 'true'))
            buildable_space_base = parser.parse_value(parser.get_property_value(building_elem, 'BuildableOnSpaceBase', 'false'))
            buildable_freighter = parser.parse_value(parser.get_property_value(building_elem, 'BuildableOnFreighter', 'false'))

            # LinkGridData (power/network)
            link_grid_data = None
            link_elem = building_elem.find('.//Property[@name="LinkGridData"]')
            if link_elem is not None:
                network_elem = link_elem.find('.//Property[@name="Network"]')
                link_type = parser.get_nested_enum(network_elem, 'LinkNetworkType', 'LinkNetworkType', '') if network_elem is not None else ''
                rate = parser.parse_value(parser.get_property_value(link_elem, 'Rate', '0'))
                storage = parser.parse_value(parser.get_property_value(link_elem, 'Storage', '0'))
                if link_type or rate or storage:
                    link_grid_data = {'Network': link_type or None, 'Rate': rate, 'Storage': storage}

            # Create building entry
            building = {
                'Id': building_id,
                'Icon': f"{building_id}.png",
                'IconPath': icon_path,
                'Name': name,
                'Group': group,
                'Description': '',
                'BaseValueUnits': 1,
                'CurrencyType': 'None',
                'Colour': 'CCCCCC',
                'CdnUrl': '',
                'Usages': ['HasDevProperties'],
                'BlueprintCost': 1,
                'BlueprintCostType': 'None',
                'BlueprintSource': 0,
                'RequiredItems': [],
                'StatBonuses': [],
                'ConsumableRewardTexts': [],
                'IconOverrideProductID': icon_override or None,
                'Style': parser.get_nested_enum(building_elem, 'Style', 'Style', '') or None,
                'DecorationType': parser.get_nested_enum(building_elem, 'DecorationType', 'DecorationType', '') or None,
                'Biome': parser.get_nested_enum(building_elem, 'Biome', 'Biome', '') or None,
                'Tag': parser.get_property_value(building_elem, 'Tag', '') or None,
                'IsTemporary': parser.parse_value(parser.get_property_value(building_elem, 'IsTemporary', 'false')),
                'IsFromModFolder': parser.parse_value(parser.get_property_value(building_elem, 'IsFromModFolder', 'false')),
                'IsPlaceable': parser.parse_value(parser.get_property_value(building_elem, 'IsPlaceable', 'true')),
                'IsDecoration': parser.parse_value(parser.get_property_value(building_elem, 'IsDecoration', 'false')),
                'BuildableOnPlanetBase': buildable_planet_base,
                'BuildableOnSpaceBase': buildable_space_base,
                'BuildableOnFreighter': buildable_freighter,
                'BuildableInShipStructural': parser.parse_value(
                    parser.get_property_value(building_elem, 'BuildableInShipStructural', 'false')
                ),
                'BuildableInShipDecorative': parser.parse_value(
                    parser.get_property_value(building_elem, 'BuildableInShipDecorative', 'false')
                ),
                'BuildableOnPlanet': parser.parse_value(parser.get_property_value(building_elem, 'BuildableOnPlanet', 'true')),
                'BuildableOnPlanetWithProduct': parser.parse_value(
                    parser.get_property_value(building_elem, 'BuildableOnPlanetWithProduct', 'false')
                ),
                'BuildableUnderwater': parser.parse_value(
                    parser.get_property_value(building_elem, 'BuildableUnderwater', 'false')
                ),
                'BuildableAboveWater': parser.parse_value(
                    parser.get_property_value(building_elem, 'BuildableAboveWater', 'false')
                ),
                'PlanetLimit': parser.parse_value(parser.get_property_value(building_elem, 'PlanetLimit', '0')),
                'RegionLimit': parser.parse_value(parser.get_property_value(building_elem, 'RegionLimit', '0')),
                'PlanetBaseLimit': parser.parse_value(parser.get_property_value(building_elem, 'PlanetBaseLimit', '0')),
                'FreighterBaseLimit': parser.parse_value(parser.get_property_value(building_elem, 'FreighterBaseLimit', '0')),
                'CorvetteBaseLimit': parser.parse_value(parser.get_property_value(building_elem, 'CorvetteBaseLimit', '0')),
                'DoesNotCountTowardsComplexity': parser.parse_value(
                    parser.get_property_value(building_elem, 'DoesNotCountTowardsComplexity', 'false')
                ),
                'CheckPlaceholderCollision': parser.parse_value(
                    parser.get_property_value(building_elem, 'CheckPlaceholderCollision', 'false')
                ),
                'CheckPlayerCollision': parser.parse_value(
                    parser.get_property_value(building_elem, 'CheckPlayerCollision', 'false')
                ),
                'CanStack': parser.parse_value(parser.get_property_value(building_elem, 'CanStack', 'false')),
                'SnapRotateBlocked': parser.parse_value(
                    parser.get_property_value(building_elem, 'SnapRotateBlocked', 'false')
                ),
                'CanRotate3D': parser.parse_value(parser.get_property_value(building_elem, 'CanRotate3D', 'false')),
                'CanScale': parser.parse_value(parser.get_property_value(building_elem, 'CanScale', 'false')),
                'StorageContainerIndex': parser.parse_value(
                    parser.get_property_value(building_elem, 'StorageContainerIndex', '-1')
                ),
                'ColourPaletteGroupId': parser.get_property_value(building_elem, 'ColourPaletteGroupId', '') or None,
                'DefaultColourPaletteId': parser.get_property_value(building_elem, 'DefaultColourPaletteId', '') or None,
                'MaterialGroupId': parser.get_property_value(building_elem, 'MaterialGroupId', '') or None,
                'DefaultMaterialId': parser.get_property_value(building_elem, 'DefaultMaterialId', '') or None,
                'CanChangeColour': parser.parse_value(parser.get_property_value(building_elem, 'CanChangeColour', 'false')),
                'CanChangeMaterial': parser.parse_value(
                    parser.get_property_value(building_elem, 'CanChangeMaterial', 'false')
                ),
                'CanPickUp': parser.parse_value(parser.get_property_value(building_elem, 'CanPickUp', 'false')),
                'ShowInBuildMenu': parser.parse_value(parser.get_property_value(building_elem, 'ShowInBuildMenu', 'true')),
                'CompositePartObjectIDs': _list_values('CompositePartObjectIDs'),
                'FamilyIDs': _list_values('FamilyIDs'),
                'BuildEffectAccelerator': parser.parse_value(
                    parser.get_property_value(building_elem, 'BuildEffectAccelerator', '1')
                ),
                'RemovesAttachedDecoration': parser.parse_value(
                    parser.get_property_value(building_elem, 'RemovesAttachedDecoration', 'false')
                ),
                'RemovesWhenUnsnapped': parser.parse_value(
                    parser.get_property_value(building_elem, 'RemovesWhenUnsnapped', 'false')
                ),
                'EditsTerrain': parser.parse_value(parser.get_property_value(building_elem, 'EditsTerrain', 'false')),
                'BaseTerrainEditShape': parser.get_nested_enum(
                    building_elem, 'BaseTerrainEditShape', 'Shape', ''
                ) or None,
                'MinimumDeleteDistance': parser.parse_value(
                    parser.get_property_value(building_elem, 'MinimumDeleteDistance', '0')
                ),
                'IsSealed': parser.parse_value(parser.get_property_value(building_elem, 'IsSealed', 'false')),
                'CloseMenuAfterBuild': parser.parse_value(
                    parser.get_property_value(building_elem, 'CloseMenuAfterBuild', 'false')
                ),
                'Groups': groups_list if groups_list else None,
                'LinkGridData': link_grid_data,
                'GhostsCountOverride': parser.parse_value(
                    parser.get_property_value(building_elem, 'GhostsCountOverride', '0')
                ),
                'ShowGhosts': parser.parse_value(parser.get_property_value(building_elem, 'ShowGhosts', 'false')),
                'SnappingDistanceOverride': parser.parse_value(
                    parser.get_property_value(building_elem, 'SnappingDistanceOverride', '0')
                ),
                'RegionSpawnLOD': parser.parse_value(parser.get_property_value(building_elem, 'RegionSpawnLOD', '0')),
                'NPCInteractionScene': parser.get_property_value(building_elem, 'NPCInteractionScene', '') or None,
                'IsModularCustomisation': parser.parse_value(
                    parser.get_property_value(building_elem, 'IsModularCustomisation', 'false')
                ),
                'ModularCustomisationBaseID': parser.get_property_value(
                    building_elem, 'ModularCustomisationBaseID', ''
                ) or None,
                'HasDescriptor': parser.parse_value(parser.get_property_value(building_elem, 'HasDescriptor', 'false')),
                'DescriptorID': parser.get_property_value(building_elem, 'DescriptorID', '') or None,
                'UseProductIDOverride': parser.parse_value(
                    parser.get_property_value(building_elem, 'UseProductIDOverride', 'false')
                ),
                'OverrideProductID': parser.get_property_value(building_elem, 'OverrideProductID', '') or None,
                'FossilDisplayID': parser.get_property_value(building_elem, 'FossilDisplayID', '') or None,
            }

            buildings.append(building)
            building_counter += 1

        except Exception as e:
            print(f"Warning: Skipped building due to error: {e}")
            continue

    print(f"[OK] Parsed {len(buildings)} buildings")
    return buildings
