"""Filesystem reconciliation for dual-target plugin marketplaces."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from convert_cc_to_codex import Converter, load_repo_config
from convert_codex_to_cc import ReverseConverter
import adaptation
import adaptation_state
from marketplace_sync import (
    plugin_source_path,
    reconcile_order,
    remove_entry,
    seed_cc_marketplace,
    seed_codex_marketplace,
    upsert_cc_entry,
    upsert_codex_entry,
)
from plugin_state import load as load_state
from plugin_state import new_plugin_state, save as save_state


@dataclass
class PluginResult:
    name: str
    status: str
    target: str
    error: str = ""


@dataclass
class ReconcileReport:
    results: list[PluginResult]
    changed_paths: list[Path]

    @property
    def exit_code(self) -> int:
        if self.changed_paths:
            return 1
        return 0 if all(result.status == "synced" for result in self.results) else 1


class Reconciler:
    def __init__(self, repo_root: Path, *, dry_run: bool = False):
        self.repo_root = repo_root.resolve()
        self.dry_run = dry_run
        self.config = load_repo_config(self.repo_root)
        self.marketplace_state_path = self.repo_root / self.config["marketplace_state"]
        self.results: list[PluginResult] = []

    def attach_marketplace(
        self,
        source: str,
        *,
        only: set[str] | None = None,
        exclude: set[str] | None = None,
    ) -> ReconcileReport:
        self._validate_source(source)
        canonical_path = self._marketplace_path(source)
        canonical = self._read_json(canonical_path)
        selected_entries = [
            entry
            for entry in canonical.get("plugins", [])
            if (only is None or entry["name"] in only)
            and (exclude is None or entry["name"] not in exclude)
        ]

        target = self._opposite(source)
        state = {
            "version": 1,
            "source_of_truth": source,
            "source_marketplace": self._rel(canonical_path),
            "targets": {target: self.config[self._marketplace_config_key(target)]},
            "plugins": {},
        }
        for entry in selected_entries:
            name = entry["name"]
            plugin_path = self._entry_plugin_path(source, entry)
            plugin_state = new_plugin_state(name, source)
            save_state(plugin_path / ".plugin-cross-port.yaml", plugin_state)
            state["plugins"][name] = {
                "path": self._rel(plugin_path),
                "source_of_truth": source,
                "status": "synced",
            }
        save_state(self.marketplace_state_path, state)
        return self._reconcile(selected_entries=selected_entries)

    def sync(
        self,
        *,
        changed_only: set[str] | None = None,
        stage: bool = False,
    ) -> ReconcileReport:
        if changed_only is not None:
            validation = self._validate_staged_generated_edits(changed_only)
            if validation is not None:
                return validation
        if self.dry_run:
            return self._dry_run_reconcile(changed_only=changed_only)
        report = self._reconcile(changed_only=changed_only)
        if stage and report.changed_paths == [] and report.exit_code == 0:
            subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True)
        return report

    def check(self) -> ReconcileReport:
        with tempfile.TemporaryDirectory() as directory:
            copy_root = Path(directory) / "repo"
            shutil.copytree(self.repo_root, copy_root, ignore=shutil.ignore_patterns(".git"))
            before = _file_hashes(self.repo_root)
            temp_report = Reconciler(copy_root)._reconcile()
            after = _file_hashes(copy_root)
            changed = [
                self.repo_root / path
                for path in sorted(set(before) | set(after))
                if before.get(path) != after.get(path)
            ]
            return ReconcileReport(temp_report.results, changed)

    def _dry_run_reconcile(self, *, changed_only: set[str] | None = None) -> ReconcileReport:
        with tempfile.TemporaryDirectory() as directory:
            copy_root = Path(directory) / "repo"
            shutil.copytree(self.repo_root, copy_root, ignore=shutil.ignore_patterns(".git"))
            before = _file_hashes(self.repo_root)
            temp_report = Reconciler(copy_root)._reconcile(changed_only=changed_only)
            after = _file_hashes(copy_root)
            changed = [
                self.repo_root / path
                for path in sorted(set(before) | set(after))
                if before.get(path) != after.get(path)
            ]
            return ReconcileReport(temp_report.results, changed)

    def _reconcile(
        self,
        *,
        selected_entries: list[dict[str, Any]] | None = None,
        changed_only: set[str] | None = None,
    ) -> ReconcileReport:
        self.results = []
        state = self._load_marketplace_state()
        source = state["source_of_truth"]
        target = self._opposite(source)
        canonical_path = self.repo_root / state["source_marketplace"]
        canonical = self._read_json(canonical_path)
        canonical_entries = selected_entries or canonical.get("plugins", [])
        if changed_only is not None:
            canonical_entries = [
                entry for entry in canonical_entries if entry.get("name") in changed_only
            ]
        canonical_names = [entry["name"] for entry in canonical.get("plugins", [])]
        active_names = [entry["name"] for entry in canonical_entries]

        sibling_path = self._marketplace_path(target)
        sibling = self._seed_or_load_marketplace(target, source, canonical, sibling_path)

        if selected_entries is None and changed_only is None:
            self._delete_removed_plugins(state, set(canonical_names))

        for entry in canonical_entries:
            name = entry["name"]
            plugin_path = self._entry_plugin_path(source, entry)
            plugin_state = load_state(
                plugin_path / ".plugin-cross-port.yaml",
                default=new_plugin_state(name, source),
            )
            plugin_source = plugin_state.get("source_of_truth", source)
            plugin_target = self._opposite(plugin_source)
            snapshot = self._snapshot_plugin(plugin_path)
            try:
                self._run_converter(plugin_path, plugin_source)
                manifest = self._manifest(plugin_path, plugin_source)
                source_path = plugin_source_path(
                    plugin_path,
                    self.repo_root,
                    Path(self.config["plugins_dir"]),
                )
                status = "synced"
                error = ""
                state_warnings: list[str] = []
                result_warning = ""
                stale_adaptation: dict[str, Any] | None = None
                adaptation_payload = self._load_adaptation_state(plugin_path)
                if adaptation_payload:
                    adaptation.replay_reproducible_adaptations(
                        plugin_path, adaptation_payload
                    )
                    stale_adaptation = adaptation_state.classify_staleness(
                        adaptation_payload, plugin_path
                    )
                    stale_status = stale_adaptation["status"]
                    if stale_status == "stale-critical":
                        status = "needs-review"
                        error = "stale critical adaptation requires review"
                    elif stale_status == "stale-non-critical":
                        warning = "stale non-critical adaptation"
                        state_warnings.append(warning)
                        result_warning = warning
                if target == "codex":
                    upsert_codex_entry(
                        sibling, manifest, source_path, status, "Development"
                    )
                elif status == "synced":
                    upsert_cc_entry(sibling, manifest, source_path, "development")
                else:
                    remove_entry(sibling, manifest["name"])
                if plugin_source != source:
                    self._update_canonical_entry(
                        canonical, plugin_source, manifest, source_path
                    )
                plugin_state = self._load_generated_plugin_state(
                    plugin_path, name, plugin_source
                )
                plugin_state["status"] = status
                if error and status != "synced":
                    plugin_state["last_error"] = error
                elif "last_error" in plugin_state:
                    del plugin_state["last_error"]
                if state_warnings:
                    plugin_state["warnings"] = _as_list(
                        plugin_state.get("warnings", [])
                    ) + state_warnings
                if stale_adaptation and stale_adaptation["status"] != "current":
                    plugin_state["stale_adaptation"] = stale_adaptation
                elif "stale_adaptation" in plugin_state:
                    del plugin_state["stale_adaptation"]
                save_state(plugin_path / ".plugin-cross-port.yaml", plugin_state)
                state["plugins"][name] = {
                    "path": self._rel(plugin_path),
                    "source_of_truth": plugin_source,
                    "status": status,
                }
                if error:
                    state["plugins"][name]["last_error"] = error
                if state_warnings:
                    state["plugins"][name]["warnings"] = state_warnings
                self.results.append(
                    PluginResult(name, status, plugin_target, error or result_warning)
                )
            except BaseException as error:
                self._restore_plugin(plugin_path, snapshot)
                status = "failed"
                state.setdefault("plugins", {})[name] = {
                    "path": self._rel(plugin_path),
                    "source_of_truth": plugin_source,
                    "status": status,
                    "last_error": str(error),
                }
                failed_state = new_plugin_state(name, plugin_source)
                failed_state["status"] = status
                failed_state["last_error"] = str(error)
                if plugin_path.exists():
                    save_state(plugin_path / ".plugin-cross-port.yaml", failed_state)
                if target == "codex":
                    source_path = f"./plugins/{name}"
                    upsert_codex_entry(
                        sibling,
                        {"name": name},
                        source_path,
                        status,
                        "Development",
                    )
                else:
                    remove_entry(sibling, name)
                self.results.append(PluginResult(name, status, plugin_target, str(error)))

        order_names = canonical_names if changed_only is not None else active_names
        if target == "codex":
            sibling = reconcile_order(sibling, order_names)
        else:
            synced_names = [
                name
                for name in order_names
                if any(result.name == name and result.status == "synced" for result in self.results)
                or changed_only is not None
            ]
            sibling = reconcile_order(sibling, synced_names)

        self._write_json(sibling_path, sibling)
        self._write_json(canonical_path, canonical)
        save_state(self.marketplace_state_path, state)
        return ReconcileReport(self.results, [])

    def _load_adaptation_state(self, plugin_path: Path) -> dict[str, Any]:
        state_path = adaptation_state.state_path(plugin_path)
        if not state_path.exists():
            return {}
        return adaptation_state.load(state_path)

    def _load_generated_plugin_state(
        self, plugin_path: Path, name: str, source: str
    ) -> dict[str, Any]:
        path = plugin_path / ".plugin-cross-port.yaml"
        default = new_plugin_state(name, source)
        try:
            return load_state(path, default=default)
        except ValueError:
            return _load_converter_legacy_state(path, default)

    def _load_marketplace_state(self) -> dict[str, Any]:
        if not self.marketplace_state_path.exists():
            raise ValueError("Repository marketplace state is missing")
        return load_state(self.marketplace_state_path, default={})

    def _validate_staged_generated_edits(
        self, changed_only: set[str]
    ) -> ReconcileReport | None:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if staged.returncode != 0:
            return None
        staged_paths = staged.stdout.splitlines()
        state = self._load_marketplace_state()
        # Reconcile a throwaway copy to learn the authoritative generated content.
        # A staged generated-side file is only an illegal manual edit when it
        # diverges from what reconcile would produce; tool-produced output that
        # already matches the source of truth is allowed.
        with tempfile.TemporaryDirectory() as directory:
            copy_root = Path(directory) / "repo"
            shutil.copytree(self.repo_root, copy_root, ignore=shutil.ignore_patterns(".git"))
            Reconciler(copy_root)._reconcile(changed_only=changed_only)
            for name in changed_only:
                plugin_info = state.get("plugins", {}).get(name, {})
                plugin_path = self.repo_root / plugin_info.get("path", f"plugins/{name}")
                plugin_state = load_state(
                    plugin_path / ".plugin-cross-port.yaml",
                    default=new_plugin_state(name, plugin_info.get("source_of_truth", state["source_of_truth"])),
                )
                source = plugin_state.get("source_of_truth", state["source_of_truth"])
                manually_maintained = set(plugin_state.get("manually_maintained", []) or [])
                prefix = f"plugins/{name}/"
                for rel_path in staged_paths:
                    if not rel_path.startswith(prefix):
                        continue
                    plugin_rel = rel_path[len(prefix):]
                    if plugin_rel in manually_maintained:
                        continue
                    if not self._is_generated_side_path(plugin_rel, source):
                        continue
                    staged_file = self.repo_root / rel_path
                    reconciled_file = copy_root / rel_path
                    staged_content = (
                        staged_file.read_text(encoding="utf-8") if staged_file.exists() else None
                    )
                    reconciled_content = (
                        reconciled_file.read_text(encoding="utf-8")
                        if reconciled_file.exists()
                        else None
                    )
                    if staged_content != reconciled_content:
                        target = self._opposite(source)
                        message = (
                            f"Generated-side edit diverges from source of truth: {rel_path}. "
                            f"Source of truth: {source}"
                        )
                        return ReconcileReport(
                            [PluginResult(name, "failed", target, message)],
                            [],
                        )
        return None

    def _is_generated_side_path(self, plugin_rel: str, source: str) -> bool:
        if source == "claude-code":
            return plugin_rel.startswith(".codex-plugin/") or plugin_rel.startswith(
                "skills/generated-from-commands/"
            )
        return plugin_rel.startswith(".claude-plugin/") or plugin_rel.startswith(
            "commands/generated-from-codex-"
        )

    def _delete_removed_plugins(self, state: dict[str, Any], canonical_names: set[str]) -> None:
        for name, info in list(state.get("plugins", {}).items()):
            if name in canonical_names:
                continue
            try:
                plugin_path = (self.repo_root / info["path"]).resolve()
                plugins_dir = (self.repo_root / self.config["plugins_dir"]).resolve()
                if plugin_path.name != name:
                    raise ValueError(f"Plugin path basename does not match {name}")
                if plugins_dir not in plugin_path.parents:
                    raise ValueError(f"Plugin path is outside plugins_dir: {plugin_path}")
                if plugin_path.exists():
                    shutil.rmtree(plugin_path)
                del state["plugins"][name]
            except Exception as error:
                self.results.append(PluginResult(name, "failed", "", str(error)))

    def _run_converter(self, plugin_path: Path, source: str) -> None:
        if source == "claude-code":
            code = Converter(
                plugin_path,
                self.repo_root,
                False,
                True,
                False,
                sync_marketplace=False,
            ).run()
        else:
            code = ReverseConverter(
                plugin_path,
                self.repo_root,
                False,
                True,
                False,
                sync_marketplace=False,
            ).run()
        if code != 0:
            raise RuntimeError(f"converter exited {code}")

    def _update_canonical_entry(
        self,
        canonical: dict[str, Any],
        plugin_source: str,
        manifest: dict[str, Any],
        source_path: str,
    ) -> None:
        if plugin_source == "codex":
            upsert_cc_entry(canonical, manifest, source_path, "development")
        else:
            upsert_codex_entry(canonical, manifest, source_path, "synced", "Development")

    def _entry_plugin_path(self, source: str, entry: dict[str, Any]) -> Path:
        if source == "claude-code":
            rel = entry.get("source", f"./plugins/{entry['name']}")
        else:
            rel = entry.get("source", {}).get("path", f"./plugins/{entry['name']}")
        return (self.repo_root / rel).resolve()

    def _manifest(self, plugin_path: Path, source: str) -> dict[str, Any]:
        if source == "claude-code":
            return self._read_json(plugin_path / ".claude-plugin/plugin.json")
        return self._read_json(plugin_path / ".codex-plugin/plugin.json")

    def _seed_or_load_marketplace(
        self,
        target: str,
        source: str,
        canonical: dict[str, Any],
        path: Path,
    ) -> dict[str, Any]:
        if path.exists():
            return self._read_json(path)
        if target == "codex":
            return seed_codex_marketplace(canonical)
        return seed_cc_marketplace(canonical)

    def _snapshot_plugin(self, plugin_path: Path) -> Path | None:
        if not plugin_path.exists():
            return None
        temp_dir = Path(tempfile.mkdtemp(prefix="plugin-cross-port-snapshot-"))
        snapshot = temp_dir / plugin_path.name
        shutil.copytree(plugin_path, snapshot)
        return snapshot

    def _restore_plugin(self, plugin_path: Path, snapshot: Path | None) -> None:
        if plugin_path.exists():
            shutil.rmtree(plugin_path)
        if snapshot is not None and snapshot.exists():
            shutil.copytree(snapshot, plugin_path)
            shutil.rmtree(snapshot.parent)

    def _marketplace_path(self, source: str) -> Path:
        return self.repo_root / self.config[self._marketplace_config_key(source)]

    def _marketplace_config_key(self, source: str) -> str:
        return "cc_marketplace" if source == "claude-code" else "codex_marketplace"

    def _opposite(self, source: str) -> str:
        return "codex" if source == "claude-code" else "claude-code"

    def _validate_source(self, source: str) -> None:
        if source not in {"claude-code", "codex"}:
            raise ValueError(f"Unsupported source: {source}")

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _rel(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.repo_root))


def _file_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _load_converter_legacy_state(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    payload: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - "):
            if current_key is not None:
                payload.setdefault(current_key, []).append(
                    _parse_converter_scalar(raw_line[4:].strip())
                )
            continue
        if raw_line.startswith("  "):
            if current_key is None:
                continue
            key, sep, value = raw_line.strip().partition(":")
            if sep:
                payload.setdefault(current_key, {})[key.strip()] = _parse_converter_scalar(
                    value.strip()
                )
            continue
        key, sep, value = raw_line.partition(":")
        if not sep:
            continue
        current_key = key.strip()
        if value.strip():
            payload[current_key] = _parse_converter_scalar(value.strip())
            current_key = None
        elif current_key in {"warnings", "manually_maintained"}:
            payload[current_key] = []
        else:
            payload[current_key] = {}
    merged = dict(default)
    merged.update(payload)
    return merged


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in {"", "[]", None}:
        return []
    return [value]


def _parse_converter_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None"}:
        return None
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value
