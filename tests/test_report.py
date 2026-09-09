"""Regression coverage for release changes versus extraction/category changes."""
import json
from pathlib import Path
import tempfile
import unittest

from utils.report import build_new_json_document


class ReleaseChangesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.current = self.repo / "data/json"
        self.baseline = self.repo / "reports/_latest_snapshot"
        self.current.mkdir(parents=True)
        self.baseline.mkdir(parents=True)

    def write(self, directory, filename, items):
        (directory / filename).write_text(json.dumps(items), encoding="utf-8")

    def document(self, **kwargs):
        return build_new_json_document(
            self.repo, version_key="7.00.0.1",
            previous_run={"version_key": "6.40.0.1"}, **kwargs,
        )

    def test_category_move_is_neither_new_nor_removed_nor_updated(self):
        old = {"Id": "SUIT_REFINER", "Name": "Personal Refiner"}
        self.write(self.baseline, "none.json", [old])
        self.write(self.current, "Technology.json", [
            {**old, "Slug": "technology/SUIT_REFINER"},
        ])
        self.assertEqual(self.document()["Summary"], {"Added": 0, "Changed": 0, "Removed": 0})

    def test_moved_item_with_game_change_stays_updated(self):
        old = {"Id": "OLD", "BaseValueUnits": 100}
        self.write(self.baseline, "none.json", [old])
        self.write(self.current, "Products.json", [{**old, "BaseValueUnits": 200}])
        doc = self.document()
        self.assertEqual(doc["Summary"], {"Added": 0, "Changed": 1, "Removed": 0})
        self.assertEqual(doc["ChangedItems"][0]["Previous"], old)
        self.assertEqual(doc["ChangedItems"][0]["ChangedFields"], ["BaseValueUnits"])

    def test_true_additions_removals_and_sectioned_data(self):
        self.write(self.baseline, "Products.json", [{"Id": "REMOVED"}, {"Id": "STAYS"}])
        self.write(self.current, "Products.json", [{"Id": "STAYS"}])
        self.write(self.current, "Creatures.json", {"Species": [{"Id": "NEW"}]})
        self.write(self.current, "new.json", {"Items": [{"Id": "STALE"}]})
        doc = self.document()
        self.assertEqual(doc["Summary"], {"Added": 1, "Changed": 0, "Removed": 1})
        self.assertEqual(doc["Items"][0]["Id"], "NEW")
        self.assertEqual(doc["RemovedIds"], [{"Id": "REMOVED", "SourceFile": "Products.json"}])

    def test_stale_baseline_is_not_used_for_previous_values(self):
        stale = self.repo / "reports/_baseline_snapshot"
        stale.mkdir()
        current_item = {"Id": "PART", "BuildableOnSpaceBase": True}
        old_item = {**current_item, "BuildableOnSpaceBase": False}
        self.write(stale, "Buildings.json", [current_item])
        self.write(self.baseline, "Buildings.json", [old_item])
        self.write(self.current, "Buildings.json", [current_item])
        change = self.document()["ChangedItems"][0]
        self.assertEqual(change["Previous"], old_item)
        self.assertEqual(change["ChangedFields"], ["BuildableOnSpaceBase"])

    def test_explicit_snapshot_controls_detection_and_previous(self):
        explicit = self.repo / "saved_snapshot"
        explicit.mkdir()
        self.write(explicit, "Products.json", [{"Id": "ITEM", "BaseValueUnits": 100}])
        self.write(self.current, "Products.json", [{"Id": "ITEM", "BaseValueUnits": 200}])
        doc = self.document(baseline_snapshot_dir=explicit)
        self.assertEqual(doc["Summary"], {"Added": 0, "Changed": 1, "Removed": 0})
        self.assertEqual(doc["ChangedItems"][0]["Previous"]["BaseValueUnits"], 100)

    def test_missing_baseline_fails_instead_of_marking_everything_new(self):
        with self.assertRaisesRegex(ValueError, "snapshot is missing"):
            self.document(baseline_snapshot_dir=self.repo / "missing")

    def test_presentation_only_changes_do_not_create_update_badges(self):
        old = {"Id": "ITEM", "Slug": "old/ITEM", "CdnUrl": "old.png"}
        self.write(self.baseline, "Products.json", [old])
        self.write(self.current, "Products.json", [{**old, "Slug": "products/ITEM", "CdnUrl": "new.png"}])
        self.assertEqual(self.document()["ChangedItems"], [])


if __name__ == "__main__":
    unittest.main()
