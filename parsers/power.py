"""Electrical metadata, preserving resource/fuel networks and conditional connections."""
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET


def power_source_provenance(pcbanks: Path, game_version):
    """Identify this extraction, never carry a stale build ID from older inputs."""
    provenance = {
        'GameVersion': game_version,
        'ObservedDate': datetime.now(timezone.utc).date().isoformat(),
    }
    for parent in pcbanks.resolve().parents:
        if parent.name.lower() != 'steamapps':
            continue
        manifest = parent / 'appmanifest_275850.acf'
        if manifest.is_file():
            content = manifest.read_text(encoding='utf-8-sig')
            app_id = re.search(r'"appid"\s+"(\d+)"', content)
            build_id = re.search(r'"buildid"\s+"(\d+)"', content)
            if app_id and app_id.group(1) == '275850' and build_id:
                provenance['SteamBuildId'] = build_id.group(1)
        break
    return provenance


def value(element, name, default=None):
    node = element.find(f'./Property[@name="{name}"]')
    return node.get('value', default) if node is not None else default


def number(element, name):
    raw = value(element, name)
    if raw is None:
        raise ValueError(f'Missing grid field: {name}')
    result = float(raw)
    if not math.isfinite(result):
        raise ValueError(f'Invalid grid field: {name}')
    return int(result) if result.is_integer() else result


def connection(element):
    node = element.find('./Property[@name="Connection"]')
    if node is None:
        raise ValueError('Missing grid Connection')
    network = node.find('./Property[@name="Network"]')
    kind = value(network, 'LinkNetworkType') if network is not None else None
    if kind not in {'Power', 'Resources', 'Fuel', 'ByteBeat', 'Portals', 'PlantGrowth'}:
        raise ValueError(f'Unknown grid network: {kind}')
    return {
        'Network': kind,
        **{key: value(node, key) for key in ('NetworkSubGroup', 'NetworkMask', 'ConnectionDistance', 'UseMinDistance')},
    }


def parse_link_grid(building):
    grid = building.find('./Property[@name="LinkGridData"]')
    if grid is None:
        return None
    primary = connection(grid)
    dependencies = []
    for dependency in grid.findall('./Property[@name="DependentConnections"]/Property'):
        dependencies.append({
            **connection(dependency),
            'DependentRate': number(dependency, 'DependentRate'),
            'DependentEffect': value(dependency, 'DependentEffect'),
        })
    result = {
        **primary,
        'Rate': number(grid, 'Rate'),
        'Storage': number(grid, 'Storage'),
        'DependsOnEnvironment': value(grid, 'DependsOnEnvironment'),
        'DependsOnHotspots': value(grid, 'DependsOnHotspots'),
        'DependentConnections': dependencies,
    }
    # Default, inert wiring metadata exists on almost every game object. Keep
    # actual networks, including zero-draw switches, wiring and conductive rooms.
    # A nonzero connection mask distinguishes these from inert default grids.
    connected = primary['NetworkMask'] not in (None, '', '0')
    return result if result['Rate'] or result['Storage'] or dependencies or connected else None


def parse_power_rules(directory: Path):
    """Read independently versioned, hash-verified supplemental game sources.

    These rules may be observed on a newer installed Steam build than the item
    catalog. Never claim their compiler version is the catalog's game version.
    """
    manifest_path = directory / 'sources.json'
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not (manifest.get('SteamBuildId') or manifest.get('GameVersion')) or not manifest.get('CompilerVersion'):
        raise ValueError('Power rules require source release/build and compiler provenance')
    roots = {}
    for name in ('gcskyglobals.globals.MXML', 'regionhotspotstable.MXML'):
        source = directory / name
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if manifest['Sources'].get(name) != digest:
            raise ValueError(f'Power source hash mismatch: {name}')
        text = source.read_text(encoding='utf-8-sig')
        if f"MBINCompiler version ({manifest['CompilerVersion']})" not in text:
            raise ValueError(f'Power source compiler mismatch: {name}')
        roots[name] = ET.fromstring(text)
    day_length = number(roots['gcskyglobals.globals.MXML'], 'DayLength')
    if not 60 <= day_length <= 86400:
        raise ValueError(f'Implausible DayLength: {day_length}')
    hotspots = roots['regionhotspotstable.MXML'].find('./Property[@name="RegionHotspots"]')
    if hotspots is None:
        raise ValueError('Power source has no RegionHotspots table')
    classes = {}
    for hotspot in hotspots:
        strengths = hotspot.find('./Property[@name="ClassStrengths"]')
        classes[hotspot.get('name')] = {key: number(strengths, key) for key in ('C', 'B', 'A', 'S')}
    if 'Power' not in classes or any(v <= 0 for row in classes.values() for v in row.values()):
        raise ValueError('Hotspot class strengths must be positive')
    return {
        'Provenance': manifest,
        'DayCycleSeconds': day_length,
        'HotspotClassStrengths': classes,
        'SolarSchedule': None,
        'Notes': 'Cycle length and class strengths are extracted. Solar phase durations and location-dependent output are not established by these fields.',
    }
