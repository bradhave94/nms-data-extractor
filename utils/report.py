#!/usr/bin/env python3
"""Builds per-run refresh reports and snapshots for extraction runs."""
from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from utils.building_variants import load_space_base_variants
from utils.reward_variants import reward_identity

IGNORED_REPORT_FILES = {
    "controllerLookup.generated.json",
    "extraction-manifest.json",
    "localization.json",
    "new.json",
}
NEW_JSON_FILENAME = "new.json"
SNAPSHOT_MANIFEST_FILENAME = "manifest.json"
RELEASE_MANIFEST_FILENAME = "manifest.json"
REPORT_SCHEMA_VERSION = 2


class SnapshotIntegrityError(ValueError):
    """Raised when an archived snapshot is absent, malformed, or tampered with."""


def _sanitize_version(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._-") or "unknown-version"


def release_identity(value: str) -> str:
    """Return a stable archive key for a release and compiler suffixes.

    ``7.00`` and ``7.00.0.1`` identify the same game release.  Non-numeric
    explicit values are retained as sanitized keys for backwards-compatible
    diagnostics; the extractor's publication validation remains responsible
    for requiring numeric game versions.
    """
    cleaned = _sanitize_version(value)
    match = re.match(r"^(\d+)\.(\d+)(?:\.|$)", cleaned)
    if not match:
        return cleaned
    return f"{int(match.group(1))}.{int(match.group(2)):02d}"


def explicit_version_key(value: str | None = None) -> str | None:
    """Return a sanitized release supplied by the caller or environment.

    The environment lookup is intentionally separate from compiler provenance.
    Publication/report paths use this helper so a compiler package version can
    never silently become the game release version.
    """
    explicit = (value or os.environ.get("NMS_GAME_VERSION") or os.environ.get("NMS_VERSION") or "").strip()
    if explicit:
        return _sanitize_version(explicit)
    return None


def compiler_version_key(repo_root: Path) -> str | None:
    """Read compiler provenance from an MXML header, if one is available.

    This is diagnostic metadata only.  It is not a release-version fallback for
    report publication.
    """
    candidate = repo_root / "data" / "mbin" / "nms_reality_gcproducttable.MXML"
    if candidate.exists():
        try:
            with open(candidate, encoding="utf-8-sig") as f:
                for _ in range(6):
                    line = f.readline()
                    if not line:
                        break
                    match = re.search(r"MBINCompiler version \(([^)]+)\)", line)
                    if match:
                        return _sanitize_version(match.group(1))
        except OSError:
            pass
    return None


def require_explicit_version(version_key: str | None = None) -> str:
    """Resolve the release version for a publication operation.

    ``detect_version_key`` remains available for non-publication diagnostics,
    but report archives must be keyed by an explicit game release.
    """
    resolved = explicit_version_key(version_key)
    if resolved is None or resolved == "unknown-version":
        raise ValueError(
            "Release version must be supplied explicitly for report publication "
            "(version_key or NMS_GAME_VERSION/NMS_VERSION)"
        )
    return resolved


def detect_version_key(repo_root: Path) -> str:
    """Return an explicit release or compiler provenance for diagnostics.

    Callers that publish a report must use :func:`require_explicit_version`.
    Keeping this fallback preserves the historical helper for check-only and
    other diagnostic callers.
    """
    explicit = explicit_version_key()
    if explicit:
        return explicit

    return compiler_version_key(repo_root) or "unknown-version"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _load_json_strict(path: Path) -> Any:
    """Load JSON and retain enough context to fail closed on archive damage."""
    if not path.is_file():
        raise SnapshotIntegrityError(f"Snapshot file is missing: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotIntegrityError(f"Snapshot JSON is corrupt: {path}") from exc


def _is_id_list(data: Any) -> bool:
    if not isinstance(data, list):
        return False
    return all(isinstance(item, dict) and "Id" in item for item in data)


def _index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or item.get("Id") is None:
            continue
        iid = str(item["Id"])
        previous = indexed.get(iid)
        if previous is not None:
            raise ValueError(f"Duplicate Id in one JSON collection: {iid}")
        indexed[iid] = item
    return indexed


def _nested_record_key(source_name: str | None, section: str, iid: str) -> str:
    """Namespace nested rows so a nested row cannot overwrite a flat/global Id."""
    source = source_name or "<sectioned>"
    return f"@nested:{source}:{section}:{iid}"


def _record_id(record_key: str, item: dict[str, Any]) -> str:
    """Return the game Id stored in a namespaced or flat record key."""
    return str(item.get("Id", record_key))


def _record_section(record_key: str) -> str | None:
    if not record_key.startswith("@nested:"):
        return None
    parts = record_key.split(":", 3)
    return parts[2] if len(parts) == 4 else None


def _record_label(record_key: str, item: dict[str, Any], duplicate_ids: set[str]) -> str:
    """Use plain IDs for ordinary records and namespaced labels for collisions."""
    iid = _record_id(record_key, item)
    if iid in duplicate_ids:
        return record_key
    return iid


def _iter_records(data: Any, *, source_name: str | None = None) -> Iterable[tuple[str, dict[str, Any]]]:
    """Yield deterministic record identities from flat and sectioned JSON.

    Section names are part of nested identity.  This preserves intentional
    duplicate game IDs such as Creatures Species/EggOverrides and PetShop vs
    flat output without allowing one row to replace another.
    """
    if data is None:
        return
    if isinstance(data, list):
        for iid, item in _index_by_id(data).items():
            yield iid, item
        return
    if not isinstance(data, dict):
        return
    for section in sorted(data):
        value = data[section]
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict) or item.get("Id") is None:
                continue
            iid = str(item["Id"])
            yield _nested_record_key(source_name, str(section), iid), item


def _is_legacy_snapshot_path(snapshot_dir: Path) -> bool:
    resolved = Path(snapshot_dir).resolve()
    return resolved.name in {"_latest_snapshot", "_baseline_snapshot"}


def _legacy_normalize_data(data: Any) -> Any:
    """Apply the old last-row-wins rule only to a trusted legacy snapshot.

    Nested sections remain separate identities; this normalization addresses
    the pre-manifest flat-list duplicates produced by the old extractor.
    """
    if isinstance(data, list):
        last_positions: dict[str, int] = {}
        for position, item in enumerate(data):
            if isinstance(item, dict) and item.get("Id") is not None:
                last_positions[str(item["Id"])] = position
        return [
            item
            for position, item in enumerate(data)
            if not isinstance(item, dict)
            or item.get("Id") is None
            or last_positions[str(item["Id"])] == position
        ]
    if isinstance(data, dict):
        normalized = dict(data)
        for section, value in data.items():
            if isinstance(value, list):
                normalized[section] = _legacy_normalize_data(value)
        return normalized
    return data


def _index_items_by_id(data: Any, *, source_name: str | None = None) -> dict[str, dict[str, Any]]:
    """Index item dicts that expose Id from a flat list or sectioned object (e.g. Creatures.json)."""
    indexed: dict[str, dict[str, Any]] = {}
    for record_key, item in _iter_records(data, source_name=source_name):
        previous = indexed.get(record_key)
        if previous is not None:
            raise ValueError(f"Duplicate distinct record identity: {record_key}")
        indexed[record_key] = item
    return indexed


def _compare_file(old_data: Any, new_data: Any, *, source_name: str | None = None) -> dict[str, Any]:
    if old_data is None and new_data is None:
        return {
            "old_count": 0,
            "new_count": 0,
            "added_ids": [],
            "removed_ids": [],
            "changed_ids": [],
            "has_changes": False,
            "mode": "missing",
        }

    old_by_id = _index_items_by_id(old_data, source_name=source_name)
    new_by_id = _index_items_by_id(new_data, source_name=source_name)
    if old_by_id or new_by_id:
        old_ids = set(old_by_id)
        new_ids = set(new_by_id)
        all_records = {**old_by_id, **new_by_id}
        duplicate_ids = {
            iid
            for iid in {_record_id(key, item) for key, item in all_records.items()}
            if sum(_record_id(key, item) == iid for key, item in all_records.items()) > 1
        }
        added_ids = sorted(
            _record_label(key, new_by_id[key], duplicate_ids)
            for key in new_ids - old_ids
        )
        removed_ids = sorted(
            _record_label(key, old_by_id[key], duplicate_ids)
            for key in old_ids - new_ids
        )
        changed_ids = sorted(
            _record_label(key, new_by_id[key], duplicate_ids)
            for key in (old_ids & new_ids)
            if json.dumps(old_by_id[key], sort_keys=True, ensure_ascii=False)
            != json.dumps(new_by_id[key], sort_keys=True, ensure_ascii=False)
        )
        return {
            "old_count": len(old_by_id),
            "new_count": len(new_by_id),
            "added_ids": added_ids,
            "removed_ids": removed_ids,
            "changed_ids": changed_ids,
            "has_changes": bool(added_ids or removed_ids or changed_ids),
            "mode": "id-list",
        }

    old_count = len(old_data) if isinstance(old_data, list) else (len(old_data) if isinstance(old_data, dict) else (0 if old_data is None else 1))
    new_count = len(new_data) if isinstance(new_data, list) else (len(new_data) if isinstance(new_data, dict) else (0 if new_data is None else 1))
    return {
        "old_count": old_count,
        "new_count": new_count,
        "added_ids": [],
        "removed_ids": [],
        "changed_ids": [],
        "has_changes": old_data != new_data,
        "mode": "generic",
    }


def _snapshot_json_files(json_dir: Path) -> list[Path]:
    if not json_dir.is_dir():
        raise SnapshotIntegrityError(f"Snapshot directory is missing: {json_dir}")
    return [
        path
        for path in sorted(json_dir.glob("*.json"))
        if path.name not in IGNORED_REPORT_FILES
        and path.name != SNAPSHOT_MANIFEST_FILENAME
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SnapshotIntegrityError(f"Cannot read snapshot file: {path}") from exc
    return digest.hexdigest()


def _snapshot_digest(files: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for filename in sorted(files):
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(files[filename]["sha256"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(files[filename]["size"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _manifest_for_snapshot(
    snapshot_dir: Path,
    *,
    version_key: str | None = None,
    role: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for path in _snapshot_json_files(snapshot_dir):
        # Validate every archived JSON before recording its digest.  A report
        # must never publish a manifest for a file that cannot be read.
        _load_json_strict(path)
        files[path.name] = {"sha256": _sha256(path), "size": path.stat().st_size}
    payload: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "files": files,
        "snapshot_digest": _snapshot_digest(files),
    }
    if version_key is not None:
        payload["version_key"] = version_key
    if role is not None:
        payload["role"] = role
    if created_at is not None:
        payload["created_at"] = created_at
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _validate_snapshot_manifest(
    snapshot_dir: Path,
    *,
    expected_version: str | None = None,
    expected_role: str | None = None,
    require_manifest: bool = False,
) -> dict[str, Any]:
    """Validate a snapshot and return its manifest (or a legacy digest).

    Legacy ``reports/_latest_snapshot`` directories predate manifests.  They
    are accepted only as migration inputs; every new versioned archive gets a
    manifest and publication validates it strictly.
    """
    if not snapshot_dir.is_dir():
        raise SnapshotIntegrityError(f"Previous-release snapshot is missing: {snapshot_dir}")
    manifest_path = snapshot_dir / SNAPSHOT_MANIFEST_FILENAME
    if not manifest_path.is_file():
        if require_manifest:
            raise SnapshotIntegrityError(f"Snapshot manifest is missing: {manifest_path}")
        return _manifest_for_snapshot(snapshot_dir)

    manifest = _load_json_strict(manifest_path)
    if not isinstance(manifest, dict):
        raise SnapshotIntegrityError(f"Snapshot manifest is invalid: {manifest_path}")
    if manifest.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise SnapshotIntegrityError(f"Unsupported snapshot manifest: {manifest_path}")
    if expected_version is not None and manifest.get("version_key") != expected_version:
        raise SnapshotIntegrityError(
            f"Snapshot version mismatch for {snapshot_dir}: "
            f"expected {expected_version}, got {manifest.get('version_key')}"
        )
    if expected_role is not None and manifest.get("role") != expected_role:
        raise SnapshotIntegrityError(
            f"Snapshot role mismatch for {snapshot_dir}: "
            f"expected {expected_role}, got {manifest.get('role')}"
        )
    declared = manifest.get("files")
    if not isinstance(declared, dict):
        raise SnapshotIntegrityError(f"Snapshot manifest files are invalid: {manifest_path}")
    actual_paths = {path.name for path in _snapshot_json_files(snapshot_dir)}
    declared_paths = set(declared)
    if actual_paths != declared_paths:
        missing = sorted(declared_paths - actual_paths)
        extra = sorted(actual_paths - declared_paths)
        raise SnapshotIntegrityError(
            f"Snapshot file set changed for {snapshot_dir}: missing={missing}, extra={extra}"
        )
    for filename in sorted(declared):
        if Path(filename).name != filename or Path(filename).suffix.lower() != ".json":
            raise SnapshotIntegrityError(f"Invalid snapshot manifest filename: {filename}")
        entry = declared[filename]
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            raise SnapshotIntegrityError(f"Invalid digest entry for {filename}: {manifest_path}")
        path = snapshot_dir / filename
        actual_size = path.stat().st_size
        actual_digest = _sha256(path)
        if entry.get("size") != actual_size or entry.get("sha256") != actual_digest:
            raise SnapshotIntegrityError(f"Snapshot digest mismatch: {path}")
        _load_json_strict(path)
    if manifest.get("snapshot_digest") != _snapshot_digest(declared):
        raise SnapshotIntegrityError(f"Snapshot aggregate digest mismatch: {manifest_path}")
    building = manifest.get("building_mxml")
    if building is not None:
        if not isinstance(building, dict) or not isinstance(building.get("path"), str):
            raise SnapshotIntegrityError(f"Invalid archived building MXML entry: {manifest_path}")
        building_path = (snapshot_dir / building["path"]).resolve()
        if not building_path.is_relative_to(snapshot_dir.resolve()) or not building_path.is_file():
            raise SnapshotIntegrityError(f"Archived building MXML is missing: {building_path}")
        if building.get("sha256") != _sha256(building_path) or building.get("size") != building_path.stat().st_size:
            raise SnapshotIntegrityError(f"Archived building MXML digest mismatch: {building_path}")
    return manifest


def _legacy_normalize_data_with_audit(
    data: Any,
    *,
    filename: str,
) -> tuple[Any, list[dict[str, Any]]]:
    audit: list[dict[str, Any]] = []

    def normalize_list(value: list[Any], section: str | None = None) -> list[Any]:
        positions: dict[str, list[int]] = {}
        for position, item in enumerate(value):
            if isinstance(item, dict) and item.get("Id") is not None:
                positions.setdefault(str(item["Id"]), []).append(position)
        for iid, duplicate_positions in positions.items():
            if len(duplicate_positions) > 1:
                audit.append(
                    {
                        "file": filename,
                        "section": section,
                        "id": iid,
                        "occurrences": len(duplicate_positions),
                        "kept_index": duplicate_positions[-1],
                        "rule": "last-row-wins",
                    }
                )
        last_positions = {iid: positions[-1] for iid, positions in positions.items()}
        return [
            item
            for position, item in enumerate(value)
            if not isinstance(item, dict)
            or item.get("Id") is None
            or last_positions[str(item["Id"])] == position
        ]

    if isinstance(data, list):
        return normalize_list(data), audit
    if isinstance(data, dict):
        normalized = dict(data)
        for section, value in data.items():
            if isinstance(value, list):
                normalized[section] = normalize_list(value, str(section))
        return normalized, audit
    return data, audit


def _copy_snapshot(
    source_json_dir: Path,
    snapshot_dir: Path,
    *,
    version_key: str | None = None,
    role: str | None = None,
    legacy_normalize: bool = False,
) -> dict[str, Any]:
    """Copy JSON into a new immutable snapshot and write its manifest."""
    if snapshot_dir.exists():
        raise SnapshotIntegrityError(f"Refusing to overwrite immutable snapshot: {snapshot_dir}")
    source_manifest = _validate_snapshot_manifest(source_json_dir)
    if not legacy_normalize:
        # New inputs and already immutable archives must not contain duplicate
        # flat records or duplicate IDs within one nested section.
        _load_all_items_by_id_from_dir(source_json_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    try:
        normalization_audit: list[dict[str, Any]] = []
        for json_file in _snapshot_json_files(source_json_dir):
            if legacy_normalize:
                data, audit = _legacy_normalize_data_with_audit(
                    _load_json_strict(json_file),
                    filename=json_file.name,
                )
                normalization_audit.extend(audit)
                if audit:
                    _write_json(snapshot_dir / json_file.name, data)
                else:
                    shutil.copy2(json_file, snapshot_dir / json_file.name)
            else:
                shutil.copy2(json_file, snapshot_dir / json_file.name)
        manifest = _manifest_for_snapshot(
            snapshot_dir,
            version_key=version_key if version_key is not None else source_manifest.get("version_key"),
            role=role if role is not None else source_manifest.get("role"),
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        if legacy_normalize:
            manifest["normalization"] = {
                "mode": "legacy-last-wins",
                "source": str(source_json_dir),
                "duplicates": normalization_audit,
            }
        _write_json(snapshot_dir / SNAPSHOT_MANIFEST_FILENAME, manifest)
        return manifest
    except BaseException:
        shutil.rmtree(snapshot_dir, ignore_errors=True)
        raise


def _attach_building_mxml(snapshot_dir: Path, source_path: Path | None) -> dict[str, Any] | None:
    """Store the building table beside a current snapshot and bind its digest."""
    if source_path is None or not source_path.is_file():
        return None
    building_dir = snapshot_dir / "building"
    building_dir.mkdir(parents=True, exist_ok=False)
    destination = building_dir / source_path.name
    shutil.copy2(source_path, destination)
    manifest_path = snapshot_dir / SNAPSHOT_MANIFEST_FILENAME
    manifest = _load_json_strict(manifest_path)
    if not isinstance(manifest, dict):
        raise SnapshotIntegrityError(f"Snapshot manifest is invalid: {manifest_path}")
    entry = {
        "path": str(Path("building") / source_path.name),
        "sha256": _sha256(destination),
        "size": destination.stat().st_size,
    }
    manifest["building_mxml"] = entry
    _write_json(manifest_path, manifest)
    return entry


def _archive_component_present(version_dir: Path) -> bool:
    return any(
        (version_dir / name).exists()
        for name in (
            "baseline_snapshot",
            "current_snapshot",
            "current_snapshots",
            RELEASE_MANIFEST_FILENAME,
        )
    )


def _release_archive_paths(version_dir: Path) -> dict[str, Path]:
    return {
        "release_dir": version_dir,
        "baseline_snapshot": version_dir / "baseline_snapshot",
        "current_snapshot": version_dir / "current_snapshot",
        "current_snapshots": version_dir / "current_snapshots",
        "building_mxml_dir": version_dir / "building",
        "manifest": version_dir / RELEASE_MANIFEST_FILENAME,
    }


def _validate_release_archive(
    version_dir: Path,
    *,
    version_key: str,
) -> dict[str, Any]:
    paths = _release_archive_paths(version_dir)
    if not paths["manifest"].is_file():
        raise SnapshotIntegrityError(f"Release manifest is missing: {paths['manifest']}")
    release_manifest = _load_json_strict(paths["manifest"])
    if not isinstance(release_manifest, dict) or release_manifest.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise SnapshotIntegrityError(f"Release manifest is invalid: {paths['manifest']}")
    if release_identity(str(release_manifest.get("version_key", ""))) != release_identity(version_key):
        raise SnapshotIntegrityError(
            f"Release version mismatch for {version_dir}: "
            f"expected {version_key}, got {release_manifest.get('version_key')}"
        )
    if release_manifest.get("baseline_snapshot") not in {None, "baseline_snapshot"}:
        raise SnapshotIntegrityError(f"Release baseline reference is invalid: {paths['manifest']}")
    _validate_snapshot_manifest(
        paths["baseline_snapshot"],
        expected_role="baseline",
        require_manifest=True,
    )
    current_candidates: list[Path] = []
    if paths["current_snapshot"].is_dir():
        current_candidates.append(paths["current_snapshot"])
    if paths["current_snapshots"].is_dir():
        current_candidates.extend(
            candidate
            for candidate in sorted(paths["current_snapshots"].iterdir())
            if candidate.is_dir()
        )
    if not current_candidates:
        raise SnapshotIntegrityError(f"Current release snapshot is missing: {version_dir}")
    # Digest validity alone is not enough: an attacker or faulty writer could
    # update both a JSON file and its manifest.  Re-index archived records so
    # duplicate flat/within-section IDs still fail closed.
    for current_snapshot in current_candidates:
        _validate_snapshot_manifest(
            current_snapshot,
            expected_role="current",
            require_manifest=True,
        )
    _load_all_items_by_id_from_dir(paths["baseline_snapshot"])
    for current_snapshot in current_candidates:
        _load_all_items_by_id_from_dir(current_snapshot)
    building_rel = release_manifest.get("building_mxml")
    if building_rel:
        building_path = version_dir / str(building_rel)
        if not building_path.is_file():
            raise SnapshotIntegrityError(f"Archived building MXML is missing: {building_path}")
        if release_manifest.get("building_sha256") != _sha256(building_path):
            raise SnapshotIntegrityError(f"Archived building MXML digest mismatch: {building_path}")
    return {
        **paths,
        "current_snapshot": current_candidates[0],
        "current_snapshot_candidates": current_candidates,
        "release_manifest": release_manifest,
    }


def _find_report_for_archive(version_dir: Path, current_snapshot: Path) -> Path | None:
    for candidate in sorted(version_dir.glob("*/report.json")):
        payload = _load_json(candidate)
        if not isinstance(payload, dict):
            continue
        archive = payload.get("archive")
        if isinstance(archive, dict):
            current_ref = archive.get("current_snapshot")
            if current_ref:
                resolved = _resolve_archive_reference(candidate, str(current_ref), version_dir.parent.parent.parent)
                if resolved == current_snapshot:
                    return candidate
        if payload.get("current_snapshot"):
            resolved = _resolve_archive_reference(candidate, str(payload["current_snapshot"]), version_dir.parent.parent.parent)
            if resolved == current_snapshot:
                return candidate
    return None


def _resolve_archive_reference(report_path: Path, reference: str, repo_root: Path) -> Path:
    normalized_reference = reference.replace("\\", "/")
    candidate = Path(normalized_reference)
    if candidate.is_absolute():
        return candidate.resolve()
    root_candidate = (repo_root / candidate).resolve()
    if root_candidate.exists() or normalized_reference.startswith("reports/"):
        return root_candidate
    return (report_path.parent / candidate).resolve()


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _latest_run_metadata(repo_root: Path) -> dict[str, Any] | None:
    payload = _load_json(repo_root / "reports" / "latest_run.json")
    return payload if isinstance(payload, dict) else None


def _archived_current_candidates(repo_root: Path, *, exclude_version: str) -> Iterable[tuple[str, Path]]:
    by_version = repo_root / "reports" / "by_version"
    if not by_version.is_dir():
        return
    for version_dir in sorted(by_version.iterdir()):
        if not version_dir.is_dir() or release_identity(version_dir.name) == release_identity(exclude_version):
            continue
        manifest = version_dir / RELEASE_MANIFEST_FILENAME
        if not manifest.is_file():
            continue
        try:
            archive = _validate_release_archive(version_dir, version_key=version_dir.name)
        except SnapshotIntegrityError:
            continue
        for current in archive["current_snapshot_candidates"]:
            yield version_dir.name, current


def _select_baseline_source(
    repo_root: Path,
    *,
    version_key: str,
    baseline_snapshot_dir: Path | None,
) -> tuple[Path, str | None]:
    if baseline_snapshot_dir is not None:
        source = Path(baseline_snapshot_dir)
        _validate_snapshot_manifest(source)
        source_version: str | None = None
        manifest = _load_json(source / SNAPSHOT_MANIFEST_FILENAME)
        if isinstance(manifest, dict):
            value = manifest.get("version_key")
            source_version = str(value) if value else None
        return source, source_version

    latest = _latest_run_metadata(repo_root)
    latest_version = str((latest or {}).get("version_key") or "")
    if not latest_version or latest_version == "unknown-version":
        raise SnapshotIntegrityError(
            "Latest release metadata must contain an explicit version before "
            "a baseline can be selected"
        )
    if release_identity(latest_version) == release_identity(version_key):
        raise SnapshotIntegrityError(
            f"Latest release {latest_version} is the same release as {version_key}; "
            "supply the prior release baseline explicitly"
        )

    report_ref = latest.get("report_json") if latest else None
    if report_ref:
        report_path = _resolve_archive_reference(
            repo_root / "reports" / "latest_run.json",
            str(report_ref),
            repo_root,
        )
        report = _load_json(report_path)
        if isinstance(report, dict):
            archive = report.get("archive")
            if isinstance(archive, dict) and archive.get("current_snapshot"):
                source = _resolve_archive_reference(report_path, str(archive["current_snapshot"]), repo_root)
                if source.is_dir():
                    release_manifest_ref = archive.get("release_manifest") or archive.get("manifest")
                    if not release_manifest_ref:
                        raise SnapshotIntegrityError(
                            f"Latest report has no immutable release manifest: {report_path}"
                        )
                    release_manifest_path = _resolve_archive_reference(
                        report_path,
                        str(release_manifest_ref),
                        repo_root,
                    )
                    release_dir = release_manifest_path.parent
                    archived = _validate_release_archive(release_dir, version_key=latest_version)
                    if source not in archived["current_snapshot_candidates"]:
                        raise SnapshotIntegrityError(
                            f"Latest report points outside its immutable archive: {report_path}"
                        )
                    return source, latest_version

    for candidate_version, candidate in _archived_current_candidates(
        repo_root,
        exclude_version=version_key,
    ):
        if release_identity(candidate_version) == release_identity(latest_version):
            return candidate, candidate_version

    legacy_latest = repo_root / "reports" / "_latest_snapshot"
    if legacy_latest.is_dir():
        _validate_snapshot_manifest(legacy_latest)
        return legacy_latest, latest_version
    raise SnapshotIntegrityError(
        f"Previous-release snapshot is missing for latest release {latest_version}: {legacy_latest}"
    )


def _current_source_digest(json_dir: Path) -> str:
    manifest = _manifest_for_snapshot(json_dir)
    return str(manifest["snapshot_digest"])


def _building_dir_for_snapshot(snapshot_dir: Path, release_dir: Path) -> Path:
    manifest = _load_json_strict(snapshot_dir / SNAPSHOT_MANIFEST_FILENAME)
    if isinstance(manifest, dict) and isinstance(manifest.get("building_mxml"), dict):
        return snapshot_dir / Path(str(manifest["building_mxml"]["path"])).parent
    return release_dir / "building"


def _append_current_snapshot(
    version_dir: Path,
    *,
    current_json_dir: Path,
    version_key: str,
    building_mxml_path: Path | None,
) -> Path:
    current_root = version_dir / "current_snapshots"
    current_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = current_root / stamp
    suffix = 1
    while target.exists():
        target = current_root / f"{stamp}_{suffix}"
        suffix += 1
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=str(version_dir)))
    stage_snapshot = stage / "current_snapshot"
    try:
        _copy_snapshot(
            current_json_dir,
            stage_snapshot,
            version_key=version_key,
            role="current",
        )
        _attach_building_mxml(stage_snapshot, building_mxml_path)
        _validate_snapshot_manifest(stage_snapshot, expected_role="current", require_manifest=True)
        os.replace(stage_snapshot, target)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
    return target


def _archive_with_current(archive: dict[str, Any], current_snapshot: Path) -> dict[str, Any]:
    return {
        **archive,
        "current_snapshot": current_snapshot,
        "building_mxml_dir": _building_dir_for_snapshot(
            current_snapshot,
            archive["release_dir"],
        ),
    }


def bootstrap_release(
    repo_root: Path,
    *,
    version_key: str,
    baseline_snapshot_dir: Path | None = None,
    current_json_dir: Path | None = None,
    building_mxml_path: Path | None = None,
    previous_version_key: str | None = None,
    generated_at: str | None = None,
    legacy_normalize_baseline: bool | None = None,
) -> dict[str, Any]:
    """Create or validate an immutable archive for one explicit release.

    The stable archive lives at ``reports/by_version/<major.minor>/``.  The
    baseline is fixed for the release.  Re-running with identical JSON reuses
    its existing immutable current snapshot; a corrected current extraction is
    stored as a new immutable snapshot while retaining that same baseline.
    """
    repo_root = Path(repo_root).resolve()
    version_key = require_explicit_version(version_key)
    current_json_dir = Path(current_json_dir or repo_root / "data" / "json").resolve()
    if not current_json_dir.is_dir():
        raise SnapshotIntegrityError(f"Current JSON directory is missing: {current_json_dir}")
    building_mxml_path = Path(
        building_mxml_path or repo_root / "data" / "mbin" / "basebuildingobjectstable.MXML"
    ).resolve()
    current_building_digest = _sha256(building_mxml_path) if building_mxml_path.is_file() else None

    reports_root = repo_root / "reports"
    version_dir = reports_root / "by_version" / release_identity(version_key)
    paths = _release_archive_paths(version_dir)
    if _archive_component_present(version_dir):
        archive = _validate_release_archive(version_dir, version_key=version_key)
        current_digest = _current_source_digest(current_json_dir)
        for candidate in archive["current_snapshot_candidates"]:
            archived_manifest = _load_json_strict(candidate / SNAPSHOT_MANIFEST_FILENAME)
            building_entry = archived_manifest.get("building_mxml")
            archived_building_digest = (building_entry.get("sha256") if isinstance(building_entry, dict)
                                       else archive["release_manifest"].get("building_sha256"))
            if (current_digest == archived_manifest.get("snapshot_digest")
                    and current_building_digest == archived_building_digest):
                return {
                    "version_key": version_key,
                    "previous_version_key": archive["release_manifest"].get("previous_version_key"),
                    "created": False,
                    **_archive_with_current(archive, candidate),
                }
        new_current = _append_current_snapshot(
            version_dir,
            current_json_dir=current_json_dir,
            version_key=version_key,
            building_mxml_path=Path(building_mxml_path).resolve() if building_mxml_path else None,
        )
        return {
            "version_key": version_key,
            "previous_version_key": archive["release_manifest"].get("previous_version_key"),
            "created": True,
            **_archive_with_current(archive, new_current),
        }

    baseline_source, detected_previous_version = _select_baseline_source(
        repo_root,
        version_key=version_key,
        baseline_snapshot_dir=baseline_snapshot_dir,
    )
    previous_version_key = previous_version_key or detected_previous_version
    if not previous_version_key or previous_version_key == "unknown-version":
        raise SnapshotIntegrityError(
            "A verified previous release version is required for baseline publication"
        )
    if release_identity(str(previous_version_key)) == release_identity(version_key):
        raise SnapshotIntegrityError(
            f"Previous release {previous_version_key} is the same release as {version_key}"
        )
    _validate_snapshot_manifest(baseline_source)
    if legacy_normalize_baseline is None:
        legacy_normalize_baseline = _is_legacy_snapshot_path(baseline_source)

    building_mxml_path = Path(
        building_mxml_path or repo_root / "data" / "mbin" / "basebuildingobjectstable.MXML"
    ).resolve()
    generated_at = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    reports_root.mkdir(parents=True, exist_ok=True)
    version_dir.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{version_key}.", dir=str(reports_root)))
    stage_version = stage / version_key
    stage_version.mkdir()
    stage_paths = _release_archive_paths(stage_version)
    try:
        _copy_snapshot(
            baseline_source,
            stage_paths["baseline_snapshot"],
            version_key=previous_version_key,
            role="baseline",
            legacy_normalize=legacy_normalize_baseline,
        )
        _copy_snapshot(
            current_json_dir,
            stage_paths["current_snapshot"],
            version_key=version_key,
            role="current",
        )
        _attach_building_mxml(
            stage_paths["current_snapshot"],
            building_mxml_path if building_mxml_path.is_file() else None,
        )
        release_manifest = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "version_key": version_key,
            "previous_version_key": previous_version_key,
            "created_at": generated_at,
            "baseline_snapshot": "baseline_snapshot",
            "current_snapshot": "current_snapshot",
            "current_snapshots_root": "current_snapshots",
            "baseline_manifest": str(Path("baseline_snapshot") / SNAPSHOT_MANIFEST_FILENAME),
            "current_manifest": str(Path("current_snapshot") / SNAPSHOT_MANIFEST_FILENAME),
            "building_mxml": None,
            "building_sha256": None,
        }
        _write_json(stage_paths["manifest"], release_manifest)
        # Move only into an archive root that did not previously contain any
        # release components.  Existing timestamped report folders are kept.
        if _archive_component_present(version_dir):
            raise SnapshotIntegrityError(f"Release archive was created concurrently: {version_dir}")
        for name in ("baseline_snapshot", "current_snapshot", RELEASE_MANIFEST_FILENAME):
            source = stage_version / name
            if not source.exists():
                continue
            target = version_dir / name
            if target.exists():
                raise SnapshotIntegrityError(f"Release archive was created concurrently: {target}")
            os.replace(source, target)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)

    archive = _validate_release_archive(version_dir, version_key=version_key)
    return {
        "version_key": version_key,
        "previous_version_key": previous_version_key,
        "created": True,
        **_archive_with_current(archive, archive["current_snapshot"]),
    }


def _build_markdown(*, version_key: str, generated_at: str, previous_run: dict[str, Any] | None, per_file: dict[str, dict[str, Any]]) -> str:
    old_total = sum(info["old_count"] for info in per_file.values())
    new_total = sum(info["new_count"] for info in per_file.values())
    added_total = sum(len(info["added_ids"]) for info in per_file.values())
    removed_total = sum(len(info["removed_ids"]) for info in per_file.values())
    changed_total = sum(len(info["changed_ids"]) for info in per_file.values())

    lines = [
        "# NMS Full Refresh Report",
        "",
        f"- Generated: `{generated_at}`",
        f"- Version key: `{version_key}`",
    ]
    if previous_run:
        lines.append(f"- Previous run: `{previous_run.get('generated_at', 'unknown')}` ({previous_run.get('version_key', 'unknown')})")
    else:
        lines.append("- Previous run: `none` (first report)")
    lines.extend(
        [
            "",
            "## Totals",
            "",
            f"- Old total items: **{old_total}**",
            f"- New total items: **{new_total}**",
            f"- Added IDs: **{added_total}**",
            f"- Removed IDs: **{removed_total}**",
            f"- Changed IDs: **{changed_total}**",
            "",
            "## Per File",
            "",
            "| File | Old | New | Added | Removed | Changed |",
            "|:-----|----:|----:|------:|--------:|--------:|",
        ]
    )

    for filename in sorted(per_file):
        info = per_file[filename]
        lines.append(f"| {filename} | {info['old_count']} | {info['new_count']} | {len(info['added_ids'])} | {len(info['removed_ids'])} | {len(info['changed_ids'])} |")

    lines.extend(["", "## Net New Highlights", ""])
    changes_found = False
    for filename in sorted(per_file):
        info = per_file[filename]
        if not info["has_changes"]:
            continue
        changes_found = True
        lines.append(f"### {filename}")
        if info["added_ids"]:
            preview = ", ".join(info["added_ids"][:25])
            lines.append(f"- Added ({len(info['added_ids'])}): {preview}")
            if len(info["added_ids"]) > 25:
                lines.append(f"  - ... and {len(info['added_ids']) - 25} more")
        if info["removed_ids"]:
            preview = ", ".join(info["removed_ids"][:25])
            lines.append(f"- Removed ({len(info['removed_ids'])}): {preview}")
            if len(info["removed_ids"]) > 25:
                lines.append(f"  - ... and {len(info['removed_ids']) - 25} more")
        if info["changed_ids"]:
            preview = ", ".join(info["changed_ids"][:25])
            lines.append(f"- Changed ({len(info['changed_ids'])}): {preview}")
            if len(info["changed_ids"]) > 25:
                lines.append(f"  - ... and {len(info['changed_ids']) - 25} more")
        lines.append("")

    if not changes_found:
        lines.append("- No net changes detected versus previous run.")

    lines.append("")
    return "\n".join(lines)


def compare_against_snapshot(
    repo_root: Path,
    *,
    baseline_snapshot_dir: Path | None = None,
    current_json_dir: Path | None = None,
    version_key: str | None = None,
    require_baseline: bool = False,
) -> tuple[dict[str, dict[str, Any]], str, dict[str, Any] | None]:
    """Diff a current JSON directory against a baseline snapshot.

    The default remains compatible with the legacy ``_latest_snapshot``
    pointer.  Versioned publication callers pass an archived baseline/current
    explicitly and set ``require_baseline`` so missing/corrupt inputs fail
    closed instead of becoming an all-new release.
    """
    reports_root = repo_root / "reports"
    baseline_snapshot_dir = Path(baseline_snapshot_dir or reports_root / "_latest_snapshot")
    current_json_dir = Path(current_json_dir or repo_root / "data" / "json")
    resolved_version = explicit_version_key(version_key) or detect_version_key(repo_root)

    previous_run = None
    latest_run_meta_path = reports_root / "latest_run.json"
    if latest_run_meta_path.exists():
        previous_run = _load_json(latest_run_meta_path)
        if not isinstance(previous_run, dict):
            previous_run = None

    if not baseline_snapshot_dir.is_dir():
        if require_baseline:
            raise SnapshotIntegrityError(
                f"Previous-release snapshot is missing: {baseline_snapshot_dir}"
            )
        return {}, resolved_version, previous_run

    _validate_snapshot_manifest(baseline_snapshot_dir, require_manifest=require_baseline)
    legacy_normalize = _is_legacy_snapshot_path(baseline_snapshot_dir) and not (
        baseline_snapshot_dir / SNAPSHOT_MANIFEST_FILENAME
    ).is_file()

    current_files = {p.name for p in _snapshot_json_files(current_json_dir)}
    previous_files = {p.name for p in _snapshot_json_files(baseline_snapshot_dir)}
    per_file: dict[str, dict[str, Any]] = {}
    for filename in sorted(current_files | previous_files):
        old_data = _load_json(baseline_snapshot_dir / filename)
        new_data = _load_json(current_json_dir / filename)
        if legacy_normalize and old_data is not None:
            old_data = _legacy_normalize_data(old_data)
        per_file[filename] = _compare_file(old_data, new_data, source_name=filename)
    return per_file, resolved_version, previous_run


def _load_all_current_items_by_id(
    repo_root: Path,
    json_dir: Path | None = None,
) -> dict[str, tuple[str, dict[str, Any]]]:
    """Map Id -> (source filename, item) across all output JSON except meta files."""
    return _load_all_items_by_id_from_dir(Path(json_dir or repo_root / "data" / "json"))


def _load_all_items_by_id_from_dir(
    json_dir: Path,
    *,
    legacy_normalize: bool = False,
) -> dict[str, tuple[str, dict[str, Any]]]:
    """Map Id -> (source filename, item) across all JSON in a directory."""
    combined: dict[str, tuple[str, dict[str, Any]]] = {}
    if not json_dir.is_dir():
        return combined
    for path in sorted(json_dir.glob("*.json")):
        if path.name in IGNORED_REPORT_FILES or path.name == SNAPSHOT_MANIFEST_FILENAME:
            continue
        data = _load_json_strict(path)
        if legacy_normalize:
            data = _legacy_normalize_data(data)
        for iid, item in _index_items_by_id(data, source_name=path.name).items():
            previous = combined.get(iid)
            if previous is not None:
                if legacy_normalize and not iid.startswith("@nested:"):
                    # Reproduce the historical sorted-file/last-row-wins
                    # behavior only for a trusted pre-manifest migration.
                    combined[iid] = (path.name, item)
                    continue
                raise ValueError(f"Duplicate global Id across JSON outputs: {iid}")
            combined[iid] = (path.name, item)
    return combined


_SKIP_CHANGE_DIFF_KEYS = frozenset(
    {
        "SourceFile",
        "SourceSection",
        "Slug",
        "SpaceBaseVariantOf",
        "RewardVariantOf",
        "Change",
        "Previous",
        "ChangedFields",
        "CdnUrl",
        "HeroIconPath",
        "AltDescription",
        "Hint",
        "PinObjective",
        "PinObjectiveTip",
        "PinObjectiveMessage",
    }
)


def _diff_changed_fields(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    keys = set(previous) | set(current)
    changed: list[str] = []
    for key in sorted(keys):
        if key in _SKIP_CHANGE_DIFF_KEYS:
            continue
        if previous.get(key) != current.get(key):
            changed.append(key)
    return changed


def _expedition_variant(item: dict[str, Any], baseline_by_id: dict) -> dict[str, Any] | None:
    match = re.match(r"^S(\d+)_", str(item.get("Id", "")))
    if not match or not item.get("Name") or not item.get("IconPath"):
        return None
    candidates = [previous for _, previous in baseline_by_id.values()
                  if previous.get("Name", "").casefold() == item["Name"].casefold()
                  and previous.get("IconPath") == item["IconPath"]]
    if not candidates:
        return None
    original = min(candidates, key=lambda candidate: (
        candidate.get("Group") != item.get("Group"), len(candidate["Id"]), candidate["Id"],
    ))
    return {"Kind": "expedition", "Expedition": int(match.group(1)),
            "BaseItemId": original["Id"], "BaseItemName": original["Name"]}


def build_new_json_document(
    repo_root: Path,
    *,
    version_key: str,
    previous_run: dict[str, Any] | None,
    generated_at: str | None = None,
    baseline_snapshot_dir: Path | None = None,
    current_snapshot_dir: Path | None = None,
    building_mxml_dir: Path | None = None,
) -> dict[str, Any]:
    """Compare archived or current item JSON without losing category moves.

    ``current_snapshot_dir`` and ``building_mxml_dir`` are used by report
    rebuilds.  When supplied, no live current JSON/MXML is consulted.
    """
    if baseline_snapshot_dir is None:
        candidate = repo_root / "reports" / "by_version" / release_identity(version_key) / "baseline_snapshot"
        baseline_snapshot_dir = candidate if candidate.is_dir() else repo_root / "reports" / "_latest_snapshot"
    baseline_snapshot_dir = Path(baseline_snapshot_dir)
    _validate_snapshot_manifest(baseline_snapshot_dir)
    legacy_normalize = _is_legacy_snapshot_path(baseline_snapshot_dir) and not (
        baseline_snapshot_dir / SNAPSHOT_MANIFEST_FILENAME
    ).is_file()
    current_source = Path(current_snapshot_dir or repo_root / "data" / "json")
    if current_snapshot_dir is not None:
        _validate_snapshot_manifest(current_source, require_manifest=True)
    all_by_id = _load_all_current_items_by_id(repo_root, json_dir=current_source)
    baseline_by_id = _load_all_items_by_id_from_dir(
        baseline_snapshot_dir,
        legacy_normalize=legacy_normalize,
    )
    mxml_dir = Path(building_mxml_dir or repo_root / "data" / "mbin")
    space_base_variants = load_space_base_variants(mxml_dir)
    previous_rewards = {signature for _, item in baseline_by_id.values()
                        if (signature := reward_identity(item)) is not None}
    added_items: list[dict[str, Any]] = []
    changed_items: list[dict[str, Any]] = []

    for iid, (source_file, item) in sorted(all_by_id.items(), key=lambda pair: (pair[1][0], pair[0])):
        entry = dict(item)
        entry["SourceFile"] = source_file
        section = _record_section(iid)
        if section:
            entry["SourceSection"] = section
        baseline = baseline_by_id.get(iid)
        if baseline is None:
            if any(_record_id(key, candidate) == str(item.get("RewardVariantOf")) for key, (_, candidate) in all_by_id.items()):
                continue
            if reward_identity(item) in previous_rewards:
                continue
            # A new product ID can describe an existing building in a new context.
            original_ids = item.get(
                "SpaceBaseVariantOf",
                space_base_variants.get(_record_id(iid, item), []),
            )
            if isinstance(original_ids, str):
                original_ids = [original_ids]
            elif original_ids is None:
                original_ids = []
            elif not isinstance(original_ids, (list, tuple, set)):
                original_ids = [original_ids]
            if any(
                any(_record_id(key, candidate) == str(original_id) for key, (_, candidate) in baseline_by_id.items())
                or any(_record_id(key, candidate) == str(original_id) for key, (_, candidate) in all_by_id.items())
                for original_id in original_ids
            ):
                continue
            entry["Change"] = "added"
            variant = _expedition_variant(item, baseline_by_id)
            if variant:
                entry["ReleaseVariant"] = variant
            added_items.append(entry)
            continue
        _source, previous_item = baseline
        changed_fields = _diff_changed_fields(previous_item, item)
        if changed_fields:
            entry["Change"] = "changed"
            entry["Previous"] = dict(previous_item)
            entry["ChangedFields"] = changed_fields
            changed_items.append(entry)

    removed_ids = []
    for iid in sorted(baseline_by_id.keys() - all_by_id.keys()):
        source_file, previous_item = baseline_by_id[iid]
        removed = {"Id": _record_id(iid, previous_item), "SourceFile": source_file}
        section = _record_section(iid)
        if section:
            removed["SourceSection"] = section
        removed_ids.append(removed)

    return {
        "VersionKey": version_key,
        "PreviousVersionKey": (previous_run or {}).get("version_key"),
        "GeneratedAt": generated_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "Summary": {
            "Added": len(added_items),
            "Changed": len(changed_items),
            "Removed": len(removed_ids),
        },
        "RemovedIds": removed_ids,
        "Items": added_items,
        "ChangedItems": changed_items,
    }


def write_new_json(repo_root: Path, document: dict[str, Any]) -> Path:
    path = repo_root / "data" / "json" / NEW_JSON_FILENAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(document, f, indent="\t", ensure_ascii=False)
    return path


def _baseline_for_release(repo_root: Path, version_key: str) -> Path | None:
    version_dir = repo_root / "reports" / "by_version" / release_identity(version_key)
    if _archive_component_present(version_dir):
        archive = _validate_release_archive(version_dir, version_key=version_key)
        return archive["baseline_snapshot"]
    return None


def update_new_json(
    repo_root: Path,
    *,
    version_key: str | None = None,
    baseline_snapshot_dir: Path | None = None,
    current_snapshot_dir: Path | None = None,
    building_mxml_dir: Path | None = None,
) -> dict[str, Any]:
    """Write ``data/json/new.json`` using a stable release baseline when one exists.

    This is the pre-publication delta helper used by the extractor.  It keeps
    the historical compiler fallback for diagnostic/non-report calls; report
    publication itself requires an explicit version.
    """
    repo_root = Path(repo_root).resolve()
    resolved_version = explicit_version_key(version_key) or detect_version_key(repo_root)
    baseline = Path(baseline_snapshot_dir) if baseline_snapshot_dir is not None else _baseline_for_release(repo_root, resolved_version)
    if baseline is None:
        baseline = repo_root / "reports" / "_latest_snapshot"
    current = Path(current_snapshot_dir) if current_snapshot_dir is not None else None
    per_file, _, previous_run = compare_against_snapshot(
        repo_root,
        baseline_snapshot_dir=baseline,
        current_json_dir=current,
        version_key=resolved_version,
    )
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    document = build_new_json_document(
        repo_root,
        version_key=resolved_version,
        previous_run=previous_run,
        generated_at=generated_at,
        baseline_snapshot_dir=baseline,
        current_snapshot_dir=current,
        building_mxml_dir=building_mxml_dir,
    )
    path = write_new_json(repo_root, document)
    return {
        "path": path,
        "version_key": resolved_version,
        "item_count": document["Summary"]["Added"],
        "summary": document["Summary"],
    }


def _report_totals(per_file: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {
        "added": sum(len(info["added_ids"]) for info in per_file.values()),
        "removed": sum(len(info["removed_ids"]) for info in per_file.values()),
        "changed": sum(len(info["changed_ids"]) for info in per_file.values()),
    }


def _archive_report_payload(
    repo_root: Path,
    archive: dict[str, Any],
) -> dict[str, Any]:
    release_manifest = archive["release_manifest"]
    release_dir = archive["release_dir"]
    current_manifest = _load_json_strict(
        archive["current_snapshot"] / SNAPSHOT_MANIFEST_FILENAME
    )
    building_entry = current_manifest.get("building_mxml") if isinstance(current_manifest, dict) else None
    if isinstance(building_entry, dict) and building_entry.get("path"):
        building_path = archive["current_snapshot"] / str(building_entry["path"])
    else:
        building_rel = release_manifest.get("building_mxml")
        building_path = release_dir / str(building_rel) if building_rel else None
    refs = {
        "release_manifest": _relative_path(archive["manifest"], repo_root),
        "baseline_snapshot": _relative_path(archive["baseline_snapshot"], repo_root),
        "current_snapshot": _relative_path(archive["current_snapshot"], repo_root),
        "baseline_manifest": _relative_path(
            archive["baseline_snapshot"] / SNAPSHOT_MANIFEST_FILENAME,
            repo_root,
        ),
        "current_manifest": _relative_path(
            archive["current_snapshot"] / SNAPSHOT_MANIFEST_FILENAME,
            repo_root,
        ),
        "building_mxml": _relative_path(building_path, repo_root) if building_path else None,
    }
    return refs


def resolve_report_archive(
    report_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Resolve and validate the archived inputs referenced by a report JSON.

    This is the public handoff for rebuild tools.  It deliberately refuses
    reports without archive references instead of falling back to live
    ``data/json`` or ``data/mbin``.
    """
    report_path = Path(report_path).resolve()
    if repo_root is None:
        reports_parent = next((parent for parent in report_path.parents if parent.name == "reports"), None)
        repo_root = reports_parent.parent if reports_parent is not None else report_path.parent
    repo_root = Path(repo_root).resolve()
    payload = _load_json_strict(report_path)
    if not isinstance(payload, dict):
        raise SnapshotIntegrityError(f"Report JSON is invalid: {report_path}")
    refs = payload.get("archive")
    if not isinstance(refs, dict):
        refs = payload
    baseline_ref = refs.get("baseline_snapshot")
    current_ref = refs.get("current_snapshot")
    manifest_ref = refs.get("release_manifest") or refs.get("manifest")
    if not baseline_ref or not current_ref or not manifest_ref:
        raise SnapshotIntegrityError(
            f"Report has no complete archived baseline/current references: {report_path}"
        )
    baseline = _resolve_archive_reference(report_path, str(baseline_ref), repo_root)
    current = _resolve_archive_reference(report_path, str(current_ref), repo_root)
    release_manifest_path = _resolve_archive_reference(report_path, str(manifest_ref), repo_root)
    release_dir = release_manifest_path.parent
    version_key = str(payload.get("version_key") or release_dir.name)
    archive = _validate_release_archive(release_dir, version_key=version_key)
    if baseline != archive["baseline_snapshot"] or current not in archive["current_snapshot_candidates"]:
        raise SnapshotIntegrityError(f"Report archive references do not match release manifest: {report_path}")
    building_ref = refs.get("building_mxml")
    if building_ref:
        building_path = _resolve_archive_reference(report_path, str(building_ref), repo_root)
        current_manifest = _load_json_strict(current / SNAPSHOT_MANIFEST_FILENAME)
        building_entry = current_manifest.get("building_mxml") if isinstance(current_manifest, dict) else None
        expected_building = current / str(building_entry["path"]) if isinstance(building_entry, dict) else None
        if expected_building is None or building_path != expected_building:
            raise SnapshotIntegrityError(f"Report building archive reference does not match release manifest: {report_path}")
        building_dir = building_path.parent
    else:
        # An archive without a building table is still detached from live
        # sources: use its absent sibling directory so the builder returns no
        # overrides rather than consulting repo_root/data/mbin.
        building_dir = _building_dir_for_snapshot(current, release_dir)
    return {
        "report": payload,
        "release_manifest": archive["manifest"],
        "baseline_snapshot_dir": archive["baseline_snapshot"],
        "current_snapshot_dir": current,
        "building_mxml_dir": building_dir,
        "archive": archive,
    }


def _next_report_dir(version_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    candidate = version_dir / stamp
    suffix = 1
    while (candidate / "report.json").exists():
        candidate = version_dir / f"{stamp}_{suffix}"
        suffix += 1
    return candidate


def generate_refresh_report(
    repo_root: Path,
    *,
    version_key: str | None = None,
    baseline_snapshot_dir: Path | None = None,
    current_json_dir: Path | None = None,
    building_mxml_path: Path | None = None,
) -> dict[str, Any]:
    """Publish one immutable, version-keyed refresh report.

    The release archive is created once at
    ``reports/by_version/<major.minor>/``.  A rerun validates the archived
    current snapshot and returns its existing report, preserving the original
    prior-release baseline.
    """
    repo_root = Path(repo_root).resolve()
    version_key = require_explicit_version(version_key)
    current_json_dir = Path(current_json_dir or repo_root / "data" / "json").resolve()
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    previous_run = _latest_run_metadata(repo_root)
    archive = bootstrap_release(
        repo_root,
        version_key=version_key,
        baseline_snapshot_dir=baseline_snapshot_dir,
        current_json_dir=current_json_dir,
        building_mxml_path=building_mxml_path,
        generated_at=generated_at,
    )
    existing_report = _find_report_for_archive(
        archive["release_dir"],
        archive["current_snapshot"],
    )
    if existing_report is not None:
        existing_payload = _load_json_strict(existing_report)
        if not isinstance(existing_payload, dict):
            raise SnapshotIntegrityError(f"Report JSON is invalid: {existing_report}")
        markdown_path = existing_report.with_name("report.md")
        per_file = existing_payload.get("files")
        if not isinstance(per_file, dict):
            raise SnapshotIntegrityError(f"Report file summary is invalid: {existing_report}")
        return {
            "version_key": version_key,
            "generated_at": existing_payload.get("generated_at", generated_at),
            "report_markdown": markdown_path,
            "report_json": existing_report,
            "totals": _report_totals(per_file),
            "archive": archive,
        }

    per_file, _, _ = compare_against_snapshot(
        repo_root,
        baseline_snapshot_dir=archive["baseline_snapshot"],
        current_json_dir=archive["current_snapshot"],
        version_key=version_key,
        require_baseline=True,
    )
    run_dir = _next_report_dir(archive["release_dir"])
    run_dir.mkdir(parents=True, exist_ok=False)
    md_path = run_dir / "report.md"
    json_path = run_dir / "report.json"
    markdown = _build_markdown(
        version_key=version_key,
        generated_at=generated_at,
        previous_run=previous_run,
        per_file=per_file,
    )
    archive_refs = _archive_report_payload(repo_root, archive)
    report_payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "version_key": version_key,
        "previous_run": previous_run,
        "files": per_file,
        "archive": archive_refs,
        # Top-level aliases keep the report easy for small scripts to consume.
        "baseline_snapshot": archive_refs["baseline_snapshot"],
        "current_snapshot": archive_refs["current_snapshot"],
        "building_mxml": archive_refs["building_mxml"],
        "release_manifest": archive_refs["release_manifest"],
    }
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write(markdown)
    _write_json(json_path, report_payload)

    reports_root = repo_root / "reports"
    with (reports_root / "latest_report.md").open("w", encoding="utf-8") as handle:
        handle.write(markdown)
    latest_meta = {
        "generated_at": generated_at,
        "version_key": version_key,
        "report_markdown": _relative_path(md_path, repo_root),
        "report_json": _relative_path(json_path, repo_root),
        "release_manifest": archive_refs["release_manifest"],
    }
    _write_json(reports_root / "latest_run.json", latest_meta)
    return {
        "version_key": version_key,
        "generated_at": generated_at,
        "report_markdown": md_path,
        "report_json": json_path,
        "totals": _report_totals(per_file),
        "archive": archive,
    }
