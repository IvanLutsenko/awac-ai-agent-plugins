#!/usr/bin/env python3
"""CLI entry point for plugin-cross-port marketplace reconciliation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from convert_cc_to_codex import Converter
from convert_codex_to_cc import ReverseConverter
from marketplace_sync import plugin_source_path, upsert_cc_entry, upsert_codex_entry
from plugin_state import load as load_state
from plugin_state import new_plugin_state, save as save_state
from reconcile import ReconcileReport, Reconciler


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    try:
        if args.area == "marketplace":
            return run_marketplace(args, repo_root)
        if args.area == "plugin":
            return run_plugin(args, repo_root)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    parser.error("missing command")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plugin Cross-Port Marketplace")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    subparsers = parser.add_subparsers(dest="area", required=True)

    marketplace = subparsers.add_parser("marketplace")
    marketplace_sub = marketplace.add_subparsers(dest="command", required=True)
    attach = marketplace_sub.add_parser("attach")
    attach.add_argument("--source", choices=["claude-code", "codex"], required=True)
    attach.add_argument("--only")
    attach.add_argument("--exclude")
    sync = marketplace_sub.add_parser("sync")
    sync.add_argument("--changed-only")
    sync.add_argument("--stage", action="store_true")
    marketplace_sub.add_parser("check")

    plugin = subparsers.add_parser("plugin")
    plugin_sub = plugin.add_subparsers(dest="command", required=True)
    convert = plugin_sub.add_parser("convert")
    convert.add_argument("path")
    convert.add_argument("--from", dest="from_source", choices=["claude-code", "codex"], required=True)
    convert.add_argument("--to", dest="to_target", choices=["claude-code", "codex"], required=True)
    attach_plugin = plugin_sub.add_parser("attach")
    attach_plugin.add_argument("path")
    attach_plugin.add_argument("--source", choices=["claude-code", "codex"], required=True)
    switch = plugin_sub.add_parser("switch-source")
    switch.add_argument("path")
    switch.add_argument("--to", dest="to_source", choices=["claude-code", "codex"], required=True)
    return parser


def run_marketplace(args: argparse.Namespace, repo_root: Path) -> int:
    reconciler = Reconciler(repo_root)
    if args.command == "attach":
        report = reconciler.attach_marketplace(
            args.source,
            only=parse_csv(args.only),
            exclude=parse_csv(args.exclude),
        )
    elif args.command == "sync":
        report = reconciler.sync(changed_only=parse_csv(args.changed_only), stage=args.stage)
    elif args.command == "check":
        report = reconciler.check()
    else:
        raise ValueError(f"Unknown marketplace command: {args.command}")
    print_summary(report)
    return report.exit_code


def run_plugin(args: argparse.Namespace, repo_root: Path) -> int:
    if args.command == "convert":
        return plugin_convert(args, repo_root)
    if args.command == "attach":
        report = plugin_attach(args, repo_root)
        print_summary(report)
        return report.exit_code
    if args.command == "switch-source":
        report = plugin_switch_source(args, repo_root)
        print_summary(report)
        return report.exit_code
    raise ValueError(f"Unknown plugin command: {args.command}")


def plugin_convert(args: argparse.Namespace, repo_root: Path) -> int:
    if args.from_source == args.to_target:
        raise ValueError("--from and --to must be different")
    plugin_path = resolve_plugin_path(repo_root, args.path)
    if args.from_source == "claude-code" and args.to_target == "codex":
        return Converter(
            plugin_path,
            repo_root,
            False,
            True,
            False,
            sync_marketplace=False,
        ).run()
    if args.from_source == "codex" and args.to_target == "claude-code":
        return ReverseConverter(
            plugin_path,
            repo_root,
            False,
            True,
            False,
            sync_marketplace=False,
        ).run()
    raise ValueError("Unsupported conversion direction")


def plugin_attach(args: argparse.Namespace, repo_root: Path) -> ReconcileReport:
    reconciler = Reconciler(repo_root)
    state = load_state(reconciler.marketplace_state_path, default={})
    if not state:
        raise ValueError("Repository marketplace state is missing")
    plugin_path = resolve_plugin_path(repo_root, args.path)
    name = plugin_path.name
    manifest = read_manifest(plugin_path, args.source)
    name = manifest.get("name", name)
    plugin_state = new_plugin_state(name, args.source)
    save_state(plugin_path / ".plugin-cross-port.yaml", plugin_state)
    state.setdefault("plugins", {})[name] = {
        "path": str(plugin_path.relative_to(repo_root)),
        "source_of_truth": args.source,
        "status": "synced",
    }
    save_state(reconciler.marketplace_state_path, state)
    append_to_canonical(reconciler, state, plugin_path, args.source, manifest)
    return reconciler.sync(changed_only={name})


def plugin_switch_source(args: argparse.Namespace, repo_root: Path) -> ReconcileReport:
    reconciler = Reconciler(repo_root)
    check = reconciler.check()
    if check.exit_code != 0:
        return check
    plugin_path = resolve_plugin_path(repo_root, args.path)
    manifest_path(args.to_source, plugin_path)
    name = plugin_path.name
    state_path = plugin_path / ".plugin-cross-port.yaml"
    state = load_state(state_path, default=new_plugin_state(name, args.to_source))
    state["source_of_truth"] = args.to_source
    save_state(state_path, state)
    return reconciler.sync(changed_only={state.get("plugin", name)})


def append_to_canonical(
    reconciler: Reconciler,
    state: dict[str, Any],
    plugin_path: Path,
    plugin_source: str,
    manifest: dict[str, Any],
) -> None:
    canonical_path = reconciler.repo_root / state["source_marketplace"]
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    source_path = plugin_source_path(
        plugin_path,
        reconciler.repo_root,
        Path(reconciler.config["plugins_dir"]),
    )
    canonical_source = state["source_of_truth"]
    if canonical_source == "claude-code":
        upsert_cc_entry(canonical, manifest, source_path, "development")
    else:
        upsert_codex_entry(canonical, manifest, source_path, "synced", "Development")
    canonical_path.write_text(
        json.dumps(canonical, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_manifest(plugin_path: Path, source: str) -> dict[str, Any]:
    path = manifest_path(source, plugin_path)
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_path(source: str, plugin_path: Path) -> Path:
    if source == "claude-code":
        path = plugin_path / ".claude-plugin/plugin.json"
    else:
        path = plugin_path / ".codex-plugin/plugin.json"
    if not path.exists():
        raise ValueError(f"Missing authoritative manifest: {path}")
    return path


def resolve_plugin_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def parse_csv(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


def print_summary(report: ReconcileReport) -> None:
    synced = sum(1 for result in report.results if result.status == "synced")
    needs_review = sum(1 for result in report.results if result.status == "needs-review")
    failed = sum(1 for result in report.results if result.status == "failed")
    print("Plugin Cross-Port Marketplace")
    print("=============================")
    print(f"Synced:       {synced}")
    print(f"Needs review: {needs_review}")
    print(f"Failed:       {failed}")
    for result in report.results:
        if result.status == "failed":
            print(f"\nFAILED {result.name} -> {result.target}: {result.error}")
    if report.changed_paths:
        print("\nStale output:")
        for path in report.changed_paths:
            print(f"  {path}")


if __name__ == "__main__":
    sys.exit(main())
