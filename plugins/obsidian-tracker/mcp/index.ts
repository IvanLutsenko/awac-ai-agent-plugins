#!/usr/bin/env node

/**
 * Obsidian Tracker MCP Server v3.0.0
 *
 * Project tracking, task management with kanban boards,
 * bug logging, and session management.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import fs from "fs/promises";
import path from "path";

import {
  CONFIG_FILE,
  loadConfig,
  saveConfig,
  getVaultPath,
  validateVaultPath,
  requireVault,
} from "./helpers.js";
import { handlers } from "./handlers.js";

// --- Server ---

const server = new Server(
  { name: "obsidian-tracker", version: "4.5.0" },
  { capabilities: { tools: {} } }
);

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
        if (!args) throw new Error("Missing arguments");
        const vaultPath = args.vaultPath as string;

        const isValid = await validateVaultPath(vaultPath);
        if (!isValid) {
          try {
            await fs.mkdir(vaultPath, { recursive: true });
          } catch (e) {
            throw new Error(`Cannot create vault path "${vaultPath}": ${(e as Error).message}`);
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

      default: {
        const handler = handlers[name];
        if (!handler) throw new Error(`Unknown tool: ${name}`);
        const vaultPath = await requireVault();
        return await handler(vaultPath, args);
      }
    }
  } catch (error) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({ error: (error as Error).message }, null, 2),
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
