"""Dependency-free JSON-compatible YAML state for plugin-cross-port."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def loads(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _loads_legacy(text)
    if not isinstance(payload, dict):
        raise ValueError("State file must contain an object")
    return payload


def load(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    return loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(payload), encoding="utf-8")


def new_plugin_state(name: str, source_of_truth: str) -> dict[str, Any]:
    return {
        "version": 2,
        "plugin": name,
        "source_of_truth": source_of_truth,
        "status": "synced",
        "manually_maintained": [],
    }


def _loads_legacy(text: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        if raw_line.startswith("  - "):
            if current_list_key is None:
                raise ValueError("Legacy list item without a key")
            payload[current_list_key].append(_parse_scalar(raw_line[4:].strip()))
            continue

        if raw_line.startswith((" ", "\t")):
            raise ValueError("Nested legacy mappings are not supported")

        key, sep, value = raw_line.partition(":")
        if not sep:
            raise ValueError(f"Invalid legacy state line: {raw_line}")
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("Legacy state key cannot be empty")

        if value == "":
            payload[key] = []
            current_list_key = key
        else:
            payload[key] = _parse_scalar(value)
            current_list_key = None

    return payload


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value
