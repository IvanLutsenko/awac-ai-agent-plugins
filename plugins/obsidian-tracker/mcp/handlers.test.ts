import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "fs/promises";
import path from "path";
import os from "os";

import {
  handlers,
  createProject,
  listProjects,
  getProject,
  addTask,
  updateTask,
  listTasks,
  deleteTask,
  addBug,
  closeBug,
  addSession,
  addSessionSummary,
  getResumeContext,
  addDecision,
  getDecision,
  closeDecision,
  supersedeDecision,
  listDecisions,
  linkEntity,
  search,
  archiveProject,
  restoreProject,
  deleteProject,
  updateProject,
  findProjectByLocalPath,
  type ToolResult,
} from "./handlers.js";

let vault: string;

function parse(res: ToolResult): any {
  return JSON.parse(res.content[0].text);
}

async function exists(p: string): Promise<boolean> {
  try {
    await fs.stat(p);
    return true;
  } catch {
    return false;
  }
}

beforeEach(async () => {
  vault = await fs.mkdtemp(path.join(os.tmpdir(), "handlers-vault-"));
  await createProject(vault, { name: "alpha", description: "Test project" });
});

afterEach(async () => {
  await fs.rm(vault, { recursive: true, force: true });
});

// --- Projects ---

describe("createProject / listProjects / getProject", () => {
  it("creates dashboard, README and board", async () => {
    expect(await exists(path.join(vault, "alpha", "!Project Dashboard.md"))).toBe(true);
    expect(await exists(path.join(vault, "alpha", "README.md"))).toBe(true);
    expect(await exists(path.join(vault, "alpha", "Board.md"))).toBe(true);
  });

  it("sanitizes project names", async () => {
    const res = parse(await createProject(vault, { name: "bad: name?", description: "x" }));
    expect(res.success).toBe(true);
    expect(await exists(path.join(vault, "bad name"))).toBe(true);
  });

  it("creates subprojects under a parent", async () => {
    await createProject(vault, { name: "child", description: "x", parent: "alpha" });
    expect(await exists(path.join(vault, "alpha", "child", "Board.md"))).toBe(true);
  });

  it("lists projects with status from dashboard", async () => {
    const res = parse(await listProjects(vault, {}));
    expect(res.projects).toHaveLength(1);
    expect(res.projects[0].name).toBe("alpha");
    expect(res.projects[0].status).toBe("Active");
  });

  it("getProject aggregates bugs, sessions and task summary", async () => {
    await addBug(vault, { project: "alpha", title: "Broken", description: "d", priority: "high" });
    await addTask(vault, { project: "alpha", title: "Do it" });
    const res = parse(await getProject(vault, { name: "alpha" }));
    expect(res.bugs).toHaveLength(1);
    expect(res.bugs[0].status).toBe("Open");
    expect(res.tasks.backlog).toBe(1);
  });

  it("rejects project names escaping the vault", async () => {
    await expect(addTask(vault, { project: "../../etc", title: "x" })).rejects.toThrow(/escapes the vault|not found/);
  });
});

describe("updateProject", () => {
  it("updates dashboard frontmatter and appends context to README", async () => {
    await updateProject(vault, { project: "alpha", status: "Paused", context: "Extra notes" });
    const dashboard = await fs.readFile(path.join(vault, "alpha", "!Project Dashboard.md"), "utf-8");
    expect(dashboard).toContain("status: Paused");
    const readme = await fs.readFile(path.join(vault, "alpha", "README.md"), "utf-8");
    expect(readme).toContain("Extra notes");
  });
});

describe("archive / restore / delete", () => {
  it("archiveProject moves project into _archive and marks status", async () => {
    await archiveProject(vault, { project: "alpha" });
    expect(await exists(path.join(vault, "_archive", "alpha"))).toBe(true);
    expect(await exists(path.join(vault, "alpha"))).toBe(false);
    const dashboard = await fs.readFile(path.join(vault, "_archive", "alpha", "!Project Dashboard.md"), "utf-8");
    expect(dashboard).toContain("status: Archived");
  });

  it("restoreProject moves it back", async () => {
    await archiveProject(vault, { project: "alpha" });
    await restoreProject(vault, { project: "alpha" });
    expect(await exists(path.join(vault, "alpha", "Board.md"))).toBe(true);
  });

  it("deleteProject removes an archived project", async () => {
    await archiveProject(vault, { project: "alpha" });
    await deleteProject(vault, { project: "alpha" });
    expect(await exists(path.join(vault, "_archive", "alpha"))).toBe(false);
  });

  it("listProjects includeArchived shows archived projects", async () => {
    await archiveProject(vault, { project: "alpha" });
    const without = parse(await listProjects(vault, {}));
    expect(without.projects).toHaveLength(0);
    const withArchived = parse(await listProjects(vault, { includeArchived: true }));
    expect(withArchived.projects).toHaveLength(1);
    expect(withArchived.projects[0].archived).toBe(true);
  });
});

// --- Tasks ---

describe("tasks", () => {
  it("addTask creates file, board entry and auto-increments ids", async () => {
    const first = parse(await addTask(vault, { project: "alpha", title: "First" }));
    const second = parse(await addTask(vault, { project: "alpha", title: "Second" }));
    expect(first.taskId).toBe(1);
    expect(second.taskId).toBe(2);
    const board = await fs.readFile(path.join(vault, "alpha", "Board.md"), "utf-8");
    expect(board).toContain("- [ ] [[TASK-001 - First]]");
    expect(board).toContain("- [ ] [[TASK-002 - Second]]");
  });

  it("addTask sanitizes titles for filenames and wiki-links", async () => {
    await addTask(vault, { project: "alpha", title: "Fix: crash | bad [chars]" });
    const files = await fs.readdir(path.join(vault, "alpha"));
    const taskFile = files.find(f => f.startsWith("TASK-001"));
    expect(taskFile).toBe("TASK-001 - Fix crash bad chars.md");
  });

  it("updateTask moves between columns and marks Done", async () => {
    await addTask(vault, { project: "alpha", title: "Move me" });
    const moved = parse(await updateTask(vault, { project: "alpha", taskId: 1, status: "In Progress" }));
    expect(moved.from).toBe("Backlog");
    await updateTask(vault, { project: "alpha", taskId: 1, status: "Done" });
    const board = await fs.readFile(path.join(vault, "alpha", "Board.md"), "utf-8");
    expect(board).toContain("- [x] [[TASK-001 - Move me]]");
    const files = await fs.readdir(path.join(vault, "alpha"));
    const taskContent = await fs.readFile(path.join(vault, "alpha", files.find(f => f.startsWith("TASK-001"))!), "utf-8");
    expect(taskContent).toMatch(/completed: \d{4}-\d{2}-\d{2}/);
  });

  it("updateTask rejects unknown status", async () => {
    await addTask(vault, { project: "alpha", title: "T" });
    await expect(updateTask(vault, { project: "alpha", taskId: 1, status: "Doing" })).rejects.toThrow(/Invalid status/);
  });

  it("updateTask preserves kanban settings block", async () => {
    await addTask(vault, { project: "alpha", title: "T" });
    const boardPath = path.join(vault, "alpha", "Board.md");
    await fs.appendFile(boardPath, '\n%% kanban:settings\n```\n{"kanban-plugin":"basic"}\n```\n%%\n');
    await updateTask(vault, { project: "alpha", taskId: 1, status: "Review" });
    const board = await fs.readFile(boardPath, "utf-8");
    expect(board).toContain("%% kanban:settings");
    expect(board).toContain("- [ ] [[TASK-001 - T]]");
  });

  it("listTasks returns ids, titles, statuses; supports filter", async () => {
    await addTask(vault, { project: "alpha", title: "A" });
    await addTask(vault, { project: "alpha", title: "B" });
    await updateTask(vault, { project: "alpha", taskId: 2, status: "In Progress" });
    const all = parse(await listTasks(vault, { project: "alpha" }));
    expect(all.tasks).toHaveLength(2);
    expect(all.summary.inProgress).toBe(1);
    const filtered = parse(await listTasks(vault, { project: "alpha", status: "In Progress" }));
    expect(filtered.tasks).toHaveLength(1);
    expect(filtered.tasks[0].title).toBe("B");
  });

  it("finds legacy unpadded task files (TASK-7) by id", async () => {
    // Pre-padding vaults have files like "TASK-7 - Legacy.md" and board links
    // "[[TASK-7 - Legacy]]" — lookups must still resolve them.
    await fs.writeFile(path.join(vault, "alpha", "TASK-7 - Legacy.md"), "---\npriority: low\n---\n# TASK-7: Legacy\n");
    const boardPath = path.join(vault, "alpha", "Board.md");
    const board = await fs.readFile(boardPath, "utf-8");
    await fs.writeFile(boardPath, board.replace("## Backlog", "## Backlog\n- [ ] [[TASK-7 - Legacy]]"));

    const moved = parse(await updateTask(vault, { project: "alpha", taskId: 7, status: "Done" }));
    expect(moved.to).toBe("Done");
    const content = await fs.readFile(path.join(vault, "alpha", "TASK-7 - Legacy.md"), "utf-8");
    expect(content).toMatch(/completed: /);
    await deleteTask(vault, { project: "alpha", taskId: 7 });
    const files = await fs.readdir(path.join(vault, "alpha"));
    expect(files.some(f => /^TASK-0*7 /.test(f))).toBe(false);
  });

  it("concurrent addTask calls get distinct ids and both board entries", async () => {
    await Promise.all([
      addTask(vault, { project: "alpha", title: "One" }),
      addTask(vault, { project: "alpha", title: "Two" }),
    ]);
    const files = (await fs.readdir(path.join(vault, "alpha"))).filter(f => f.startsWith("TASK-"));
    expect(files).toHaveLength(2);
    expect(new Set(files.map(f => f.split(" ")[0])).size).toBe(2);
    const board = await fs.readFile(path.join(vault, "alpha", "Board.md"), "utf-8");
    expect(board).toContain("[[TASK-001 -");
    expect(board).toContain("[[TASK-002 -");
  });

  it("concurrent addDecision calls get distinct ids", async () => {
    const dec = { project: "alpha", context: "c", decision: "d", consequences: "q" };
    const [a, b] = await Promise.all([
      addDecision(vault, { ...dec, title: "One" }),
      addDecision(vault, { ...dec, title: "Two" }),
    ]);
    const ids = [JSON.parse(a.content[0].text).id, JSON.parse(b.content[0].text).id];
    expect(new Set(ids).size).toBe(2);
  });

  it("deleteTask removes file and board line", async () => {
    await addTask(vault, { project: "alpha", title: "Gone" });
    await deleteTask(vault, { project: "alpha", taskId: 1 });
    const files = await fs.readdir(path.join(vault, "alpha"));
    expect(files.some(f => /^TASK-0*1 /.test(f))).toBe(false);
    const board = await fs.readFile(path.join(vault, "alpha", "Board.md"), "utf-8");
    expect(board).not.toContain("TASK-001");
  });
});

// --- Bugs ---

describe("bugs", () => {
  it("addBug creates a sanitized bug file", async () => {
    const res = parse(await addBug(vault, { project: "alpha", title: 'Crash: NPE in "foo"', description: "boom" }));
    expect(res.success).toBe(true);
    expect(await exists(path.join(vault, "alpha", "BUG - Crash NPE in foo.md"))).toBe(true);
  });

  it("closeBug matches partial title and records resolution", async () => {
    await addBug(vault, { project: "alpha", title: "Login broken", description: "d" });
    const res = parse(await closeBug(vault, { project: "alpha", title: "login", resolution: "Fixed the token" }));
    expect(res.success).toBe(true);
    const content = await fs.readFile(path.join(vault, "alpha", "BUG - Login broken.md"), "utf-8");
    expect(content).toContain("**Status:** Closed");
    expect(content).toContain("Fixed the token");
  });

  it("closeBug throws for unknown bug", async () => {
    await expect(closeBug(vault, { project: "alpha", title: "nope" })).rejects.toThrow(/not found/);
  });
});

// --- Sessions ---

describe("sessions", () => {
  it("addSession appends entries to a daily file", async () => {
    await addSession(vault, { project: "alpha", goal: "G1", actions: ["did a thing"] });
    await addSession(vault, { project: "alpha", goal: "G2" });
    const files = await fs.readdir(path.join(vault, "alpha", "Sessions"));
    expect(files).toHaveLength(1);
    const content = await fs.readFile(path.join(vault, "alpha", "Sessions", files[0]), "utf-8");
    expect(content).toContain("G1");
    expect(content).toContain("G2");
    expect(content).toContain("- did a thing");
  });

  it("addSessionSummary writes structured summary readable by getResumeContext", async () => {
    await addSessionSummary(vault, {
      project: "alpha",
      completed: ["shipped X"],
      blockers: ["waiting for review"],
      nextSteps: ["do Y"],
      linkedTasks: ["TASK-1"],
    });
    await addTask(vault, { project: "alpha", title: "Active work" });
    await updateTask(vault, { project: "alpha", taskId: 1, status: "In Progress" });

    const ctx = parse(await getResumeContext(vault, { project: "alpha" }));
    expect(ctx.latestSummary.completed).toEqual(["shipped X"]);
    expect(ctx.latestSummary.blockers).toEqual(["waiting for review"]);
    expect(ctx.activeTasks).toHaveLength(1);
    expect(ctx.suggestedAction).toBe("Resolve blocker: waiting for review");
  });

  it("getResumeContext suggests continuing in-progress work when no blockers", async () => {
    await addTask(vault, { project: "alpha", title: "Current" });
    await updateTask(vault, { project: "alpha", taskId: 1, status: "In Progress" });
    const ctx = parse(await getResumeContext(vault, { project: "alpha" }));
    expect(ctx.suggestedAction).toBe("Continue: Current");
  });
});

// --- Decisions ---

describe("decisions", () => {
  const dec = { project: "alpha", title: "Use SQLite", context: "ctx", decision: "dec", consequences: "cons" };

  it("addDecision creates DEC-001 with frontmatter; getDecision reads it back", async () => {
    const created = parse(await addDecision(vault, dec));
    expect(created.id).toBe("DEC-001");
    const got = parse(await getDecision(vault, { project: "alpha", id: 1 }));
    expect(got.title).toBe("Use SQLite");
    expect(got.status).toBe("Active");
    expect(got.context).toBe("ctx");
  });

  it("closeDecision marks status Closed with reason", async () => {
    await addDecision(vault, dec);
    await closeDecision(vault, { project: "alpha", id: 1, reason: "obsolete" });
    const got = parse(await getDecision(vault, { project: "alpha", id: 1 }));
    expect(got.status).toBe("Closed");
  });

  it("supersedeDecision closes old and links both ways", async () => {
    await addDecision(vault, dec);
    const res = parse(await supersedeDecision(vault, {
      project: "alpha", id: 1,
      newTitle: "Use Postgres", newContext: "c", newDecision: "d", newConsequences: "q",
    }));
    expect(res.newId).toBe("DEC-002");
    const oldDec = parse(await getDecision(vault, { project: "alpha", id: 1 }));
    expect(oldDec.status).toBe("Superseded");
    expect(oldDec.links.supersededBy).toBe("DEC-002");
    const newDec = parse(await getDecision(vault, { project: "alpha", id: 2 }));
    expect(newDec.links.supersedes).toBe("DEC-001");
  });

  it("listDecisions filters by status", async () => {
    await addDecision(vault, dec);
    await addDecision(vault, { ...dec, title: "Second" });
    await closeDecision(vault, { project: "alpha", id: 1 });
    const active = parse(await listDecisions(vault, { project: "alpha", status: "Active" }));
    expect(active.decisions).toHaveLength(1);
    expect(active.decisions[0].id).toBe("DEC-002");
  });
});

// --- Linking ---

describe("linkEntity", () => {
  it("merges commits into task frontmatter without duplicates", async () => {
    await addTask(vault, { project: "alpha", title: "Linked" });
    await linkEntity(vault, { project: "alpha", entity: "TASK-1", commits: ["abc1234"] });
    await linkEntity(vault, { project: "alpha", entity: "TASK-1", commits: ["abc1234", "def5678"] });
    const files = await fs.readdir(path.join(vault, "alpha"));
    const content = await fs.readFile(path.join(vault, "alpha", files.find(f => f.startsWith("TASK-001"))!), "utf-8");
    const matches = content.match(/abc1234/g) || [];
    expect(matches).toHaveLength(1);
    expect(content).toContain('"def5678"');
  });

  it("rejects unknown entity formats", async () => {
    await expect(linkEntity(vault, { project: "alpha", entity: "WAT-1" })).rejects.toThrow(/Unknown entity format/);
  });
});

// --- Search ---

describe("search", () => {
  it("finds content in nested projects and session files", async () => {
    await createProject(vault, { name: "nested", description: "x", parent: "alpha" });
    await addSession(vault, { project: "nested", goal: "unique-xyzzy-goal" });
    const res = parse(await search(vault, { query: "unique-xyzzy-goal" }));
    expect(res.count).toBe(1);
    expect(res.results[0].project).toBe(path.join("alpha", "nested", "Sessions"));
  });

  it("tag search matches hashtags", async () => {
    await addBug(vault, { project: "alpha", title: "Tagged", description: "d", priority: "critical" });
    const res = parse(await search(vault, { query: "tag:critical" }));
    expect(res.count).toBe(1);
  });
});

// --- Discovery ---

describe("findProjectByLocalPath", () => {
  it("matches a project by dashboard localPath", async () => {
    await createProject(vault, { name: "located", description: "x", localPath: "/tmp/some/repo" });
    const res = parse(await findProjectByLocalPath(vault, { localPath: "/tmp/some/repo/" }));
    expect(res.found).toBe(true);
    expect(res.matches[0].name).toBe("located");
  });

  it("reports not found for unknown paths", async () => {
    const res = parse(await findProjectByLocalPath(vault, { localPath: "/nowhere" }));
    expect(res.found).toBe(false);
  });
});

// --- Registry ---

describe("handlers registry", () => {
  it("exposes all 24 vault-scoped tools", () => {
    expect(Object.keys(handlers)).toHaveLength(24);
    for (const fn of Object.values(handlers)) {
      expect(typeof fn).toBe("function");
    }
  });
});
