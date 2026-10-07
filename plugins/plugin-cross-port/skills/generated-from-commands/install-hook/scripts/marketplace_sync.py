"""Pure marketplace transformations for plugin-cross-port."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


VALID_STATUSES = {"synced", "needs-review", "failed"}


def seed_codex_marketplace(canonical: dict[str, Any]) -> dict[str, Any]:
    name = canonical.get("name", "cross-port")
    display_name = canonical.get("interface", {}).get(
        "displayName", name.replace("-", " ").title()
    )
    return {"name": name, "interface": {"displayName": display_name}, "plugins": []}


def seed_cc_marketplace(canonical: dict[str, Any]) -> dict[str, Any]:
    root = {
        key: canonical[key]
        for key in ("$schema", "name", "version", "description", "owner")
        if key in canonical
    }
    root.setdefault("name", "cross-port")
    root["plugins"] = []
    return root


def plugin_source_path(plugin_path: Path, repo_root: Path, plugins_dir: Path) -> str:
    root = repo_root.resolve()
    allowed_dir = (root / plugins_dir).resolve()
    resolved_plugin = plugin_path.resolve()
    if not _is_relative_to(resolved_plugin, allowed_dir):
        raise ValueError(f"Plugin path is outside plugins_dir: {plugin_path}")
    relative = os.path.relpath(resolved_plugin, root)
    return f"./{relative}"


def upsert_cc_entry(
    market: dict[str, Any],
    manifest: dict[str, Any],
    source_path: str,
    category: str,
) -> dict[str, Any]:
    entry = _find_or_append(market, manifest["name"])
    entry["name"] = manifest["name"]
    entry["version"] = manifest.get("version", "")
    entry["description"] = manifest.get("description", "")
    if "author" in manifest:
        entry["author"] = manifest["author"]
    entry["source"] = source_path
    entry["category"] = entry.get("category", category)
    return market


def upsert_codex_entry(
    market: dict[str, Any],
    manifest: dict[str, Any],
    source_path: str,
    status: str,
    category: str,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Unknown plugin status: {status}")

    entry = _find_or_append(market, manifest["name"])
    existing_policy = entry.get("policy", {})
    entry["name"] = manifest["name"]
    entry["source"] = {"source": "local", "path": source_path}
    entry["category"] = entry.get("category", category)

    installation = "AVAILABLE" if status == "synced" else "NOT_AVAILABLE"
    if status == "synced" and existing_policy.get("installation") == "INSTALLED_BY_DEFAULT":
        installation = "INSTALLED_BY_DEFAULT"

    policy = {
        "installation": installation,
        "authentication": existing_policy.get("authentication", "ON_INSTALL"),
    }
    if "products" in existing_policy:
        policy["products"] = existing_policy["products"]
    entry["policy"] = policy
    return market


def reconcile_order(market: dict[str, Any], canonical_names: list[str]) -> dict[str, Any]:
    by_name = {entry["name"]: entry for entry in market.get("plugins", [])}
    market["plugins"] = [by_name[name] for name in canonical_names if name in by_name]
    return market


def remove_entry(market: dict[str, Any], plugin_name: str) -> dict[str, Any]:
    market["plugins"] = [
        entry for entry in market.get("plugins", []) if entry.get("name") != plugin_name
    ]
    return market


def _find_or_append(market: dict[str, Any], plugin_name: str) -> dict[str, Any]:
    plugins = market.setdefault("plugins", [])
    for entry in plugins:
        if entry.get("name") == plugin_name:
            return entry
    entry = {"name": plugin_name}
    plugins.append(entry)
    return entry


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
