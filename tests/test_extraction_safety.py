"""Failure-path tests must never touch the real game data or report snapshots."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import extract
from utils.workspace import publish_directories, using_workspace, extraction_lock
from utils.localization import build_localization_json, LOCALE_MXML_FILES
from utils.generate_controller_lookup import main as generate_lookup
from parsers.base_parser import EXMLParser, normalize_control_tokens
from utils.coverage import validate_building_coverage
from utils.smoke import run_smoke_check, EXPECTED_JSON_FILES, _CREATURES_REQUIRED_SECTIONS
from utils.mbin import consolidate_mbin


class ExtractionSafetyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(lambda: setattr(EXMLParser, '_controller_lookup', None))

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')
        return path

    def test_publish_retains_recoverable_previous_output(self):
        self.write('stage/data/json/item.json', 'new')
        self.write('live/data/json/item.json', 'old')
        backup = publish_directories(self.root / 'stage', self.root / 'live', ['data/json'])
        self.assertEqual((backup / 'data/json/item.json').read_text(), 'old')
        self.assertEqual((self.root / 'live/data/json/item.json').read_text(), 'new')

    def test_failed_second_rename_rolls_back_all_targets(self):
        for rel in ('data/json', 'reports'):
            self.write(f'stage/{rel}/value', 'new')
            self.write(f'live/{rel}/value', 'old')
        replace = os.replace
        def fail_report(source, destination):
            if Path(source) == self.root / 'stage/reports':
                raise OSError('simulated publish failure')
            replace(source, destination)
        with patch('utils.workspace.os.replace', side_effect=fail_report):
            with self.assertRaises(OSError):
                publish_directories(self.root / 'stage', self.root / 'live', ['data/json', 'reports'])
        for rel in ('data/json', 'reports'):
            self.assertEqual((self.root / f'live/{rel}/value').read_text(), 'old')

    def test_broad_publication_target_is_rejected(self):
        with self.assertRaises(ValueError):
            publish_directories(self.root, self.root / 'live', ['..'])

    def test_second_extraction_cannot_acquire_lock(self):
        with extraction_lock(self.root):
            with self.assertRaises(RuntimeError):
                with extraction_lock(self.root):
                    pass
        self.assertFalse((self.root / '.extraction.lock').exists())

    def test_missing_compiler_preflight_does_not_touch_output(self):
        self.write('game/a.pak', 'pak')
        original = self.write('data/json/item.json', 'old')
        with patch.object(extract, 'SOURCE_ROOT', self.root), patch.object(extract, '_load_hgpaktool_api'):
            with self.assertRaises(ValueError):
                extract.preflight_refresh(str(self.root / 'game'))
        self.assertEqual(original.read_text(), 'old')

    def test_mixed_compiler_headers_are_rejected(self):
        for name in extract.EXPECTED_MXML_AFTER_REFRESH:
            self.write(f'data/mbin/{name}', '<!--File created using MBINCompiler version (7.00.0.1)-->\n<Data/>')
        self.assertEqual(extract.validate_mxml_sources(self.root / 'data/mbin', '7.00'), '7.00.0.1')
        with self.assertRaises(ValueError):
            extract.validate_mxml_sources(self.root / 'data/mbin', '6.40')
        self.write('data/mbin/fishdatatable.MXML', '<!--File created using MBINCompiler version (6.40.0.1)-->\n<Data/>')
        with self.assertRaises(ValueError):
            extract.validate_mxml_sources(self.root / 'data/mbin')

    def test_empty_and_missing_localization_preserves_old_file(self):
        old = self.write('data/json/localization.json', '{"old":"name"}')
        with self.assertRaises(ValueError):
            build_localization_json(self.root)
        for name in LOCALE_MXML_FILES:
            self.write(f'data/mbin/{name}', '<Data><Property name="Table"/></Data>')
        with self.assertRaises(ValueError):
            build_localization_json(self.root)
        self.assertEqual(old.read_text(), '{"old":"name"}')

    def test_missing_actions_produces_defaults_and_readable_unknown_slots(self):
        with using_workspace(self.root), patch.dict(os.environ, {'NMS_FE_TOKEN_MODE': 'resolved', 'NMS_INPUT_PLATFORM': 'Win'}):
            output = self.root / 'data/json/controllerLookup.generated.json'
            self.assertEqual(generate_lookup(['--allow-missing', '--output', str(output)]), 0)
            self.assertTrue(output.is_file())
            EXMLParser._controller_lookup = None
            self.assertEqual(normalize_control_tokens('Use FE_ALT1 then FE_NEW_SLOT'), 'Use [E] then [NEW SLOT]')

    def smoke_fixture(self):
        for filename in EXPECTED_JSON_FILES:
            value = [{"Id": filename}]
            if filename == 'Creatures.json':
                value = {section: [{'Id': section}] for section in _CREATURES_REQUIRED_SECTIONS}
                value['CreatureGlobals'] = {'Diet': 'food'}
            self.write(f'data/json/{filename}', json.dumps(value))

    def smoke(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return run_smoke_check(self.root, fail_on_duplicate_ids=True, **kwargs)

    def test_empty_dataset_fails_strict_smoke(self):
        self.smoke_fixture()
        self.assertEqual(self.smoke(), 0)
        self.write('data/json/Products.json', '[]')
        self.assertEqual(self.smoke(), 1)

    def test_nested_duplicate_and_missing_egg_modifiers_fail(self):
        self.smoke_fixture()
        self.write('data/json/Products.json', '[{"Id":"Species"}]')
        self.assertEqual(self.smoke(), 1)
        self.smoke_fixture()
        (self.root / 'data/json/EggModifiers.json').unlink()
        self.assertEqual(self.smoke(), 1)

    def test_broken_recipe_and_unresolved_prompt_fail(self):
        self.smoke_fixture()
        self.write('data/json/Products.json', '[{"Id":"A","RequiredItems":[{"Id":"missing"}]}]')
        self.assertEqual(self.smoke(), 1)
        self.write('data/json/Products.json', '[{"Id":"A","Description":"Press FE_NEW"}]')
        self.assertEqual(self.smoke(check_display_tokens=True), 1)

    def test_count_drop_needs_review(self):
        self.smoke_fixture()
        self.write('previous/Products.json', json.dumps([{'Id': str(i)} for i in range(10)]))
        self.assertEqual(self.smoke(baseline_json_dir=self.root / 'previous'), 1)

    def test_new_object_only_building_cannot_silently_disappear(self):
        self.write('data/mbin/basebuildingobjectstable.MXML', '<Data><Property name="Objects"><Property name="Objects"><Property name="ID" value="NEW_OBJECT"/></Property></Property></Data>')
        with self.assertRaisesRegex(ValueError, 'NEW_OBJECT'):
            validate_building_coverage(self.root / 'data/mbin', {})
        result = validate_building_coverage(self.root / 'data/mbin', {'Buildings.json': [{'Id': 'NEW_OBJECT'}]})
        self.assertEqual(result['sourceObjects'], 1)

    def test_conflicting_source_basenames_are_not_overwritten(self):
        self.write('data/metadata/first/source.mbin', 'first')
        self.write('data/metadata/second/source.mbin', 'second')
        with self.assertRaisesRegex(ValueError, 'Conflicting MBIN'):
            consolidate_mbin(self.root)
        self.assertTrue((self.root / 'data/metadata/first/source.mbin').exists())
        self.assertTrue((self.root / 'data/metadata/second/source.mbin').exists())

    def test_failed_staged_parser_preserves_live_outputs(self):
        self.write('data/json/item.json', 'old')
        self.write('data/mbin/source.MXML', 'old source')
        self.write('reports/snapshot.json', 'old report')
        args = argparse.Namespace(refresh=False, pcbanks='', game_version='7.00', check_only=False, no_strict=False, report=True)
        with patch.object(extract, 'REPO_ROOT', self.root), patch.object(extract, 'validate_mxml_sources'), patch.object(extract, 'run_json_extraction', side_effect=ValueError('failed parser')):
            with self.assertRaises(ValueError):
                extract.run_staged_json(args, '')
        self.assertEqual((self.root / 'data/json/item.json').read_text(), 'old')
        self.assertEqual((self.root / 'reports/snapshot.json').read_text(), 'old report')


if __name__ == '__main__':
    unittest.main()
