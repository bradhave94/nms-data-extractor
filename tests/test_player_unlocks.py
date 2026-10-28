"""Player titles: synthetic fixtures plus counts on the real tables."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from parsers.base_parser import EXMLParser
from parsers.player_unlocks import parse_player_titles

REPO = Path(__file__).resolve().parent.parent
LOCALIZATION = {
    "UI_TITLE_SPOOK": "Mind Harvester %NAME%",
    "UI_HINT_SPOOK": "Gather haunting mementos",
    "UI_OWNED_SPOOK": "Gathered %NUM% haunting mementos",
    "UI_TITLE_MECH": "Pilot %NAME%",
    "UI_OWNED_MECH": "Owned an Exo-Mech",
    "UI_TITLE_X": "%NAME% the Tester",
}


def title(title_id, title_key, *, stat="", value="0.000000", rank="0", product="", mission="", trophy="",
          interaction="None", index="0", race="None", main_races="false", hint="", owned="", revealed="",
          seasons="", specials=""):
    return f'''<Property name="Titles" value="GcPlayerTitle" _id="{title_id}">
      <Property name="ID" value="{title_id}" />
      <Property name="Title" value="{title_key}" />
      <Property name="UnlockDescription" value="{hint}" />
      <Property name="AlreadyUnlockedDescription" value="{owned}" />
      <Property name="RevealedBy" value="{revealed}" />
      <Property name="UnlockedByProductRecipe" value="{product}" />
      <Property name="UnlockedByMission" value="{mission}" />
      <Property name="UnlockedByTrophy" value="{trophy}" />
      <Property name="UnlockedByStat" value="{stat}" />
      <Property name="UnlockedByStatValue" value="{value}" />
      <Property name="UnlockedByLeveledStatRank" value="{rank}" />
      <Property name="UnlockedByInteraction" value="GcInteractionType"><Property name="InteractionType" value="{interaction}" /></Property>
      <Property name="UnlockedByInteractionIndex" value="{index}" />
      <Property name="UnlockedByInteractionRace" value="GcAlienRace"><Property name="AlienRace" value="{race}" /></Property>
      <Property name="UnlockedByInteractionOnlyTestMainRaces" value="{main_races}" />
      <Property name="BlockedInSeasons">{seasons}</Property>
      <Property name="TitleUnlocksSpecials">{specials}</Property>
    </Property>'''


def unlock_title_reward(title_id):
    return f'''<Property name="List" value="GcRewardTableItem" _index="0">
      <Property name="Reward" value="GcRewardUnlockTitle"><Property name="GcRewardUnlockTitle">
        <Property name="TitleID" value="{title_id}" />
      </Property></Property>
    </Property>'''


def entry(entry_id, *rewards, table="GenericTable", id_field="Id"):
    return (f'<Property name="{table}" value="GcGenericRewardTableEntry">'
            f'<Property name="{id_field}" value="{entry_id}" />'
            f'<Property name="List" value="GcRewardTableItemList"><Property name="List">{"".join(rewards)}</Property></Property>'
            f'</Property>')


class PlayerUnlocksTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(EXMLParser, "load_localization", return_value=LOCALIZATION)
        patcher.start()
        self.addCleanup(patcher.stop)
        EXMLParser.clear_xml_cache()
        self.rewards()

    def write(self, name, body):
        EXMLParser.clear_xml_cache()
        path = Path(self.temp.name) / name
        path.write_text(f'<?xml version="1.0" encoding="utf-8"?>\n<Data>{body}</Data>', encoding="utf-8")
        return str(path)

    def rewards(self, *tables):
        return self.write("rewardtable.MXML", "".join(tables) or '<Property name="GenericTable" />')

    def titles(self, *rows):
        return parse_player_titles(self.write("playertitledata.MXML", f'<Property name="Titles">{"".join(rows)}</Property>'))

    def test_titles_resolve_text_fill_thresholds_and_skip_the_bare_name(self):
        rows = {row["Id"]: row for row in self.titles(
            title("T_DEFAULT", "%NAME%"),
            title("T_SPOOK", "UI_TITLE_SPOOK", stat="SPOOK_PACKAGES", value="20.000000",
                  hint="UI_HINT_SPOOK", owned="UI_OWNED_SPOOK",
                  specials='<Property name="TitleUnlocksSpecials" value="GRUB_HAT" />'),
            title("T_MECH", "UI_TITLE_MECH", product="GARAGE_MECH", owned="-", revealed="T_SPOOK",
                  seasons='<Property name="BlockedInSeasons" value="45" />'),
        )}
        self.assertEqual(sorted(rows), ["T_MECH", "T_SPOOK"])
        self.assertEqual(rows["T_SPOOK"]["Name"], "Mind Harvester %NAME%")
        self.assertEqual(rows["T_SPOOK"]["Unlocked"], "Gathered 20 haunting mementos")
        self.assertEqual(rows["T_SPOOK"]["Unlock"], {"Type": "Stat", "Stat": "SPOOK_PACKAGES", "Value": 20.0})
        self.assertEqual(rows["T_SPOOK"]["UnlocksSpecials"], ["GRUB_HAT"])
        self.assertEqual(rows["T_MECH"]["Unlock"], {"Type": "Product", "ProductId": "GARAGE_MECH"})
        self.assertIsNone(rows["T_MECH"]["Unlocked"])
        self.assertIsNone(rows["T_MECH"]["Hint"])
        self.assertEqual(rows["T_MECH"]["RevealedBy"], "T_SPOOK")
        self.assertEqual(rows["T_MECH"]["BlockedInSeasons"], [45])

    def test_every_unlock_condition_type(self):
        rows = {row["Id"]: row["Unlock"] for row in self.titles(
            title("T_RANK", "UI_TITLE_X", stat="DIST_WALKED", rank="4"),
            title("T_MISSION", "UI_TITLE_X", mission="HUB_PILGRIM"),
            title("T_TROPHY", "UI_TITLE_X", trophy="TOLIVEFOREVER"),
            title("T_MONO", "UI_TITLE_X", interaction="Monolith", index="2", race="Traders", main_races="true"),
            title("T_NONE", "UI_TITLE_X"),
        )}
        self.assertEqual(rows["T_RANK"], {"Type": "Stat", "Stat": "DIST_WALKED", "Value": 0.0, "LeveledStatRank": 4})
        self.assertEqual(rows["T_MISSION"], {"Type": "Mission", "MissionId": "HUB_PILGRIM"})
        self.assertEqual(rows["T_TROPHY"], {"Type": "Trophy", "TrophyId": "TOLIVEFOREVER"})
        self.assertEqual(rows["T_MONO"], {"Type": "Interaction", "Interaction": "Monolith", "InteractionIndex": 2,
                                          "Race": "Traders", "OnlyMainRaces": True})
        self.assertEqual(rows["T_NONE"], {"Type": "None"})

    def test_titles_with_no_way_to_earn_them_are_reported(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.titles(title("T_NONE", "UI_TITLE_X"), title("T_MECH", "UI_TITLE_MECH", product="GARAGE_MECH"))
        self.assertIn("no unlock condition or granting reward: T_NONE", output.getvalue())
        self.assertNotIn("T_MECH", output.getvalue())

    def test_titles_granted_by_rewards(self):
        self.rewards('<Property name="SeasonRewardTable21">'
                     f'{entry("RS_S21_S2M4", unlock_title_reward("T_EXO"), table="SeasonRewardTable21")}</Property>')
        [row] = self.titles(title("T_EXO", "UI_TITLE_X"))
        self.assertEqual(row["GrantedByRewards"], [{"Id": "RS_S21_S2M4", "RewardTable": "SeasonRewardTable21"}])
        self.rewards(f'<Property name="GenericTable">{entry("R_X", unlock_title_reward("T_GONE"))}</Property>')
        with self.assertRaisesRegex(ValueError, "unknown player titles: T_GONE"):
            self.titles(title("T_EXO", "UI_TITLE_X"))

    def test_unknown_text_and_conflicting_conditions_fail(self):
        with self.assertRaisesRegex(ValueError, "UI_TITLE_NEW"):
            self.titles(title("T_NEW", "UI_TITLE_NEW"))
        with self.assertRaisesRegex(ValueError, "Ui_Title_Lower"):
            self.titles(title("T_NEW", "Ui_Title_Lower"))
        with self.assertRaisesRegex(ValueError, "several unlock conditions"):
            self.titles(title("T_BOTH", "UI_TITLE_MECH", stat="X", product="Y"))
        [row] = self.titles(title("T_OLD", "UI_TITLE_X", hint="UI_PLAYER_TDESC_OLD"))
        self.assertIsNone(row["Hint"])


MBIN = REPO / "data/mbin"


@unittest.skipUnless((MBIN / "playertitledata.MXML").is_file() and (REPO / "data/json/localization.json").is_file(),
                     "real game tables not present")
class RealPlayerUnlocksTest(unittest.TestCase):
    """Parses the committed 7.10 tables directly, so a parser regression fails before publishing."""

    def test_real_counts(self):
        EXMLParser.clear_xml_cache()
        titles = parse_player_titles(str(MBIN / "playertitledata.MXML"))
        self.assertEqual(len(titles), 346)
        by_id = {row["Id"]: row for row in titles}
        self.assertEqual(by_id["T_SPOOKPACKAGE"]["Unlocked"], "Gathered 20 haunting mementos")
        self.assertEqual(by_id["T_EXO_KILL"]["GrantedByRewards"], [{"Id": "RS_S21_S2M4", "RewardTable": "SeasonRewardTable21"}])
        self.assertEqual(sum(1 for row in titles if row["GrantedByRewards"]), 24)


if __name__ == "__main__":
    unittest.main()
