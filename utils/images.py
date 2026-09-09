#!/usr/bin/env python3
"""Extract item icons into validated PNGs for CDN/site synchronization.

The image directory is treated as a published output.  Conversion happens in
a sibling staging directory and is published only after every expected icon
has converted to a valid PNG.  Existing output is left alone on failure.
"""

from __future__ import annotations

import binascii
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parsers.base_parser import shared_texture_icon_name


ICON_JSON_FILES = [
    "Buildings.json",
    "ConstructedTechnology.json",
    "Food.json",
    "Corvette.json",
    "Curiosities.json",
    "EggModifiers.json",
    "Exocraft.json",
    "Fish.json",
    "NutrientProcessor.json",
    "Others.json",
    "Products.json",
    "RawMaterials.json",
    "Refinery.json",
    "Starships.json",
    "Technology.json",
    "TechnologyModule.json",
    "Trade.json",
    "Upgrades.json",
    "Creatures.json",
]

# Only these fields are consumed by the site today.  In particular, do not
# turn every ``*IconPath`` metadata field into a required output: HeroIconPath
# and the various buff/background fields describe optional art that the site
# does not render as an item image.
_REQUIRED_ICON_FIELD_SPECS = (
    ("Icon", "IconPath"),
    ("BattleAffinityIcon", "BattleAffinityIconPath"),
    ("CategoryIcon", "CategoryIconPath"),
)
_IGNORED_JSON_NAMES = {
    "controllerlookup.generated.json",
    "extraction-manifest.json",
    "localization.json",
    "manifest.json",
    "new.json",
}
_IMAGE_MANIFEST_FILENAME = "manifest.json"
IMAGE_MANIFEST_FILENAME = _IMAGE_MANIFEST_FILENAME
ICON_MANIFEST_FILENAME = _IMAGE_MANIFEST_FILENAME
_IMAGE_MANIFEST_VERSION = 1
_IMAGE_MANIFEST_ALGORITHM = "sha256"
_IMAGE_PROVENANCE_FILE_ONLY = "fileIntegrityOnly"
_IMAGE_PROVENANCE_GAME_INVENTORY = "gameInventory"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_PNG_CHUNK_LENGTH = 64 * 1024 * 1024


def sanitize_filename(id_str: str) -> str:
    if not id_str:
        return "unknown"
    return re.sub(r'[\\/:*?"<>|]', "_", str(id_str)).strip() or "unknown"


def _text_value(value) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    return value


def _field_value(item: dict, field_name: str):
    """Return a field using case-insensitive matching for parser variants."""
    wanted = field_name.casefold()
    for key, value in item.items():
        if str(key).casefold() == wanted:
            return value
    return None


def _direct_png_stem(value) -> str:
    """Return a direct ``.png`` filename stem, or ``""`` for other values."""
    value = _text_value(value).replace("\\", "/")
    if not value or "/" in value or not value.casefold().endswith(".png"):
        return ""
    stem = value[:-4]
    return stem if stem else ""


def _iter_item_dicts(data) -> Iterator[dict]:
    """Yield every dict nested in a JSON value, including direct object nodes."""
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from _iter_item_dicts(value)
    elif isinstance(data, list):
        for value in data:
            yield from _iter_item_dicts(value)


def _iter_item_lists(data) -> list[list]:
    """Return every nested list for compatibility with the old helper API."""
    if isinstance(data, list):
        result = [data]
        for value in data:
            result.extend(_iter_item_lists(value))
        return result
    if isinstance(data, dict):
        result = []
        for value in data.values():
            result.extend(_iter_item_lists(value))
        return result
    return []


def _iter_json_paths(json_dir: Path) -> Iterator[Path]:
    """Yield known JSON files followed by any additional data JSON files.

    The explicit order keeps the existing duplicate-ID precedence stable while
    the discovery pass covers newly added tables such as EggModifiers.json.
    Generated metadata and localization are intentionally excluded because
    they are not current site icon inventories.  ``new.json`` is read only
    for its version key by :func:`read_game_version`; its historical change
    records must never add removed/old textures to the required set.
    """
    seen_names = set()
    for filename in ICON_JSON_FILES:
        path = json_dir / filename
        seen_names.add(filename.casefold())
        if path.is_file():
            yield path

    if not json_dir.is_dir():
        return
    for path in sorted(json_dir.glob("*.json"), key=lambda candidate: candidate.name.casefold()):
        name = path.name.casefold()
        if name in _IGNORED_JSON_NAMES or name in seen_names or not path.is_file():
            continue
        yield path


def _dds_output_name(dds_path: str) -> str:
    """Derive a stable output name for a shared texture asset."""
    normalized = _text_value(dds_path).replace("\\", "/")
    if not normalized:
        return "unknown"
    parsed = PurePosixPath(normalized)
    if parsed.parent == PurePosixPath("."):
        return parsed.stem.lower() or "unknown"
    icon_name = shared_texture_icon_name(normalized)
    if icon_name and icon_name.endswith(".png"):
        return icon_name[:-4]
    return icon_name or "unknown"


def collect_id_icon_pairs(json_dir: Path) -> list[tuple[str, str]]:
    """Collect unique ``(output_name, source_texture_path)`` pairs.

    ``output_name`` is the PNG stem used by the extractor.  A record's
    explicit ``Icon`` is authoritative; this is important for nested records
    such as ``PetEggTypes`` whose icon name is not their ``Id``.  Records with
    no actual ``Icon`` may use their canonical ``ItemId`` (for example,
    ``EggModifiers``), but never synthesize an icon from a metadata ``Id``.

    The two supplemental fields used by the site are collected explicitly.
    This intentionally excludes broad ``*IconPath`` discovery so optional
    art cannot make a strict extraction fail.  All JSON files in the data
    directory are considered, with the known tables retaining their prior
    precedence; generated ``new.json`` and manifests are excluded.
    """
    seen_output_names: set[str] = set()
    pairs: list[tuple[str, str]] = []

    def add_pair(output_name: str, source_path: str) -> None:
        safe_name = sanitize_filename(output_name)
        key = safe_name.casefold()
        if not source_path or key in seen_output_names:
            return
        seen_output_names.add(key)
        pairs.append((safe_name, source_path.replace("\\", "/")))

    for path in _iter_json_paths(Path(json_dir)):
        try:
            with path.open(encoding="utf-8") as stream:
                data = json.load(stream)
        except (json.JSONDecodeError, OSError) as error:
            raise ValueError(f"Cannot build a complete icon inventory from {path.name}: {error}") from error

        for item in _iter_item_dicts(data):
            icon_value = _text_value(_field_value(item, "Icon"))
            icon_stem = _direct_png_stem(icon_value)
            icon_path = _text_value(_field_value(item, "IconPath"))

            if icon_value:
                # An explicit but malformed/non-direct icon must not silently
                # become an Id-based filename.  The source IconPath is still
                # required because it is what gets converted.
                if icon_stem and icon_path:
                    add_pair(icon_stem, icon_path)
            else:
                item_id = _text_value(_field_value(item, "ItemId"))
                if item_id and icon_path:
                    add_pair(item_id, icon_path)

            for icon_field, path_field in _REQUIRED_ICON_FIELD_SPECS[1:]:
                supplemental_icon = _direct_png_stem(_field_value(item, icon_field))
                supplemental_path = _text_value(_field_value(item, path_field))
                if supplemental_icon and supplemental_path:
                    add_pair(supplemental_icon, supplemental_path)

    return pairs


def expected_png_filenames(json_dir: Path) -> list[str]:
    """Return the exact direct PNG names required by the current JSON data."""
    return sorted(
        {f"{sanitize_filename(output_name)}.png" for output_name, _ in collect_id_icon_pairs(Path(json_dir))},
        key=str.casefold,
    )


def build_icon_inventory(pairs: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    """Build the canonical filename/source rows used for provenance hashing."""
    rows = {
        (
            f"{sanitize_filename(output_name)}.png",
            _text_value(source_path).replace("\\", "/"),
        )
        for output_name, source_path in pairs
        if _text_value(output_name) and _text_value(source_path)
    }
    return [
        {"filename": filename, "source": source}
        for filename, source in sorted(rows, key=lambda row: (row[0].casefold(), row[1]))
    ]


def icon_inventory_sha256(
    json_dir: Path,
    pairs: Iterable[tuple[str, str]] | None = None,
) -> str:
    """Hash the canonical current filename/source-icon-path inventory.

    The canonical bytes are compact, sorted JSON with stable keys.  Source
    paths use forward slashes, while output names are the exact direct PNG
    names the extractor publishes.
    """
    if pairs is None:
        pairs = collect_id_icon_pairs(Path(json_dir))
    canonical = json.dumps(
        build_icon_inventory(pairs),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def read_game_version(
    json_dir: Path,
    extraction_manifest_path: Path | None = None,
) -> str | None:
    """Read the current game version from ``new.json`` or extraction metadata."""
    json_dir = Path(json_dir)
    candidates: list[Path] = [json_dir / "new.json"]
    if extraction_manifest_path is not None:
        candidates.append(Path(extraction_manifest_path))
    candidates.extend(
        [
            json_dir / "extraction-manifest.json",
            json_dir.parent / "extraction-manifest.json",
            json_dir.parent.parent / "extraction-manifest.json",
        ]
    )

    seen_paths: set[Path] = set()
    for path in candidates:
        try:
            path = path.resolve()
        except OSError:
            continue
        if path in seen_paths or not path.is_file():
            continue
        seen_paths.add(path)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(value, dict):
            continue
        version = _text_value(value.get("VersionKey"))
        if not version:
            version = _text_value(value.get("gameVersion"))
        if version:
            return version
    return None


def is_valid_png(path: Path) -> bool:
    """Validate PNG structure, chunk CRCs, and the compressed image stream."""
    try:
        with Path(path).open("rb") as stream:
            if stream.read(len(_PNG_SIGNATURE)) != _PNG_SIGNATURE:
                return False

            saw_ihdr = False
            saw_idat = False
            saw_iend = False
            idat_data = bytearray()

            while True:
                header = stream.read(8)
                if len(header) != 8:
                    return False
                length, chunk_type = struct.unpack(">I4s", header)
                if length > _MAX_PNG_CHUNK_LENGTH:
                    return False
                if not all(65 <= byte <= 90 or 97 <= byte <= 122 for byte in chunk_type):
                    return False

                chunk_data = stream.read(length)
                crc_bytes = stream.read(4)
                if len(chunk_data) != length or len(crc_bytes) != 4:
                    return False
                expected_crc = struct.unpack(">I", crc_bytes)[0]
                actual_crc = binascii.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
                if actual_crc != expected_crc:
                    return False

                if not saw_ihdr and chunk_type != b"IHDR":
                    return False
                if chunk_type == b"IHDR":
                    if saw_ihdr or length != 13:
                        return False
                    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                        ">IIBBBBB", chunk_data
                    )
                    valid_bit_depths = {
                        0: {1, 2, 4, 8, 16},
                        2: {8, 16},
                        3: {1, 2, 4, 8},
                        4: {8, 16},
                        6: {8, 16},
                    }
                    if (
                        width == 0
                        or height == 0
                        or color_type not in valid_bit_depths
                        or bit_depth not in valid_bit_depths[color_type]
                        or compression != 0
                        or filtering != 0
                        or interlace not in (0, 1)
                    ):
                        return False
                    saw_ihdr = True
                elif chunk_type == b"IDAT":
                    saw_idat = True
                    idat_data.extend(chunk_data)
                elif chunk_type == b"IEND":
                    if saw_iend or length != 0:
                        return False
                    saw_iend = True
                    break

            if not saw_ihdr or not saw_idat or not saw_iend:
                return False
            if stream.read(1):
                return False
            zlib.decompress(bytes(idat_data))
            return True
    except (OSError, struct.error, ValueError, zlib.error):
        return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_filename(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    if not value or Path(value).name != value or Path(value).suffix.casefold() != ".png":
        return None
    if value in {".", ".."} or any(part in {"", ".", ".."} for part in PurePosixPath(value).parts):
        return None
    return value


def _valid_digest(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def build_image_manifest(
    image_dir: Path,
    filenames: Iterable[str | Path] | None = None,
    *,
    game_version: str | None = None,
    inventory_sha256: str | None = None,
    source_dds_hashes: dict[str, str] | None = None,
) -> dict:
    """Build a deterministic manifest for validated PNG files.

    With no game metadata this is deliberately a ``fileIntegrityOnly``
    manifest.  It proves only the bytes currently in ``image_dir``; it does
    not claim that those bytes came from the current game's JSON/DDS inputs.
    Extraction supplies both ``game_version`` and ``inventory_sha256`` to
    create a source-bound ``gameInventory`` manifest.  When ``filenames`` is
    omitted, all direct ``*.png`` files are covered.
    """
    if (game_version is None) != (inventory_sha256 is None):
        raise ValueError("game_version and inventory_sha256 must be supplied together")
    if inventory_sha256 is not None and not _valid_digest(inventory_sha256):
        raise ValueError("inventory_sha256 must be a lowercase SHA-256 digest")
    if game_version is not None and not _text_value(game_version):
        raise ValueError("game_version must not be empty")

    image_dir = Path(image_dir)
    if filenames is None:
        paths = sorted(image_dir.glob("*.png"), key=lambda candidate: candidate.name.casefold())
    else:
        paths = []
        for filename in filenames:
            name = str(filename)
            safe_name = _manifest_filename(name)
            if safe_name is None:
                raise ValueError(f"Manifest filename must be a direct PNG name: {name!r}")
            paths.append(image_dir / safe_name)
        paths.sort(key=lambda candidate: candidate.name.casefold())

    files: dict[str, dict[str, int | str]] = {}
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        if not is_valid_png(path):
            raise ValueError(f"Cannot manifest invalid PNG: {path}")
        files[path.name] = {
            "sha256": _sha256_file(path),
            "size": path.stat().st_size,
        }

    manifest = {
        "schema_version": _IMAGE_MANIFEST_VERSION,
        "algorithm": _IMAGE_MANIFEST_ALGORITHM,
        "provenance": (
            _IMAGE_PROVENANCE_GAME_INVENTORY
            if game_version is not None
            else _IMAGE_PROVENANCE_FILE_ONLY
        ),
        "files": files,
    }
    if game_version is not None:
        manifest["gameVersion"] = _text_value(game_version)
        manifest["inventorySha256"] = inventory_sha256
        if source_dds_hashes is not None:
            normalized_hashes: dict[str, str] = {}
            for source_path, digest in source_dds_hashes.items():
                normalized_path = _text_value(source_path).replace("\\", "/")
                if not normalized_path or not _valid_digest(digest):
                    raise ValueError("source_dds_hashes must contain normalized paths and SHA-256 digests")
                normalized_hashes[normalized_path] = digest
            manifest["sourceDdsSha256"] = {
                name: normalized_hashes[name] for name in sorted(normalized_hashes)
            }
    return manifest


def write_image_manifest(
    image_dir: Path,
    filenames: Iterable[str | Path] | None = None,
    *,
    game_version: str | None = None,
    inventory_sha256: str | None = None,
    source_dds_hashes: dict[str, str] | None = None,
) -> Path:
    """Write an image manifest atomically and return its path.

    Omitting provenance arguments intentionally writes a
    ``fileIntegrityOnly`` manifest, even when the PNGs happen to be from a
    game extraction.
    """
    image_dir = Path(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = image_dir / _IMAGE_MANIFEST_FILENAME
    content = json.dumps(
        build_image_manifest(
            image_dir,
            filenames,
            game_version=game_version,
            inventory_sha256=inventory_sha256,
            source_dds_hashes=source_dds_hashes,
        ),
        indent=2,
        sort_keys=True,
    ) + "\n"
    temporary_path: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(
            prefix=".image-manifest-",
            suffix=".json",
            dir=str(image_dir),
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, manifest_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
    return manifest_path


def validate_image_outputs(
    image_dir: Path,
    expected_filenames: Iterable[str | Path] | None = None,
    *,
    require_manifest: bool = False,
    expected_json_dir: Path | None = None,
    expected_game_version: str | None = None,
    expected_inventory_sha256: str | None = None,
) -> dict:
    """Validate existing PNG output and, when supplied, current provenance.

    The result distinguishes structurally valid legacy PNGs from PNGs covered
    by a matching SHA-256 manifest.  Passing ``expected_json_dir`` derives the
    exact current icon inventory and game version, then rejects a previous
    release's otherwise-valid manifest.  A missing manifest therefore never
    turns into a newly generated manifest or a ``provenance=True`` result.
    Site sync can request ``require_manifest=True`` when only current,
    attributable output is publishable, while a legacy import/check can
    inspect files with the default.
    """
    image_dir = Path(image_dir)
    expected_provenance = any(
        value is not None
        for value in (expected_json_dir, expected_game_version, expected_inventory_sha256)
    )
    if expected_json_dir is not None:
        expected_json_dir = Path(expected_json_dir)
        expected_filenames = expected_png_filenames(expected_json_dir)
        if expected_game_version is None:
            expected_game_version = read_game_version(expected_json_dir)
        if expected_inventory_sha256 is None:
            expected_inventory_sha256 = icon_inventory_sha256(expected_json_dir)

    png_paths = (
        sorted(image_dir.glob("*.png"), key=lambda candidate: candidate.name.casefold())
        if image_dir.is_dir()
        else []
    )
    png_names = {path.name for path in png_paths}
    invalid_pngs = [path.name for path in png_paths if not is_valid_png(path)]

    expected_names: set[str] = set()
    invalid_expected_names: list[str] = []
    if expected_filenames is not None:
        for filename in expected_filenames:
            safe_name = _manifest_filename(str(filename))
            if safe_name is None:
                invalid_expected_names.append(str(filename))
            else:
                expected_names.add(safe_name)

    manifest_path = image_dir / _IMAGE_MANIFEST_FILENAME
    manifest_present = manifest_path.is_file()
    manifest_valid = False
    manifest_names: set[str] = set()
    manifest_hashes: dict[str, str] = {}
    manifest_sizes: dict[str, int] = {}
    manifest: dict = {}
    if manifest_present:
        try:
            parsed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = parsed_manifest if isinstance(parsed_manifest, dict) else {}
            files = manifest.get("files") if isinstance(manifest, dict) else None
            if (
                isinstance(manifest, dict)
                and manifest.get("schema_version") == _IMAGE_MANIFEST_VERSION
                and manifest.get("algorithm") == _IMAGE_MANIFEST_ALGORITHM
                and isinstance(files, dict)
            ):
                parsed_hashes = {}
                parsed_sizes = {}
                for filename, digest in files.items():
                    safe_name = _manifest_filename(filename)
                    if safe_name is None or not isinstance(digest, dict):
                        break
                    file_hash = digest.get("sha256")
                    file_size = digest.get("size")
                    if (
                        not _valid_digest(file_hash)
                        or isinstance(file_size, bool)
                        or not isinstance(file_size, int)
                        or file_size < 0
                    ):
                        break
                    parsed_hashes[safe_name] = file_hash
                    parsed_sizes[safe_name] = file_size
                else:
                    manifest_hashes = parsed_hashes
                    manifest_sizes = parsed_sizes
                    manifest_names = set(parsed_hashes)
                    manifest_valid = True
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    names_to_check = expected_names or manifest_names
    missing_files = sorted(name for name in names_to_check if name not in png_names)
    missing_manifest = sorted(name for name in expected_names if name not in manifest_names)
    hash_mismatches = []
    size_mismatches = []
    if manifest_valid:
        for name, expected_hash in manifest_hashes.items():
            path = image_dir / name
            if not path.is_file() or not is_valid_png(path):
                continue
            try:
                actual_hash = _sha256_file(path)
            except OSError:
                continue
            if actual_hash != expected_hash:
                hash_mismatches.append(name)
            try:
                if path.stat().st_size != manifest_sizes[name]:
                    size_mismatches.append(name)
            except OSError:
                continue

    manifest_provenance = (
        manifest.get("provenance") if isinstance(manifest, dict) else None
    )
    manifest_game_version = _text_value(manifest.get("gameVersion")) if isinstance(manifest, dict) else ""
    manifest_inventory_sha256 = (
        _text_value(manifest.get("inventorySha256")) if isinstance(manifest, dict) else ""
    )
    metadata_valid = bool(
        manifest_provenance == _IMAGE_PROVENANCE_GAME_INVENTORY
        and manifest_game_version
        and _valid_digest(manifest_inventory_sha256)
    )
    version_mismatch = bool(
        expected_game_version is not None
        and manifest_game_version != _text_value(expected_game_version)
    )
    inventory_mismatch = bool(
        expected_inventory_sha256 is not None
        and manifest_inventory_sha256 != _text_value(expected_inventory_sha256)
    )

    file_integrity = bool(
        image_dir.is_dir()
        and not invalid_expected_names
        and not invalid_pngs
        and not missing_files
        and not hash_mismatches
        and not size_mismatches
        and (not manifest_present or manifest_valid)
    )
    provenance = bool(
        manifest_present
        and manifest_valid
        and metadata_valid
        and file_integrity
        and not missing_manifest
        and not version_mismatch
        and not inventory_mismatch
    )
    valid = bool(
        file_integrity
        and (not require_manifest or provenance)
        and (not expected_provenance or provenance)
    )
    return {
        "valid": valid,
        "file_integrity": file_integrity,
        "provenance": provenance,
        "provenance_kind": (
            manifest_provenance
            if manifest_present and manifest_valid
            else ("legacy" if not manifest_present else None)
        ),
        "legacy": bool(png_names) and not manifest_present,
        "manifest_present": manifest_present,
        "manifest_valid": manifest_valid,
        "metadata_valid": metadata_valid,
        "game_version": manifest_game_version or None,
        "inventory_sha256": manifest_inventory_sha256 or None,
        "expected_game_version": expected_game_version,
        "expected_inventory_sha256": expected_inventory_sha256,
        "version_mismatch": version_mismatch,
        "inventory_mismatch": inventory_mismatch,
        "png_files": sorted(png_names, key=str.casefold),
        "manifest_files": sorted(manifest_names, key=str.casefold),
        "invalid_pngs": sorted(invalid_pngs, key=str.casefold),
        "missing_files": missing_files,
        "missing_manifest": missing_manifest,
        "hash_mismatches": sorted(hash_mismatches, key=str.casefold),
        "size_mismatches": sorted(size_mismatches, key=str.casefold),
        "invalid_expected": sorted(invalid_expected_names, key=str.casefold),
    }


def validate_image_manifest(
    image_dir: Path,
    expected_filenames: Iterable[str | Path] | None = None,
    *,
    require_manifest: bool = False,
    expected_json_dir: Path | None = None,
    expected_game_version: str | None = None,
    expected_inventory_sha256: str | None = None,
) -> dict:
    """Compatibility alias for callers focused on manifest validation."""
    return validate_image_outputs(
        image_dir,
        expected_filenames,
        require_manifest=require_manifest,
        expected_json_dir=expected_json_dir,
        expected_game_version=expected_game_version,
        expected_inventory_sha256=expected_inventory_sha256,
    )


def _manifest_png_names(image_dir: Path) -> set[str]:
    """Read names managed by a prior valid manifest; invalid manifests are inert."""
    manifest_path = Path(image_dir) / _IMAGE_MANIFEST_FILENAME
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return set()
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != _IMAGE_MANIFEST_VERSION
        or data.get("algorithm") != _IMAGE_MANIFEST_ALGORITHM
    ):
        return set()
    files = data.get("files")
    if not isinstance(files, dict):
        return set()
    return {
        safe_name
        for name, digest in files.items()
        if (safe_name := _manifest_filename(name)) is not None
        and isinstance(digest, dict)
        and _valid_digest(digest.get("sha256"))
        and isinstance(digest.get("size"), int)
        and not isinstance(digest.get("size"), bool)
        and digest.get("size") >= 0
    }


def _publish_staged_files(
    stage_dir: Path,
    output_dir: Path,
    install_names: Iterable[str],
    remove_names: Iterable[str] = (),
) -> None:
    """Publish direct files with rollback, preserving unrelated output files."""
    output_dir = Path(output_dir)
    output_parent = output_dir.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    output_existed = output_dir.exists() or output_dir.is_symlink()
    if output_existed and not output_dir.is_dir():
        raise NotADirectoryError(output_dir)

    install_names = sorted(set(install_names))
    remove_names = sorted(set(remove_names) - set(install_names))
    all_target_names = sorted(set(install_names) | set(remove_names))
    for name in all_target_names:
        if (
            name != _IMAGE_MANIFEST_FILENAME
            and (Path(name).name != name or Path(name).suffix.casefold() not in {".png", ".dds"})
        ):
            raise ValueError(f"Unsafe staged output name: {name!r}")
    for name in install_names:
        staged_path = Path(stage_dir) / name
        if not staged_path.is_file():
            raise FileNotFoundError(staged_path)

    backup_dir = Path(tempfile.mkdtemp(prefix=".image-backup-", dir=str(output_parent)))
    moved: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    created_output = False
    try:
        if not output_existed:
            output_dir.mkdir()
            created_output = True

        for name in all_target_names:
            target = output_dir / name
            if not target.exists() and not target.is_symlink():
                continue
            if target.is_dir() and not target.is_symlink():
                raise IsADirectoryError(target)
            backup_path = backup_dir / name
            os.replace(target, backup_path)
            moved.append((target, backup_path))

        for name in install_names:
            target = output_dir / name
            os.replace(Path(stage_dir) / name, target)
            installed.append(target)
    except Exception:
        for target in reversed(installed):
            try:
                target.unlink()
            except FileNotFoundError:
                pass
        for target, backup_path in reversed(moved):
            if backup_path.exists() or backup_path.is_symlink():
                os.replace(backup_path, target)
        if created_output:
            try:
                output_dir.rmdir()
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(backup_dir, ignore_errors=True)


def _source_path(extracted_root: Path, icon_path: str) -> Path | None:
    """Resolve a relative texture path without allowing traversal outside root."""
    normalized = _text_value(icon_path).replace("\\", "/")
    if not normalized:
        return None
    parsed = PurePosixPath(normalized)
    if parsed.is_absolute() or re.match(r"^[A-Za-z]:($|/)", normalized):
        return None
    parts = tuple(part for part in parsed.parts if part not in {"", "."})
    if not parts or ".." in parts:
        return None

    root = Path(extracted_root)
    try:
        root_resolved = root.resolve()
    except OSError:
        return None

    candidate = root.joinpath(*parts)
    try:
        if candidate.is_file() and candidate.resolve().is_relative_to(root_resolved):
            return candidate
    except OSError:
        return None

    # Reused EXTRACTED trees can retain case from a different unpacker.  Find
    # a unique case-insensitive component without leaving the extracted root.
    current = root
    try:
        for part in parts:
            exact = current / part
            if exact.exists():
                current = exact
                continue
            matches = [child for child in current.iterdir() if child.name.casefold() == part.casefold()]
            if len(matches) != 1:
                return None
            current = matches[0]
        if current.is_file() and current.resolve().is_relative_to(root_resolved):
            return current
    except OSError:
        return None
    return None


def dds_to_png(source: Path, dest: Path) -> bool:
    """Convert one source image to a valid PNG without touching an old dest on failure."""
    source = Path(source)
    dest = Path(dest)
    if not source.is_file():
        return False
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{dest.stem}-",
            suffix=".png",
            dir=str(dest.parent),
        )
        temporary_path = Path(temporary_name)
        os.close(fd)
    except OSError:
        return False

    try:
        subprocess.run(
            ["magick", str(source), f"PNG32:{temporary_path}"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        if not is_valid_png(temporary_path):
            return False
        os.replace(temporary_path, dest)
        temporary_path = None
        return is_valid_png(dest)
    except (OSError, subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _has_magick() -> bool:
    try:
        subprocess.run(["magick", "-version"], capture_output=True, check=True, timeout=5)
        return True
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _extract_dds_fallback(
    pairs: list[tuple[str, str]],
    extracted_root: Path,
    output_dir: Path,
) -> tuple[int, int, bool]:
    """Explicit legacy fallback: stage DDS copies, without a PNG manifest."""
    total = len(pairs)
    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        stage_dir = Path(tempfile.mkdtemp(prefix=".image-stage-dds-", dir=str(output_dir.parent)))
    except OSError as error:
        print(f"[ERROR] Could not create image staging directory: {error}")
        return 0, total, False

    success = 0
    names: list[str] = []
    try:
        for id_value, icon_path in pairs:
            source = _source_path(extracted_root, icon_path)
            if source is None:
                continue
            name = f"{sanitize_filename(id_value)}.dds"
            try:
                shutil.copy2(source, stage_dir / name)
            except OSError:
                continue
            names.append(name)
            success += 1
        skipped = total - success
        if skipped:
            print(f"[WARN] DDS fallback incomplete ({success}/{total}); output was not published")
            return success, skipped, False
        _publish_staged_files(stage_dir, output_dir, names)
        print(f"[OK] Published {success} DDS fallback files (no PNG manifest)")
        return success, skipped, False
    except OSError as error:
        print(f"[ERROR] DDS fallback publication failed; existing output preserved: {error}")
        return 0, total, False
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


def extract_icons(
    json_dir: Path,
    extracted_root: Path,
    output_dir: Path,
    copy_dds_if_no_magick: bool = False,
    keep_dds: bool = False,
) -> tuple[int, int, bool]:
    """Extract icons and return ``(success, skipped, used_magick)``.

    PNG conversion is strict by default.  If any source is missing, conversion
    fails, or the generated PNG is invalid, no staged file or manifest is
    published.  ``copy_dds_if_no_magick=True`` is an explicit legacy fallback;
    it publishes DDS files only and returns ``used_magick=False`` so callers
    can keep them out of a PNG/site sync.
    """
    del keep_dds  # Retained for API compatibility; successful PNG runs never delete DDS assets.
    json_dir = Path(json_dir)
    extracted_root = Path(extracted_root)
    output_dir = Path(output_dir)
    pairs = collect_id_icon_pairs(json_dir)
    if not pairs:
        print("[WARN] No id+icon pairs found in JSON files.")
        return 0, 0, False

    total = len(pairs)
    print(f"[INFO] Found {total} items with icons")
    has_magick = _has_magick()
    if not has_magick:
        if copy_dds_if_no_magick:
            print("[INFO] ImageMagick not found. DDS fallback is explicitly enabled and is not PNG publication.")
            return _extract_dds_fallback(pairs, extracted_root, output_dir)
        print("[WARN] ImageMagick not found. Strict PNG output was not published.")
        return 0, total, False

    game_version = read_game_version(json_dir)
    if not game_version:
        print(
            "[WARN] Current game version is missing from new.json/extraction-manifest.json. "
            "Strict PNG output was not published."
        )
        return 0, total, True
    inventory_sha256 = icon_inventory_sha256(json_dir, pairs)

    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        stage_dir = Path(tempfile.mkdtemp(prefix=".image-stage-", dir=str(output_dir.parent)))
    except OSError as error:
        print(f"[ERROR] Could not create image staging directory: {error}")
        return 0, total, True

    success = 0
    skipped = 0
    staged_names: list[str] = []
    source_dds_hashes: dict[str, str] = {}
    seen_names: set[str] = set()
    progress_interval = max(1, min(100, total // 20))
    try:
        for index, (id_value, icon_path) in enumerate(pairs, start=1):
            if index % progress_interval == 0 or index == total:
                print(f"[INFO] Converting {index}/{total} ...", flush=True)

            safe_name = sanitize_filename(id_value)
            output_name = f"{safe_name}.png"
            if output_name.casefold() in seen_names:
                skipped += 1
                continue
            seen_names.add(output_name.casefold())

            source = _source_path(extracted_root, icon_path)
            if source is None:
                skipped += 1
                continue

            staged_path = stage_dir / output_name
            if dds_to_png(source, staged_path) and is_valid_png(staged_path):
                normalized_source = _text_value(icon_path).replace("\\", "/")
                try:
                    source_dds_hashes[normalized_source] = _sha256_file(source)
                except OSError:
                    skipped += 1
                    try:
                        staged_path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                staged_names.append(output_name)
                success += 1
            else:
                skipped += 1

        if skipped or success != total:
            print(
                f"[WARN] PNG extraction incomplete ({success}/{total}); "
                "existing output was not changed"
            )
            return success, skipped, True

        try:
            write_image_manifest(
                stage_dir,
                staged_names,
                game_version=game_version,
                inventory_sha256=inventory_sha256,
                source_dds_hashes=source_dds_hashes,
            )
            old_names = _manifest_png_names(output_dir)
            _publish_staged_files(
                stage_dir,
                output_dir,
                [*staged_names, _IMAGE_MANIFEST_FILENAME],
                remove_names=old_names - set(staged_names),
            )
        except (OSError, ValueError) as error:
            print(f"[ERROR] PNG publication failed; existing output preserved: {error}")
            return 0, total, True

        print(f"[OK] Published {success} validated PNG files and {_IMAGE_MANIFEST_FILENAME}")
        return success, skipped, True
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
