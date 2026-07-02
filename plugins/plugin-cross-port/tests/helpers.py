import json
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def plugin_side_root(root: Path, side: str) -> Path:
    if side == "claude-code":
        return root / ".claude-plugin" / "plugins"
    if side == "codex":
        return root / ".agents" / "plugins" / "plugins"
    raise ValueError(f"unsupported plugin side: {side}")


def write_plugin_file(
    root: Path, side: str, name: str, relative_path: str, content: str
) -> Path:
    path = plugin_side_root(root, side) / name / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_adaptation_state(root: Path, side: str, name: str, state: dict) -> Path:
    path = (
        plugin_side_root(root, side)
        / name
        / ".plugin-cross-port"
        / "adaptation-state.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def add_cc_command(
    repo: Path, plugin_name: str, command_name: str, body: str = "Body"
) -> Path:
    command = repo / "plugins" / plugin_name / "commands" / f"{command_name}.md"
    command.parent.mkdir(parents=True, exist_ok=True)
    command.write_text(
        f"---\ndescription: {command_name.title()} command\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return command


def add_cc_hook(repo: Path, plugin_name: str, event: str = "SessionStart") -> Path:
    plugin = repo / "plugins" / plugin_name
    manifest_path = plugin / ".claude-plugin" / "plugin.json"
    manifest = read_json(manifest_path)
    hook_path = plugin / "hooks" / f"{event.lower()}.sh"
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("#!/bin/bash\nprintf 'hook'\n", encoding="utf-8")
    manifest["hooks"] = {
        event: [
            {
                "type": "command",
                "command": f"hooks/{event.lower()}.sh",
                "timeout": 10,
            }
        ]
    }
    write_json(manifest_path, manifest)
    return hook_path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def make_cc_marketplace(repo: Path, names: list[str]) -> Path:
    path = repo / ".claude-plugin" / "marketplace.json"
    write_json(
        path,
        {
            "name": "sample-marketplace",
            "version": "1.0.0",
            "description": "Sample marketplace",
            "owner": {"name": "Tester"},
            "plugins": [
                {
                    "name": name,
                    "version": "1.0.0",
                    "description": f"{name} plugin.",
                    "source": f"./plugins/{name}",
                    "category": "development",
                }
                for name in names
            ],
        },
    )
    return path


def make_codex_marketplace(repo: Path, names: list[str]) -> Path:
    path = repo / ".agents" / "plugins" / "marketplace.json"
    write_json(
        path,
        {
            "name": "sample-marketplace",
            "interface": {"displayName": "Sample Marketplace"},
            "plugins": [
                {
                    "name": name,
                    "source": {"source": "local", "path": f"./plugins/{name}"},
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Development",
                }
                for name in names
            ],
        },
    )
    return path


def make_cc_plugin(repo: Path, name: str) -> Path:
    plugin = repo / "plugins" / name
    write_json(
        plugin / ".claude-plugin" / "plugin.json",
        {
            "name": name,
            "version": "1.0.0",
            "description": f"{name} plugin.",
            "author": {"name": "Tester"},
        },
    )
    return plugin


def make_codex_plugin(repo: Path, name: str) -> Path:
    plugin = repo / "plugins" / name
    write_json(
        plugin / ".codex-plugin" / "plugin.json",
        {
            "name": name,
            "version": "1.0.0",
            "description": f"{name} plugin.",
            "author": {"name": "Tester"},
            "skills": "./skills/",
            "interface": {
                "displayName": name.replace("-", " ").title(),
                "shortDescription": f"{name} plugin",
                "developerName": "Tester",
                "category": "Development",
                "capabilities": ["Read"],
            },
        },
    )
    skill = plugin / "skills" / "main" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("---\nname: main\ndescription: Main skill\n---\n\nBody\n", encoding="utf-8")
    return plugin
