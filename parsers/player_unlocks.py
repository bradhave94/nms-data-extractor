"""Parse player titles (playertitledata, plus title rewards from rewardtable).

Titles come from GcPlayerTitleData: each row names the title, the game's hint, the
text shown once it is earned, and at most one unlock condition (a stat threshold,
owning a product, a mission, a trophy or an alien interaction). Rewards can also
grant a title (GcRewardUnlockTitle in rewardtable, e.g. expedition milestones); those
are listed in GrantedByRewards. A title with neither is reported as a warning.

Localization keys must resolve: a missing key raises instead of printing the key.
"""
from pathlib import Path

from .base_parser import EXMLParser, strip_markup_tags

# Keys the game references but ships no English text for (checked in every nms_loc*_english
# table for 7.10). They become null; any other missing key stops the run.
KNOWN_MISSING_KEYS = frozenset({
    "UI_PLAYER_TDESC_OLD",    # hint of the T_OLD title
    "UI_BIGGS_COCKPIT_TREE",  # a corvette research tree whose parts no longer exist
})
# Values used as literal text instead of a localization key: the bare player name and
# "-" (no earned text). Anything else that isn't a key is an unknown format and fails.
_LITERALS = frozenset({"%NAME%", "-"})


def _text(key: str, problems: set[str]) -> str | None:
    """English text for a localization key, or one of the known literal values."""
    if not key:
        return None
    loc = EXMLParser.load_localization()
    if key in loc:
        return strip_markup_tags(loc[key])
    if key in _LITERALS:
        return key
    if key not in KNOWN_MISSING_KEYS:
        problems.add(key)
    return None


def _child_value(element, path: str) -> str:
    found = element.find(path)
    return found.get("value", "") if found is not None else ""


def _field(element, name: str) -> str:
    """A direct child's value. EXMLParser.get_property_value falls back to a deep search,
    which would read an Id nested inside a reward (e.g. an inventory slot) as the reward's Id."""
    return _child_value(element, f'./Property[@name="{name}"]')


def _number_text(value) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _reward_entries(root):
    """(reward table, entry, reward id) for every entry of every reward table."""
    for table in root:
        for entry in table:
            yield table.get("name", ""), entry, _field(entry, "Id") or _field(entry, "RewardId")


def _title_rewards(reward_mxml: Path) -> dict[str, list[dict]]:
    """Title Id -> the rewards that grant it (GcRewardUnlockTitle)."""
    granted: dict[str, list[dict]] = {}
    for table_name, entry, reward_id in _reward_entries(EXMLParser.load_xml(str(reward_mxml))):
        for node in entry.iter("Property"):
            if node.get("value") != "GcRewardUnlockTitle":
                continue
            title_id = _child_value(node, './/Property[@name="TitleID"]')
            if not reward_id or not title_id:
                raise ValueError(f"Title reward in {table_name} has no reward ID or title ID")
            granted.setdefault(title_id, []).append({"Id": reward_id, "RewardTable": table_name})
    return granted


def parse_player_titles(mxml_path: str) -> list:
    """Parse playertitledata.MXML (plus title rewards from rewardtable.MXML beside it)."""
    root = EXMLParser.load_xml(mxml_path)
    parser = EXMLParser()
    rows = root.findall('./Property[@name="Titles"]/Property[@name="Titles"]')
    if not rows:
        raise ValueError("Player title source is empty or incompatible")
    reward_mxml = Path(mxml_path).with_name("rewardtable.MXML")
    if not reward_mxml.is_file():
        raise ValueError(f"Required title reward source missing: {reward_mxml.name}")
    rewards = _title_rewards(reward_mxml)
    problems: set[str] = set()
    titles = []
    for row in rows:
        title_id = _field(row, "ID")
        if not title_id:
            raise ValueError("Player title has no game ID")
        name = _text(_field(row, "Title"), problems)
        # T_DEFAULT is the bare player name ("%NAME%"), not an earnable title.
        if not name or name.strip() == "%NAME%":
            rewards.pop(title_id, None)
            continue
        unlock = _unlock_condition(row, parser)
        title = {
            "Id": title_id,
            "Name": name,
            "Hint": _text(_field(row, "UnlockDescription"), problems),
            "Unlocked": _text(_field(row, "AlreadyUnlockedDescription"), problems),
            "Unlock": unlock,
            "GrantedByRewards": sorted(rewards.pop(title_id, []), key=lambda reward: reward["Id"]),
            "RevealedBy": _field(row, "RevealedBy") or None,
            "BlockedInSeasons": sorted(
                int(parser.parse_value(item.get("value", "0")))
                for item in row.findall('./Property[@name="BlockedInSeasons"]/Property')
            ),
            "UnlocksSpecials": sorted(
                item.get("value", "")
                for item in row.findall('./Property[@name="TitleUnlocksSpecials"]/Property')
                if item.get("value")
            ),
        }
        if title["Unlocked"] == "-":
            title["Unlocked"] = None
        # The game fills %NUM% with the stat threshold when it shows the text.
        if unlock["Type"] == "Stat":
            for key in ("Hint", "Unlocked"):
                if title[key] and "%NUM%" in title[key]:
                    title[key] = title[key].replace("%NUM%", _number_text(unlock["Value"]))
        titles.append(title)
    if problems:
        raise ValueError(f"Player title text keys are missing or in an unknown format: {', '.join(sorted(problems))}")
    if rewards:
        raise ValueError(f"Rewards grant unknown player titles: {', '.join(sorted(rewards))}")
    unexplained = sorted(t["Id"] for t in titles if t["Unlock"]["Type"] == "None" and not t["GrantedByRewards"])
    if unexplained:
        print(f"  [WARN] Player titles with no unlock condition or granting reward: {', '.join(unexplained)}")
    return sorted(titles, key=lambda item: item["Id"])


def _unlock_condition(row, parser) -> dict:
    """The unlock condition the game checks for a title (Type "None" when there is none)."""
    stat = _field(row, "UnlockedByStat")
    product = _field(row, "UnlockedByProductRecipe")
    mission = _field(row, "UnlockedByMission")
    trophy = _field(row, "UnlockedByTrophy")
    interaction = _child_value(row, './Property[@name="UnlockedByInteraction"]/Property[@name="InteractionType"]')
    race = _child_value(row, './Property[@name="UnlockedByInteractionRace"]/Property[@name="AlienRace"]')
    conditions = [kind for kind, present in (
        ("Stat", stat), ("Product", product), ("Mission", mission), ("Trophy", trophy),
        ("Interaction", interaction and interaction != "None"),
    ) if present]
    if len(conditions) > 1:
        raise ValueError(f"Player title {_field(row, 'ID')} has several unlock conditions: {conditions}")
    kind = conditions[0] if conditions else "None"
    unlock = {"Type": kind}
    if kind == "Stat":
        unlock["Stat"] = stat
        unlock["Value"] = parser.parse_value(_field(row, "UnlockedByStatValue") or "0")
        rank = parser.parse_value(_field(row, "UnlockedByLeveledStatRank") or "0")
        if rank:
            unlock["LeveledStatRank"] = rank
    elif kind == "Product":
        unlock["ProductId"] = product
    elif kind == "Mission":
        unlock["MissionId"] = mission
    elif kind == "Trophy":
        unlock["TrophyId"] = trophy
    elif kind == "Interaction":
        unlock["Interaction"] = interaction
        unlock["InteractionIndex"] = parser.parse_value(_field(row, "UnlockedByInteractionIndex") or "0")
        if race and race != "None":
            unlock["Race"] = race
        if _field(row, "UnlockedByInteractionOnlyTestMainRaces") == "true":
            unlock["OnlyMainRaces"] = True
    return unlock

