import json
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
