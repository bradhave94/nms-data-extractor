"""Nutrient Ingestor bonus on products: the nested GcStatsTypes enum from the real 7.10 table,
and duration = BaseFoodDuration x CookingValue."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from parsers import product_lookup
from parsers.base_parser import EXMLParser
from parsers.product_lookup import load_product_lookup
from utils.workspace import using_workspace

REPO = Path(__file__).resolve().parent.parent
PRODUCTS = REPO / "data" / "mbin" / "nms_reality_gcproducttable.MXML"


def lookup():
    EXMLParser.clear_xml_cache()
    product_lookup._PRODUCT_LOOKUP_CACHE.clear()
    return load_product_lookup(
        parser=EXMLParser(), localization=EXMLParser.load_localization(), products_mxml_path=PRODUCTS,
    )


class BaseFoodDurationTest(unittest.TestCase):
    def test_reads_gameplay_globals_and_is_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            with using_workspace(Path(tmp)):
                self.assertIsNone(product_lookup.base_food_duration())
                mbin = Path(tmp) / "data" / "mbin"
                mbin.mkdir(parents=True)
                (mbin / "gcgameplayglobals.global.MXML").write_text(
                    '<?xml version="1.0" encoding="utf-8"?>\n<Data template="GcGameplayGlobals">'
                    '<Property name="BaseFoodDuration" value="600.000000" /></Data>', encoding="utf-8")
                EXMLParser.clear_xml_cache()
                self.assertEqual(product_lookup.base_food_duration(), 600.0)


@unittest.skipUnless(PRODUCTS.exists(), "real product table not present")
class FoodBonusStatTest(unittest.TestCase):
    def test_food_bonus_stat_is_read_and_unspecified_is_none(self):
        rows = lookup()
        with_stat = {k: v['FoodBonusStat'] for k, v in rows.items() if v.get('FoodBonusStat')}
        self.assertGreater(len(with_stat), 500)
        self.assertNotIn('Unspecified', set(with_stat.values()))
        self.assertTrue(all(v.startswith(('Suit_', 'Weapon_')) for v in with_stat.values()))

    def test_name_and_duration(self):
        with patch.object(product_lookup, "base_food_duration", return_value=600.0):
            rows = lookup()
        cracker = rows['FOOD_B_CHEESE']  # Curdy Cracker, CookingValue 0.66
        self.assertEqual(cracker['FoodBonusStat'], 'Suit_Jetpack_Tank')
        self.assertEqual(cracker['FoodBonusStatName'], 'Jetpack Tanks')
        self.assertEqual(cracker['FoodBonusDurationSeconds'], 396.0)
        self.assertIsNone(rows['CASING']['FoodBonusDurationSeconds'])
        product_lookup._PRODUCT_LOOKUP_CACHE.clear()
