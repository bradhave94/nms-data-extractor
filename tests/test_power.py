import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from subprocess import CompletedProcess
import xml.etree.ElementTree as ET

from parsers.power import parse_link_grid, parse_power_rules, power_source_provenance
from extract import enrich_buildings_metadata, convert_mbin


def grid(network='Power', rate=0, storage=0, dependency=''):
    return ET.fromstring(f'''<Property><Property name="LinkGridData">
      <Property name="Connection"><Property name="Network"><Property name="LinkNetworkType" value="{network}"/></Property></Property>
      <Property name="Rate" value="{rate}"/><Property name="Storage" value="{storage}"/>
      <Property name="DependsOnEnvironment" value="DayNight"/>
      <Property name="DependsOnHotspots" value="None"/>
      <Property name="DependentConnections">{dependency}</Property>
    </Property></Property>''')


class PowerTest(unittest.TestCase):
    def test_refresh_provenance_uses_current_installed_build_not_pending_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            steamapps = Path(tmp) / 'steamapps'
            steamapps.mkdir()
            manifest = steamapps / 'appmanifest_275850.acf'
            manifest.write_text('"appid" "275850"\n"buildid" "123"\n"TargetBuildID" "456"')
            pcbanks = steamapps / 'common' / 'No Man\'s Sky' / 'GAMEDATA' / 'PCBANKS'
            provenance = power_source_provenance(pcbanks, '7.00')
            self.assertEqual(provenance['SteamBuildId'], '123')
            self.assertEqual(provenance['GameVersion'], '7.00')
            self.assertRegex(provenance['ObservedDate'], r'^\d{4}-\d{2}-\d{2}$')
            manifest.unlink()
            self.assertNotIn('SteamBuildId', power_source_provenance(pcbanks, '7.00'))
            self.assertNotIn('SteamBuildId', power_source_provenance(Path(tmp), '7.00'))

    def test_compiler_warning_is_failure_even_with_zero_exit(self):
        with patch('extract.subprocess.run', return_value=CompletedProcess([], 0, '1 files converted.', '[WARN]: File not recognized.')):
            with self.assertRaisesRegex(ValueError, 'Compiler warning'):
                convert_mbin(Path('compiler'), Path('sky.mbin'))

    def test_inert_objects_are_not_reported_as_power_equipment(self):
        self.assertIsNone(parse_link_grid(grid()))

    def test_zero_draw_connected_parts_are_preserved(self):
        item = grid()
        connection = item.find('.//Property[@name="Connection"]')
        ET.SubElement(connection, 'Property', name='NetworkMask', value='132')
        data = parse_link_grid(item)
        self.assertEqual(data['Rate'], 0)
        self.assertEqual(data['NetworkMask'], '132')
        connection.find('Property[@name="NetworkMask"]').set('value', '0')
        self.assertIsNone(parse_link_grid(item))

    def test_hotspot_condition_is_preserved(self):
        item = grid(rate=1)
        item.find('.//Property[@name="DependsOnHotspots"]').set('value', 'Power')
        self.assertEqual(parse_link_grid(item)['DependsOnHotspots'], 'Power')

    def test_solar_and_battery_units_stay_separate(self):
        solar = parse_link_grid(grid(rate=50))
        self.assertEqual((solar['Network'], solar['Rate'], solar['DependsOnEnvironment']), ('Power', 50, 'DayNight'))
        self.assertEqual(parse_link_grid(grid(storage=45000))['Storage'], 45000)

    def test_resource_and_fuel_dependencies_are_preserved(self):
        for primary, rate, storage, electrical in [('Resources', 100, 360000, -50), ('Fuel', -1, 180000, 50), ('PlantGrowth', 1, 14400, 0)]:
            dep = f'''<Property><Property name="Connection"><Property name="Network"><Property name="LinkNetworkType" value="Power"/></Property></Property><Property name="DependentRate" value="{electrical}"/><Property name="DependentEffect" value="EnablesRate"/></Property>'''
            data = parse_link_grid(grid(primary, rate, storage, dep))
            self.assertEqual(data['Network'], primary)
            self.assertEqual(data['DependentConnections'][0]['DependentRate'], electrical)
            self.assertEqual(data['DependentConnections'][0]['DependentEffect'], 'EnablesRate')

    def test_missing_or_nonfinite_rates_fail(self):
        for rate in ('NaN', 'Infinity', 'bad'):
            with self.assertRaises(ValueError):
                parse_link_grid(grid(rate=rate))

    def test_enriches_technology_and_products_not_only_buildings(self):
        with tempfile.TemporaryDirectory() as tmp:
            objects = ET.Element('Property', name='Objects')
            for item_id in ['SOLAR', 'CROP']:
                obj = copy.deepcopy(grid(rate=50))
                obj.set('name', 'Objects')
                ET.SubElement(obj, 'Property', name='ID', value=item_id)
                objects.append(obj)
            root = ET.Element('Data'); root.append(objects)
            ET.ElementTree(root).write(Path(tmp) / 'basebuildingobjectstable.MXML')
            files = {'ConstructedTechnology.json': [{'Id': 'SOLAR'}], 'Products.json': [{'Id': 'CROP'}]}
            self.assertEqual(enrich_buildings_metadata(files, Path(tmp)), 2)
            self.assertEqual(files['ConstructedTechnology.json'][0]['LinkGridData']['Rate'], 50)
            self.assertEqual(files['Products.json'][0]['LinkGridData']['Network'], 'Power')

    def test_supplemental_sources_are_verified_and_solar_schedule_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            files = {
                'gcskyglobals.globals.MXML': '<Data><Property name="DayLength" value="1800"/></Data>',
                'regionhotspotstable.MXML': '<Data><Property name="RegionHotspots"><Property name="Power"><Property name="ClassStrengths">' + ''.join(f'<Property name="{key}" value="{v}"/>' for key, v in [('C',150),('B',220),('A',250),('S',300)]) + '</Property></Property></Property></Data>',
            }
            for name, content in files.items():
                (directory / name).write_text('<!--MBINCompiler version (7.03.2.2)-->\n' + content)
            manifest = {'SteamBuildId': '123', 'CompilerVersion': '7.03.2.2', 'Sources': {name: hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in files}}
            (directory/'sources.json').write_text(json.dumps(manifest))
            result = parse_power_rules(directory)
            self.assertEqual(result['DayCycleSeconds'], 1800)
            self.assertEqual(result['HotspotClassStrengths']['Power']['S'], 300)
            self.assertIsNone(result['SolarSchedule'])
            (directory/'gcskyglobals.globals.MXML').write_text('corrupt')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                parse_power_rules(directory)


if __name__ == '__main__':
    unittest.main()
