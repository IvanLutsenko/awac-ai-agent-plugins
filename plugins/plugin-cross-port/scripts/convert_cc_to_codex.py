#!/usr/bin/env python3
"""
convert_cc_to_codex.py — Convert a Claude Code plugin to Codex format.

Usage:
    python3 scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root .
    python3 scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root . --dry-run
    python3 scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root . --force
    python3 scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root . --strict
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# YAML helpers (no external deps — minimal subset we actually need)
# ---------------------------------------------------------------------------

def _yaml_str(value: str) -> str:
    if any(c in value for c in (':', '#', '[', ']', '{', '}', ',', '&', '*', '?', '|', '-', '<', '>', '=', '!', '%', '@', '`', '"', "'")):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    if '\n' in value:
        lines = value.split('\n')
        body = '\n'.join('  ' + l for l in lines)
        return f"|\n{body}"
    return value


def _build_yaml(data: dict, indent: int = 0) -> list[str]:
    lines: list[str] = []
    pad = '  ' * indent
    for key, value in data.items():
        if isinstance(value, bool):
            lines.append(f"{pad}{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{pad}{key}: {value}")
        elif value is None:
            lines.append(f"{pad}{key}:")
        elif isinstance(value, str):
            lines.append(f"{pad}{key}: {_yaml_str(value)}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}:")
                for item in value:
                    if isinstance(item, str):
                        lines.append(f"{pad}  - {_yaml_str(item)}")
                    else:
                        lines.append(f"{pad}  - {item}")
        elif isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.extend(_build_yaml(value, indent + 1))
    return lines


def dump_yaml(data: dict) -> str:
    return '\n'.join(_build_yaml(data)) + '\n'


def _parse_yaml_simple(text: str) -> dict:
    """Parse the subset of YAML we write (flat and one-level nested lists only)."""
    result: dict = {}
    current_key: str | None = None
    current_list: list | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith('#'):
            continue

        # list item
        stripped = line.lstrip()
        if stripped.startswith('- ') and current_list is not None:
            item = stripped[2:].strip().strip("'")
            current_list.append(item)
            continue

        if ':' in line:
            key_part, _, val_part = line.partition(':')
            key = key_part.strip()
            val = val_part.strip()

            # Flush previous list
            if current_list is not None and current_key is not None:
                result[current_key] = current_list
                current_list = None
                current_key = None

            if val == '' or val == '|':
                # Could be a nested dict or list; treat as empty for our needs
                current_key = key
                current_list = []
                result[key] = current_list
            elif val == '[]':
                result[key] = []
                current_key = None
                current_list = None
            elif val.lower() == 'true':
                result[key] = True
                current_key = None
            elif val.lower() == 'false':
                result[key] = False
                current_key = None
            elif val.lstrip('-').isdigit():
                result[key] = int(val)
                current_key = None
            else:
                result[key] = val.strip("'")
                current_key = None
        else:
            pass  # continuation line; skip for our simple usage

    if current_list is not None and current_key is not None:
        result[current_key] = current_list

    return result


# ---------------------------------------------------------------------------
# Repo-level config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict = {
    'plugins_dir': 'plugins',
    'codex_marketplace': '.agents/plugins/marketplace.json',
    'default_source_of_truth': 'claude-code',
}


def load_repo_config(repo_root: Path) -> dict:
    path = repo_root / '.plugin-cross-port.config.yaml'
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    raw = _parse_yaml_simple(path.read_text(encoding='utf-8'))
    return {**DEFAULT_CONFIG, **{k: v for k, v in raw.items() if k in DEFAULT_CONFIG}}


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Body excludes frontmatter block."""
    if not text.startswith('---'):
        return {}, text
    end = text.find('\n---', 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 4:].lstrip('\n')
    fm: dict = {}
    for line in fm_block.splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            fm[k.strip()] = v.strip().strip('"')
    return fm, body


# ---------------------------------------------------------------------------
# Core conversion logic
# ---------------------------------------------------------------------------

class Converter:
    def __init__(
        self,
        plugin_path: Path,
        repo_root: Path,
        dry_run: bool,
        force: bool,
        strict: bool,
    ):
        self.plugin_path = plugin_path.resolve()
        self.repo_root = repo_root.resolve()
        self.dry_run = dry_run
        self.force = force
        self.strict = strict
        self.warnings: list[str] = []
        self.created: list[str] = []
        self.skipped: list[str] = []
        self.config = load_repo_config(repo_root.resolve())

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.repo_root))
        except ValueError:
            return str(path)

    def _write(self, path: Path, content: str, *, overwrite: bool = False) -> bool:
        """Write file; return True if written. Respects dry_run / force / overwrite."""
        if path.exists() and not overwrite and not self.force:
            self.skipped.append(self._rel(path))
            return False
        if self.dry_run:
            print(f"  [dry-run] would write: {self._rel(path)}")
            self.created.append(self._rel(path))
            return True
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        self.created.append(self._rel(path))
        return True

    def _copy(self, src: Path, dst: Path) -> bool:
        if dst.exists() and not self.force:
            self.skipped.append(self._rel(dst))
            return False
        if self.dry_run:
            print(f"  [dry-run] would copy: {self._rel(src)} -> {self._rel(dst)}")
            self.created.append(self._rel(dst))
            return True
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        self.created.append(self._rel(dst))
        return True

    # ------------------------------------------------------------------

    def load_cc_manifest(self) -> dict:
        manifest_path = self.plugin_path / '.claude-plugin' / 'plugin.json'
        if not manifest_path.exists():
            print(f"ERROR: Not a Claude Code plugin — missing {manifest_path}")
            sys.exit(1)
        return json.loads(manifest_path.read_text(encoding='utf-8'))

    def load_decision_file(self) -> dict:
        path = self.plugin_path / '.plugin-cross-port.yaml'
        if not path.exists():
            return {}
        return _parse_yaml_simple(path.read_text(encoding='utf-8'))

    def build_codex_manifest(self, cc: dict) -> dict:
        name = cc.get('name', self.plugin_path.name)
        version = cc.get('version', '0.1.0')
        description = cc.get('description', '')
        author_name = ''
        author = cc.get('author', {})
        if isinstance(author, dict):
            author_name = author.get('name', '')
        elif isinstance(author, str):
            author_name = author

        # Display name: Title Case
        display_name = ' '.join(w.capitalize() for w in name.replace('-', ' ').split())

        # Short description: first sentence, max 80 chars
        short = description.split('.')[0][:80]

        return {
            'name': name,
            'version': version,
            'description': description,
            'author': {'name': author_name} if author_name else {},
            'skills': './skills/',
            'interface': {
                'displayName': display_name,
                'shortDescription': short,
                'developerName': author_name,
                'category': 'Development',
                'capabilities': ['Read', 'Write'],
            },
        }

    def convert_command_to_skill(self, cmd_path: Path, plugin_name: str) -> str:
        text = cmd_path.read_text(encoding='utf-8')
        fm, body = parse_frontmatter(text)
        command_name = cmd_path.stem
        description = fm.get('description', f'Command: {command_name}')
        skill_name = f'{plugin_name}-{command_name}'
        trigger_hint = f'Use when the user invokes /{command_name}.'

        skill_description = description
        if not skill_description.rstrip().endswith('.'):
            skill_description = skill_description.rstrip() + '.'
        skill_description = f'{skill_description} {trigger_hint}'

        return (
            f'---\n'
            f'name: {skill_name}\n'
            f'description: {skill_description}\n'
            f'version: 0.1.0\n'
            f'---\n\n'
            f'> Converted from Claude Code command `/{command_name}`.\n'
            f'> Review and adapt: remove `allowed-tools` references and any `${{CLAUDE_PLUGIN_ROOT}}` paths.\n\n'
            f'{body}'
        )

    def update_codex_marketplace(self, plugin_name: str) -> None:
        marketplace_path = self.repo_root / self.config['codex_marketplace']

        if marketplace_path.exists():
            data = json.loads(marketplace_path.read_text(encoding='utf-8'))
        else:
            data = {'plugins': []}

        plugins: list[dict] = data.get('plugins', [])

        # Idempotent: update existing entry or append new one
        existing_idx = next((i for i, p in enumerate(plugins) if p.get('name') == plugin_name), None)

        entry: dict[str, Any] = {
            'name': plugin_name,
            'source': {
                'source': 'local',
                'path': f'./plugins/{plugin_name}',
            },
            'policy': {
                'installation': 'AVAILABLE',
                'authentication': 'ON_INSTALL',
            },
            'category': 'Development',
        }

        if existing_idx is not None:
            plugins[existing_idx] = entry
        else:
            plugins.append(entry)

        data['plugins'] = plugins
        content = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
        self._write(marketplace_path, content, overwrite=True)

    def run(self) -> int:
        cc = self.load_cc_manifest()
        plugin_name: str = cc.get('name', self.plugin_path.name)
        decision = self.load_decision_file()
        manually_maintained: list[str] = decision.get('manually_maintained', []) or []

        # Guard: refuse to override source_of_truth without --force
        existing_sot = decision.get('source_of_truth', '')
        if existing_sot == 'codex' and not self.force:
            print(f"ERROR: {plugin_name} has source_of_truth=codex in .plugin-cross-port.yaml")
            print("This plugin was set up with Codex as source of truth.")
            print("Running CC→Codex would silently flip that. Use --force to override.")
            return 1

        print(f"\nPlugin Cross-Port: {plugin_name}")
        print('=' * (20 + len(plugin_name)))

        # --- .codex-plugin/plugin.json ---
        codex_manifest_path = self.plugin_path / '.codex-plugin' / 'plugin.json'
        if self._rel(codex_manifest_path) not in manually_maintained:
            codex = self.build_codex_manifest(cc)
            self._write(
                codex_manifest_path,
                json.dumps(codex, indent=2, ensure_ascii=False) + '\n',
                overwrite=True,
            )
        else:
            print(f"  Skipping manually maintained: {self._rel(codex_manifest_path)}")

        # --- .mcp.json ---
        mcp_src = self.plugin_path / '.mcp.json'
        if mcp_src.exists():
            # .mcp.json lives at plugin root — same location for both CC and Codex
            pass  # already shared, no copy needed

        # --- skills/ — shared, no action ---
        skills_dir = self.plugin_path / 'skills'
        existing_skills = list(skills_dir.glob('*/SKILL.md')) if skills_dir.exists() else []
        # Filter out generated ones for the count
        non_generated = [
            s for s in existing_skills
            if 'generated-from-commands' not in str(s)
        ]

        # --- commands/ → skills/generated-from-commands/ ---
        commands_dir = self.plugin_path / 'commands'
        converted_count = 0
        if commands_dir.exists():
            cmd_files = sorted(commands_dir.glob('*.md'))
            for cmd_file in cmd_files:
                command_name = cmd_file.stem
                out_dir = self.plugin_path / 'skills' / 'generated-from-commands' / command_name
                out_path = out_dir / 'SKILL.md'
                rel_out = self._rel(out_path)

                if rel_out in manually_maintained:
                    print(f"  Skipping manually maintained: {rel_out}")
                    continue

                # Idempotent: skip if generated file is newer than source
                if out_path.exists() and not self.force:
                    src_mtime = cmd_file.stat().st_mtime
                    dst_mtime = out_path.stat().st_mtime
                    if dst_mtime >= src_mtime:
                        self.skipped.append(rel_out)
                        continue

                content = self.convert_command_to_skill(cmd_file, plugin_name)
                self._write(out_path, content, overwrite=True)
                converted_count += 1
        else:
            cmd_files = []

        # --- agents/ --- warn or strict fail
        agents_dir = self.plugin_path / 'agents'
        agent_warnings: list[str] = []
        if agents_dir.exists():
            for agent_file in sorted(agents_dir.glob('*.md')):
                msg = f"agents/{agent_file.name}: not auto-converted — add manually to skills/"
                agent_warnings.append(msg)
                self.warnings.append(msg)

        if agent_warnings and self.strict:
            print("\nSTRICT MODE: unresolved agents detected:")
            for w in agent_warnings:
                print(f"  ✗ {w}")
            print("\nUpdate .plugin-cross-port.yaml decisions.agents_converted before proceeding.")
            return 1

        # --- hooks --- warn or strict fail
        hooks = cc.get('hooks', {})
        hook_warnings: list[str] = []
        if hooks:
            for hook_event in hooks.keys():
                msg = f"hooks.{hook_event}: no Codex equivalent — implement as GitHub Action or skill side-effect"
                hook_warnings.append(msg)
                self.warnings.append(msg)

        if hook_warnings and self.strict:
            print("\nSTRICT MODE: unresolved hooks detected:")
            for w in hook_warnings:
                print(f"  ✗ {w}")
            print("\nUpdate .plugin-cross-port.yaml decisions.hooks_converted before proceeding.")
            return 1

        # --- .plugin-cross-port.yaml ---
        decision_data = {
            'version': 1,
            'plugin': plugin_name,
            'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'source_of_truth': 'claude-code',
            'decisions': {
                'skills_shared': bool(non_generated),
                'commands_converted': commands_dir.exists(),
                'agents_converted': False,
                'hooks_converted': False,
            },
            'warnings': self.warnings,
            'manually_maintained': manually_maintained,
        }
        decision_path = self.plugin_path / '.plugin-cross-port.yaml'
        self._write(decision_path, dump_yaml(decision_data), overwrite=True)

        # --- Codex marketplace ---
        self.update_codex_marketplace(plugin_name)

        # --- Summary ---
        print('\nGenerated:')
        for f in self.created:
            print(f'  ✅ {f}')

        if self.skipped:
            print('\nSkipped (up-to-date):')
            for f in self.skipped:
                print(f'  — {f}')

        if self.warnings:
            print('\nWarnings:')
            for w in self.warnings:
                print(f'  ⚠️  {w}')

        if commands_dir.exists() and len(cmd_files) > 0:
            print(f'\nConverted {converted_count}/{len(cmd_files)} commands to Codex skills.')

        if non_generated:
            print(f'Shared skills/ (no action): {len(non_generated)} skill(s)')

        print('\nManual steps:')
        print('  1. Review skills/generated-from-commands/ — remove CC-specific allowed-tools and ${CLAUDE_PLUGIN_ROOT} references.')
        if agent_warnings:
            print('  2. Convert agents manually (see warnings above).')
        if hook_warnings:
            print('  3. Re-implement hooks as GitHub Actions or remove (see references/continuous-mode.md).')

        return 0


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Convert a Claude Code plugin to Codex format.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('plugin_path', help='Path to plugin directory, e.g. plugins/obsidian-tracker')
    parser.add_argument('--repo-root', default='.', help='Repository root (default: current directory)')
    parser.add_argument('--dry-run', action='store_true', help='Print planned changes without writing')
    parser.add_argument('--force', action='store_true', help='Overwrite all generated files')
    parser.add_argument('--strict', action='store_true', help='Fail on unresolved agents/hooks')
    args = parser.parse_args()

    plugin_path = Path(args.plugin_path)
    repo_root = Path(args.repo_root)

    if not plugin_path.is_absolute():
        plugin_path = repo_root / plugin_path

    if not plugin_path.exists():
        print(f"ERROR: Plugin path not found: {plugin_path}")
        sys.exit(1)

    converter = Converter(
        plugin_path=plugin_path,
        repo_root=repo_root,
        dry_run=args.dry_run,
        force=args.force,
        strict=args.strict,
    )
    sys.exit(converter.run())


if __name__ == '__main__':
    main()
