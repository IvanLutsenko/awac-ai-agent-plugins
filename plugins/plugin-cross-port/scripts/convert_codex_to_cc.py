#!/usr/bin/env python3
"""
convert_codex_to_cc.py — Convert a Codex plugin to Claude Code format.

Usage:
    python3 scripts/convert_codex_to_cc.py plugins/my-codex-plugin --repo-root .
    python3 scripts/convert_codex_to_cc.py plugins/my-codex-plugin --repo-root . --dry-run
    python3 scripts/convert_codex_to_cc.py plugins/my-codex-plugin --repo-root . --force
    python3 scripts/convert_codex_to_cc.py plugins/my-codex-plugin --repo-root . --strict
"""

import argparse
import json
import os
import re
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
    result: dict = {}
    current_key: str | None = None
    current_list: list | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith('#'):
            continue

        stripped = line.lstrip()
        if stripped.startswith('- ') and current_list is not None:
            item = stripped[2:].strip().strip("'")
            current_list.append(item)
            continue

        if ':' in line:
            key_part, _, val_part = line.partition(':')
            key = key_part.strip()
            val = val_part.strip()

            if current_list is not None and current_key is not None:
                result[current_key] = current_list
                current_list = None
                current_key = None

            if val == '' or val == '|':
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

    if current_list is not None and current_key is not None:
        result[current_key] = current_list

    return result


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
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
# Capabilities → allowed-tools mapping
# ---------------------------------------------------------------------------

CAPABILITIES_TO_TOOLS: dict[str, list[str]] = {
    'Read':    ['Read', 'Glob', 'Grep'],
    'Write':   ['Write', 'Edit'],
    'Execute': ['Bash'],
    'Network': ['WebFetch', 'WebSearch'],
}


def capabilities_to_allowed_tools(capabilities: list[str]) -> list[str]:
    tools: list[str] = []
    for cap in capabilities:
        tools.extend(CAPABILITIES_TO_TOOLS.get(cap, []))
    return list(dict.fromkeys(tools))  # dedupe, preserve order


# ---------------------------------------------------------------------------
# Core conversion logic
# ---------------------------------------------------------------------------

class ReverseConverter:
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

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.repo_root))
        except ValueError:
            return str(path)

    def _write(self, path: Path, content: str, *, overwrite: bool = False) -> bool:
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

    # ------------------------------------------------------------------

    def load_codex_manifest(self) -> dict:
        manifest_path = self.plugin_path / '.codex-plugin' / 'plugin.json'
        if not manifest_path.exists():
            print(f"ERROR: Not a Codex plugin — missing {manifest_path}")
            sys.exit(1)
        return json.loads(manifest_path.read_text(encoding='utf-8'))

    def load_decision_file(self) -> dict:
        path = self.plugin_path / '.plugin-cross-port.yaml'
        if not path.exists():
            return {}
        return _parse_yaml_simple(path.read_text(encoding='utf-8'))

    def build_cc_manifest(self, codex: dict, skill_files: list[Path]) -> dict:
        name = codex.get('name', self.plugin_path.name)
        version = codex.get('version', '0.1.0')
        description = codex.get('description', '')

        author_name = ''
        author = codex.get('author', {})
        if isinstance(author, dict):
            author_name = author.get('name', '')
        elif isinstance(author, str):
            author_name = author

        # Keywords from interface category
        iface = codex.get('interface', {})
        category = iface.get('category', 'Development').lower()

        manifest: dict[str, Any] = {
            'name': name,
            'description': description,
            'version': version,
        }

        if author_name:
            manifest['author'] = {
                'name': author_name,
                'email': '',
                'url': '',
            }

        manifest['keywords'] = [category, 'codex', 'cross-platform']
        manifest['license'] = 'MIT'

        # Skills: list existing + generated-from-codex-skills
        if skill_files:
            manifest['skills'] = [
                f'./{self._rel(sf).replace(str(self._rel(self.plugin_path)) + "/", "")}'
                for sf in skill_files
                if 'generated-from-codex-skills' not in str(sf)
            ]
            # Also add generated commands
            gen_commands = list((self.plugin_path / 'commands').glob('generated-from-codex-*.md'))
            if gen_commands or self.dry_run:
                manifest['commands'] = [
                    f'./commands/generated-from-codex-{sf.parent.name}.md'
                    for sf in skill_files
                    if 'generated-from-commands' not in str(sf)
                ]

        return manifest

    def convert_skill_to_command(self, skill_path: Path, plugin_name: str, capabilities: list[str]) -> str:
        text = skill_path.read_text(encoding='utf-8')
        fm, body = parse_frontmatter(text)
        skill_name = skill_path.parent.name
        description = fm.get('description', f'Skill: {skill_name}')

        # Trim the "Use when the user invokes /xxx." suffix if it was added by cc-to-codex
        description = re.sub(r'\s+Use when the user invokes /[^\s.]+\.?$', '', description).strip()

        allowed_tools = capabilities_to_allowed_tools(capabilities)
        tools_str = ', '.join(allowed_tools) if allowed_tools else 'Read'

        # Strip "Converted from Claude Code command" header if present (round-trip case)
        body = re.sub(
            r'^>\s*Converted from Claude Code command.*\n'
            r'>\s*Review and adapt.*\n\n?',
            '',
            body,
            flags=re.MULTILINE,
        ).lstrip('\n')

        return (
            f'---\n'
            f'description: {description}\n'
            f'argument-hint: "[args]"\n'
            f'allowed-tools: [{tools_str}]\n'
            f'---\n\n'
            f'> Converted from Codex skill `{skill_name}`.\n'
            f'> Review and adapt: add specific `allowed-tools` entries and `${{CLAUDE_PLUGIN_ROOT}}` paths as needed.\n\n'
            f'{body}'
        )

    def run(self) -> int:
        codex = self.load_codex_manifest()
        plugin_name: str = codex.get('name', self.plugin_path.name)
        decision = self.load_decision_file()
        manually_maintained: list[str] = decision.get('manually_maintained', []) or []

        print(f"\nPlugin Cross-Port (Codex → CC): {plugin_name}")
        print('=' * (30 + len(plugin_name)))

        # --- Collect Codex skills ---
        skills_dir = self.plugin_path / 'skills'
        skill_files = sorted(skills_dir.glob('*/SKILL.md')) if skills_dir.exists() else []
        non_generated = [
            s for s in skill_files
            if 'generated-from-commands' not in str(s) and 'generated-from-codex' not in str(s)
        ]

        if not skill_files:
            w = "skills/ is empty — no skills to convert to CC commands"
            self.warnings.append(w)
            if self.strict:
                print(f"\nSTRICT MODE: {w}")
                return 1

        # --- .claude-plugin/plugin.json ---
        cc_manifest_path = self.plugin_path / '.claude-plugin' / 'plugin.json'
        rel_cc = self._rel(cc_manifest_path)
        if rel_cc not in manually_maintained:
            cc_manifest = self.build_cc_manifest(codex, skill_files)
            self._write(
                cc_manifest_path,
                json.dumps(cc_manifest, indent=2, ensure_ascii=False) + '\n',
                overwrite=True,
            )
        else:
            print(f"  Skipping manually maintained: {rel_cc}")

        # --- skills/ → commands/generated-from-codex-<name>.md ---
        iface = codex.get('interface', {})
        capabilities: list[str] = iface.get('capabilities', ['Read', 'Write'])
        converted_count = 0

        for skill_path in non_generated:
            skill_name = skill_path.parent.name
            out_path = self.plugin_path / 'commands' / f'generated-from-codex-{skill_name}.md'
            rel_out = self._rel(out_path)

            if rel_out in manually_maintained:
                print(f"  Skipping manually maintained: {rel_out}")
                continue

            # Idempotent: skip if generated file is newer than source
            if out_path.exists() and not self.force:
                src_mtime = skill_path.stat().st_mtime
                dst_mtime = out_path.stat().st_mtime
                if dst_mtime >= src_mtime:
                    self.skipped.append(rel_out)
                    continue

            content = self.convert_skill_to_command(skill_path, plugin_name, capabilities)
            self._write(out_path, content, overwrite=True)
            converted_count += 1

        # --- .plugin-cross-port.yaml ---
        decision_data = {
            'version': 1,
            'plugin': plugin_name,
            'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'source_of_truth': 'codex',
            'decisions': {
                'skills_shared': bool(non_generated),
                'skills_converted_to_commands': bool(non_generated),
                'hooks_converted': False,
            },
            'warnings': self.warnings,
            'manually_maintained': manually_maintained,
        }
        decision_path = self.plugin_path / '.plugin-cross-port.yaml'
        self._write(decision_path, dump_yaml(decision_data), overwrite=True)

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

        if non_generated:
            print(f'\nConverted {converted_count}/{len(non_generated)} Codex skills to CC commands.')
            print(f'Shared skills/ (no action): {len(skill_files)} skill(s)')

        print('\nManual steps:')
        print('  1. Review commands/generated-from-codex-*.md — add specific allowed-tools entries.')
        print('  2. Add hooks to .claude-plugin/plugin.json if needed (SessionStart, PostToolUse, etc.).')
        print('  3. Move generated commands to commands/ root and remove "generated-from-codex-" prefix when ready.')

        return 0


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Convert a Codex plugin to Claude Code format.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('plugin_path', help='Path to plugin directory, e.g. plugins/my-codex-plugin')
    parser.add_argument('--repo-root', default='.', help='Repository root (default: current directory)')
    parser.add_argument('--dry-run', action='store_true', help='Print planned changes without writing')
    parser.add_argument('--force', action='store_true', help='Overwrite all generated files')
    parser.add_argument('--strict', action='store_true', help='Fail on empty skills/')
    args = parser.parse_args()

    plugin_path = Path(args.plugin_path)
    repo_root = Path(args.repo_root)

    if not plugin_path.is_absolute():
        plugin_path = repo_root / plugin_path

    if not plugin_path.exists():
        print(f"ERROR: Plugin path not found: {plugin_path}")
        sys.exit(1)

    converter = ReverseConverter(
        plugin_path=plugin_path,
        repo_root=repo_root,
        dry_run=args.dry_run,
        force=args.force,
        strict=args.strict,
    )
    sys.exit(converter.run())


if __name__ == '__main__':
    main()
