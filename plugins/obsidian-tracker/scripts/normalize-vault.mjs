#!/usr/bin/env node
// Normalize existing vault file/dir names to Obsidian-safe form.
// Renames entries whose names contain characters forbidden in Obsidian note
// names (* " \ / < > : | ?) or wiki-links (# ^ [ ]), then rewrites [[wiki-links]]
// that pointed to renamed .md files.
//
// Usage: node normalize-vault.mjs [--dry-run] [vault-path]
// Vault resolution: CLI arg > ~/.config/obsidian-tracker/config.json > $OBSIDIAN_VAULT

import fs from "fs/promises";
import path from "path";
import os from "os";
import { fileURLToPath } from "url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const helpersPath = path.join(scriptDir, "..", "mcp", "dist", "helpers.js");

let sanitizeTitle;
try {
  ({ sanitizeTitle } = await import(helpersPath));
} catch {
  console.error(`Cannot load ${helpersPath} — build the MCP server first: cd mcp && npm install && npm run build`);
  process.exit(1);
}

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
const vaultArg = args.find(a => !a.startsWith("--"));

async function resolveVault() {
  if (vaultArg) return vaultArg;
  try {
    const config = JSON.parse(
      await fs.readFile(path.join(os.homedir(), ".config", "obsidian-tracker", "config.json"), "utf-8")
    );
    if (config.vaultPath) return config.vaultPath;
  } catch {}
  if (process.env.OBSIDIAN_VAULT) return process.env.OBSIDIAN_VAULT.replace(/\$HOME/g, os.homedir());
  console.error("No vault path: pass as argument, set in config.json, or export OBSIDIAN_VAULT");
  process.exit(1);
}

function safeName(basename, isMarkdown) {
  if (isMarkdown) {
    const sanitized = sanitizeTitle(basename.slice(0, -3));
    return `${sanitized}.md`;
  }
  return sanitizeTitle(basename);
}

async function collectEntries(root) {
  const entries = [];
  async function walk(dir, depth) {
    let items;
    try {
      items = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const item of items) {
      if (item.name.startsWith(".")) continue;
      const full = path.join(dir, item.name);
      entries.push({ path: full, name: item.name, isDir: item.isDirectory(), depth });
      if (item.isDirectory()) await walk(full, depth + 1);
    }
  }
  await walk(root, 0);
  return entries;
}

async function uniquePath(dir, name) {
  const ext = name.endsWith(".md") ? ".md" : "";
  const stem = ext ? name.slice(0, -3) : name;
  for (let i = 1; ; i++) {
    const candidate = i === 1 ? name : `${stem} ${i}${ext}`;
    try {
      await fs.stat(path.join(dir, candidate));
    } catch {
      return candidate;
    }
  }
}

const vault = path.resolve(await resolveVault());
console.log(`Vault: ${vault}${dryRun ? " (dry run)" : ""}`);

const entries = await collectEntries(vault);
// Deepest first: children are renamed before their parent dirs, so collected
// paths stay valid throughout.
entries.sort((a, b) => b.depth - a.depth);

const linkRenames = new Map(); // old basename without .md → new basename without .md
let renamed = 0;

for (const entry of entries) {
  const isMd = !entry.isDir && entry.name.endsWith(".md");
  const wanted = safeName(entry.name, isMd);
  if (wanted === entry.name) continue;

  const dir = path.dirname(entry.path);
  const target = dryRun ? wanted : await uniquePath(dir, wanted);
  console.log(`rename: ${path.relative(vault, entry.path)}\n     → ${path.join(path.relative(vault, dir), target)}`);

  if (!dryRun) {
    await fs.rename(entry.path, path.join(dir, target));
  }
  if (isMd) {
    linkRenames.set(entry.name.slice(0, -3), target.slice(0, -3));
  }
  renamed++;
}

// Rewrite [[wiki-links]] (and ![[embeds]]) that referenced renamed notes.
let relinked = 0;
if (linkRenames.size > 0 && !dryRun) {
  const { walkMarkdownFiles } = await import(helpersPath);
  for (const file of await walkMarkdownFiles(vault)) {
    let content = await fs.readFile(file, "utf-8");
    let changed = false;
    for (const [oldName, newName] of linkRenames) {
      const needle = `[[${oldName}`;
      if (content.includes(needle)) {
        content = content.split(needle).join(`[[${newName}`);
        changed = true;
      }
    }
    if (changed) {
      await fs.writeFile(file, content);
      relinked++;
      console.log(`links:  ${path.relative(vault, file)}`);
    }
  }
}

console.log(`\n${dryRun ? "Would rename" : "Renamed"}: ${renamed} entries; links updated in ${relinked} files.`);
