"""Focused regression coverage for strict icon extraction and publication."""

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib
from unittest.mock import patch

from utils.images import (
    build_image_manifest,
    collect_id_icon_pairs,
    extract_icons,
    expected_png_filenames,
    icon_inventory_sha256,
    is_valid_png,
    validate_image_outputs,
    write_image_manifest,
)


def png_bytes(pixel: bytes = b"\x01\x02\x03\xff") -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00" + pixel))
        + chunk(b"IEND", b"")
    )


class ImageExtractionTest(unittest.TestCase):
    def test_invalid_json_cannot_silently_reduce_inventory(self):
        (self.json_dir / 'Buildings.json').write_text('{invalid', encoding='utf-8')
        with self.assertRaises(ValueError):
            collect_id_icon_pairs(self.json_dir)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.json_dir = self.root / "json"
        self.extracted = self.root / "extracted"
        self.output = self.root / "images"
        self.json_dir.mkdir()
        self.extracted.mkdir()
        (self.json_dir / "new.json").write_text(
            json.dumps({"VersionKey": "7.00.0.1"}),
            encoding="utf-8",
        )

    def write_json(self, filename, value):
        (self.json_dir / filename).write_text(json.dumps(value), encoding="utf-8")

    def write_source(self, path):
        source = self.extracted / Path(path.replace("\\", "/"))
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"DDS source")

    def fake_magick(self, outputs):
        output_iter = iter(outputs)

        def run(command, **kwargs):
            if command == ["magick", "-version"]:
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(command[0], "magick")
            self.assertTrue(command[-1].startswith("PNG32:"))
            staged_path = Path(command[-1][len("PNG32:"):])
            staged_path.write_bytes(next(output_iter))
            return subprocess.CompletedProcess(command, 0)

        return run

    def test_collects_nested_site_icons_without_synthesizing_metadata_ids(self):
        self.write_json(
            "Products.json",
            [{"Id": "ROOT", "Icon": "root.png", "IconPath": "textures/items/root.dds"}],
        )
        self.write_json(
            "FutureTable.json",
            {
                "Sections": {
                    "Items": [
                        {
                            "Id": "NESTED",
                            "Icon": "nested.png",
                            "iconPath": "textures/items/nested.dds",
                        },
                        {
                            "Id": "LAND1:Helpfulness",
                            "ItemId": "LAND1",
                            "IconPath": "textures/items/land1.dds",
                        },
                        {
                            "Id": "DEFAULT",
                            "Icon": "products--product.creatureegg.png",
                            "IconPath": "textures/pets/egg.dds",
                            "BattleAffinityIcon": "wrong-default-name.png",
                            "BattleAffinityIconPath": "textures/pets/default-affinity.dds",
                        },
                    ]
                },
                "Metadata": {
                    "BattleAffinityIcon": "pets--affinity.png",
                    "BattleAffinityIconPath": "textures/pets/affinity.dds",
                    "CategoryIcon": "moves--category.png",
                    "CategoryIconPath": "textures/moves/category.dds",
                    "HeroIconPath": "textures/special/hero.dds",
                },
            },
        )
        self.write_json(
            "new.json",
            {
                "VersionKey": "7.00.0.1",
                "Removed": [
                    {"Id": "OLD", "Icon": "old.png", "IconPath": "textures/old.dds"}
                ],
            },
        )

        pairs = dict(collect_id_icon_pairs(self.json_dir))

        self.assertEqual(pairs["root"], "textures/items/root.dds")
        self.assertEqual(pairs["nested"], "textures/items/nested.dds")
        self.assertEqual(pairs["LAND1"], "textures/items/land1.dds")
        self.assertEqual(pairs["products--product.creatureegg"], "textures/pets/egg.dds")
        self.assertNotIn("DEFAULT", pairs)
        self.assertEqual(pairs["wrong-default-name"], "textures/pets/default-affinity.dds")
        self.assertEqual(pairs["pets--affinity"], "textures/pets/affinity.dds")
        self.assertEqual(pairs["moves--category"], "textures/moves/category.dds")
        self.assertNotIn("special--hero", pairs)
        self.assertNotIn("OLD", pairs)
        self.assertEqual(
            expected_png_filenames(self.json_dir),
            sorted(f"{name}.png" for name in pairs),
        )

    def test_invalid_png_does_not_publish_partial_stage_or_count_stale_output(self):
        self.write_json(
            "Products.json",
            [
                {"Id": "A", "Icon": "A.png", "IconPath": "textures/items/a.dds"},
                {"Id": "B", "Icon": "B.png", "IconPath": "textures/items/b.dds"},
            ],
        )
        self.write_source("textures/items/a.dds")
        self.write_source("textures/items/b.dds")
        self.output.mkdir()
        old_a = b"old output"
        (self.output / "A.png").write_bytes(old_a)
        (self.output / "manual-art.png").write_bytes(png_bytes())

        with patch("utils.images.subprocess.run", side_effect=self.fake_magick([png_bytes(), b"not png"])):
            result = extract_icons(self.json_dir, self.extracted, self.output)

        self.assertEqual(result, (1, 1, True))
        self.assertEqual((self.output / "A.png").read_bytes(), old_a)
        self.assertFalse((self.output / "B.png").exists())
        self.assertFalse((self.output / "manifest.json").exists())
        self.assertTrue((self.output / "manual-art.png").exists())
        self.assertEqual(list(self.root.glob(".image-stage-*")), [])

    def test_missing_source_with_old_png_is_skipped_and_old_png_is_unchanged(self):
        self.write_json(
            "Products.json",
            [{"Id": "STALE", "Icon": "STALE.png", "IconPath": "textures/items/missing.dds"}],
        )
        self.output.mkdir()
        old_png = png_bytes(b"\x09\x08\x07\xff")
        (self.output / "STALE.png").write_bytes(old_png)

        with patch("utils.images.subprocess.run", side_effect=self.fake_magick([])):
            result = extract_icons(self.json_dir, self.extracted, self.output)

        self.assertEqual(result, (0, 1, True))
        self.assertEqual((self.output / "STALE.png").read_bytes(), old_png)
        self.assertFalse((self.output / "manifest.json").exists())

    def test_success_replaces_only_tracked_old_icons_and_writes_hash_manifest(self):
        self.write_json(
            "Products.json",
            [{"Id": "CURRENT", "Icon": "CURRENT.png", "IconPath": "textures/items/current.dds"}],
        )
        self.write_source("textures/items/current.dds")
        self.output.mkdir()
        old_png = png_bytes()
        (self.output / "OLD.png").write_bytes(old_png)
        (self.output / "manual-art.svg").write_text("keep", encoding="utf-8")
        old_hash = hashlib.sha256(old_png).hexdigest()
        (self.output / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "algorithm": "sha256",
                    "provenance": "fileIntegrityOnly",
                    "files": {"OLD.png": {"sha256": old_hash, "size": len(old_png)}},
                }
            ),
            encoding="utf-8",
        )

        with patch("utils.images.subprocess.run", side_effect=self.fake_magick([png_bytes()])):
            result = extract_icons(self.json_dir, self.extracted, self.output)

        self.assertEqual(result, (1, 0, True))
        self.assertTrue(is_valid_png(self.output / "CURRENT.png"))
        self.assertFalse((self.output / "OLD.png").exists())
        self.assertTrue((self.output / "manual-art.svg").exists())
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["algorithm"], "sha256")
        self.assertEqual(manifest["provenance"], "gameInventory")
        self.assertEqual(manifest["gameVersion"], "7.00.0.1")
        self.assertEqual(manifest["inventorySha256"], icon_inventory_sha256(self.json_dir))
        self.assertEqual(
            manifest["files"],
            {
                "CURRENT.png": {
                    "sha256": hashlib.sha256((self.output / "CURRENT.png").read_bytes()).hexdigest(),
                    "size": (self.output / "CURRENT.png").stat().st_size,
                }
            },
        )
        file_only_manifest = build_image_manifest(self.output)
        self.assertEqual(file_only_manifest["provenance"], "fileIntegrityOnly")
        self.assertNotIn("gameVersion", file_only_manifest)
        self.assertNotIn("inventorySha256", file_only_manifest)
        validation = validate_image_outputs(
            self.output,
            expected_json_dir=self.json_dir,
            require_manifest=True,
        )
        self.assertTrue(validation["valid"])
        self.assertTrue(validation["provenance"])
        self.assertTrue(validation["metadata_valid"])

    def test_existing_legacy_pngs_are_validatable_without_fabricating_provenance(self):
        self.output.mkdir()
        (self.output / "LEGACY.png").write_bytes(png_bytes())

        result = validate_image_outputs(self.output)
        strict_result = validate_image_outputs(self.output, require_manifest=True)

        self.assertTrue(result["valid"])
        self.assertTrue(result["legacy"])
        self.assertFalse(result["manifest_present"])
        self.assertFalse(result["provenance"])
        self.assertFalse(strict_result["valid"])
        self.assertFalse((self.output / "manifest.json").exists())

    def test_file_only_manifest_does_not_claim_game_source_provenance(self):
        self.output.mkdir()
        (self.output / "LEGACY.png").write_bytes(png_bytes())

        write_image_manifest(self.output)
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        result = validate_image_outputs(self.output)
        strict_result = validate_image_outputs(self.output, require_manifest=True)

        self.assertEqual(manifest["provenance"], "fileIntegrityOnly")
        self.assertNotIn("gameVersion", manifest)
        self.assertNotIn("inventorySha256", manifest)
        self.assertTrue(result["valid"])
        self.assertFalse(result["provenance"])
        self.assertFalse(strict_result["valid"])

    def test_old_manifest_for_previous_game_version_is_rejected(self):
        self.write_json(
            "Products.json",
            [{"Id": "CURRENT", "Icon": "CURRENT.png", "IconPath": "textures/items/current.dds"}],
        )
        self.output.mkdir()
        (self.output / "CURRENT.png").write_bytes(png_bytes())

        write_image_manifest(
            self.output,
            game_version="6.40.0.1",
            inventory_sha256=icon_inventory_sha256(self.json_dir),
        )
        result = validate_image_outputs(
            self.output,
            expected_json_dir=self.json_dir,
            require_manifest=True,
        )

        self.assertFalse(result["valid"])
        self.assertFalse(result["provenance"])
        self.assertTrue(result["version_mismatch"])
        self.assertFalse(result["inventory_mismatch"])

    def test_strict_default_does_not_publish_dds_when_magick_is_missing(self):
        self.write_json(
            "Products.json",
            [{"Id": "NO_MAGICK", "Icon": "NO_MAGICK.png", "IconPath": "textures/items/no-magick.dds"}],
        )
        self.write_source("textures/items/no-magick.dds")
        self.output.mkdir()
        (self.output / "keep.txt").write_text("keep", encoding="utf-8")

        def no_magick(command, **kwargs):
            raise FileNotFoundError(command[0])

        with patch("utils.images.subprocess.run", side_effect=no_magick):
            result = extract_icons(self.json_dir, self.extracted, self.output)

        self.assertEqual(result, (0, 1, False))
        self.assertFalse((self.output / "NO_MAGICK.dds").exists())
        self.assertTrue((self.output / "keep.txt").exists())


if __name__ == "__main__":
    unittest.main()
