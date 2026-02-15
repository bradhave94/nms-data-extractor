#!/usr/bin/env python3
"""
Generate a controller lookup JSON for NMS control tokens.

This script combines:
1) Extracted game action metadata from ACTIONS.JSON
2) Curated token->icon mappings for FE_* style prompt tokens

Why curated mappings are needed:
- Tokens like FE_ALT1 are prompt slots used in localized text.
- ACTIONS.JSON defines action paths/labels, but does not directly provide a
  one-step FE_ALT1 -> concrete key/button icon mapping for every platform.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


# Curated defaults for the common FE prompt tokens.
# These match known in-game defaults for major platforms.
CURATED_TOKEN_ICONS: dict[str, dict[str, str]] = {
    "Win": {
        "FE_ALT1": "KEYBOARD/INTERACT.E.png",
        "FE_SELECT": "MOUSE/KEY.MOUSELEFT.png",
    },
    "Psn": {
        "FE_ALT1": "DS4/PS.WHITE.SQUARE.png",
        "FE_SELECT": "DS4/PS.WHITE.CROSS.png",
    },
    "Xbx": {
        "FE_ALT1": "XBOX/XBOX.WHITE.X.png",
        "FE_SELECT": "XBOX/XBOX.WHITE.A.png",
    },
    "Nsw": {
        "FE_ALT1": "SWITCH/SWITCH.WHITE.X.png",
        "FE_SELECT": "SWITCH/SWITCH.WHITE.A.png",
    },
}


# Action paths to FE token aliases.
ACTION_PATH_TO_FE_TOKEN = {
    "/actions/FRONTEND/in/menu_transfer": "FE_ALT1",
    "/actions/FRONTEND/in/select": "FE_SELECT",
    "/actions/FRONTEND/in/back": "FE_BACK",
}


def _load_actions_json(actions_json_path: Path) -> dict:
    with open(actions_json_path, encoding="utf-8") as f:
        return json.load(f)


def _extract_english_action_labels(actions_data: dict) -> dict[str, str]:
    """
    Extract English action labels from ACTIONS.JSON.
    Returns mapping of action path -> label.
    """
    localizations = actions_data.get("localization", [])
    if not isinstance(localizations, list):
        return {}
    for entry in localizations:
        if not isinstance(entry, dict):
            continue
        if entry.get("language_tag") != "en_US":
            continue
        return {
            str(k): str(v)
            for k, v in entry.items()
            if isinstance(k, str)
            and isinstance(v, str)
            and k.startswith("/actions/")
        }
    return {}


def _build_lookup_payload(action_labels: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    """
    Build output with FE token aliases and icons by platform.
    Includes Label for debug/traceability.
    """
    payload: dict[str, list[dict[str, str]]] = {}
    for platform, curated_icons in CURATED_TOKEN_ICONS.items():
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for action_path, fe_token in ACTION_PATH_TO_FE_TOKEN.items():
            if fe_token in seen:
                continue
            seen.add(fe_token)
            rows.append(
                {
                    "Key": fe_token,
                    "Icon": curated_icons.get(fe_token, ""),
                    "ActionPath": action_path,
                    "Label": action_labels.get(action_path, ""),
                }
            )
        payload[platform] = sorted(rows, key=lambda r: r["Key"])
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate NMS controller lookup JSON")
    parser.add_argument(
        "--actions-json",
        type=Path,
        default=None,
        help="Path to NMS ACTIONS.JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/json/controllerLookup.generated.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Exit successfully when ACTIONS.JSON is not found (skip generation).",
    )
    args = parser.parse_args(argv)

    actions_json_path = args.actions_json
    if actions_json_path is None:
        candidates = [
            Path(r"X:/Steam/steamapps/common/No Man's Sky/GAMEDATA/INPUT/ACTIONS.JSON"),
            Path(r"C:/Program Files (x86)/Steam/steamapps/common/No Man's Sky/GAMEDATA/INPUT/ACTIONS.JSON"),
            Path("data/EXTRACTED/input/actions.json"),
            Path("data/EXTRACTED/INPUT/ACTIONS.JSON"),
        ]
        actions_json_path = next((p for p in candidates if p.exists()), None)

    if actions_json_path is None or not actions_json_path.exists():
        if args.allow_missing:
            print("[INFO] ACTIONS.JSON not found; skipping controller lookup generation.")
            return 0
        print("[ERROR] Could not locate ACTIONS.JSON. Pass --actions-json explicitly.")
        return 1

    actions_data = _load_actions_json(actions_json_path)
    action_labels = _extract_english_action_labels(actions_data)
    lookup = _build_lookup_payload(action_labels)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(lookup, f, indent=2, ensure_ascii=False)

    total_rows = sum(len(rows) for rows in lookup.values())
    print(
        f"[OK] Wrote {args.output} ({total_rows} rows across {len(lookup)} platforms) "
        f"from {actions_json_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
