#!/usr/bin/env python3
"""Bump plugin version and update all references across the repo.

Usage:
    python3 scripts/publish-plugin.py <plugin_name> [patch|minor|major]

Does:
  1. Bumps version in plugins/{name}/.claude-plugin/plugin.json
  2. Updates version string in plugins/{name}/README.md
  3. Updates version in root README.md
  4. Updates version in CLAUDE.md (Active Plugins)
  5. Updates version in root .claude-plugin/marketplace.json
  6. Updates plugins/{name}/.codex-plugin/plugin.json when present

Does NOT:
  - Write changelog entries (the caller should do this — needs context)
  - Commit or push (the caller decides when)

Output: YAML summary of what was updated + new version string.
Exit code: 0 on success, 1 on error.
"""
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bump_version(version, bump_type):
    parts = version.split('.')
    if len(parts) != 3:
        raise ValueError(f"Invalid semver: {version}")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    else:  # patch
        patch += 1
    return f"{major}.{minor}.{patch}"


def update_plugin_json(plugin_name, new_version):
    path = os.path.join(REPO_ROOT, 'plugins', plugin_name, '.claude-plugin', 'plugin.json')
    with open(path) as f:
        data = json.load(f)
    old_version = data['version']
    data['version'] = new_version
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    return old_version, path


def update_file_version(filepath, old_version, new_version, count=-1):
    """Replace old_version with new_version in a file. Returns True if changed."""
    with open(filepath) as f:
        content = f.read()
    if old_version not in content:
        return False
    new_content = content.replace(old_version, new_version, count)
    with open(filepath, 'w') as f:
        f.write(new_content)
    return True


def update_json_version(filepath, plugin_name, new_version):
    """Update plugin version in a manifest or marketplace. Returns True if changed."""
    with open(filepath) as f:
        data = json.load(f)

    changed = False
    if data.get('name') == plugin_name and data.get('version') != new_version:
        data['version'] = new_version
        changed = True

    for plugin in data.get('plugins', []):
        if plugin.get('name') == plugin_name and plugin.get('version') != new_version:
            plugin['version'] = new_version
            changed = True

    if changed:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
    return changed


def update_npm_version(filepath, new_version):
    """Set the root package version in package.json / package-lock.json."""
    with open(filepath) as f:
        data = json.load(f)

    changed = False
    if data.get('version') != new_version:
        data['version'] = new_version
        changed = True

    root_pkg = data.get('packages', {}).get('')  # package-lock v2/v3
    if root_pkg is not None and root_pkg.get('version') != new_version:
        root_pkg['version'] = new_version
        changed = True

    if changed:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
    return changed


def main():
    if len(sys.argv) < 2:
        print("Usage: publish-plugin.py <plugin_name> [patch|minor|major]", file=sys.stderr)
        sys.exit(1)

    plugin_name = sys.argv[1]
    bump_type = sys.argv[2] if len(sys.argv) > 2 else 'patch'

    if bump_type not in ('patch', 'minor', 'major'):
        print(f"ERROR: bump type must be patch|minor|major, got '{bump_type}'", file=sys.stderr)
        sys.exit(1)

    plugin_dir = os.path.join(REPO_ROOT, 'plugins', plugin_name)
    if not os.path.isdir(plugin_dir):
        print(f"ERROR: plugin '{plugin_name}' not found at {plugin_dir}", file=sys.stderr)
        sys.exit(1)

    plugin_json = os.path.join(plugin_dir, '.claude-plugin', 'plugin.json')
    if not os.path.isfile(plugin_json):
        print(f"ERROR: no plugin.json at {plugin_json}", file=sys.stderr)
        sys.exit(1)

    # Read current version
    with open(plugin_json) as f:
        data = json.load(f)
    old_version = data['version']
    new_version = bump_version(old_version, bump_type)

    # 1. Update plugin.json
    data['version'] = new_version
    with open(plugin_json, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')

    updated = [f"plugins/{plugin_name}/.claude-plugin/plugin.json"]

    # 2. Update plugin README.md
    plugin_readme = os.path.join(plugin_dir, 'README.md')
    if os.path.isfile(plugin_readme) and update_file_version(plugin_readme, old_version, new_version, count=1):
        updated.append(f"plugins/{plugin_name}/README.md")

    # 3. Update root README.md
    root_readme = os.path.join(REPO_ROOT, 'README.md')
    if os.path.isfile(root_readme) and update_file_version(root_readme, old_version, new_version):
        updated.append("README.md")

    # 4. Update CLAUDE.md
    claude_md = os.path.join(REPO_ROOT, 'CLAUDE.md')
    if os.path.isfile(claude_md) and update_file_version(claude_md, old_version, new_version):
        updated.append("CLAUDE.md")

    # 5. Update root marketplace.json if exists
    marketplace = os.path.join(REPO_ROOT, '.claude-plugin', 'marketplace.json')
    if os.path.isfile(marketplace) and update_json_version(marketplace, plugin_name, new_version):
        updated.append(".claude-plugin/marketplace.json")

    # 6. Keep dual-target plugin manifest in sync
    codex_manifest = os.path.join(plugin_dir, '.codex-plugin', 'plugin.json')
    if os.path.isfile(codex_manifest) and update_json_version(codex_manifest, plugin_name, new_version):
        updated.append(f"plugins/{plugin_name}/.codex-plugin/plugin.json")

    # 7. Keep bundled MCP server package version in sync
    for lock in ('package.json', 'package-lock.json'):
        pkg = os.path.join(plugin_dir, 'mcp', lock)
        if os.path.isfile(pkg) and update_npm_version(pkg, new_version):
            updated.append(f"plugins/{plugin_name}/mcp/{lock}")

    # Output summary
    print("publish:")
    print(f"  plugin: {plugin_name}")
    print(f"  old_version: {old_version}")
    print(f"  new_version: {new_version}")
    print(f"  bump: {bump_type}")
    print(f"  updated_files:")
    for f in updated:
        print(f"    - {f}")
    print(f"  remaining:")
    print(f"    - Add changelog entry to plugins/{plugin_name}/README.md")
    print(f"    - Add 'What\\'s New' to root README.md")
    print(f"    - Commit and push")


if __name__ == '__main__':
    main()
