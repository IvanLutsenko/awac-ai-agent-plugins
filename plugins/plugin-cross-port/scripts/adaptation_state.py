"""Adaptation state and source snapshot helpers for plugin-cross-port."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Iterable


STATE_DIR = ".plugin-cross-port"
STATE_FILE = "adaptation-state.yaml"
PLAN_FILE = "adaptation-plan.md"
HASH_PREFIX = "sha256:"
_MISSING_MARKER = b"<plugin-cross-port:missing-source>"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_state import load as load_json_yaml
from plugin_state import save as save_json_yaml


def state_path(plugin_dir: Path) -> Path:
    return plugin_dir / STATE_DIR / STATE_FILE


def plan_dir(plugin_dir: Path) -> Path:
    return plugin_dir / STATE_DIR


def plan_path(plugin_dir: Path) -> Path:
    return plan_dir(plugin_dir) / PLAN_FILE


def load(path_or_plugin_dir: Path) -> dict[str, Any]:
    return load_json_yaml(_resolve_state_path(path_or_plugin_dir), default={})


def save(path_or_plugin_dir: Path, payload: dict[str, Any]) -> None:
    save_json_yaml(_resolve_state_path(path_or_plugin_dir), payload)


def plan_hash(text: str) -> str:
    return _hash_bytes(text.encode("utf-8"))


def source_snapshot(plugin_dir: Path, source_files: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(str(source_file) for source_file in source_files):
        path = _safe_plugin_path(plugin_dir, relative)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if path.exists():
            digest.update(path.read_bytes())
        else:
            digest.update(_MISSING_MARKER)
        digest.update(b"\0")
    return f"{HASH_PREFIX}{digest.hexdigest()}"


def classify_staleness(payload: dict[str, Any], plugin_dir: Path) -> dict[str, Any]:
    source_files = _adaptation_source_files(payload)
    current_snapshot = source_snapshot(plugin_dir, source_files)
    stored_snapshot = payload.get("source_snapshot")
    payload_is_stale = bool(stored_snapshot and stored_snapshot != current_snapshot)
    stale_adaptations = _stale_adaptations(payload, plugin_dir, payload_is_stale)
    stale = payload_is_stale or bool(stale_adaptations)
    critical = any(
        adaptation.get("criticality", "critical") == "critical"
        for adaptation in stale_adaptations
    )

    if not stale:
        status = "current"
    elif critical:
        status = "stale-critical"
    else:
        status = "stale-non-critical"

    return {
        "stale": stale,
        "critical": critical,
        "status": status,
        "source_snapshot": current_snapshot,
    }


def _resolve_state_path(path_or_plugin_dir: Path) -> Path:
    if path_or_plugin_dir.is_dir() or path_or_plugin_dir.name != STATE_FILE:
        return state_path(path_or_plugin_dir)
    return path_or_plugin_dir


def _hash_bytes(content: bytes) -> str:
    return f"{HASH_PREFIX}{hashlib.sha256(content).hexdigest()}"


def _safe_plugin_path(plugin_dir: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise ValueError(f"Adaptation source path is outside plugin: {relative}")
    resolved_plugin = plugin_dir.resolve()
    resolved_path = (resolved_plugin / path).resolve()
    try:
        resolved_path.relative_to(resolved_plugin)
    except ValueError as error:
        raise ValueError(f"Adaptation source path is outside plugin: {relative}") from error
    return resolved_path


def _adaptation_source_files(payload: dict[str, Any]) -> list[str]:
    source_files: set[str] = set()
    for adaptation in payload.get("adaptations", []):
        for source_file in adaptation.get("source_files", []):
            source_files.add(str(source_file))
    return sorted(source_files)


def _stale_adaptations(
    payload: dict[str, Any], plugin_dir: Path, payload_is_stale: bool
) -> list[dict[str, Any]]:
    stale: list[dict[str, Any]] = []
    for adaptation in payload.get("adaptations", []):
        adaptation_snapshot = adaptation.get("source_snapshot")
        if adaptation_snapshot:
            current = source_snapshot(plugin_dir, adaptation.get("source_files", []))
            if adaptation_snapshot != current:
                stale.append(adaptation)
        elif payload_is_stale:
            stale.append(adaptation)
    return stale
