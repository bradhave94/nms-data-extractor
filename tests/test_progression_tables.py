"""Milestones, inventory limits and trading: synthetic fixtures plus values from the real tables."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from parsers.base_parser import EXMLParser
from parsers.progression_tables import (
    _SHIP_LABEL_KEYS, _WEAPON_LABEL_KEYS, parse_inventory, parse_milestones, parse_trading,
)

REPO = Path(__file__).resolve().parent.parent
LOCALIZATION = {
    "DIST_TITLE": "On-foot Exploration", "DIST_NOTIFY": "Travelled %STAT%", "DIST_00": "First Steps", "DIST_01": "Setting Out",
    "JM_00_L": "Apollo", "JM_01_L": "Pathfinder",
    **{f"UI_ECON_CLASS_MINING_{index}": name for index, name in enumerate(("Mining", "Minerals", "Ore Extraction", "Prospecting"), 1)}, "CAT_MINERAL": "MINING COMMODITY", "CAT_ENERGY": "TRADABLE ENERGY SOURCE",
    **{key: key.title() for key in (*_SHIP_LABEL_KEYS.values(), *_WEAPON_LABEL_KEYS.values())},
}


def prop(name, value=None, *children):
    value_attr = f' value="{value}"' if value is not None else ""
    return f'<Property name="{name}"{value_attr}>{"".join(children)}</Property>'


def per_class(name, c, b, a, s):
    return prop(name, None, prop("C", c), prop("B", b), prop("A", a), prop("S", s))


class ProgressionTablesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(EXMLParser, "load_localization", return_value=LOCALIZATION)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, name, *body):
        EXMLParser.clear_xml_cache()
        path = Path(self.temp.name) / name
        path.write_text(f'<?xml version="1.0" encoding="utf-8"?>\n<Data>{"".join(body)}</Data>', encoding="utf-8")
        return str(path)

    def test_milestones_keep_thresholds_and_allow_missing_text_only_on_hidden_ladders(self):
        level = lambda name, value: prop("StatLevels", "Gc", prop("LevelName", name),
                                         prop("Value", "GcStatValueData", prop("IntValue", value), prop("FloatValue", "0.000000")))
        ladder = lambda stat, title, shown, *levels: prop("LeveledStatTable", "Gc", prop("StatId", stat), prop("StatTitle", title),
            prop("NotifyMessage", "DIST_NOTIFY" if shown == "true" else ""),
            prop("ShowInTerminal", shown), prop("UseRankNotStats", "false"), prop("StatLevels", None, *levels))
        self.write("journeymilestonetable.MXML", prop("JourneyMilestoneTable", None,
            prop("JourneyMilestoneTable", "Gc", prop("JourneyMilestoneId", "JOURNEY00"), prop("PointsToUnlock", "0"), prop("JourneyMilestoneTitleLower", "JM_00_L")),
            prop("JourneyMilestoneTable", "Gc", prop("JourneyMilestoneId", "JOURNEY01"), prop("PointsToUnlock", "5"), prop("JourneyMilestoneTitleLower", "JM_01_L"))))
        path = self.write("leveledstatstable.MXML", prop("LeveledStatTable", None,
            ladder("DIST_WALKED", "DIST_TITLE", "true", level("DIST_00", "0"), level("DIST_01", "8000")),
            ladder("HIDDEN", "NO_SUCH_TITLE", "false", level("NO_SUCH_LEVEL", "1"))))
        result = parse_milestones(path)
        walked, hidden = result["Ladders"]
        self.assertEqual(walked["Title"], "On-foot Exploration")
        self.assertEqual(walked["Notify"], "Travelled %STAT%")
        self.assertEqual([(entry["Name"], entry["Value"]) for entry in walked["Levels"]], [("First Steps", 0), ("Setting Out", 8000)])
        self.assertIsNone(hidden["Title"])
        self.assertEqual(result["Journey"], [{"Id": "JOURNEY00", "Name": "Apollo", "Points": 0},
                                             {"Id": "JOURNEY01", "Name": "Pathfinder", "Points": 5}])
        # A rank ladder (standing) must have its text even though the terminal doesn't show it.
        rank = prop("LeveledStatTable", "Gc", prop("StatId", "TRA_STANDING"), prop("StatTitle", ""), prop("NotifyMessage", ""),
                    prop("ShowInTerminal", "false"), prop("UseRankNotStats", "true"), prop("StatLevels", None, level("NO_SUCH_RANK", "3")))
        path = self.write("leveledstatstable.MXML", prop("LeveledStatTable", None, rank))
        with self.assertRaisesRegex(ValueError, "NO_SUCH_RANK"):
            parse_milestones(path)
        both = prop("StatLevels", "Gc", prop("LevelName", "DIST_00"),
                    prop("Value", "GcStatValueData", prop("IntValue", "3"), prop("FloatValue", "3.5")))
        path = self.write("leveledstatstable.MXML", prop("LeveledStatTable", None, ladder("DIST_WALKED", "DIST_TITLE", "true", both)))
        with self.assertRaisesRegex(ValueError, "both IntValue"):
            parse_milestones(path)
        path = self.write("leveledstatstable.MXML", prop("LeveledStatTable", None, ladder("SHOWN", "NO_SUCH_TITLE", "true")))
        with self.assertRaisesRegex(ValueError, "NO_SUCH_TITLE"):
            parse_milestones(path)

    def test_inventory_limits_odds_and_stats_by_class(self):
        stats = prop("BaseStatsPerClass", None, *[prop(grade, "Gc", prop("BaseStats", None, prop("BaseStats", "Gc",
            prop("BaseStatID", "SHIP_DAMAGE"), prop("Min", str(index)), prop("Max", str(index + 10))))) for index, grade in enumerate("CBAS")])
        path = self.write("inventorytable.MXML",
            prop("ShipInventoryMaxUpgradeSize", None, prop("Fighter", "Gc",
                per_class("MaxInventoryCapacity", 50, 70, 80, 100), per_class("MaxTechInventoryCapacity", 30, 40, 50, 60),
                per_class("MaxCargoInventoryCapacity", 0, 0, 0, 0))),
            prop("WeaponInventoryMaxUpgradeSize", "Gc", per_class("MaxInventoryCapacity", 21, 30, 45, 60)),
            prop("ClassProbabilityData", None, prop("Wealthy", "Gc", per_class("ClassProbabilities", 30, 40, 28, 2))),
            prop("ShipBaseStatsData", None, prop("Fighter", "Gc", stats)),
            prop("WeaponBaseStatsData", None, prop("Pistol", "Gc", stats)))
        result = parse_inventory(path)
        self.assertEqual(result["MaxSlots"]["Fighter"]["General"], {"C": 50, "B": 70, "A": 80, "S": 100})
        self.assertEqual(result["MultiToolMaxSlots"], {"C": 21, "B": 30, "A": 45, "S": 60})
        self.assertEqual(result["ClassOdds"]["Wealthy"]["S"], 2)
        self.assertEqual(result["BaseStats"]["Ships"]["Fighter"]["S"], [{"Stat": "SHIP_DAMAGE", "Min": 3, "Max": 13}])
        path = self.write("inventorytable.MXML", prop("WeaponInventoryMaxUpgradeSize", "Gc", prop("MaxInventoryCapacity", None, prop("C", "1"))))
        with self.assertRaisesRegex(ValueError, "ShipInventoryMaxUpgradeSize|C/B/A/S"):
            parse_inventory(path)

    def test_trading_economies_use_known_categories(self):
        economy = lambda name, sells, needs: prop(name, "Gc", prop("Sells", "Gc", prop("TradeCategory", sells)),
            prop("Needs", "Gc", prop("TradeCategory", needs)), prop("MinSellingPriceMultiplier", "0.7"),
            prop("MaxSellingPriceMultiplier", "0.9"), prop("MinBuyingPriceMultiplier", "1.4"), prop("MaxBuyingPriceMultiplier", "1.8"),
            prop("MinBuyingPriceMultiplierSurge", "1.8"), prop("MaxBuyingPriceMultiplierSurge", "2.8"))
        category = lambda name, key: prop(name, "Gc", prop("Name", key), prop("ProductMultiplierChangePer100", "0.3"),
                                         prop("SubstanceMultiplierChangePer100", "0.03"))
        categories = prop("CategoryData", None, category("Mineral", "CAT_MINERAL"), category("Energy", "CAT_ENERGY"), category("None", "NONE"))
        path = self.write("tradingclassdatatable.MXML", prop("TradingClassesData", None, economy("Mining", "Mineral", "Energy")),
                          categories, prop("MaxTradingMultiplier", "3.0"), prop("MinTradingMultiplier", "0.2"))
        result = parse_trading(path)
        self.assertEqual(result["Economies"][0]["Sells"], "Mineral")
        self.assertEqual(result["Economies"][0]["Names"], ["Mining", "Minerals", "Ore Extraction", "Prospecting"])
        self.assertEqual(result["Economies"][0]["MaxBuyingPriceMultiplierSurge"], 2.8)
        self.assertEqual(sorted(result["Categories"]), ["Energy", "Mineral", "None"])
        self.assertIsNone(result["Categories"]["None"]["Name"])
        self.assertEqual(result["Categories"]["Mineral"]["Name"], "MINING COMMODITY")
        path = self.write("tradingclassdatatable.MXML", prop("TradingClassesData", None, economy("Mining", "Mineral", "Plutonium")), categories)
        with self.assertRaisesRegex(ValueError, "Plutonium"):
            parse_trading(path)


MBIN = REPO / "data/mbin"


@unittest.skipUnless((MBIN / "inventorytable.MXML").is_file() and (REPO / "data/json/localization.json").is_file(),
                     "real game tables not present")
class RealProgressionTablesTest(unittest.TestCase):
    def test_real_values(self):
        EXMLParser.clear_xml_cache()
        milestones = parse_milestones(str(MBIN / "leveledstatstable.MXML"))
        self.assertEqual(len(milestones["Ladders"]), 54)
        gek = next(ladder for ladder in milestones["Ladders"] if ladder["Id"] == "TRA_STANDING")
        self.assertEqual((gek["Levels"][-1]["Name"], gek["Levels"][-1]["Value"]), ("Trade Lord", 100))
        self.assertEqual(milestones["Journey"][-1], {"Id": "JOURNEY11", "Name": "Galileo", "Points": 55})
        walked = next(ladder for ladder in milestones["Ladders"] if ladder["Id"] == "DIST_WALKED")
        self.assertEqual(walked["Levels"][1]["Value"], 8000)
        inventory = parse_inventory(str(MBIN / "inventorytable.MXML"))
        self.assertEqual(inventory["MaxSlots"]["Fighter"]["General"], {"C": 50, "B": 70, "A": 80, "S": 100})
        self.assertEqual(inventory["ClassOdds"]["Wealthy"], {"C": 30, "B": 40, "A": 28, "S": 2})
        self.assertEqual(inventory["Labels"]["Ships"]["Dropship"], "Hauler")
        self.assertEqual(inventory["Labels"]["Weapons"]["Pristine"], "Experimental")
        trading = parse_trading(str(MBIN / "tradingclassdatatable.MXML"))
        self.assertEqual([(e["Id"], e["Sells"], e["Needs"]) for e in trading["Economies"]][0], ("Mining", "Mineral", "Energy"))
        self.assertEqual(next(e for e in trading["Economies"] if e["Id"] == "Trading")["Names"][0], "Mercantile")


if __name__ == "__main__":
    unittest.main()
