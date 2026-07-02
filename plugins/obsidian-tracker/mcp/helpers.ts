/**
 * Shared helpers for Obsidian Tracker MCP server.
 * Extracted for testability — used by index.ts and tests.
 */

import fs from "fs/promises";
import path from "path";
import os from "os";

export const BOARD_COLUMNS = ["Backlog", "In Progress", "Review", "Done"];

export const CONFIG_DIR = path.join(os.homedir(), ".config", "obsidian-tracker");
export const CONFIG_FILE = path.join(CONFIG_DIR, "config.json");

export interface Config {
  vaultPath?: string;
  initialized: boolean;
}

export const DEFAULT_CONFIG: Config = { initialized: false };

export async function loadConfig(): Promise<Config> {
  try {
    const data = await fs.readFile(CONFIG_FILE, "utf-8");
    return { ...DEFAULT_CONFIG, ...JSON.parse(data) };
  } catch {
    return DEFAULT_CONFIG;
  }
}

export async function saveConfig(config: Config): Promise<void> {
  await fs.mkdir(CONFIG_DIR, { recursive: true });
  await fs.writeFile(CONFIG_FILE, JSON.stringify(config, null, 2));
}

export async function getVaultPath(): Promise<string | null> {
  const config = await loadConfig();
  if (config.vaultPath) return config.vaultPath;
  if (process.env.OBSIDIAN_VAULT) {
    let envPath = process.env.OBSIDIAN_VAULT;
    if (envPath.includes("$HOME")) {
      envPath = envPath.replace(/\$HOME/g, os.homedir());
    }
    return envPath;
  }
  return null;
}

export async function validateVaultPath(vaultPath: string): Promise<boolean> {
  try {
    const stat = await fs.stat(vaultPath);
    return stat.isDirectory();
  } catch {
    return false;
  }
}

// --- Filename helpers ---

/**
 * Make a title safe for use as an Obsidian note name and inside [[wiki-links]].
 * Obsidian forbids * " \ / < > : | ? in note names (mobile/Sync reject them);
 * # ^ [ ] | break wiki-links. Forbidden chars become spaces, whitespace is
 * collapsed, trailing dots/spaces are stripped (Windows/Sync), length capped.
 */
export function sanitizeTitle(title: string, maxLength = 180): string {
  const cleaned = title
    .replace(/[*"\\/<>:|?#^\[\]]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[. ]+$/, "")
    .slice(0, maxLength)
    .trim();
  return cleaned || "untitled";
}

// --- Markdown helpers ---

export async function parseMarkdown(filePath: string) {
  const content = await fs.readFile(filePath, "utf-8");
  const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---\n/);
  let frontmatter: Record<string, any> = {};
  let body = content;

  if (frontmatterMatch) {
    const fm = frontmatterMatch[1];
    body = content.slice(frontmatterMatch[0].length);
    for (const line of fm.split("\n")) {
      const match = line.match(/^([\w-]+):\s*(.+)$/);
      if (match) {
        const [, key, value] = match;
        frontmatter[key] = value.replace(/^["']|["']$/g, "");
      }
    }
  }

  return { frontmatter, body };
}

/**
 * Parse frontmatter from raw string content (no file I/O).
 * Useful for testing without filesystem.
 */
export function parseMarkdownContent(content: string) {
  const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---\n/);
  let frontmatter: Record<string, any> = {};
  let body = content;

  if (frontmatterMatch) {
    const fm = frontmatterMatch[1];
    body = content.slice(frontmatterMatch[0].length);
    for (const line of fm.split("\n")) {
      const match = line.match(/^([\w-]+):\s*(.+)$/);
      if (match) {
        const [, key, value] = match;
        frontmatter[key] = value.replace(/^["']|["']$/g, "");
      }
    }
  }

  return { frontmatter, body };
}

// --- Session helpers ---

/**
 * Render one session entry appended to `Sessions/Session - <date>.md`.
 * CONTRACT: hooks/session-clear.sh writes the same structure in bash
 * (tested by tests/hooks/session_clear.bats "format contract" test) —
 * change both together or the vault gets mixed session formats.
 */
export function renderSessionEntry(opts: {
  time: string;
  duration?: string;
  goal?: string;
  actions?: string[];
  results?: string;
  nextSteps?: string;
}): string {
  const actionsText = opts.actions && opts.actions.length > 0
    ? opts.actions.map(a => `- ${a}`).join("\n")
    : "- No actions recorded";
  const heading = `## Session - ${opts.time} UTC${opts.duration ? ` (${opts.duration})` : ""}`;

  return `

${heading}

### Goal
${opts.goal || "No goal specified"}

### Actions
${actionsText}

### Results
${opts.results || "In progress..."}

### Next Time
${opts.nextSteps || "TBD"}

---
`;
}

// --- Board (kanban) helpers ---

export async function parseBoard(boardPath: string): Promise<Map<string, string[]>> {
  const columns = new Map<string, string[]>();
  for (const col of BOARD_COLUMNS) columns.set(col, []);

  try {
    const content = await fs.readFile(boardPath, "utf-8");
    return parseBoardContent(content);
  } catch {
    return columns;
  }
}

/**
 * Parse board content from raw string (no file I/O).
 */
export function parseBoardContent(content: string): Map<string, string[]> {
  const columns = new Map<string, string[]>();
  for (const col of BOARD_COLUMNS) columns.set(col, []);

  let currentColumn: string | null = null;

  for (const line of content.split("\n")) {
    const headerMatch = line.match(/^## (.+)$/);
    if (headerMatch) {
      const colName = headerMatch[1].trim();
      // Unknown headers end the current column — their items belong to the
      // custom section and are preserved verbatim by renderBoardContent.
      currentColumn = BOARD_COLUMNS.includes(colName) ? colName : null;
      continue;
    }
    if (currentColumn && line.match(/^- \[[ x]\] /)) {
      columns.get(currentColumn)!.push(line);
    }
  }

  return columns;
}

export async function writeBoard(boardPath: string, columns: Map<string, string[]>): Promise<void> {
  let original = "";
  try {
    original = await fs.readFile(boardPath, "utf-8");
  } catch {}
  await fs.writeFile(boardPath, renderBoardContent(original, columns));
}

/**
 * Re-render known kanban columns into an existing board, preserving everything
 * else verbatim: frontmatter, unknown columns, notes, and the
 * `%% kanban:settings %%` block written by the Obsidian Kanban plugin.
 */
export function renderBoardContent(original: string, columns: Map<string, string[]>): string {
  if (!original.trim()) return renderBoard(columns);

  const out: string[] = [];
  const seen = new Set<string>();
  let currentColumn: string | null = null;
  let extras: string[] = [];

  const flushColumn = () => {
    if (!currentColumn) return;
    out.push(`## ${currentColumn}`);
    for (const item of columns.get(currentColumn) || []) out.push(item);
    out.push(...extras);
    out.push("");
    currentColumn = null;
    extras = [];
  };

  for (const line of original.split("\n")) {
    const header = line.match(/^## (.+)$/);
    if (header && BOARD_COLUMNS.includes(header[1].trim())) {
      flushColumn();
      currentColumn = header[1].trim();
      seen.add(currentColumn);
      continue;
    }
    if (header || line.startsWith("%% kanban:")) {
      flushColumn();
      out.push(line);
      continue;
    }
    if (currentColumn) {
      // Checkbox items are replaced by the Map; keep any other non-blank lines
      if (/^- \[[ x]\] /.test(line) || line.trim() === "") continue;
      extras.push(line);
      continue;
    }
    out.push(line);
  }
  flushColumn();

  for (const col of BOARD_COLUMNS) {
    if (seen.has(col)) continue;
    out.push(`## ${col}`);
    for (const item of columns.get(col) || []) out.push(item);
    out.push("");
  }

  return out.join("\n");
}

export function renderBoard(columns: Map<string, string[]>): string {
  let content = "---\nkanban-plugin: basic\n---\n";
  for (const col of BOARD_COLUMNS) {
    content += `\n## ${col}\n`;
    for (const item of columns.get(col) || []) {
      content += `${item}\n`;
    }
  }
  return content;
}

// --- Concurrency ---

const projectLocks = new Map<string, Promise<unknown>>();

/**
 * Serialize id-allocation + file creation per project within this process.
 * ponytail: cross-process races (two MCP servers on one vault) are only
 * guarded by the wx write flag — same id with different titles can still
 * collide there; add file-based locking if that ever becomes real.
 */
export async function withProjectLock<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const prev = projectLocks.get(key) ?? Promise.resolve();
  const next = prev.then(fn, fn);
  projectLocks.set(key, next.then(() => undefined, () => undefined));
  return next;
}

/** Task ids are zero-padded to 3 digits in filenames/links (like DEC-NNN). */
export function formatTaskId(id: number): string {
  return String(id).padStart(3, "0");
}

/** Matches a task file for the id in both padded and legacy unpadded form. */
export function taskFileRegex(id: number): RegExp {
  return new RegExp(`^TASK-0*${id} `);
}

/** Matches a board wiki-link for the id in both padded and legacy unpadded form. */
export function taskLinkRegex(id: number): RegExp {
  return new RegExp(`\\[\\[TASK-0*${id}\\s*-`);
}

export async function getNextTaskId(projectPath: string): Promise<number> {
  try {
    const files = await fs.readdir(projectPath);
    const ids = files
      .map(f => f.match(/^TASK-(\d+)/))
      .filter((m): m is RegExpMatchArray => m !== null)
      .map(m => parseInt(m[1], 10));
    return ids.length > 0 ? Math.max(...ids) + 1 : 1;
  } catch {
    return 1;
  }
}

export async function getNextDecisionId(projectPath: string): Promise<number> {
  const decisionsPath = path.join(projectPath, "Decisions");
  try {
    const files = await fs.readdir(decisionsPath);
    const ids = files
      .map(f => f.match(/^DEC-(\d+)/))
      .filter((m): m is RegExpMatchArray => m !== null)
      .map(m => parseInt(m[1], 10));
    return ids.length > 0 ? Math.max(...ids) + 1 : 1;
  } catch {
    return 1;
  }
}

export async function updateTaskFrontmatter(taskPath: string, updates: Record<string, string>): Promise<void> {
  let content = await fs.readFile(taskPath, "utf-8");
  const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);

  if (fmMatch) {
    let fm = fmMatch[1];
    for (const [key, value] of Object.entries(updates)) {
      const regex = new RegExp(`^${key}:.*$`, "m");
      if (regex.test(fm)) {
        fm = fm.replace(regex, `${key}: ${value}`);
      } else {
        fm += `\n${key}: ${value}`;
      }
    }
    content = `---\n${fm}\n---` + content.slice(fmMatch[0].length);
    await fs.writeFile(taskPath, content);
  }
}

/**
 * Recursively list all .md files under root (absolute paths).
 * Skips dot-directories (.obsidian, .trash, …).
 */
export async function walkMarkdownFiles(root: string): Promise<string[]> {
  const results: string[] = [];
  let entries;
  try {
    entries = await fs.readdir(root, { withFileTypes: true });
  } catch {
    return results;
  }
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    const entryPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      results.push(...(await walkMarkdownFiles(entryPath)));
    } else if (entry.name.endsWith(".md")) {
      results.push(entryPath);
    }
  }
  return results;
}

// --- Path helpers ---

export function getProjectPath(vaultPath: string, name: string) {
  return path.join(vaultPath, name);
}

export async function requireVault(): Promise<string> {
  const vaultPath = await getVaultPath();
  if (!vaultPath) {
    throw new Error("Obsidian Tracker not initialized. Please run initVault first.");
  }
  const isValid = await validateVaultPath(vaultPath);
  if (!isValid) {
    throw new Error(`Vault path "${vaultPath}" does not exist or is not a directory.`);
  }
  return vaultPath;
}
