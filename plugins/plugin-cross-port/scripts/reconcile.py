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
from marketplace_sync import (
    plugin_source_path,
    reconcile_order,
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
                if target == "codex":
                    upsert_codex_entry(sibling, manifest, source_path, status, "Development")
                else:
                    upsert_cc_entry(sibling, manifest, source_path, "development")
                if plugin_source != source:
                    self._update_canonical_entry(canonical, plugin_source, manifest, source_path)
                plugin_state = new_plugin_state(name, plugin_source)
                plugin_state["status"] = status
                save_state(plugin_path / ".plugin-cross-port.yaml", plugin_state)
                state["plugins"][name] = {
                    "path": self._rel(plugin_path),
                    "source_of_truth": plugin_source,
                    "status": status,
                }
                self.results.append(PluginResult(name, status, plugin_target))
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

    def _load_marketplace_state(self) -> dict[str, Any]:
        if not self.marketplace_state_path.exists():
            raise ValueError("Repository marketplace state is missing")
        return load_state(self.marketplace_state_path, default={})

    def _delete_removed_plugins(self, state: dict[str, Any], canonical_names: set[str]) -> None:
        for name, info in list(state.get("plugins", {}).items()):
            if name in canonical_names:
                continue
            try:
                plugin_path = (self.repo_root / info["path"]).resolve()
                plugins_dir = (self.repo_root / self.config["plugins_dir"]).resolve()
                if plugin_path.name != name:
                    raise ValueError(f"Plugin path basename does not match {name}")
                plugin_source_path(plugin_path, self.repo_root, Path(self.config["plugins_dir"]))
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
