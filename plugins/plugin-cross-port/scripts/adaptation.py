"""Semantic adaptation planning for plugin-cross-port 0.7.0."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MACHINE_BLOCK_START = "```json plugin-cross-port-adaptations"
MACHINE_BLOCK_END = "```"
CLAUDE_PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adaptation_state
from plugin_state import load as load_plugin_state


@dataclass
class AdaptationReport:
    plugin: Path
    adaptations: list[dict[str, Any]]
    changed_paths: list[Path]
    status: str = "planned"
    error: str = ""

    @property
    def exit_code(self) -> int:
        return 0 if not self.error else 1


def analyze(repo_root: Path, plugin_path: Path) -> AdaptationReport:
    plugin = plugin_path.resolve()
    state = load_plugin_state(
        plugin / ".plugin-cross-port.yaml",
        default={
            "plugin": plugin.name,
            "source_of_truth": "claude-code",
        },
    )
    source_of_truth = state.get("source_of_truth", "claude-code")
    if source_of_truth != "claude-code":
        raise ValueError(
            "0.7.0 adaptation analysis currently supports only claude-code "
            f"source_of_truth, got {source_of_truth}"
        )

    adaptations = _detect_hook_adaptations(plugin)
    adaptations.extend(_detect_plugin_root_command_adaptations(plugin))

    for item in adaptations:
        item["source_snapshot"] = adaptation_state.source_snapshot(
            plugin, item.get("source_files", [])
        )

    source_files = _all_source_files(adaptations)
    payload: dict[str, Any] = {
        "version": 1,
        "plugin": plugin.name,
        "source_of_truth": source_of_truth,
        "status": "planned",
        "source_snapshot": adaptation_state.source_snapshot(plugin, source_files),
        "adaptations": adaptations,
    }
    payload["plan_hash"] = plan_payload_hash(payload)
    plan_text = render_plan(payload)

    plan_path = adaptation_state.plan_path(plugin)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan_text, encoding="utf-8")
    adaptation_state.save(plugin, payload)

    return AdaptationReport(
        plugin=plugin,
        adaptations=adaptations,
        changed_paths=[plan_path, adaptation_state.state_path(plugin)],
    )


def render_plan(payload: dict[str, Any]) -> str:
    lines = [
        "# Plugin Cross-Port Adaptation Plan",
        "",
        f"Plugin: {payload.get('plugin', '')}",
        f"Status: {payload.get('status', 'planned')}",
        "",
        "## Adaptations",
        "",
    ]
    adaptations = payload.get("adaptations", [])
    if not adaptations:
        lines.extend(["No semantic adaptations detected.", ""])
    for item in adaptations:
        lines.extend(
            [
                f"### {item.get('id', 'unknown')}",
                "",
                f"- Strategy: {item.get('strategy', '')}",
                f"- Criticality: {item.get('criticality', '')}",
                f"- Action: {item.get('action', {}).get('type', '')}",
                f"- Rationale: {item.get('rationale', '')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Machine Data",
            "",
            MACHINE_BLOCK_START,
            json.dumps(payload, indent=2, sort_keys=True),
            MACHINE_BLOCK_END,
            "",
        ]
    )
    return "\n".join(lines)


def plan_payload_hash(payload: dict[str, Any]) -> str:
    canonical = deepcopy(payload)
    canonical["plan_hash"] = ""
    machine_text = json.dumps(canonical, indent=2, sort_keys=True)
    return adaptation_state.plan_hash(machine_text)


def parse_plan(text: str) -> dict[str, Any]:
    start = text.find(MACHINE_BLOCK_START)
    if start == -1:
        raise ValueError("Adaptation plan is missing the machine-readable JSON block")
    json_start = start + len(MACHINE_BLOCK_START)
    end = text.find(MACHINE_BLOCK_END, json_start)
    if end == -1:
        raise ValueError("Adaptation plan machine-readable JSON block is not closed")
    raw = text[json_start:end].strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"Adaptation plan machine-readable JSON is invalid: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("Adaptation plan machine-readable JSON must be an object")
    return payload


def replay_reproducible_adaptations(
    plugin_path: Path, payload: dict[str, Any]
) -> list[Path]:
    changed: list[Path] = []
    for item in payload.get("adaptations", []):
        if item.get("strategy") != "reproducible":
            continue
        changed.extend(_apply_adaptation_item(plugin_path, item))
    return changed


def apply_plan(repo_root: Path, plugin_path: Path) -> AdaptationReport:
    del repo_root
    plugin = plugin_path.resolve()
    plan_path = adaptation_state.plan_path(plugin)
    try:
        payload = parse_plan(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return AdaptationReport(
            plugin=plugin,
            adaptations=[],
            changed_paths=[],
            status="error",
            error=str(error),
        )

    adaptations = payload.get("adaptations", [])
    expected_plan_hash = payload.get("plan_hash")
    if expected_plan_hash and expected_plan_hash != plan_payload_hash(payload):
        return AdaptationReport(
            plugin=plugin,
            adaptations=adaptations,
            changed_paths=[],
            status="error",
            error="stale plan hash; rerun plugin adapt before --apply",
        )
    saved_state = adaptation_state.load(plugin)
    source_files = _all_source_files(adaptations)
    try:
        current_snapshot = adaptation_state.source_snapshot(plugin, source_files)
        target_paths = _target_paths(plugin, adaptations)
    except ValueError as error:
        return AdaptationReport(
            plugin=plugin,
            adaptations=adaptations,
            changed_paths=[],
            status="error",
            error=str(error),
        )
    expected_snapshot = saved_state.get("source_snapshot") or payload.get("source_snapshot")
    if expected_snapshot and expected_snapshot != current_snapshot:
        return AdaptationReport(
            plugin=plugin,
            adaptations=adaptations,
            changed_paths=[],
            status="error",
            error="stale source snapshot; rerun plugin adapt before --apply",
        )

    target_snapshots = _snapshot_paths(target_paths)
    changed_paths: list[Path] = []
    try:
        for item in adaptations:
            changed_paths.extend(_apply_adaptation_item(plugin, item))
    except Exception as error:
        _restore_snapshots(target_snapshots)
        return AdaptationReport(
            plugin=plugin,
            adaptations=adaptations,
            changed_paths=[],
            status="error",
            error=str(error),
        )

    for item in adaptations:
        item["source_snapshot"] = adaptation_state.source_snapshot(
            plugin, item.get("source_files", [])
        )
    payload["status"] = "applied"
    payload["source_snapshot"] = current_snapshot
    adaptation_state.save(plugin, payload)
    changed_paths.append(adaptation_state.state_path(plugin))

    return AdaptationReport(
        plugin=plugin,
        adaptations=adaptations,
        changed_paths=_unique_paths(changed_paths),
        status="applied",
    )


def _detect_hook_adaptations(plugin: Path) -> list[dict[str, Any]]:
    manifest_path = plugin / ".claude-plugin" / "plugin.json"
    manifest = _read_json(manifest_path)
    adaptations: list[dict[str, Any]] = []
    for event, definitions in sorted(manifest.get("hooks", {}).items()):
        event_id = event.lower()
        source_files = [".claude-plugin/plugin.json"]
        for command_path in _hook_command_paths(definitions):
            source_files.append(command_path)
        adaptations.append(
            {
                "id": f"hooks-{event_id}",
                "strategy": "semantic",
                "criticality": "critical",
                "rationale": (
                    f"Claude Code {event} hooks require human review before "
                    "mapping to Codex behavior."
                ),
                "source_files": sorted(set(source_files)),
                "target_files": [f"skills/generated-from-hooks/{event_id}/SKILL.md"],
                "action": {
                    "type": "write_review_stub",
                    "text": _review_stub(f"Claude Code hook {event}"),
                },
            }
        )
    return adaptations


def _detect_plugin_root_command_adaptations(plugin: Path) -> list[dict[str, Any]]:
    adaptations: list[dict[str, Any]] = []
    commands_dir = plugin / "commands"
    if not commands_dir.exists():
        return adaptations
    for command in sorted(commands_dir.glob("*.md")):
        text = command.read_text(encoding="utf-8")
        if CLAUDE_PLUGIN_ROOT_TOKEN not in text:
            continue
        relative = command.relative_to(plugin).as_posix()
        stem = command.stem
        adaptations.append(
            {
                "id": f"command-{stem}-plugin-root-path",
                "strategy": "semantic",
                "criticality": "non-critical",
                "rationale": (
                    "Claude Code command references ${CLAUDE_PLUGIN_ROOT}; "
                    "review path handling when converting to Codex skills."
                ),
                "source_files": [relative],
                "target_files": [f"skills/generated-from-commands/{stem}/SKILL.md"],
                "action": {
                    "type": "append_text",
                    "text": (
                        "\n\nReview note: this source command referenced "
                        "${CLAUDE_PLUGIN_ROOT}; verify the generated Codex skill "
                        "uses an equivalent plugin-root path.\n"
                    ),
                },
            }
        )
    return adaptations


def _append_text(
    plugin: Path, item: dict[str, Any], action: dict[str, Any]
) -> list[Path]:
    text = action.get("text", "")
    changed: list[Path] = []
    for relative in item.get("target_files", []):
        path = _safe_plugin_path(plugin, relative, "target")
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if text in existing:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(existing + text, encoding="utf-8")
        changed.append(path)
    return changed


def _apply_adaptation_item(plugin: Path, item: dict[str, Any]) -> list[Path]:
    action = item.get("action", {})
    action_type = action.get("type")
    if action_type == "append_text":
        return _append_text(plugin, item, action)
    if action_type == "write_review_stub":
        return _write_review_stub(plugin, item)
    raise ValueError(f"Unknown adaptation action: {action_type}")


def _target_paths(plugin: Path, adaptations: list[dict[str, Any]]) -> list[Path]:
    paths: list[Path] = []
    for item in adaptations:
        for relative in item.get("target_files", []):
            paths.append(_safe_plugin_path(plugin, relative, "target"))
    return _unique_paths(paths)


def _snapshot_paths(paths: list[Path]) -> dict[Path, bytes | None]:
    snapshots: dict[Path, bytes | None] = {}
    for path in paths:
        snapshots[path] = path.read_bytes() if path.exists() else None
    return snapshots


def _restore_snapshots(snapshots: dict[Path, bytes | None]) -> None:
    for path, content in snapshots.items():
        if content is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _safe_plugin_path(plugin: Path, relative: str, label: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise ValueError(f"Adaptation {label} path is outside plugin: {relative}")
    plugin_root = plugin.resolve()
    resolved = (plugin_root / path).resolve()
    try:
        resolved.relative_to(plugin_root)
    except ValueError as error:
        raise ValueError(
            f"Adaptation {label} path is outside plugin: {relative}"
        ) from error
    return plugin / path


def _write_review_stub(plugin: Path, item: dict[str, Any]) -> list[Path]:
    text = item.get("action", {}).get("text", _review_stub(item.get("id", "adaptation")))
    changed: list[Path] = []
    for relative in item.get("target_files", []):
        path = _safe_plugin_path(plugin, relative, "target")
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        changed.append(path)
    return changed


def _hook_command_paths(definitions: Any) -> list[str]:
    paths: list[str] = []
    _collect_hook_command_paths(definitions, paths)
    return paths


def _collect_hook_command_paths(value: Any, paths: list[str]) -> None:
    if isinstance(value, dict):
        command = value.get("command")
        if isinstance(command, str):
            paths.append(command)
        for child in value.values():
            _collect_hook_command_paths(child, paths)
    elif isinstance(value, list):
        for child in value:
            _collect_hook_command_paths(child, paths)


def _all_source_files(adaptations: list[dict[str, Any]]) -> list[str]:
    source_files: set[str] = set()
    for item in adaptations:
        for source_file in item.get("source_files", []):
            source_files.add(str(source_file))
    return sorted(source_files)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _review_stub(subject: str) -> str:
    return (
        "---\n"
        f"name: generated-{_slug(subject)}\n"
        f"description: Review semantic adaptation for {subject}.\n"
        "---\n\n"
        "This generated placeholder requires manual semantic review before use.\n"
    )


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value)
