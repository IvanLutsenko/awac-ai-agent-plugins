import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "fs/promises";
import path from "path";
import os from "os";

import {
  parseMarkdownContent,
  parseBoardContent,
  renderBoard,
  renderBoardContent,
  renderSessionEntry,
  sanitizeTitle,
  walkMarkdownFiles,
  BOARD_COLUMNS,
  getNextTaskId,
  getNextDecisionId,
  updateTaskFrontmatter,
  validateVaultPath,
  getProjectPath,
} from "./helpers.js";

// --- sanitizeTitle ---

describe("sanitizeTitle", () => {
  it("replaces Obsidian-forbidden characters with spaces", () => {
    expect(sanitizeTitle("Fitbod: calories editing")).toBe("Fitbod calories editing");
    expect(sanitizeTitle('App label = "unnamed" on Android')).toBe("App label = unnamed on Android");
    expect(sanitizeTitle("guard (>100 files)")).toBe("guard ( 100 files)");
  });

  it("removes wiki-link breaking characters", () => {
    expect(sanitizeTitle("a | b [c] #d ^e")).toBe("a b c d e");
  });

  it("strips trailing dots and spaces", () => {
    expect(sanitizeTitle("ends with dots...")).toBe("ends with dots");
    expect(sanitizeTitle("  padded  ")).toBe("padded");
  });

  it("caps length", () => {
    expect(sanitizeTitle("x".repeat(500)).length).toBeLessThanOrEqual(180);
  });

  it("falls back to 'untitled' when nothing survives", () => {
    expect(sanitizeTitle(":::")).toBe("untitled");
    expect(sanitizeTitle("...")).toBe("untitled");
  });

  it("keeps normal titles untouched", () => {
    expect(sanitizeTitle("Обычный заголовок задачи (v2)")).toBe("Обычный заголовок задачи (v2)");
  });
});

// --- renderSessionEntry ---

describe("renderSessionEntry", () => {
  it("matches the golden format shared with hooks/session-clear.sh", () => {
    // CONTRACT: session-clear.sh writes this exact structure in bash.
    // If this golden changes, update the heredoc there and its bats test.
    const entry = renderSessionEntry({
      time: "12:34",
      duration: "1h 5m",
      goal: "Fix bugs",
      actions: ["did X", "did Y"],
      results: "done",
      nextSteps: "more",
    });
    expect(entry).toBe(`

## Session - 12:34 UTC (1h 5m)

### Goal
Fix bugs

### Actions
- did X
- did Y

### Results
done

### Next Time
more

---
`);
  });

  it("uses placeholders when fields are missing", () => {
    const entry = renderSessionEntry({ time: "00:00" });
    expect(entry).toContain("## Session - 00:00 UTC\n");
    expect(entry).toContain("No goal specified");
    expect(entry).toContain("- No actions recorded");
    expect(entry).toContain("In progress...");
    expect(entry).toContain("TBD");
  });
});

// --- renderBoardContent ---

describe("renderBoardContent", () => {
  const settingsBlock = `%% kanban:settings
\`\`\`
{"kanban-plugin":"basic","list-collapse":[false,false]}
\`\`\`
%%`;

  it("preserves kanban settings block and frontmatter on rewrite", () => {
    const original = `---
kanban-plugin: basic
---

## Backlog
- [ ] [[TASK-1 - First]]

## In Progress

## Review

## Done

${settingsBlock}
`;
    const columns = parseBoardContent(original);
    columns.get("Backlog")!.push("- [ ] [[TASK-2 - Second]]");
    const rendered = renderBoardContent(original, columns);

    expect(rendered).toContain("kanban-plugin: basic");
    expect(rendered).toContain('%% kanban:settings');
    expect(rendered).toContain('"list-collapse"');
    expect(rendered).toContain("- [ ] [[TASK-2 - Second]]");
  });

  it("preserves custom sections with their items", () => {
    const original = `## Backlog
- [ ] [[TASK-1 - Real]]

## Random Section
- [ ] custom item
some note

## Done
`;
    const columns = parseBoardContent(original);
    const rendered = renderBoardContent(original, columns);

    expect(rendered).toContain("## Random Section");
    expect(rendered).toContain("- [ ] custom item");
    expect(rendered).toContain("some note");
    // not duplicated into Backlog
    expect(rendered.indexOf("- [ ] custom item")).toBe(rendered.lastIndexOf("- [ ] custom item"));
  });

  it("moves items between columns", () => {
    const original = `## Backlog
- [ ] [[TASK-1 - Move me]]

## In Progress

## Review

## Done
`;
    const columns = parseBoardContent(original);
    const item = columns.get("Backlog")!.pop()!;
    columns.get("Done")!.push(item.replace("- [ ]", "- [x]"));
    const rendered = renderBoardContent(original, columns);
    const reparsed = parseBoardContent(rendered);

    expect(reparsed.get("Backlog")).toHaveLength(0);
    expect(reparsed.get("Done")).toEqual(["- [x] [[TASK-1 - Move me]]"]);
  });

  it("appends known columns missing from the original", () => {
    const original = `## Backlog
- [ ] [[TASK-1 - Only column]]
`;
    const columns = parseBoardContent(original);
    const rendered = renderBoardContent(original, columns);
    for (const col of BOARD_COLUMNS) {
      expect(rendered).toContain(`## ${col}`);
    }
  });

  it("falls back to legacy render for empty original", () => {
    const columns = parseBoardContent("");
    columns.get("Backlog")!.push("- [ ] [[TASK-1 - New]]");
    expect(renderBoardContent("", columns)).toBe(renderBoard(columns));
  });

  it("round-trips without duplication", () => {
    const original = `---
kanban-plugin: basic
---

## Backlog
- [ ] [[TASK-1 - A]]

## In Progress

## Review

## Done

${settingsBlock}
`;
    const once = renderBoardContent(original, parseBoardContent(original));
    const twice = renderBoardContent(once, parseBoardContent(once));
    expect(twice).toBe(once);
  });
});

// --- walkMarkdownFiles ---

describe("walkMarkdownFiles", () => {
  it("finds .md files recursively, skipping dot-dirs", async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), "walk-test-"));
    try {
      await fs.mkdir(path.join(root, "proj", "Sessions"), { recursive: true });
      await fs.mkdir(path.join(root, "parent", "nested"), { recursive: true });
      await fs.mkdir(path.join(root, ".obsidian"), { recursive: true });
      await fs.writeFile(path.join(root, "proj", "Board.md"), "x");
      await fs.writeFile(path.join(root, "proj", "Sessions", "Session - 2026-01-01.md"), "x");
      await fs.writeFile(path.join(root, "parent", "nested", "note.md"), "x");
      await fs.writeFile(path.join(root, "proj", "data.json"), "x");
      await fs.writeFile(path.join(root, ".obsidian", "hidden.md"), "x");

      const files = (await walkMarkdownFiles(root)).map(f => path.relative(root, f)).sort();
      expect(files).toEqual([
        "parent/nested/note.md",
        "proj/Board.md",
        "proj/Sessions/Session - 2026-01-01.md",
      ]);
    } finally {
      await fs.rm(root, { recursive: true, force: true });
    }
  });
});

// --- frontmatter: dashed keys ---

describe("parseMarkdownContent dashed keys", () => {
  it("parses keys with dashes (linked-tasks, superseded-by)", () => {
    const md = `---
linked-tasks: ["TASK-5"]
superseded-by: DEC-002
---
body
`;
    const result = parseMarkdownContent(md);
    expect(result.frontmatter["linked-tasks"]).toBe('["TASK-5"]');
    expect(result.frontmatter["superseded-by"]).toBe("DEC-002");
  });
});

// --- parseMarkdownContent ---

describe("parseMarkdownContent", () => {
  it("parses frontmatter and body", () => {
    const md = `---
status: Active
description: My project
tags: [a, b]
---
# Title

Body content here.
`;
    const result = parseMarkdownContent(md);
    expect(result.frontmatter.status).toBe("Active");
    expect(result.frontmatter.description).toBe("My project");
    expect(result.frontmatter.tags).toBe("[a, b]");
    expect(result.body).toContain("# Title");
    expect(result.body).toContain("Body content here.");
  });

  it("returns full content as body when no frontmatter", () => {
    const md = "# Just a title\n\nSome text.";
    const result = parseMarkdownContent(md);
    expect(result.frontmatter).toEqual({});
    expect(result.body).toBe(md);
  });

  it("strips quotes from values", () => {
    const md = `---
name: "quoted value"
other: 'single quotes'
---
body
`;
    const result = parseMarkdownContent(md);
    expect(result.frontmatter.name).toBe("quoted value");
    expect(result.frontmatter.other).toBe("single quotes");
  });

  it("handles empty frontmatter", () => {
    const md = `---

---
body
`;
    const result = parseMarkdownContent(md);
    expect(result.frontmatter).toEqual({});
    expect(result.body).toBe("body\n");
  });

  it("handles multiline content after frontmatter", () => {
    const md = `---
key: value
---
line 1
line 2
line 3
`;
    const result = parseMarkdownContent(md);
    expect(result.frontmatter.key).toBe("value");
    expect(result.body).toContain("line 1");
    expect(result.body).toContain("line 3");
  });
});

// --- parseBoardContent ---

describe("parseBoardContent", () => {
  it("parses kanban board with tasks", () => {
    const content = `---
kanban-plugin: basic
---

## Backlog
- [ ] [[TASK-1 - Do something]]
- [ ] [[TASK-2 - Another task]]

## In Progress
- [ ] [[TASK-3 - Working on it]]

## Review

## Done
- [x] [[TASK-4 - Finished]]
`;
    const columns = parseBoardContent(content);
    expect(columns.get("Backlog")).toHaveLength(2);
    expect(columns.get("In Progress")).toHaveLength(1);
    expect(columns.get("Review")).toHaveLength(0);
    expect(columns.get("Done")).toHaveLength(1);
  });

  it("returns empty columns for empty board", () => {
    const content = `---
kanban-plugin: basic
---

## Backlog

## In Progress

## Review

## Done
`;
    const columns = parseBoardContent(content);
    for (const col of BOARD_COLUMNS) {
      expect(columns.get(col)).toHaveLength(0);
    }
  });

  it("items under non-board headers belong to the custom section, not a column", () => {
    // "## Random Section" is not a valid board column; its items must not be
    // claimed by Backlog — renderBoardContent preserves them verbatim instead.
    const content = `## Backlog
- [ ] [[TASK-1 - Real task]]

## Random Section
- [ ] This belongs to Random Section

## Done
`;
    const columns = parseBoardContent(content);
    expect(columns.get("Backlog")).toHaveLength(1);
    expect(columns.get("Done")).toHaveLength(0);
  });

  it("handles checked tasks [x]", () => {
    const content = `## Done
- [x] [[TASK-1 - Done task]]
- [x] [[TASK-2 - Also done]]
`;
    const columns = parseBoardContent(content);
    expect(columns.get("Done")).toHaveLength(2);
  });

  it("ignores plain list items (no checkbox)", () => {
    const content = `## Backlog
- [ ] [[TASK-1 - With checkbox]]
- Just a note without checkbox
- Another note
`;
    const columns = parseBoardContent(content);
    expect(columns.get("Backlog")).toHaveLength(1);
  });
});

// --- renderBoard ---

describe("renderBoard", () => {
  it("round-trips: parse → render → parse produces same result", () => {
    const content = `---
kanban-plugin: basic
---

## Backlog
- [ ] [[TASK-1 - First]]

## In Progress
- [ ] [[TASK-2 - Second]]

## Review

## Done
- [x] [[TASK-3 - Third]]
`;
    const parsed = parseBoardContent(content);
    const rendered = renderBoard(parsed);
    const reparsed = parseBoardContent(rendered);

    expect(reparsed.get("Backlog")).toEqual(parsed.get("Backlog"));
    expect(reparsed.get("In Progress")).toEqual(parsed.get("In Progress"));
    expect(reparsed.get("Review")).toEqual(parsed.get("Review"));
    expect(reparsed.get("Done")).toEqual(parsed.get("Done"));
  });

  it("renders all four columns", () => {
    const columns = new Map<string, string[]>();
    for (const col of BOARD_COLUMNS) columns.set(col, []);
    const rendered = renderBoard(columns);
    expect(rendered).toContain("## Backlog");
    expect(rendered).toContain("## In Progress");
    expect(rendered).toContain("## Review");
    expect(rendered).toContain("## Done");
  });

  it("includes kanban frontmatter", () => {
    const columns = new Map<string, string[]>();
    for (const col of BOARD_COLUMNS) columns.set(col, []);
    const rendered = renderBoard(columns);
    expect(rendered).toContain("kanban-plugin: basic");
  });
});

// --- getNextTaskId (filesystem) ---

describe("getNextTaskId", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "tracker-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("returns 1 for empty directory", async () => {
    expect(await getNextTaskId(tmpDir)).toBe(1);
  });

  it("returns max + 1", async () => {
    await fs.writeFile(path.join(tmpDir, "TASK-3 - Something.md"), "");
    await fs.writeFile(path.join(tmpDir, "TASK-1 - First.md"), "");
    expect(await getNextTaskId(tmpDir)).toBe(4);
  });

  it("ignores non-task files", async () => {
    await fs.writeFile(path.join(tmpDir, "BUG - Something.md"), "");
    await fs.writeFile(path.join(tmpDir, "README.md"), "");
    await fs.writeFile(path.join(tmpDir, "TASK-5 - Real task.md"), "");
    expect(await getNextTaskId(tmpDir)).toBe(6);
  });

  it("returns 1 for non-existent directory", async () => {
    expect(await getNextTaskId("/nonexistent/path")).toBe(1);
  });
});

// --- getNextDecisionId (filesystem) ---

describe("getNextDecisionId", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "tracker-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("returns 1 when no Decisions dir", async () => {
    expect(await getNextDecisionId(tmpDir)).toBe(1);
  });

  it("returns max + 1", async () => {
    const decisionsDir = path.join(tmpDir, "Decisions");
    await fs.mkdir(decisionsDir);
    await fs.writeFile(path.join(decisionsDir, "DEC-001 - Use Kotlin.md"), "");
    await fs.writeFile(path.join(decisionsDir, "DEC-003 - Pick Koin.md"), "");
    expect(await getNextDecisionId(tmpDir)).toBe(4);
  });
});

// --- updateTaskFrontmatter (filesystem) ---

describe("updateTaskFrontmatter", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "tracker-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("updates existing field", async () => {
    const filePath = path.join(tmpDir, "task.md");
    await fs.writeFile(filePath, `---\nstatus: Active\npriority: high\n---\n# Task\n`);

    await updateTaskFrontmatter(filePath, { status: "Archived" });
    const content = await fs.readFile(filePath, "utf-8");
    expect(content).toContain("status: Archived");
    expect(content).not.toContain("status: Active");
  });

  it("adds new field", async () => {
    const filePath = path.join(tmpDir, "task.md");
    await fs.writeFile(filePath, `---\nstatus: Active\n---\n# Task\n`);

    await updateTaskFrontmatter(filePath, { assignee: "Ivan" });
    const content = await fs.readFile(filePath, "utf-8");
    expect(content).toContain("assignee: Ivan");
    expect(content).toContain("status: Active");
  });

  it("preserves body content", async () => {
    const filePath = path.join(tmpDir, "task.md");
    await fs.writeFile(filePath, `---\nstatus: Active\n---\n# Task\n\nBody text.\n`);

    await updateTaskFrontmatter(filePath, { status: "Done" });
    const content = await fs.readFile(filePath, "utf-8");
    expect(content).toContain("# Task");
    expect(content).toContain("Body text.");
  });

  it("does nothing if no frontmatter", async () => {
    const filePath = path.join(tmpDir, "task.md");
    const original = "# No frontmatter\n\nJust text.";
    await fs.writeFile(filePath, original);

    await updateTaskFrontmatter(filePath, { status: "Done" });
    const content = await fs.readFile(filePath, "utf-8");
    expect(content).toBe(original);
  });
});

// --- validateVaultPath ---

describe("validateVaultPath", () => {
  it("returns true for existing directory", async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "tracker-test-"));
    expect(await validateVaultPath(tmpDir)).toBe(true);
    await fs.rm(tmpDir, { recursive: true });
  });

  it("returns false for file (not directory)", async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "tracker-test-"));
    const filePath = path.join(tmpDir, "file.txt");
    await fs.writeFile(filePath, "content");
    expect(await validateVaultPath(filePath)).toBe(false);
    await fs.rm(tmpDir, { recursive: true });
  });

  it("returns false for non-existent path", async () => {
    expect(await validateVaultPath("/nonexistent/path/xyz")).toBe(false);
  });
});

// --- getProjectPath ---

describe("getProjectPath", () => {
  it("joins vault and project name", () => {
    expect(getProjectPath("/vault", "my-project")).toBe("/vault/my-project");
  });

  it("handles nested paths", () => {
    expect(getProjectPath("/vault", "parent/child")).toBe("/vault/parent/child");
  });
});
