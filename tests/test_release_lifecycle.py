"""Lifecycle coverage for immutable release archives and detached rebuilds."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from utils.report import (
    SnapshotIntegrityError,
    bootstrap_release,
    build_new_json_document,
    generate_refresh_report,
    resolve_report_archive,
)


class ReleaseLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.current = self.repo / "data/json"
        self.baseline = self.repo / "reports/_latest_snapshot"
        self.mbin = self.repo / "data/mbin"
        self.current.mkdir(parents=True)
        self.baseline.mkdir(parents=True)
        self.mbin.mkdir(parents=True)
        (self.repo / "reports/latest_run.json").write_text(
            json.dumps({"version_key": "6.40.0.1"}),
            encoding="utf-8",
        )

    def write(self, directory: Path, filename: str, value):
        (directory / filename).write_text(
            json.dumps(value, indent=2),
            encoding="utf-8",
        )

    def test_legacy_baseline_is_normalized_and_audited_once(self):
        self.write(
            self.baseline,
            "none.json",
            [{"Id": "OLD", "Value": 1}, {"Id": "OLD", "Value": 2}],
        )
        self.write(self.current, "Products.json", [{"Id": "OLD", "Value": 3}])
        before = (self.baseline / "none.json").read_bytes()

        archive = bootstrap_release(self.repo, version_key="7.00")

        self.assertEqual((self.baseline / "none.json").read_bytes(), before)
        normalized = json.loads(
            (archive["baseline_snapshot"] / "none.json").read_text(encoding="utf-8")
        )
        self.assertEqual(normalized, [{"Id": "OLD", "Value": 2}])
        manifest = json.loads(
            (archive["baseline_snapshot"] / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["normalization"]["mode"], "legacy-last-wins")
        self.assertEqual(manifest["normalization"]["duplicates"][0]["id"], "OLD")

    def test_building_only_changes_create_a_new_archived_current(self):
        self.write(self.baseline, 'Buildings.json', [{'Id': 'OLD', 'Name': 'Room'}])
        self.write(self.current, 'Buildings.json', [{'Id': 'OLD', 'Name': 'Room'}, {'Id': 'NEW', 'Name': 'Room'}])
        building = self.mbin / 'basebuildingobjectstable.MXML'
        building.write_text('<Data/>', encoding='utf-8')
        first = generate_refresh_report(self.repo, version_key='7.00')
        building.write_text('<Data><Property name="Objects"><Property name="Objects"><Property name="ID" value="OLD"/><Property name="UseProductIDOverrideInSpace" value="true"/><Property name="OverrideProductID" value="NEW"/></Property></Property></Data>', encoding='utf-8')
        second = generate_refresh_report(self.repo, version_key='7.00')
        first_archive = resolve_report_archive(first['report_json'], repo_root=self.repo)
        second_archive = resolve_report_archive(second['report_json'], repo_root=self.repo)
        self.assertNotEqual(first_archive['current_snapshot_dir'], second_archive['current_snapshot_dir'])
        for archive, count in [(first_archive, 1), (second_archive, 0)]:
            result = build_new_json_document(self.repo, version_key='7.00', previous_run={'version_key': '6.40'},
                baseline_snapshot_dir=archive['baseline_snapshot_dir'], current_snapshot_dir=archive['current_snapshot_dir'],
                building_mxml_dir=archive['building_mxml_dir'])
            self.assertEqual(result['Summary']['Added'], count)

    def test_metadata_and_nested_rows_do_not_collide_or_enter_release_delta(self):
        self.write(self.baseline, "Products.json", [{"Id": "OLD"}])
        self.write(
            self.current,
            "Creatures.json",
            {
                "Species": [{"Id": "SAME", "Value": "species"}],
                "EggOverrides": [{"Id": "SAME", "Value": "override"}],
            },
        )
        self.write(self.current, "extraction-manifest.json", {"gameVersion": "7.00"})
        self.write(self.current, "controllerLookup.generated.json", [{"Id": "SAME"}])
        archive = bootstrap_release(self.repo, version_key="7.00")

        self.assertFalse(
            (archive["current_snapshot"] / "extraction-manifest.json").exists()
        )
        self.assertFalse(
            (archive["current_snapshot"] / "controllerLookup.generated.json").exists()
        )
        document = build_new_json_document(
            self.repo,
            version_key="7.00",
            previous_run=None,
            baseline_snapshot_dir=archive["baseline_snapshot"],
            current_snapshot_dir=archive["current_snapshot"],
            building_mxml_dir=archive["building_mxml_dir"],
        )
        self.assertEqual(document["Summary"]["Added"], 2)
        self.assertEqual(
            {item["SourceSection"] for item in document["Items"]},
            {"Species", "EggOverrides"},
        )

    def test_same_release_reuses_identical_snapshot_and_keeps_baseline_on_correction(self):
        self.write(self.baseline, "Products.json", [{"Id": "OLD", "Value": 1}])
        self.write(self.current, "Products.json", [{"Id": "OLD", "Value": 2}])

        first = generate_refresh_report(self.repo, version_key="7.00")
        baseline_path = first["archive"]["baseline_snapshot"]
        baseline_digest = hashlib.sha256(
            (baseline_path / "Products.json").read_bytes()
        ).hexdigest()
        second = generate_refresh_report(self.repo, version_key="7.00.0.1")
        self.assertEqual(second["report_json"], first["report_json"])
        self.assertEqual(second["archive"]["current_snapshot"], first["archive"]["current_snapshot"])

        self.write(self.current, "Products.json", [{"Id": "OLD", "Value": 3}])
        corrected = generate_refresh_report(self.repo, version_key="7.00")
        self.assertNotEqual(corrected["archive"]["current_snapshot"], first["archive"]["current_snapshot"])
        self.assertTrue(
            str(corrected["archive"]["current_snapshot"]).endswith("current_snapshots\\" + corrected["archive"]["current_snapshot"].name)
            or corrected["archive"]["current_snapshot"].parent.name == "current_snapshots"
        )
        self.assertEqual(
            hashlib.sha256((baseline_path / "Products.json").read_bytes()).hexdigest(),
            baseline_digest,
        )
        rerun = generate_refresh_report(self.repo, version_key="7.00")
        self.assertEqual(rerun["report_json"], corrected["report_json"])

    def test_next_release_uses_corrected_current_as_verified_baseline(self):
        self.write(self.baseline, "Products.json", [{"Id": "OLD", "Value": 1}])
        self.write(self.current, "Products.json", [{"Id": "OLD", "Value": 2}])
        generate_refresh_report(self.repo, version_key="7.00")

        self.write(self.current, "Products.json", [{"Id": "OLD", "Value": 3}])
        corrected = generate_refresh_report(self.repo, version_key="7.00")

        next_release = bootstrap_release(self.repo, version_key="7.01")
        archived_baseline = json.loads(
            (next_release["baseline_snapshot"] / "Products.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(archived_baseline, [{"Id": "OLD", "Value": 3}])
        self.assertEqual(
            next_release["previous_version_key"],
            corrected["version_key"],
        )

    def test_duplicate_identity_in_one_nested_section_fails_closed(self):
        self.write(self.baseline, "Products.json", [{"Id": "OLD"}])
        self.write(
            self.current,
            "Creatures.json",
            {"Species": [{"Id": "DUP"}, {"Id": "DUP", "Changed": True}]},
        )
        with self.assertRaisesRegex(ValueError, "Duplicate distinct record identity"):
            bootstrap_release(
                self.repo,
                version_key="7.00",
                baseline_snapshot_dir=self.baseline,
                previous_version_key="6.40",
            )

    def test_rebuild_uses_archived_current_and_building_table(self):
        self.write(self.baseline, "Buildings.json", [{"Id": "OLD"}])
        self.write(
            self.current,
            "Buildings.json",
            [{"Id": "OLD"}, {"Id": "ALIAS"}],
        )
        (self.mbin / "basebuildingobjectstable.MXML").write_text(
            """<Data><Property name="Objects">
              <Property name="Objects"><Property name="ID" value="OLD"/>
                <Property name="OverrideProductID" value="ALIAS"/>
                <Property name="UseProductIDOverrideInSpace" value="true"/>
              </Property>
            </Property></Data>""",
            encoding="utf-8",
        )
        report = generate_refresh_report(self.repo, version_key="7.00")
        sources = resolve_report_archive(report["report_json"], repo_root=self.repo)

        # Make the live inputs disagree.  The detached build must continue to
        # use only the report's archived current JSON and MXML.
        self.write(self.current, "Buildings.json", [{"Id": "ALIAS"}, {"Id": "LIVE_ONLY"}])
        (self.mbin / "basebuildingobjectstable.MXML").write_text("<Data/>", encoding="utf-8")
        document = build_new_json_document(
            self.repo,
            version_key="7.00",
            previous_run=None,
            baseline_snapshot_dir=sources["baseline_snapshot_dir"],
            current_snapshot_dir=sources["current_snapshot_dir"],
            building_mxml_dir=sources["building_mxml_dir"],
        )
        self.assertEqual(document["Summary"], {"Added": 0, "Changed": 0, "Removed": 0})

    def test_corrupt_archive_and_ambiguous_new_input_fail_closed(self):
        self.write(self.baseline, "Products.json", [{"Id": "OLD"}])
        self.write(self.current, "Products.json", [{"Id": "NEW"}])
        report = generate_refresh_report(self.repo, version_key="7.00")
        archived_current = report["archive"]["current_snapshot"]
        (archived_current / "Products.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(SnapshotIntegrityError, "digest mismatch"):
            resolve_report_archive(report["report_json"], repo_root=self.repo)

        # A new current input is rejected before it can become an immutable
        # archive; legacy normalization is restricted to the named pointers.
        self.write(self.current, "Products.json", [{"Id": "X"}, {"Id": "X", "Changed": True}])
        with self.assertRaisesRegex(ValueError, "Duplicate Id"):
            bootstrap_release(
                self.repo,
                version_key="7.01",
                baseline_snapshot_dir=self.baseline,
                previous_version_key="6.40",
            )

    def test_missing_or_same_latest_version_cannot_select_legacy_baseline(self):
        self.write(self.baseline, "Products.json", [{"Id": "OLD"}])
        self.write(self.current, "Products.json", [{"Id": "NEW"}])
        (self.repo / "reports/latest_run.json").write_text(
            json.dumps({"version_key": "unknown-version"}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SnapshotIntegrityError, "explicit version"):
            bootstrap_release(self.repo, version_key="7.00")

        (self.repo / "reports/latest_run.json").write_text(
            json.dumps({"version_key": "7.00.0.1"}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SnapshotIntegrityError, "same release"):
            bootstrap_release(self.repo, version_key="7.00")


if __name__ == "__main__":
    unittest.main()
