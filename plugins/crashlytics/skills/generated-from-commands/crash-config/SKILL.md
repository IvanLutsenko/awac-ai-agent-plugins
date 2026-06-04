---
name: crashlytics-crash-config
description: Configure Crashlytics plugin settings (language, branch, platform, model, Firebase IDs). Use when the user invokes /crash-config.
version: 0.1.0
---

> Converted from Claude Code command `/crash-config`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Crashlytics Plugin Configuration

Interactive setup for the Crashlytics plugin. Reads the current config (if exists), lets the user change settings via interactive prompts, and writes the result.

## Step 0: Read current config

```yaml
1. Check if config exists:
   Read: .claude/crashlytics.local.md

2. If exists → parse YAML frontmatter, use current values as defaults
3. If not exists → use these defaults:
   language: en
   default_branch: master   # local branch name; plugin uses origin/<this> for git blame
   default_platform: android
   forensics_model: opus
   output_format: both
   firebase_project_id: ""
   firebase_app_id_android: ""
   firebase_app_id_ios: ""
```

## Step 1: Ask core settings

Use **a single AskUserQuestion call** with up to 4 questions:

```yaml
AskUserQuestion:
  questions:
    - question: "What language should crash reports be written in?"
      header: "Language"
      options:
        - label: "English"
          description: "Reports in English (default)"
        - label: "Russian"
          description: "Reports in Russian (Русский)"
        - label: "Other"
          description: "Any other language of your choice"
      multiSelect: false

    - question: "Which branch should be used for git blame analysis?"
      header: "Branch"
      options:
        - label: "master"
          description: "Use master branch (default)"
        - label: "main"
          description: "Use main branch"
        - label: "develop"
          description: "Use develop branch"
        - label: "Other"
          description: "Any other branch of your choice"
      multiSelect: false

    - question: "What is your default platform?"
      header: "Platform"
      options:
        - label: "Android"
          description: "Android (Kotlin/Java) — default"
        - label: "iOS"
          description: "iOS (Swift/Objective-C)"
      multiSelect: false

    - question: "Which model should the forensics agent use?"
      header: "Model"
      options:
        - label: "Opus (Recommended)"
          description: "Deepest analysis, best for complex crashes"
        - label: "Sonnet"
          description: "Faster, good for most crashes"
        - label: "Haiku"
          description: "Fastest and cheapest, although weakest analysis"
      multiSelect: false
```

## Step 2: Ask output format

```yaml
AskUserQuestion:
  questions:
    - question: "What report format do you need?"
      header: "Format"
      options:
        - label: "Both (Recommended)"
          description: "Detailed analysis + JIRA Brief"
        - label: "Detailed only"
          description: "Full analysis without JIRA Brief"
        - label: "JIRA only"
          description: "Compact JIRA-ready format only"
      multiSelect: false
```

## Step 3: Auto-detect Firebase (optional)

If `firebase_project_id` is empty in current config:

```yaml
1. Try to detect Firebase project:
   Bash: which firebase 2>/dev/null && firebase projects:list --json 2>/dev/null

2. If Firebase CLI is available and projects found:
   - Parse the project list
   - If exactly 1 project → use it automatically, inform user
   - If multiple projects → present them via AskUserQuestion:

   AskUserQuestion:
     questions:
       - question: "Which Firebase project should be used?"
         header: "Firebase"
         options:
           - label: "{project_1_name}"
             description: "Project ID: {project_1_id}"
           - label: "{project_2_name}"
             description: "Project ID: {project_2_id}"
           # ... up to 3 detected projects
           - label: "Enter manually"
             description: "Type a Firebase project ID manually"
         multiSelect: false

3. If project selected, try to detect app IDs:
   Bash: firebase apps:list --project {PROJECT_ID} --json 2>/dev/null

   Parse and store android/ios app IDs automatically.

4. If Firebase CLI not available → skip, leave empty
   Inform user: "Firebase IDs not configured. They will be auto-detected on first crash report run."
```

## Step 4: Write config

Create the config file at `.claude/crashlytics.local.md`:

```yaml
Write file: .claude/crashlytics.local.md

Content (YAML frontmatter + markdown body):

---
language: {selected_language}      # en | ru | es | de | fr | pt | it | ...
default_branch: {selected_branch}  # local branch name; analysis uses origin/<this>
default_platform: {selected_platform}  # android | ios
forensics_model: {selected_model}  # opus | sonnet | haiku
output_format: {selected_format}   # both | detailed_only | jira_only
firebase_project_id: "{detected_or_empty}"
firebase_app_id_android: "{detected_or_empty}"
firebase_app_id_ios: "{detected_or_empty}"
---

# Crashlytics Plugin Config

Configured via `/crash-config` on {current_date}.
Edit this file manually or re-run `/crash-config` to update.
```

## Step 5: Confirm

Display a summary of all saved settings to the user:

```
Crashlytics plugin configured:

  Language:     {language}
  Branch:       {default_branch}
  Platform:     {default_platform}
  Model:        {forensics_model}
  Format:       {output_format}
  Firebase:     {project_id or "auto-detect"}

Config saved to .claude/crashlytics.local.md
Re-run /crash-config anytime to update.
```
