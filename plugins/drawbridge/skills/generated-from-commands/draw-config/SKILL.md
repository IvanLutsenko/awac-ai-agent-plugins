---
name: drawbridge-draw-config
description: View or change drawbridge defaults (target, translate flag). Use when the user invokes /draw-config.
version: 0.1.0
---

> Converted from Claude Code command `/draw-config`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# /draw-config — view or update settings

Settings live in YAML frontmatter of `~/.claude/drawbridge.local.md` (project-local override: `<cwd>/.claude/drawbridge.local.md`).

## Subcommands

### `show` (default if no args)

```bash
source plugins/drawbridge/scripts/lib.sh
echo "config_path: $(db_config_path)"
echo "default_target: $(db_default_target)"
echo "translate_to_english: $(db_translate_enabled)"
```

If config file does not exist, say so explicitly and offer to create one with defaults (`gemini`, `true`) via AskUserQuestion.

### `set <key> <value>`

Allowed keys: `default_target`, `translate_to_english`.

For `default_target`, validate against `gemini | chatgpt | grok | midjourney`.
For `translate_to_english`, accept `true | false`.

If the user-global config does not exist yet, create it. Use the Write tool with this template:

```yaml
---
default_target: gemini
translate_to_english: true
---
# drawbridge — user settings
```

Then patch the requested key. Read existing file, replace the line in frontmatter, write back.

After change, echo the updated values via the `show` flow.

## No subcommand → ask interactively

If `$ARGUMENTS` is empty, ask the user via AskUserQuestion:
- "Show current settings or change something?"
- options: `show`, `change default_target`, `change translate_to_english`

For `change` paths, ask the new value via a follow-up AskUserQuestion with constrained options.
