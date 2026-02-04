"""JSON key formatting utilities"""


def _to_camel_case_key(key: str) -> str:
    """Convert a PascalCase key to camelCase (first letter lowercase)."""
    if not key:
        return key
    return key[0].lower() + key[1:] if len(key) > 1 else key.lower()


def keys_to_camel(obj):
    """
    Recursively convert all dict keys to camelCase (first letter lowercase).
    e.g. "ConsumableRewardTexts" -> "consumableRewardTexts"
    """
    if isinstance(obj, dict):
        return {_to_camel_case_key(k): keys_to_camel(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [keys_to_camel(item) for item in obj]
    return obj
