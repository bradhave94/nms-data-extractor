"""Frigate traits, settlement perks, item sources and research trees: synthetic fixtures
plus counts on the real 7.10 tables."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from parsers.base_parser import EXMLParser
from parsers.reference_tables import (
    parse_frigate_traits, parse_item_sources, parse_research_trees, parse_settlement_perks,
)

REPO = Path(__file__).resolve().parent.parent
LOCALIZATION = {
    "TRAIT_GUNNERS": "Cowardly Gunners", "TRAIT_TANKS": "Large Tanks",
    "STAT_COMBAT": "%amount% Combat", "STAT_FUEL": "%amount% Expedition Fuel Cost",
    "PERK_WORMS": "Worm infestation", "PERK_WORMS_DESC": "Increases maintenance costs",
    "SEASON_1": "The Pioneers", "OPTION_OFFER": "Make Offering", "GUN_GRUB": "Larva Cannon",
    "TREE_STATION": "<IMG>DIAMONDBULLET<> Basic Construction DIAMONDBULLET", "TREE_TIMBER": "Timber Structures",
    "FLEET_UI_TYPE_MINING": "Industrial", "FLEET_UI_TYPE_PIRATE": "RAIDER",
    "UI_SETTLEMENT_STAT_COST_NAME": "Upkeep Costs",
}


def prop(name, value=None, *children, **attrs):
    extra = "".join(f' {key}="{val}"' for key, val in attrs.items())
    value_attr = f' value="{value}"' if value is not None else ""
    return f'<Property name="{name}"{value_attr}{extra}>{"".join(children)}</Property>'


def enum(outer, inner, value):
    return prop(outer, "Gc", prop(inner, value))


class ReferenceTablesTest(unittest.TestCase):
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

    def test_frigate_trait_effects_use_fleet_globals_and_the_games_sign(self):
        values = lambda: prop("StatAlteration", None, prop("NegativeSmall", "-2"), prop("Primary", "15"))
        self.write("gcfleetglobals.global.MXML", prop("FrigateTraitStrengths", "Gc", prop("FrigateStatType", None,
            prop("Combat", "Gc", values(), prop("StatLocID", "STAT_COMBAT"), prop("StatDisplaysPositive", "true")),
            prop("FuelCapacity", "Gc", values(), prop("StatLocID", "STAT_FUEL"), prop("StatDisplaysPositive", "false")))))
        trait = lambda trait_id, name, stat, strength: prop("Traits", "GcFrigateTraitData",
            prop("ID", trait_id), prop("DisplayName", name), enum("FrigateStatType", "FrigateStatType", stat),
            enum("Strength", "FrigateTraitStrength", strength),
            prop("ChanceOfBeingOffered", None, prop("Combat", "0"), prop("Mining", "5"), prop("Pirate", "2")))
        path = self.write("frigatetraittable.MXML", prop("Traits", None,
            trait("COMBAT_BAD_1", "TRAIT_GUNNERS", "Combat", "NegativeSmall"),
            trait("FUEL_PRI", "TRAIT_TANKS", "FuelCapacity", "Primary")))
        rows = {row["Id"]: row for row in parse_frigate_traits(path)}
        self.assertEqual(rows["COMBAT_BAD_1"]["Effect"], "-2 Combat")
        self.assertFalse(rows["COMBAT_BAD_1"]["Beneficial"])
        self.assertEqual(rows["COMBAT_BAD_1"]["OfferedOn"], [{"Class": "Mining", "Label": "Industrial", "Weight": 5},
                                                             {"Class": "Pirate", "Label": "Raider", "Weight": 2}])
        self.assertEqual(rows["FUEL_PRI"]["Value"], 15)
        self.assertEqual(rows["FUEL_PRI"]["Effect"], "-15 Expedition Fuel Cost")
        path = self.write("frigatetraittable.MXML", prop("Traits", None, trait("X", "TRAIT_TANKS", "Combat", "Huge")))
        with self.assertRaisesRegex(ValueError, "unknown stat or strength"):
            parse_frigate_traits(path)

    def test_settlement_perks_take_ranges_from_settlement_globals(self):
        self.write("gcsettlementglobals.MXML", prop("PerkStatStrengthValues", None, prop("Upkeep", "Gc",
            prop("PerkStatStrengthValues", None, prop("NegativeMedium", "Gc", prop("AmountMin", "-3"), prop("AmountMax", "-2"))))))
        path = self.write("settlementperkstable.MXML", prop("Table", None, prop("Table", "GcSettlementPerkData",
            prop("ID", "STARTING_NEG1"), prop("Name", "PERK_WORMS"), prop("Description", "PERK_WORMS_DESC"),
            prop("IsNegative", "true"), prop("IsStarter", "true"),
            prop("StatChanges", None, prop("StatChanges", "Gc", enum("Stat", "SettlementStatType", "Upkeep"),
                                           enum("Strength", "SettlementStatStrength", "NegativeMedium"))),
            prop("AssociatedBuildings", None, prop("AssociatedBuildings", "Gc", prop("BuildingClass", "Settlement_Farm"))))))
        [perk] = parse_settlement_perks(path)
        self.assertEqual(perk["Name"], "Worm infestation")
        self.assertTrue(perk["IsNegative"] and perk["IsStarter"])
        self.assertEqual(perk["Effects"], [{"Stat": "Upkeep", "Label": "Upkeep Costs", "Strength": "NegativeMedium",
                                            "Min": -3, "Max": -2, "ChangesPopulation": False}])
        self.assertEqual(perk["Buildings"], ["Settlement_Farm"])

    def test_item_sources_and_fixed_price_exchanges(self):
        item = lambda kind, body, chance="100": prop("List", "GcRewardTableItem", prop("PercentageChance", chance),
                                                     prop("Reward", kind, prop(kind, None, *body)))
        reward = lambda reward_id, choice, *items: prop("GenericTable", "Gc", prop("Id", reward_id),
            prop("List", "GcRewardTableItemList", prop("RewardChoice", choice), prop("List", None, *items)))
        self.write("rewardtable.MXML", prop("GenericTable", None,
            reward("R_GRUB_GUN", "GiveAll", item("GcRewardSpecificWeapon", [prop("NameOverride", "GUN_GRUB")])),
            reward("R_CHART", "SelectAlways", item("GcRewardSpecificProduct", [prop("ID", "CHART_A")]),
                   item("GcRewardSpecificProduct", [prop("ID", "CHART_B")])),
            reward("R_GEL", "GiveAll", item("GcRewardSpecificProduct", [prop("ID", "PRODFUEL2"), prop("AmountMin", "2"), prop("AmountMax", "2")])),
            reward("R_FOOD", "GiveAll", item("GcRewardSpecificProduct", [prop("ID", "FOOD_P"), prop("AmountMin", "5"), prop("AmountMax", "10")])),
            reward("R_HELMET", "GiveAll", item("GcRewardSpecificSpecial", [prop("ID", "DIVE_HELMET")])),
            reward("R_TUBERS", "GiveAll", item("GcRewardSpecificProduct", [prop("ID", "TUBER"), prop("AmountMin", "5"), prop("AmountMax", "10")]))))
        cost = lambda cost_id, kind, *body: prop("InteractionTable", "Gc", prop("Id", cost_id), prop("Cost", kind, prop(kind, None, *body)))
        self.write("costtable.MXML", prop("InteractionTable", None,
            cost("C_GUN", "GcCostProduct", prop("Id", "SPOOK_PACKAGE2"), prop("Amount", "5")),
            cost("C_CHART", "GcCostProduct", prop("Id", "NAV_DATA"), prop("Amount", "1")),
            cost("C_GEL", "GcCostMoney", prop("Cost", "500"), enum("CostCurrency", "Currency", "Units")),
            prop("InteractionTable", "Gc", prop("Id", "C_FREE"), prop("DontCharge", "true"),
                 prop("Cost", "GcCostProduct", prop("GcCostProduct", None, prop("Id", "NAV_DATA"), prop("Amount", "1")))),
            cost("C_DEFAULT_AMOUNT", "GcCostProduct", prop("Id", "NAV_DATA"), prop("Amount", "1"), prop("UseDefaultAmount", "true")),
            cost("C_SEASON_ID", "GcCostProduct", prop("Id", "NAV_DATA"), prop("Amount", "1"), prop("TakeIDFromSeasonData", "true")),
            cost("C_SEASON_AMOUNT", "GcCostProduct", prop("Id", "NAV_DATA"), prop("Amount", "1"), prop("TakeAmountFromSeasonData", "true")),
            cost("C_DEFAULT_ITEM", "GcCostProduct", prop("Id", "NAV_DATA"), prop("Amount", "1"),
                 prop("Default", "GcDefaultMissionProductEnum", prop("DefaultProductType", "PrimaryProduct"))),
            cost("C_LOCAL", "GcCostSubstance", prop("Id", "FUEL1"), prop("Amount", "5"), prop("UseRandomPlanetIndex", "true")),
            cost("C_FUEL", "GcCostSubstance", prop("Id", "FUEL1"), prop("Amount", "5"), prop("UseRandomPlanetIndex", "false"))))
        option = lambda cost_id, reward_id: prop("Options", "GcAlienPuzzleOption", prop("Name", "OPTION_OFFER"),
            prop("Cost", cost_id), prop("Rewards", None, prop("Rewards", reward_id)))
        dialog = lambda race, *options: prop("Table", "GcAlienPuzzleEntry", prop("Id", "?SHOP"),
            enum("Race", "AlienRace", race), enum("Type", "InteractionType", "Shop"),
            enum("Category", "AlienPuzzleCategory", "BiomeCold"), prop("Options", None, *options))
        self.write("nms_dialog_gcalienpuzzletable.MXML", prop("Table", None,
            dialog("Traders", option("C_GUN", "R_GRUB_GUN"), option("C_CHART", "R_CHART"), option("C_GEL", "R_GEL"),
                   option("C_GEL", "R_FOOD"), option("C_FREE", "R_HELMET"), option("C_GEL", "R_HELMET"),
                   option("C_DEFAULT_AMOUNT", "R_HELMET"), option("C_SEASON_ID", "R_HELMET"), option("C_SEASON_AMOUNT", "R_HELMET"),
                   option("C_DEFAULT_ITEM", "R_HELMET"), option("C_LOCAL", "R_HELMET"),
                   prop("Options", "GcAlienPuzzleOption", prop("Name", "OPTION_OFFER"), prop("Cost", "C_FUEL"),
                        prop("Rewards", None, prop("Rewards", "R_TUBERS"), prop("Rewards", "R_TUBERS")))),
            dialog("Warriors", option("C_GUN", "R_GRUB_GUN"))))
        self.write("unlockabletwitchrewards.MXML", prop("Table", None, prop("Table", "Gc", prop("TwitchId", "TWITCH_1"), prop("ProductId", "S_POSTER29"))))
        self.write("unlockableplatformrewards.MXML", prop("Table", None, prop("Table", "Gc", prop("RewardId", "TGA_SHIP1"), prop("ProductId", "TGA_SHIP01"))))
        self.write("purchaseablespecials.MXML", prop("Table", None, prop("Table", "Gc", prop("ID", "BASE_DUST12"), prop("ShopNumber", "118"), prop("MissionTier", "3"))))
        self.write("historicalseasondatatable.MXML", prop("Table", None, prop("Table", "Gc", prop("SeasonName", "SEASON_1"),
            prop("SeasonNumber", "1"), prop("RemixNumber", "0"), prop("DisplayNumber", "1"))))
        path = self.write("unlockableseasonrewards.MXML", prop("Table", None, prop("Table", "Gc", prop("ID", "EXPD_TITLE23"),
            prop("SeasonIds", None, prop("SeasonIds", "23")), prop("StageIds", None, prop("StageIds", "5")))))
        sources = parse_item_sources(path)
        self.assertEqual(sources["Items"]["EXPD_TITLE23"], [{"Type": "Expedition", "Expeditions": [23], "Phases": [5], "SwitchExclusive": False}])
        self.assertEqual(sources["Items"]["S_POSTER29"], [{"Type": "Twitch", "Drop": "TWITCH_1"}])
        self.assertEqual(sources["Items"]["BASE_DUST12"], [{"Type": "Quicksilver", "Shop": 118, "MissionTier": 3}])
        self.assertEqual(sources["Expeditions"], [{"Number": 1, "Remix": 0, "DisplayNumber": 1, "Name": "The Pioneers"}])
        exchanges = {exchange["Id"]: exchange for exchange in sources["Exchanges"]}
        # The chart reward picks one of two at random, and C_FREE is never charged: neither is a fixed-price exchange.
        # The same dialog for another race is its own exchange.
        # Costs that aren't plain fixed prices (never charged, default or season amounts, a default
        # item, a planet-local substance) are not exchanges.
        self.assertEqual(sorted(exchanges), ["?SHOP@Traders#0", "?SHOP@Traders#11", "?SHOP@Traders#2", "?SHOP@Traders#3",
                                             "?SHOP@Traders#5", "?SHOP@Warriors#0"])
        # The same reward listed twice pays out twice.
        self.assertEqual(exchanges["?SHOP@Traders#11"]["Gives"], [{"Type": "Product", "Id": "TUBER", "AmountMin": 10, "AmountMax": 20}])
        gun = exchanges["?SHOP@Traders#0"]
        self.assertEqual(gun["Cost"], {"Type": "Product", "Id": "SPOOK_PACKAGE2", "Amount": 5})
        self.assertEqual(gun["Gives"], [{"Type": "Weapon", "Id": "R_GRUB_GUN", "Name": "Larva Cannon"}])
        self.assertEqual((gun["Race"], gun["Interaction"], gun["Category"]), ("Traders", "Shop", "BiomeCold"))
        self.assertEqual(exchanges["?SHOP@Traders#2"]["Cost"], {"Type": "Currency", "Id": "Units", "Amount": 500})
        self.assertEqual(exchanges["?SHOP@Traders#3"]["Gives"], [{"Type": "Product", "Id": "FOOD_P", "AmountMin": 5, "AmountMax": 10}])
        self.assertEqual(exchanges["?SHOP@Traders#5"]["Gives"], [{"Type": "Product", "Id": "DIVE_HELMET", "AmountMin": 1, "AmountMax": 1}])
        self.assertEqual(sources["Items"]["PRODFUEL2"], [{"Type": "Exchange", "Exchange": "?SHOP@Traders#2"}])
        self.assertNotIn("CHART_A", sources["Items"])

    def test_conflicting_exchanges_and_unknown_expeditions(self):
        self.test_item_sources_and_fixed_price_exchanges()
        folder = Path(self.temp.name)
        # The same dialog Id and race twice, offering different things: the identity is ambiguous.
        entry = lambda reward_id: prop("Table", "GcAlienPuzzleEntry", prop("Id", "?DUP"), enum("Race", "AlienRace", "Traders"),
            prop("Options", None, prop("Options", "GcAlienPuzzleOption", prop("Name", "OPTION_OFFER"), prop("Cost", "C_GEL"),
                                       prop("Rewards", None, prop("Rewards", reward_id)))))
        self.write("nms_dialog_gcalienpuzzletable.MXML", prop("Table", None, entry("R_GEL"), entry("R_FOOD")))
        with self.assertRaisesRegex(ValueError, "share the identity"):
            parse_item_sources(str(folder / "unlockableseasonrewards.MXML"))

        self.write("nms_dialog_gcalienpuzzletable.MXML", prop("Table", None))
        path = self.write("unlockableseasonrewards.MXML", prop("Table", None, prop("Table", "Gc", prop("ID", "EXPD_NEXT"),
            prop("SeasonIds", None, prop("SeasonIds", "24")), prop("StageIds", None, prop("StageIds", "1")))))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            parse_item_sources(path)
        self.assertIn("expeditions with no history row: 24", output.getvalue())

    def test_research_trees_keep_order_skip_test_trees_and_check_currencies(self):
        node = lambda item_id, *children: prop("Children", "Gc", prop("Unlockable", item_id), prop("Children", None, *children))
        priced = lambda field, *pairs: prop("Table", None, *[prop("Table", "Gc", prop("ID", key), prop(field, value)) for key, value in pairs])
        self.write("nms_reality_gcproducttable.MXML", priced("RecipeCost", ("T_FLOOR", "2")))
        self.write("nms_basepartproducts.MXML", priced("RecipeCost", ("T_WALL", "1")))
        self.write("nms_reality_gctechnologytable.MXML", priced("FragmentCost", ("T_RAMP", "90")))
        tree = lambda title, cost_id, root: prop("Trees", "Gc", prop("Title", title), prop("CostTypeID", cost_id),
            prop("Root", "Gc", prop("Unlockable", root[0]), prop("Children", None, *root[1:])))
        cost_types = prop("CostTypes", None, prop("CostTypes", "Gc", prop("CostTypeID", "SALVAGE"),
            prop("TypeOfCost", "Product"), prop("TypeID", "BP_SALVAGE")))
        path = self.write("unlockableitemtrees.MXML", prop("Trees", None,
            prop("Test", "Gc", prop("Title", "TEST"), prop("Trees", None, tree("TREE_TIMBER", "SALVAGE", ["X"]))),
            prop("BasicBaseParts", "Gc", prop("Title", "TREE_STATION"), prop("Trees", None,
                tree("TREE_TIMBER", "SALVAGE", ["T_WALL", node("T_FLOOR", node("T_RAMP"))]))),
        ), cost_types)
        [group] = parse_research_trees(path)["Groups"]
        self.assertEqual(group["Name"], "Basic Construction")
        [timber] = group["Trees"]
        self.assertEqual(timber["Cost"], {"Type": "Product", "Id": "BP_SALVAGE"})
        self.assertEqual(timber["Nodes"], [{"Id": "T_WALL", "Parent": None, "Price": 1},
                                           {"Id": "T_FLOOR", "Parent": "T_WALL", "Price": 2},
                                           {"Id": "T_RAMP", "Parent": "T_FLOOR", "Price": 90}])
        path = self.write("unlockableitemtrees.MXML", prop("Trees", None, prop("Base", "Gc", prop("Title", "TREE_STATION"),
            prop("Trees", None, tree("TREE_TIMBER", "MYSTERY", ["T_WALL"])))), cost_types)
        with self.assertRaisesRegex(ValueError, "unknown cost type: MYSTERY"):
            parse_research_trees(path)


MBIN = REPO / "data/mbin"


@unittest.skipUnless((MBIN / "unlockableitemtrees.MXML").is_file() and (REPO / "data/json/localization.json").is_file(),
                     "real game tables not present")
class RealReferenceTablesTest(unittest.TestCase):
    def test_real_counts(self):
        EXMLParser.clear_xml_cache()
        self.assertEqual(len(parse_frigate_traits(str(MBIN / "frigatetraittable.MXML"))), 178)
        self.assertEqual(len(parse_settlement_perks(str(MBIN / "settlementperkstable.MXML"))), 90)
        sources = parse_item_sources(str(MBIN / "unlockableseasonrewards.MXML"))
        self.assertEqual(len(sources["Expeditions"]), 23)
        self.assertEqual(len(sources["Exchanges"]), 26)
        self.assertEqual(len(sources["Exchanges"]), len({exchange["Id"] for exchange in sources["Exchanges"]}))
        counts = {}
        for item_sources in sources["Items"].values():
            for source in item_sources:
                counts[source["Type"]] = counts.get(source["Type"], 0) + 1
        self.assertEqual({key: counts[key] for key in ("Twitch", "Quicksilver", "Expedition", "Platform")},
                         {"Twitch": 435, "Quicksilver": 336, "Expedition": 293, "Platform": 3})
        grub = [exchange for exchange in sources["Exchanges"] if exchange["Gives"][0]["Id"] == "R_GRUB_GUN"]
        self.assertEqual(grub[0]["Cost"], {"Type": "Product", "Id": "SPOOK_PACKAGE2", "Amount": 5})
        groups = parse_research_trees(str(MBIN / "unlockableitemtrees.MXML"))["Groups"]
        self.assertEqual(len(groups), 14)
        nodes = {node["Id"]: node for group in groups for tree in group["Trees"] for node in tree["Nodes"]}
        self.assertEqual(nodes["SUIT_ROCKET"]["Price"], 90)
        self.assertEqual(nodes["STA_62"]["Price"], 20)


if __name__ == "__main__":
    unittest.main()
