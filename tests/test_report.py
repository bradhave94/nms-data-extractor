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

    def test_space_base_override_of_existing_building_is_not_new(self):
        self.write(self.baseline, "Buildings.json", [{"Id": "FRE_ROOM_DRESS"}])
        self.write(self.current, "Buildings.json", [
            {"Id": "FRE_ROOM_DRESS"},
            {"Id": "STA_ROOM_DRESS", "SpaceBaseVariantOf": ["FRE_ROOM_DRESS"]},
        ])
        self.assertEqual(self.document()["Summary"], {"Added": 0, "Changed": 0, "Removed": 0})

    def test_variant_of_a_new_building_is_still_new(self):
        self.write(self.current, "Buildings.json", [
            {"Id": "STA_NEW", "SpaceBaseVariantOf": ["FRE_NEW"]},
        ])
        self.assertEqual([i["Id"] for i in self.document()["Items"]], ["STA_NEW"])

    def test_new_building_and_its_override_are_listed_once(self):
        self.write(self.current, "Buildings.json", [
            {"Id": "FRE_NEW"},
            {"Id": "STA_NEW", "SpaceBaseVariantOf": ["FRE_NEW"]},
        ])
        self.assertEqual([i["Id"] for i in self.document()["Items"]], ["FRE_NEW"])

    def test_expedition_variant_is_included_with_context(self):
        original = {"Id": "BEACON", "Name": "Myth Beacon", "IconPath": "beacon.dds", "Consumable": False}
        self.write(self.baseline, "Buildings.json", [original])
        self.write(self.current, "Buildings.json", [original,
            {**original, "Id": "S23_BEACON", "Consumable": True},
            {**original, "Id": "S23_NEW", "Name": "New Item", "IconPath": "new.dds"},
        ])
        added = {i["Id"]: i for i in self.document()["Items"]}
        self.assertEqual(added["S23_BEACON"]["ReleaseVariant"]["BaseItemId"], "BEACON")
        self.assertEqual(added["S23_BEACON"]["ReleaseVariant"]["Expedition"], 23)
        self.assertNotIn("ReleaseVariant", added["S23_NEW"])

    def test_reissued_reward_is_not_new_but_different_reward_is(self):
        original = {"Id": "ORIGINAL", "Name": "Firework Pack", "IconPath": "firework.dds",
                    "TradeCategory": "SpecialShop", "GiveRewardOnSpecialPurchase": "FIREWORKS"}
        self.write(self.baseline, "Others.json", [original])
        self.write(self.current, "Others.json", [original,
            {**original, "Id": "REISSUE", "Icon": "REISSUE.png", "Slug": "other/REISSUE"},
            {**original, "Id": "DIFFERENT", "GiveRewardOnSpecialPurchase": "OTHER_FIREWORKS"},
        ])
        self.assertEqual([i["Id"] for i in self.document()["Items"]], ["DIFFERENT"])

    def test_reward_aliases_preserve_real_differences(self):
        from utils.reward_variants import enrich_reward_variants
        original = {"Id": "PACK", "Name": "Pack", "IconPath": "pack.dds",
                    "TradeCategory": "SpecialShop", "GiveRewardOnSpecialPurchase": "REWARD"}
        files = {"Others.json": [original, {**original, "Id": "REISSUED_PACK"},
                 {**original, "Id": "OTHER", "GiveRewardOnSpecialPurchase": "OTHER_REWARD"}]}
        self.assertEqual(enrich_reward_variants(files), 1)
        self.assertEqual(files["Others.json"][1]["RewardVariantOf"], "PACK")
        self.assertNotIn("RewardVariantOf", files["Others.json"][2])

    def test_override_relationship_can_be_read_from_game_table(self):
        mbin = self.repo / "data/mbin"
        mbin.mkdir()
        (mbin / "basebuildingobjectstable.MXML").write_text('''<Data><Property name="Objects">
          <Property name="Objects"><Property name="ID" value="OLD"/>
            <Property name="OverrideProductID" value="ALIAS"/>
            <Property name="UseProductIDOverrideInSpace" value="true"/>
          </Property>
          <Property name="Objects"><Property name="ID" value="OLD"/>
            <Property name="OverrideProductID" value="UNUSED"/>
            <Property name="UseProductIDOverrideInSpace" value="false"/>
          </Property>
        </Property></Data>''', encoding="utf-8")
        self.write(self.baseline, "Buildings.json", [{"Id": "OLD"}])
        self.write(self.current, "Buildings.json", [{"Id": "OLD"}, {"Id": "ALIAS"}, {"Id": "UNUSED"}])
        self.assertEqual([i["Id"] for i in self.document()["Items"]], ["UNUSED"])
        from utils.building_variants import enrich_space_base_variants
        files = {"Exocraft.json": [{"Id": "ALIAS"}, {"Id": "UNUSED"}]}
        self.assertEqual(enrich_space_base_variants(files, mbin), 1)
        self.assertEqual(files["Exocraft.json"][0]["SpaceBaseVariantOf"], ["OLD"])
        self.assertNotIn("SpaceBaseVariantOf", files["Exocraft.json"][1])


if __name__ == "__main__":
    unittest.main()
