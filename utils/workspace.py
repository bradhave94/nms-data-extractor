"""Scoped extraction workspace and recoverable publication of validated outputs."""
from contextlib import contextmanager
from pathlib import Path
import os
import uuid


def workspace_root() -> Path:
    return Path(os.environ.get("NMS_WORK_ROOT") or Path(__file__).resolve().parent.parent).resolve()


@contextmanager
def using_workspace(root: Path):
    previous = os.environ.get("NMS_WORK_ROOT")
    os.environ["NMS_WORK_ROOT"] = str(root.resolve())
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("NMS_WORK_ROOT", None)
        else:
            os.environ["NMS_WORK_ROOT"] = previous


def publish_directories(stage: Path, destination: Path, relatives: list[str]) -> Path:
    """Rename validated directories with rollback; keep previous data for recovery.

    Readers must not run during the short multi-directory commit. The caller holds
    the extraction lock. Backups deliberately remain after a successful commit.
    """
    allowed = {"data/json", "data/mbin", "reports"}
    if not relatives or len(set(relatives)) != len(relatives) or not set(relatives) <= allowed:
        raise ValueError("Publication targets must be explicit extraction output directories")
    stage, destination = stage.resolve(), destination.resolve()
    if stage == destination:
        raise ValueError("Staging must be separate from the live workspace")
    for rel in relatives:
        source, target = (stage / rel).resolve(), (destination / rel).resolve()
        if not source.is_relative_to(stage) or not target.is_relative_to(destination):
            raise ValueError("Publication target escapes its workspace")
        if not source.is_dir():
            raise ValueError(f"Missing staged output: {rel}")
    backup = destination / ".refresh-backups" / uuid.uuid4().hex
    if not backup.resolve().is_relative_to(destination):
        raise ValueError("Backup location escapes the destination workspace")
    moved_old, installed = [], []
    try:
        for rel in relatives:
            source, target, old = stage / rel, destination / rel, backup / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                old.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, old)
                moved_old.append(rel)
            os.replace(source, target)
            installed.append(rel)
    except BaseException:
        for rel in reversed(installed):
            (stage / rel).parent.mkdir(parents=True, exist_ok=True)
            os.replace(destination / rel, stage / rel)
        for rel in reversed(moved_old):
            os.replace(backup / rel, destination / rel)
        raise
    return backup


@contextmanager
def extraction_lock(root: Path):
    lock = root / ".extraction.lock"
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
    except FileExistsError as exc:
        raise RuntimeError(f"Extraction already locked: {lock}. Check its PID before removing a stale lock.") from exc
    try:
        yield
    finally:
        lock.unlink()
