#!/usr/bin/env node
/**
 * Obsidian Tracker MCP Server v3.0.0
 *
 * Project tracking, task management with kanban boards,
 * bug logging, and session management.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema, } from "@modelcontextprotocol/sdk/types.js";
import fs from "fs/promises";
import path from "path";
import { BOARD_COLUMNS, CONFIG_FILE, loadConfig, saveConfig, getVaultPath, validateVaultPath, parseMarkdown, parseBoard, writeBoard, getNextTaskId, getNextDecisionId, updateTaskFrontmatter, getProjectPath, requireVault, sanitizeTitle, walkMarkdownFiles, } from "./helpers.js";
async function resolveProjectPath(vaultPath, name) {
    // 1. Exact path (handles "project" and "parent/subproject")
    const exactPath = path.join(vaultPath, name);
    if (!path.resolve(exactPath).startsWith(path.resolve(vaultPath) + path.sep)) {
        throw new Error(`Project name "${name}" escapes the vault`);
    }
    if (await validateVaultPath(exactPath))
        return exactPath;
    // 2. Recursive search by short name
    const matches = [];
    await findProjectByName(vaultPath, name, matches);
    if (matches.length === 1)
        return matches[0];
    if (matches.length > 1) {
        const names = matches.map(p => path.relative(vaultPath, p));
        throw new Error(`Ambiguous project name "${name}". Matches: ${names.join(", ")}`);
    }
    throw new Error(`Project "${name}" not found`);
}
async function findProjectByName(dir, name, matches) {
    try {
        const entries = await fs.readdir(dir, { withFileTypes: true });
        for (const entry of entries) {
            if (!entry.isDirectory() || entry.name === "Sessions" || entry.name === "_archive")
                continue;
            const entryPath = path.join(dir, entry.name);
            if (entry.name === name) {
                // Verify it's a project (has Board.md, Dashboard, or README)
                const markers = ["Board.md", "!Project Dashboard.md", "README.md"];
                for (const marker of markers) {
                    try {
                        await fs.stat(path.join(entryPath, marker));
                        matches.push(entryPath);
                        break;
                    }
                    catch { }
                }
            }
            await findProjectByName(entryPath, name, matches);
        }
    }
    catch { }
}
async function scanProject(projectPath, name, archived, isSubproject = false) {
    const dashboardPath = path.join(projectPath, "!Project Dashboard.md");
    const readmePath = path.join(projectPath, "README.md");
    let frontmatter = {};
    let hasDashboard = false;
    try {
        const parsed = await parseMarkdown(dashboardPath);
        frontmatter = parsed.frontmatter;
        hasDashboard = true;
    }
    catch {
        // No dashboard — for subprojects, check README
        if (isSubproject) {
            try {
                await fs.stat(readmePath);
                // README exists, treat as subproject
            }
            catch {
                return null; // Neither dashboard nor README
            }
        }
        else {
            return null; // Top-level projects require a dashboard
        }
    }
    const files = await fs.readdir(projectPath);
    const bugFiles = files.filter(f => f.startsWith("BUG -") && f.endsWith(".md"));
    const taskCount = files.filter(f => /^TASK-\d+/.test(f)).length;
    let openBugs = 0;
    for (const bf of bugFiles) {
        try {
            const bugContent = await fs.readFile(path.join(projectPath, bf), "utf-8");
            if (!bugContent.includes("**Status:** Closed"))
                openBugs++;
        }
        catch {
            openBugs++;
        }
    }
    // Scan subdirectories for subprojects
    const subprojects = [];
    const entries = await fs.readdir(projectPath, { withFileTypes: true });
    for (const sub of entries) {
        if (sub.isDirectory() && sub.name !== "Sessions" && sub.name !== "_archive") {
            const subProject = await scanProject(path.join(projectPath, sub.name), sub.name, archived, true);
            if (subProject)
                subprojects.push(subProject);
        }
    }
    return {
        name,
        status: frontmatter.status || (archived ? "Archived" : "Unknown"),
        description: frontmatter.description || "",
        bugs: openBugs,
        tasks: taskCount,
        archived,
        path: projectPath,
        ...(frontmatter.localPath ? { localPath: frontmatter.localPath } : {}),
        ...(subprojects.length > 0 ? { subprojects } : {}),
    };
}
// --- Server ---
const server = new Server({ name: "obsidian-tracker", version: "4.4.0" }, { capabilities: { tools: {} } });
server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [
            {
                name: "initVault",
                description: "Initialize Obsidian Tracker with vault path",
                inputSchema: {
                    type: "object",
                    properties: {
                        vaultPath: {
                            type: "string",
                            description: "Full path to Obsidian vault Projects folder",
                        },
                    },
                    required: ["vaultPath"],
                },
            },
            {
                name: "getConfig",
                description: "Get current Obsidian Tracker configuration",
                inputSchema: { type: "object", properties: {} },
            },
            {
                name: "listProjects",
                description: "List all projects from Obsidian vault",
                inputSchema: {
                    type: "object",
                    properties: {
                        includeArchived: {
                            type: "boolean",
                            description: "Include archived projects (default: false)",
                        },
                    },
                },
            },
            {
                name: "getProject",
                description: "Get details for a specific project",
                inputSchema: {
                    type: "object",
                    properties: {
                        name: { type: "string", description: "Project name" },
                    },
                    required: ["name"],
                },
            },
            {
                name: "createProject",
                description: "Create a new project in Obsidian with kanban board",
                inputSchema: {
                    type: "object",
                    properties: {
                        name: { type: "string", description: "Project name" },
                        description: { type: "string", description: "Project description" },
                        parent: { type: "string", description: "Parent project name (creates subproject). Resolved by short name." },
                        repository: { type: "string", description: "Repository URL" },
                        localPath: { type: "string", description: "Local code path on filesystem (metadata only)" },
                    },
                    required: ["name", "description"],
                },
            },
            {
                name: "addBug",
                description: "Add a bug report to a project",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        title: { type: "string", description: "Bug title" },
                        description: { type: "string", description: "Bug description" },
                        priority: {
                            type: "string",
                            enum: ["critical", "high", "medium", "low"],
                            description: "Bug priority",
                        },
                    },
                    required: ["project", "title", "description"],
                },
            },
            {
                name: "addSession",
                description: "Add a session log to a project",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        goal: { type: "string", description: "Session goal" },
                        actions: {
                            type: "array",
                            items: { type: "string" },
                            description: "Actions taken",
                        },
                        results: { type: "string", description: "Results achieved" },
                        nextSteps: { type: "string", description: "Next steps" },
                    },
                    required: ["project", "goal"],
                },
            },
            {
                name: "search",
                description: "Search projects by tags or content",
                inputSchema: {
                    type: "object",
                    properties: {
                        query: { type: "string", description: "Search query (supports tag: syntax)" },
                    },
                    required: ["query"],
                },
            },
            {
                name: "archiveProject",
                description: "Archive a project (move to _archive folder)",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                    },
                    required: ["project"],
                },
            },
            {
                name: "restoreProject",
                description: "Restore an archived project back to active",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                    },
                    required: ["project"],
                },
            },
            {
                name: "deleteProject",
                description: "Permanently delete a project",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        fromArchive: {
                            type: "boolean",
                            description: "Delete from archive (default: true). Set false to delete active project.",
                        },
                    },
                    required: ["project"],
                },
            },
            {
                name: "closeBug",
                description: "Close a bug report in a project",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        title: { type: "string", description: "Bug title (exact or partial match)" },
                        resolution: { type: "string", description: "How the bug was resolved" },
                    },
                    required: ["project", "title"],
                },
            },
            {
                name: "addTask",
                description: "Create a task with auto-increment ID and add to kanban board",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        title: { type: "string", description: "Task title" },
                        priority: {
                            type: "string",
                            enum: ["critical", "high", "medium", "low"],
                            description: "Task priority (default: medium)",
                        },
                        effort: { type: "string", description: "Estimated effort (e.g., '2h', '1d')" },
                        assignee: { type: "string", description: "Assignee name" },
                        extra: {
                            type: "object",
                            description: "Additional custom YAML fields",
                            additionalProperties: true,
                        },
                    },
                    required: ["project", "title"],
                },
            },
            {
                name: "updateTask",
                description: "Move a task between kanban board columns",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        taskId: { type: "number", description: "Task ID number" },
                        status: {
                            type: "string",
                            enum: ["Backlog", "In Progress", "Review", "Done"],
                            description: "Target column",
                        },
                        actual: { type: "string", description: "Actual time spent (e.g., '1h')" },
                    },
                    required: ["project", "taskId", "status"],
                },
            },
            {
                name: "listTasks",
                description: "List tasks from kanban board with statuses",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        status: {
                            type: "string",
                            enum: ["Backlog", "In Progress", "Review", "Done"],
                            description: "Filter by status (optional)",
                        },
                    },
                    required: ["project"],
                },
            },
            {
                name: "deleteTask",
                description: "Delete a task from project and remove from kanban board",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        taskId: { type: "number", description: "Task ID number" },
                    },
                    required: ["project", "taskId"],
                },
            },
            {
                name: "findProjectByLocalPath",
                description: "Find project(s) matching a local filesystem path (e.g., code repository directory)",
                inputSchema: {
                    type: "object",
                    properties: {
                        localPath: { type: "string", description: "Local filesystem path to match against project localPath frontmatter" },
                    },
                    required: ["localPath"],
                },
            },
            {
                name: "addSessionSummary",
                description: "Create a structured, machine-friendly session summary",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        completed: { type: "array", items: { type: "string" }, description: "List of completed items" },
                        decisions: { type: "array", items: { type: "string" }, description: "Decisions made" },
                        blockers: { type: "array", items: { type: "string" }, description: "Blockers encountered" },
                        nextSteps: { type: "array", items: { type: "string" }, description: "Next steps" },
                        duration: { type: "string", description: "Session duration (e.g., '45m', '2h')" },
                        linkedTasks: { type: "array", items: { type: "string" }, description: "Linked task IDs" },
                        linkedBugs: { type: "array", items: { type: "string" }, description: "Linked bug titles" },
                        linkedDecisions: { type: "array", items: { type: "string" }, description: "Linked decision IDs" },
                        linkedCommits: { type: "array", items: { type: "string" }, description: "Linked commit hashes" },
                    },
                    required: ["project", "completed"],
                },
            },
            {
                name: "getResumeContext",
                description: "Aggregate latest session summary, active tasks, open bugs, and decisions for a project",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                    },
                    required: ["project"],
                },
            },
            {
                name: "addDecision",
                description: "Create a lightweight ADR (Architecture Decision Record) with auto-increment ID",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        title: { type: "string", description: "Decision title" },
                        context: { type: "string", description: "Context / problem statement" },
                        decision: { type: "string", description: "The decision itself" },
                        consequences: { type: "string", description: "Consequences of the decision" },
                        linkedTasks: { type: "array", items: { type: "string" }, description: "Linked task IDs" },
                        linkedBugs: { type: "array", items: { type: "string" }, description: "Linked bug titles" },
                    },
                    required: ["project", "title", "context", "decision", "consequences"],
                },
            },
            {
                name: "getDecision",
                description: "Get details of a specific decision by ID",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        id: { type: "number", description: "Decision ID number" },
                    },
                    required: ["project", "id"],
                },
            },
            {
                name: "closeDecision",
                description: "Close a decision (mark as no longer active)",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        id: { type: "number", description: "Decision ID number" },
                        reason: { type: "string", description: "Reason for closing" },
                    },
                    required: ["project", "id"],
                },
            },
            {
                name: "supersedeDecision",
                description: "Supersede a decision with a new one (closes old, creates new with backlink)",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        id: { type: "number", description: "ID of the decision to supersede" },
                        newTitle: { type: "string", description: "Title for the new decision" },
                        newContext: { type: "string", description: "Context for the new decision" },
                        newDecision: { type: "string", description: "The new decision" },
                        newConsequences: { type: "string", description: "Consequences of the new decision" },
                    },
                    required: ["project", "id", "newTitle", "newContext", "newDecision", "newConsequences"],
                },
            },
            {
                name: "listDecisions",
                description: "List decisions for a project, optionally filtered by status",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        status: { type: "string", enum: ["Active", "Superseded", "Closed"], description: "Filter by status" },
                    },
                    required: ["project"],
                },
            },
            {
                name: "linkEntity",
                description: "Add commit/PR/decision/session links to any entity (task, bug, or decision)",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        entity: { type: "string", description: "Entity identifier (e.g., 'TASK-5', 'BUG - Title', 'DEC-001')" },
                        commits: { type: "array", items: { type: "string" }, description: "Commit hashes to link" },
                        prs: { type: "array", items: { type: "string" }, description: "PR references (e.g., '#482', 'owner/repo#483')" },
                        decisions: { type: "array", items: { type: "string" }, description: "Decision IDs to link" },
                        sessions: { type: "array", items: { type: "string" }, description: "Session IDs to link" },
                    },
                    required: ["project", "entity"],
                },
            },
            {
                name: "updateProject",
                description: "Update project description, status, or add context to README",
                inputSchema: {
                    type: "object",
                    properties: {
                        project: { type: "string", description: "Project name" },
                        description: { type: "string", description: "New project description" },
                        status: { type: "string", description: "New project status" },
                        repository: { type: "string", description: "Repository URL" },
                        localPath: { type: "string", description: "Local code path" },
                        context: { type: "string", description: "Additional context to append to README (markdown)" },
                    },
                    required: ["project"],
                },
            },
        ],
    };
});
// --- Tool implementations ---
server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    try {
        switch (name) {
            case "initVault": {
                if (!args)
                    throw new Error("Missing arguments");
                const vaultPath = args.vaultPath;
                const isValid = await validateVaultPath(vaultPath);
                if (!isValid) {
                    try {
                        await fs.mkdir(vaultPath, { recursive: true });
                    }
                    catch (e) {
                        throw new Error(`Cannot create vault path "${vaultPath}": ${e.message}`);
                    }
                }
                await saveConfig({ vaultPath, initialized: true });
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                message: "Obsidian Tracker initialized successfully!",
                                vaultPath,
                                configFile: CONFIG_FILE,
                            }, null, 2),
                        }],
                };
            }
            case "getConfig": {
                const config = await loadConfig();
                const vaultPath = await getVaultPath();
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                initialized: config.initialized,
                                vaultPath: vaultPath || "NOT SET",
                                configFile: CONFIG_FILE,
                                envVar: process.env.OBSIDIAN_VAULT || "NOT SET",
                            }, null, 2),
                        }],
                };
            }
            case "listProjects": {
                const vaultPath = await requireVault();
                const includeArchived = args?.includeArchived ?? false;
                const entries = await fs.readdir(vaultPath, { withFileTypes: true });
                const projects = [];
                for (const entry of entries) {
                    if (entry.isDirectory() && entry.name !== "_archive") {
                        const project = await scanProject(path.join(vaultPath, entry.name), entry.name, false);
                        if (project)
                            projects.push(project);
                    }
                }
                if (includeArchived) {
                    const archivePath = path.join(vaultPath, "_archive");
                    try {
                        const archiveEntries = await fs.readdir(archivePath, { withFileTypes: true });
                        for (const entry of archiveEntries) {
                            if (entry.isDirectory()) {
                                const project = await scanProject(path.join(archivePath, entry.name), entry.name, true);
                                if (project)
                                    projects.push(project);
                            }
                        }
                    }
                    catch {
                        // No _archive directory
                    }
                }
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({ projects }, null, 2),
                        }],
                };
            }
            case "getProject": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectName = args.name;
                const projectPath = await resolveProjectPath(vaultPath, projectName);
                const dashboardPath = path.join(projectPath, "!Project Dashboard.md");
                let frontmatter = {};
                let body = "";
                try {
                    const parsed = await parseMarkdown(dashboardPath);
                    frontmatter = parsed.frontmatter;
                    body = parsed.body;
                }
                catch {
                    body = "No dashboard found";
                }
                let bugs = [];
                try {
                    const allFiles = (await fs.readdir(projectPath)).filter(f => f.startsWith("BUG -") && f.endsWith(".md"));
                    for (const bf of allFiles) {
                        const title = bf.replace("BUG - ", "").replace(".md", "");
                        try {
                            const bugContent = await fs.readFile(path.join(projectPath, bf), "utf-8");
                            const isClosed = bugContent.includes("**Status:** Closed");
                            const priorityMatch = bugContent.match(/\*\*Priority:\*\* (\w+)/);
                            bugs.push({
                                title,
                                status: isClosed ? "Closed" : "Open",
                                priority: priorityMatch?.[1] ?? "medium",
                            });
                        }
                        catch {
                            bugs.push({ title, status: "Unknown", priority: "medium" });
                        }
                    }
                }
                catch { }
                const sessionsPath = path.join(projectPath, "Sessions");
                let sessions = [];
                try {
                    sessions = (await fs.readdir(sessionsPath)).filter(f => f.endsWith(".md"));
                }
                catch { }
                // Task summary from board
                const boardPath = path.join(projectPath, "Board.md");
                const columns = await parseBoard(boardPath);
                const taskSummary = {
                    backlog: columns.get("Backlog")?.length ?? 0,
                    inProgress: columns.get("In Progress")?.length ?? 0,
                    review: columns.get("Review")?.length ?? 0,
                    done: columns.get("Done")?.length ?? 0,
                };
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                name: projectName,
                                path: projectPath,
                                frontmatter,
                                dashboard: body,
                                bugs,
                                sessions,
                                tasks: taskSummary,
                            }, null, 2),
                        }],
                };
            }
            case "createProject": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectName = sanitizeTitle(args.name);
                const parentName = args.parent;
                let projectPath;
                if (parentName) {
                    const parentPath = await resolveProjectPath(vaultPath, parentName);
                    projectPath = path.join(parentPath, projectName);
                }
                else {
                    projectPath = getProjectPath(vaultPath, projectName);
                }
                await fs.mkdir(projectPath, { recursive: true });
                const createdDate = new Date().toISOString().split("T")[0];
                const projectTag = projectName.toLowerCase().replace(/\s+/g, "-");
                const dashboard = `---
status: Active
description: ${args.description ?? ""}
repository: ${args.repository ?? ""}
localPath: ${args.localPath ?? ""}
created: ${createdDate}
tags: [project, ${projectTag}]
---

# ${projectName} - Dashboard

## Status
- **Description:** ${args.description ?? "N/A"}
- **Repository:** ${args.repository ?? "N/A"}
- **Local path:** ${args.localPath ?? "N/A"}
- **Status:** Active
- **Created:** ${createdDate}

## Plugins/Subprojects

## Known Issues

## Quick Commands

---
#project #${projectTag}
`;
                await fs.writeFile(path.join(projectPath, "!Project Dashboard.md"), dashboard);
                await fs.writeFile(path.join(projectPath, "README.md"), `# ${projectName}\n\n${args.description ?? "N/A"}\n`);
                // Kanban board
                const boardContent = "---\nkanban-plugin: basic\n---\n\n## Backlog\n\n## In Progress\n\n## Review\n\n## Done\n";
                await fs.writeFile(path.join(projectPath, "Board.md"), boardContent);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                path: projectPath,
                                message: `Project "${projectName}" created successfully`,
                            }, null, 2),
                        }],
                };
            }
            case "addBug": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const title = sanitizeTitle(args.title);
                const priority = args.priority ?? "medium";
                const description = args.description;
                const date = new Date().toISOString().split("T")[0];
                const bugContent = `# ${title}

## Status
- **Priority:** ${priority}
- **Status:** Open
- **Date:** ${date}

## Description
${description}

## Attempted Fixes
| # | Action | Result |
|---|--------|--------|

## Next Steps

---
#bug #${priority}
`;
                const bugPath = path.join(projectPath, `BUG - ${title}.md`);
                await fs.writeFile(bugPath, bugContent);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                path: bugPath,
                                message: `Bug report created: "${title}"`,
                            }, null, 2),
                        }],
                };
            }
            case "addSession": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const sessionsPath = path.join(projectPath, "Sessions");
                await fs.mkdir(sessionsPath, { recursive: true });
                const now = new Date();
                const date = now.toISOString().split("T")[0];
                const time = now.toISOString().split("T")[1].slice(0, 5);
                const sessionPath = path.join(sessionsPath, `Session - ${date}.md`);
                let existingContent = "";
                try {
                    existingContent = await fs.readFile(sessionPath, "utf-8");
                }
                catch { }
                const actions = args.actions;
                const actionsText = actions && actions.length > 0
                    ? actions.map((a) => `- ${a}`).join("\n")
                    : "- No actions recorded";
                const sessionEntry = `

## Session - ${time} UTC

### Goal
${args.goal ?? "No goal specified"}

### Actions
${actionsText}

### Results
${args.results ?? "In progress..."}

### Next Time
${args.nextSteps ?? "TBD"}

---
`;
                await fs.writeFile(sessionPath, existingContent + sessionEntry);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                path: sessionPath,
                                message: "Session logged",
                            }, null, 2),
                        }],
                };
            }
            case "search": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const query = args.query;
                const results = [];
                const isTagSearch = query.startsWith("tag:");
                const searchTerm = isTagSearch ? query.slice(4).trim() : query.toLowerCase();
                const tagRegex = isTagSearch ? new RegExp(`#${searchTerm}(?:\\s|$|\\])`, "i") : null;
                const MAX_RESULTS = 100;
                // Recursive: covers nested projects, Sessions/ and Decisions/ subdirs
                const files = await walkMarkdownFiles(vaultPath);
                for (const filePath of files) {
                    if (results.length >= MAX_RESULTS)
                        break;
                    let content;
                    try {
                        content = await fs.readFile(filePath, "utf-8");
                    }
                    catch {
                        continue;
                    }
                    const matched = tagRegex
                        ? tagRegex.test(content)
                        : content.toLowerCase().includes(searchTerm);
                    if (matched) {
                        results.push({
                            project: path.relative(vaultPath, path.dirname(filePath)) || ".",
                            file: path.basename(filePath),
                            match: isTagSearch ? `tag:#${searchTerm}` : "content",
                        });
                    }
                }
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({ query, results, count: results.length, truncated: results.length >= MAX_RESULTS }, null, 2),
                        }],
                };
            }
            // --- Archive / Restore / Delete ---
            case "archiveProject": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectName = args.project;
                const projectPath = await resolveProjectPath(vaultPath, projectName);
                const archivePath = path.join(vaultPath, "_archive");
                await fs.mkdir(archivePath, { recursive: true });
                const dashboardPath = path.join(projectPath, "!Project Dashboard.md");
                try {
                    await updateTaskFrontmatter(dashboardPath, { status: "Archived" });
                }
                catch {
                    // Dashboard may not exist, proceed anyway
                }
                const archivedPath = path.join(archivePath, path.basename(projectPath));
                await fs.rename(projectPath, archivedPath);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                message: `Project "${projectName}" archived`,
                                archivedPath,
                            }, null, 2),
                        }],
                };
            }
            case "restoreProject": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectName = args.project;
                const archivedPath = path.join(vaultPath, "_archive", projectName);
                const exists = await validateVaultPath(archivedPath);
                if (!exists)
                    throw new Error(`Archived project "${projectName}" not found in _archive`);
                const dashboardPath = path.join(archivedPath, "!Project Dashboard.md");
                try {
                    await updateTaskFrontmatter(dashboardPath, { status: "Active" });
                }
                catch {
                    // Dashboard may not exist
                }
                const restoredPath = getProjectPath(vaultPath, projectName);
                await fs.rename(archivedPath, restoredPath);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                message: `Project "${projectName}" restored`,
                                restoredPath,
                            }, null, 2),
                        }],
                };
            }
            case "deleteProject": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectName = args.project;
                const fromArchive = args.fromArchive ?? true;
                const targetPath = fromArchive
                    ? path.join(vaultPath, "_archive", projectName)
                    : getProjectPath(vaultPath, projectName);
                const exists = await validateVaultPath(targetPath);
                if (!exists) {
                    const location = fromArchive ? "_archive" : "vault";
                    throw new Error(`Project "${projectName}" not found in ${location}`);
                }
                await fs.rm(targetPath, { recursive: true, force: true });
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                message: `Project "${projectName}" permanently deleted`,
                                deletedPath: targetPath,
                            }, null, 2),
                        }],
                };
            }
            case "closeBug": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const searchTitle = args.title.toLowerCase();
                const resolution = args.resolution ?? "";
                const files = await fs.readdir(projectPath);
                const bugFiles = files.filter(f => f.startsWith("BUG -") && f.endsWith(".md"));
                // Find bug by exact or partial title match
                const bugFile = bugFiles.find(f => {
                    const title = f.replace("BUG - ", "").replace(".md", "").toLowerCase();
                    return title === searchTitle || title.includes(searchTitle);
                });
                if (!bugFile)
                    throw new Error(`Bug matching "${args.title}" not found in project "${args.project}"`);
                const bugPath = path.join(projectPath, bugFile);
                let content = await fs.readFile(bugPath, "utf-8");
                // Update status from Open to Closed
                content = content.replace("**Status:** Open", "**Status:** Closed");
                // Add resolved date after Status line
                const resolvedDate = new Date().toISOString().split("T")[0];
                content = content.replace("**Status:** Closed", `**Status:** Closed\n- **Resolved:** ${resolvedDate}`);
                // Add resolution to Attempted Fixes if provided
                if (resolution) {
                    content = content.replace("## Next Steps", `## Resolution\n${resolution}\n\n## Next Steps`);
                }
                await fs.writeFile(bugPath, content);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                path: bugPath,
                                message: `Bug closed: "${bugFile.replace("BUG - ", "").replace(".md", "")}"`,
                                resolvedDate,
                            }, null, 2),
                        }],
                };
            }
            // --- Task management ---
            case "addTask": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const title = sanitizeTitle(args.title);
                const priority = args.priority ?? "medium";
                const effort = args.effort ?? "";
                const assignee = args.assignee ?? "";
                const extra = args.extra ?? {};
                const createdDate = new Date().toISOString().split("T")[0];
                const taskId = await getNextTaskId(projectPath);
                const taskFileName = `TASK-${taskId} - ${title}.md`;
                const taskPath = path.join(projectPath, taskFileName);
                let yaml = `---\npriority: ${priority}\n`;
                if (effort)
                    yaml += `effort: ${effort}\n`;
                if (assignee)
                    yaml += `assignee: ${assignee}\n`;
                yaml += `created: ${createdDate}\n`;
                for (const [key, value] of Object.entries(extra)) {
                    yaml += `${key}: ${value}\n`;
                }
                yaml += `---\n`;
                const taskContent = `${yaml}
# TASK-${taskId}: ${title}

## Description

## Notes

---
#task #${priority}
`;
                await fs.writeFile(taskPath, taskContent);
                // Add to board
                const boardPath = path.join(projectPath, "Board.md");
                const columns = await parseBoard(boardPath);
                columns.get("Backlog").push(`- [ ] [[TASK-${taskId} - ${title}]]`);
                await writeBoard(boardPath, columns);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                taskId,
                                path: taskPath,
                                message: `Task TASK-${taskId} created: "${title}"`,
                            }, null, 2),
                        }],
                };
            }
            case "updateTask": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const taskId = args.taskId;
                const targetStatus = args.status;
                if (!BOARD_COLUMNS.includes(targetStatus)) {
                    throw new Error(`Invalid status "${targetStatus}". Must be one of: ${BOARD_COLUMNS.join(", ")}`);
                }
                const actual = args.actual;
                const boardPath = path.join(projectPath, "Board.md");
                const columns = await parseBoard(boardPath);
                // Find and remove task from current column
                let taskLine = null;
                let sourceColumn = null;
                const taskPattern = new RegExp(`\\[\\[TASK-${taskId}\\s*-`);
                for (const [col, items] of columns) {
                    const idx = items.findIndex(line => taskPattern.test(line));
                    if (idx !== -1) {
                        taskLine = items[idx];
                        sourceColumn = col;
                        items.splice(idx, 1);
                        break;
                    }
                }
                if (!taskLine)
                    throw new Error(`Task TASK-${taskId} not found on board`);
                // Update checkbox
                if (targetStatus === "Done") {
                    taskLine = taskLine.replace("- [ ]", "- [x]");
                }
                else {
                    taskLine = taskLine.replace("- [x]", "- [ ]");
                }
                columns.get(targetStatus).push(taskLine);
                await writeBoard(boardPath, columns);
                // Update task file frontmatter
                if (actual || targetStatus === "Done") {
                    const files = await fs.readdir(projectPath);
                    const taskFile = files.find(f => f.startsWith(`TASK-${taskId} `));
                    if (taskFile) {
                        const updates = {};
                        if (actual)
                            updates.actual = actual;
                        if (targetStatus === "Done") {
                            updates.completed = new Date().toISOString().split("T")[0];
                        }
                        await updateTaskFrontmatter(path.join(projectPath, taskFile), updates);
                    }
                }
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                taskId,
                                from: sourceColumn,
                                to: targetStatus,
                                actual: actual ?? null,
                                message: `Task TASK-${taskId}: ${sourceColumn} → ${targetStatus}`,
                            }, null, 2),
                        }],
                };
            }
            case "listTasks": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const statusFilter = args.status;
                const boardPath = path.join(projectPath, "Board.md");
                const columns = await parseBoard(boardPath);
                const tasks = [];
                for (const [col, items] of columns) {
                    if (statusFilter && col !== statusFilter)
                        continue;
                    for (const item of items) {
                        const match = item.match(/\[\[TASK-(\d+)\s*-\s*(.+?)\]\]/);
                        if (match) {
                            tasks.push({
                                id: parseInt(match[1], 10),
                                title: match[2].trim(),
                                status: col,
                            });
                        }
                    }
                }
                tasks.sort((a, b) => a.id - b.id);
                const summary = {
                    backlog: columns.get("Backlog")?.length ?? 0,
                    inProgress: columns.get("In Progress")?.length ?? 0,
                    review: columns.get("Review")?.length ?? 0,
                    done: columns.get("Done")?.length ?? 0,
                };
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({ project: args.project, tasks, summary }, null, 2),
                        }],
                };
            }
            case "deleteTask": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const taskId = args.taskId;
                // Find and delete task file
                const files = await fs.readdir(projectPath);
                const taskFile = files.find(f => f.startsWith(`TASK-${taskId} `));
                if (!taskFile)
                    throw new Error(`Task TASK-${taskId} not found`);
                await fs.rm(path.join(projectPath, taskFile));
                // Remove from board
                const boardPath = path.join(projectPath, "Board.md");
                const columns = await parseBoard(boardPath);
                const taskPattern = new RegExp(`\\[\\[TASK-${taskId}\\s*-`);
                for (const [, items] of columns) {
                    const idx = items.findIndex(line => taskPattern.test(line));
                    if (idx !== -1) {
                        items.splice(idx, 1);
                        break;
                    }
                }
                await writeBoard(boardPath, columns);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                message: `Task TASK-${taskId} deleted`,
                            }, null, 2),
                        }],
                };
            }
            case "updateProject": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                // Update dashboard frontmatter
                const dashboardPath = path.join(projectPath, "!Project Dashboard.md");
                const updates = {};
                if (args.description)
                    updates.description = args.description;
                if (args.status)
                    updates.status = args.status;
                if (args.repository)
                    updates.repository = args.repository;
                if (args.localPath)
                    updates.localPath = args.localPath;
                if (Object.keys(updates).length > 0) {
                    try {
                        await updateTaskFrontmatter(dashboardPath, updates);
                    }
                    catch {
                        // No dashboard — update README description instead
                    }
                }
                // Update README description
                if (args.description) {
                    const readmePath = path.join(projectPath, "README.md");
                    try {
                        let readme = await fs.readFile(readmePath, "utf-8");
                        // Replace first paragraph after the heading
                        const lines = readme.split("\n");
                        const headingIdx = lines.findIndex(l => l.startsWith("# "));
                        if (headingIdx !== -1 && headingIdx + 2 < lines.length) {
                            lines[headingIdx + 2] = args.description;
                            readme = lines.join("\n");
                        }
                        await fs.writeFile(readmePath, readme);
                    }
                    catch { }
                }
                // Append context to README
                if (args.context) {
                    const readmePath = path.join(projectPath, "README.md");
                    try {
                        let readme = await fs.readFile(readmePath, "utf-8");
                        readme += `\n${args.context}\n`;
                        await fs.writeFile(readmePath, readme);
                    }
                    catch {
                        // Create README if missing
                        const projectName = path.basename(projectPath);
                        await fs.writeFile(readmePath, `# ${projectName}\n\n${args.context}\n`);
                    }
                }
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                message: `Project "${args.project}" updated`,
                                updated: {
                                    ...updates,
                                    ...(args.context ? { contextAppended: true } : {}),
                                },
                            }, null, 2),
                        }],
                };
            }
            case "addSessionSummary": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const sessionsPath = path.join(projectPath, "Sessions");
                await fs.mkdir(sessionsPath, { recursive: true });
                const now = new Date();
                const date = now.toISOString().split("T")[0];
                const time = now.toISOString().split("T")[1].slice(0, 5);
                const sessionId = `${date}T${time.replace(":", "-")}-00`;
                const summaryPath = path.join(sessionsPath, `Summary-${sessionId}.md`);
                const completed = args.completed || [];
                const decisions = args.decisions || [];
                const blockers = args.blockers || [];
                const nextSteps = args.nextSteps || [];
                const duration = args.duration || "unknown";
                const linkedTasks = args.linkedTasks || [];
                const linkedBugs = args.linkedBugs || [];
                const linkedDecisions = args.linkedDecisions || [];
                const linkedCommits = args.linkedCommits || [];
                const frontmatter = [
                    "---",
                    "type: session-summary",
                    `date: "${date}"`,
                    `time: "${time}"`,
                    `project: ${args.project}`,
                    `session-id: "${sessionId}"`,
                    `duration: ${duration}`,
                    `linked-tasks: [${linkedTasks.map(t => `"${t}"`).join(", ")}]`,
                    `linked-bugs: [${linkedBugs.map(b => `"${b}"`).join(", ")}]`,
                    `linked-decisions: [${linkedDecisions.map(d => `"${d}"`).join(", ")}]`,
                    `linked-commits: [${linkedCommits.map(c => `"${c}"`).join(", ")}]`,
                    "---",
                ].join("\n");
                const body = [
                    "",
                    "# Session Summary",
                    "",
                    "## Completed",
                    ...(completed.length > 0 ? completed.map(c => `- ${c}`) : ["- None"]),
                    "",
                    "## Decisions",
                    ...(decisions.length > 0 ? decisions.map(d => `- ${d}`) : ["- None"]),
                    "",
                    "## Blockers",
                    ...(blockers.length > 0 ? blockers.map(b => `- ${b}`) : ["- None"]),
                    "",
                    "## Next Steps",
                    ...(nextSteps.length > 0 ? nextSteps.map(n => `- ${n}`) : ["- TBD"]),
                    "",
                ].join("\n");
                await fs.writeFile(summaryPath, frontmatter + body);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                path: summaryPath,
                                sessionId,
                            }, null, 2),
                        }],
                };
            }
            case "getResumeContext": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                // 1. Latest session summary
                const sessionsPath = path.join(projectPath, "Sessions");
                let latestSummary = null;
                try {
                    const sessionFiles = await fs.readdir(sessionsPath);
                    const summaryFiles = sessionFiles.filter(f => f.startsWith("Summary-")).sort().reverse();
                    if (summaryFiles.length > 0) {
                        const parsed = await parseMarkdown(path.join(sessionsPath, summaryFiles[0]));
                        const content = await fs.readFile(path.join(sessionsPath, summaryFiles[0]), "utf-8");
                        const extractSection = (section) => {
                            const regex = new RegExp(`## ${section}\\n([\\s\\S]*?)(?=\\n## |$)`);
                            const match = content.match(regex);
                            if (!match)
                                return [];
                            return match[1].trim().split("\n").filter(l => l.startsWith("- ")).map(l => l.slice(2));
                        };
                        latestSummary = {
                            date: parsed.frontmatter.date || summaryFiles[0].replace("Summary-", "").replace(".md", ""),
                            completed: extractSection("Completed"),
                            decisions: extractSection("Decisions"),
                            blockers: extractSection("Blockers"),
                            nextSteps: extractSection("Next Steps"),
                        };
                    }
                }
                catch { }
                // 2. All non-Done tasks (Backlog + In Progress + Review)
                const boardPath = path.join(projectPath, "Board.md");
                const columns = await parseBoard(boardPath);
                const taskRegex = /\[\[TASK-(\d+)\s*-\s*(.+?)\]\]/;
                const activeTasks = [];
                for (const status of ["In Progress", "Review", "Backlog"]) {
                    for (const line of columns.get(status) || []) {
                        const match = line.match(taskRegex);
                        if (match)
                            activeTasks.push({ id: parseInt(match[1]), title: match[2], status });
                    }
                }
                // 3. Open bugs (sorted by priority)
                const files = await fs.readdir(projectPath);
                const bugFiles = files.filter(f => f.startsWith("BUG -") && f.endsWith(".md"));
                const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
                const openBugs = [];
                for (const bf of bugFiles) {
                    try {
                        const bugContent = await fs.readFile(path.join(projectPath, bf), "utf-8");
                        if (!bugContent.includes("**Status:** Closed")) {
                            const priorityMatch = bugContent.match(/\*\*Priority:\*\*\s*(\w+)/);
                            openBugs.push({
                                title: bf.replace("BUG - ", "").replace(".md", ""),
                                priority: priorityMatch ? priorityMatch[1] : "medium",
                            });
                        }
                    }
                    catch { }
                }
                openBugs.sort((a, b) => (priorityOrder[a.priority] ?? 3) - (priorityOrder[b.priority] ?? 3));
                // 4. Active decisions (last 5)
                const activeDecisions = [];
                const decisionsPath = path.join(projectPath, "Decisions");
                try {
                    const decFiles = await fs.readdir(decisionsPath);
                    for (const df of decFiles.filter(f => f.startsWith("DEC-") && f.endsWith(".md")).sort().reverse().slice(0, 5)) {
                        try {
                            const parsed = await parseMarkdown(path.join(decisionsPath, df));
                            if (parsed.frontmatter.status === "Active") {
                                const idMatch = df.match(/^(DEC-\d+)/);
                                activeDecisions.push({
                                    id: idMatch ? idMatch[1] : df,
                                    title: df.replace(/^DEC-\d+\s*-\s*/, "").replace(".md", ""),
                                    date: parsed.frontmatter.date || "",
                                });
                            }
                        }
                        catch { }
                    }
                }
                catch { }
                // 5. Suggested action
                let suggestedAction = "Review backlog";
                const summaryBlockers = latestSummary?.blockers?.filter((b) => b !== "None") || [];
                const summaryNextSteps = latestSummary?.nextSteps?.filter((n) => n !== "TBD") || [];
                if (summaryBlockers.length > 0) {
                    suggestedAction = `Resolve blocker: ${summaryBlockers[0]}`;
                }
                else if (activeTasks.length > 0) {
                    const inProgress = activeTasks.find(t => t.status === "In Progress");
                    const inReview = activeTasks.find(t => t.status === "Review");
                    if (inProgress) {
                        suggestedAction = `Continue: ${inProgress.title}`;
                    }
                    else if (inReview) {
                        suggestedAction = `Review: ${inReview.title}`;
                    }
                    else {
                        suggestedAction = `Pick from backlog (${activeTasks.length} tasks)`;
                    }
                }
                else if (summaryNextSteps.length > 0) {
                    suggestedAction = `Next: ${summaryNextSteps[0]}`;
                }
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                project: args.project,
                                latestSummary,
                                activeTasks,
                                openBugs,
                                activeDecisions,
                                suggestedAction,
                            }, null, 2),
                        }],
                };
            }
            case "addDecision": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const decisionsPath = path.join(projectPath, "Decisions");
                await fs.mkdir(decisionsPath, { recursive: true });
                const id = await getNextDecisionId(projectPath);
                const idStr = String(id).padStart(3, "0");
                const date = new Date().toISOString().split("T")[0];
                const title = sanitizeTitle(args.title);
                const linkedTasks = args.linkedTasks || [];
                const linkedBugs = args.linkedBugs || [];
                const content = `---
type: decision
id: DEC-${idStr}
status: Active
date: "${date}"
project: ${args.project}
linked-tasks: [${linkedTasks.map(t => `"${t}"`).join(", ")}]
linked-bugs: [${linkedBugs.map(b => `"${b}"`).join(", ")}]
superseded-by:
supersedes:
tags: [decision]
---

# DEC-${idStr}: ${title}

## Context
${args.context}

## Decision
${args.decision}

## Consequences
${args.consequences}
`;
                const filePath = path.join(decisionsPath, `DEC-${idStr} - ${title}.md`);
                await fs.writeFile(filePath, content);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                id: `DEC-${idStr}`,
                                path: filePath,
                                message: `Decision DEC-${idStr} created: "${title}"`,
                            }, null, 2),
                        }],
                };
            }
            case "getDecision": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const decisionsPath = path.join(projectPath, "Decisions");
                const idStr = String(args.id).padStart(3, "0");
                const decFiles = await fs.readdir(decisionsPath);
                const decFile = decFiles.find(f => f.startsWith(`DEC-${idStr}`));
                if (!decFile)
                    throw new Error(`Decision DEC-${idStr} not found`);
                const filePath = path.join(decisionsPath, decFile);
                const fileContent = await fs.readFile(filePath, "utf-8");
                const parsed = await parseMarkdown(filePath);
                const extractSection = (section) => {
                    const regex = new RegExp(`## ${section}\\n([\\s\\S]*?)(?=\\n## |$)`);
                    const match = fileContent.match(regex);
                    return match ? match[1].trim() : "";
                };
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                id: `DEC-${idStr}`,
                                title: decFile.replace(/^DEC-\d+\s*-\s*/, "").replace(".md", ""),
                                status: parsed.frontmatter.status || "Unknown",
                                date: parsed.frontmatter.date || "",
                                context: extractSection("Context"),
                                decision: extractSection("Decision"),
                                consequences: extractSection("Consequences"),
                                links: {
                                    tasks: parsed.frontmatter["linked-tasks"] || "",
                                    bugs: parsed.frontmatter["linked-bugs"] || "",
                                    supersededBy: parsed.frontmatter["superseded-by"] || "",
                                    supersedes: parsed.frontmatter["supersedes"] || "",
                                },
                            }, null, 2),
                        }],
                };
            }
            case "closeDecision": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const decisionsPath = path.join(projectPath, "Decisions");
                const idStr = String(args.id).padStart(3, "0");
                const decFiles = await fs.readdir(decisionsPath);
                const decFile = decFiles.find(f => f.startsWith(`DEC-${idStr}`));
                if (!decFile)
                    throw new Error(`Decision DEC-${idStr} not found`);
                const filePath = path.join(decisionsPath, decFile);
                let content = await fs.readFile(filePath, "utf-8");
                content = content.replace(/^status: Active$/m, "status: Closed");
                if (args.reason) {
                    content = content.replace(/## Consequences/, `## Close Reason\n${args.reason}\n\n## Consequences`);
                }
                await fs.writeFile(filePath, content);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                message: `Decision DEC-${idStr} closed`,
                            }, null, 2),
                        }],
                };
            }
            case "supersedeDecision": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const decisionsPath = path.join(projectPath, "Decisions");
                const oldIdStr = String(args.id).padStart(3, "0");
                const decFiles = await fs.readdir(decisionsPath);
                const oldDecFile = decFiles.find(f => f.startsWith(`DEC-${oldIdStr}`));
                if (!oldDecFile)
                    throw new Error(`Decision DEC-${oldIdStr} not found`);
                // Create new decision
                const newId = await getNextDecisionId(projectPath);
                const newIdStr = String(newId).padStart(3, "0");
                const date = new Date().toISOString().split("T")[0];
                const newContent = `---
type: decision
id: DEC-${newIdStr}
status: Active
date: "${date}"
project: ${args.project}
linked-tasks: []
linked-bugs: []
superseded-by:
supersedes: DEC-${oldIdStr}
tags: [decision]
---

# DEC-${newIdStr}: ${args.newTitle}

## Context
${args.newContext}

## Decision
${args.newDecision}

## Consequences
${args.newConsequences}
`;
                const newFilePath = path.join(decisionsPath, `DEC-${newIdStr} - ${args.newTitle}.md`);
                await fs.writeFile(newFilePath, newContent);
                // Update old decision
                const oldFilePath = path.join(decisionsPath, oldDecFile);
                let oldContent = await fs.readFile(oldFilePath, "utf-8");
                oldContent = oldContent.replace(/^status: Active$/m, "status: Superseded");
                oldContent = oldContent.replace(/^superseded-by:\s*$/m, `superseded-by: DEC-${newIdStr}`);
                await fs.writeFile(oldFilePath, oldContent);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                oldId: `DEC-${oldIdStr}`,
                                newId: `DEC-${newIdStr}`,
                                newPath: newFilePath,
                                message: `DEC-${oldIdStr} superseded by DEC-${newIdStr}`,
                            }, null, 2),
                        }],
                };
            }
            case "listDecisions": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const decisionsPath = path.join(projectPath, "Decisions");
                const filterStatus = args.status;
                const decisions = [];
                try {
                    const decFiles = (await fs.readdir(decisionsPath)).filter(f => f.startsWith("DEC-") && f.endsWith(".md")).sort();
                    for (const df of decFiles) {
                        try {
                            const parsed = await parseMarkdown(path.join(decisionsPath, df));
                            const status = parsed.frontmatter.status || "Unknown";
                            if (filterStatus && status !== filterStatus)
                                continue;
                            const idMatch = df.match(/^(DEC-\d+)/);
                            decisions.push({
                                id: idMatch ? idMatch[1] : df,
                                title: df.replace(/^DEC-\d+\s*-\s*/, "").replace(".md", ""),
                                status,
                                date: parsed.frontmatter.date || "",
                            });
                        }
                        catch { }
                    }
                }
                catch { }
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({ project: args.project, decisions }, null, 2),
                        }],
                };
            }
            case "linkEntity": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const projectPath = await resolveProjectPath(vaultPath, args.project);
                const entity = args.entity;
                // Find entity file
                let filePath;
                if (entity.startsWith("TASK-")) {
                    const files = await fs.readdir(projectPath);
                    const taskFile = files.find(f => f.startsWith(entity));
                    if (!taskFile)
                        throw new Error(`Entity ${entity} not found`);
                    filePath = path.join(projectPath, taskFile);
                }
                else if (entity.startsWith("BUG -") || entity.startsWith("BUG -")) {
                    filePath = path.join(projectPath, `${entity}.md`);
                }
                else if (entity.startsWith("DEC-")) {
                    const decisionsPath = path.join(projectPath, "Decisions");
                    const files = await fs.readdir(decisionsPath);
                    const decFile = files.find(f => f.startsWith(entity));
                    if (!decFile)
                        throw new Error(`Entity ${entity} not found`);
                    filePath = path.join(decisionsPath, decFile);
                }
                else {
                    throw new Error(`Unknown entity format: ${entity}. Use TASK-N, BUG - Title, or DEC-NNN`);
                }
                let content = await fs.readFile(filePath, "utf-8");
                const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);
                if (fmMatch) {
                    let fm = fmMatch[1];
                    const linkFields = {
                        commits: args.commits,
                        prs: args.prs,
                        "linked-decisions": args.decisions,
                        "linked-sessions": args.sessions,
                    };
                    for (const [key, values] of Object.entries(linkFields)) {
                        if (!values || values.length === 0)
                            continue;
                        const regex = new RegExp(`^${key}:\\s*\\[(.*)\\]\\s*$`, "m");
                        const match = fm.match(regex);
                        if (match) {
                            // Merge with existing values
                            const existing = match[1] ? match[1].split(",").map(s => s.trim().replace(/"/g, "")).filter(Boolean) : [];
                            const merged = [...new Set([...existing, ...values])];
                            fm = fm.replace(regex, `${key}: [${merged.map(v => `"${v}"`).join(", ")}]`);
                        }
                        else {
                            // Add new field
                            fm += `\n${key}: [${values.map(v => `"${v}"`).join(", ")}]`;
                        }
                    }
                    content = `---\n${fm}\n---` + content.slice(fmMatch[0].length);
                    await fs.writeFile(filePath, content);
                }
                else {
                    // No frontmatter — prepend it
                    const linkLines = ["---"];
                    if (args.commits)
                        linkLines.push(`commits: [${args.commits.map(v => `"${v}"`).join(", ")}]`);
                    if (args.prs)
                        linkLines.push(`prs: [${args.prs.map(v => `"${v}"`).join(", ")}]`);
                    if (args.decisions)
                        linkLines.push(`linked-decisions: [${args.decisions.map(v => `"${v}"`).join(", ")}]`);
                    if (args.sessions)
                        linkLines.push(`linked-sessions: [${args.sessions.map(v => `"${v}"`).join(", ")}]`);
                    linkLines.push("---\n");
                    content = linkLines.join("\n") + content;
                    await fs.writeFile(filePath, content);
                }
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                success: true,
                                entity,
                                message: `Links updated for ${entity}`,
                            }, null, 2),
                        }],
                };
            }
            case "findProjectByLocalPath": {
                const vaultPath = await requireVault();
                if (!args)
                    throw new Error("Missing arguments");
                const targetPath = path.resolve(args.localPath.replace(/\/+$/, ""));
                const matches = [];
                async function scanForLocalPath(dir, parentName) {
                    const entries = await fs.readdir(dir, { withFileTypes: true });
                    for (const entry of entries) {
                        if (!entry.isDirectory() || entry.name === "Sessions" || entry.name === "_archive")
                            continue;
                        const entryPath = path.join(dir, entry.name);
                        const dashboardPath = path.join(entryPath, "!Project Dashboard.md");
                        try {
                            const parsed = await parseMarkdown(dashboardPath);
                            const lp = parsed.frontmatter.localPath;
                            if (lp && path.resolve(lp.replace(/\/+$/, "")) === targetPath) {
                                matches.push({
                                    name: entry.name,
                                    vaultPath: entryPath,
                                    localPath: lp,
                                    isSubproject: !!parentName,
                                    ...(parentName ? { parent: parentName } : {}),
                                });
                            }
                            // Recurse into subdirectories for subprojects
                            await scanForLocalPath(entryPath, entry.name);
                        }
                        catch {
                            // No dashboard, try subdirectories anyway
                            await scanForLocalPath(entryPath, parentName);
                        }
                    }
                }
                await scanForLocalPath(vaultPath);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify({
                                found: matches.length > 0,
                                matches,
                            }, null, 2),
                        }],
                };
            }
            default:
                throw new Error(`Unknown tool: ${name}`);
        }
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({ error: error.message }, null, 2),
                }],
            isError: true,
        };
    }
});
// Start server
async function main() {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("Obsidian Tracker MCP server running on stdio");
}
main().catch((error) => {
    console.error("Fatal error:", error);
    process.exit(1);
});
