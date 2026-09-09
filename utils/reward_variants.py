"""Identify identical special-shop rewards reissued under additional product IDs."""
import json


def reward_identity(item: dict) -> str | None:
    if not item.get("GiveRewardOnSpecialPurchase") or item.get("TradeCategory") != "SpecialShop":
        return None
    if not item.get("Name") or not item.get("IconPath"):
        return None
    return json.dumps({k: v for k, v in item.items() if k not in {
        "Id", "Icon", "Slug", "RewardVariantOf",
    }}, sort_keys=True, ensure_ascii=False)


def enrich_reward_variants(final_files: dict) -> int:
    enriched = 0
    for filename, items in final_files.items():
        if filename in {"new.json", "localization.json"} or not isinstance(items, list):
            continue
        groups: dict[str, list[dict]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            item.pop("RewardVariantOf", None)
            signature = reward_identity(item)
            if signature:
                groups.setdefault(signature, []).append(item)
        for group in groups.values():
            group.sort(key=lambda item: (len(item["Id"]), item["Id"]))
            for item in group[1:]:
                item["RewardVariantOf"] = group[0]["Id"]
                enriched += 1
    return enriched
