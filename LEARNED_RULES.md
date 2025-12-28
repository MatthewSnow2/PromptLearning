# Learned Rules & Patterns

Rules automatically generated from the Prompt Learning Loop.

This file is a backup/reference of rules that have been appended to `~/.claude/CLAUDE.md`.

---

## Workflow Management
- **Rule**: Always check for existing workflows using `n8n_list_workflows` before creating a new workflow
- **When**: Implementing any new infrastructure workflow in n8n
- **Why**: Prevents redundant workflow creation and maintains efficient infrastructure management
  - **Source**: Learned on 2025-12-23 22:53 from integration_error (manual report)

## Configuration Versioning
- **Rule**: Always check and dynamically adapt node configuration for version-specific changes
- **When**: Updating or deploying workflows across different n8n versions
- **Why**: Prevents breaking changes and ensures backwards compatibility
  - **Source**: Learned on 2025-12-28 04:58 from workflow_error (manual report)

### Details: n8n Form Trigger Path Location (v2.2+ Breaking Change)

**Problem:** Form Trigger returning "workflow deactivated" error even when workflow is active.

**Root Cause:** Path property location changed between versions:

| Version | Path Location |
|---------|---------------|
| ≤ 2.1 | `parameters.path` |
| ≥ 2.2 | `options.path` |

**Detection:** Run `n8n_validate_workflow` - look for warning:
```
Property 'path' won't be used - not visible with current settings
```

**Fix:** Move path from root parameters into options object:
```json
// WRONG (for v2.2+)
{ "parameters": { "path": "my-form", "options": {} } }

// CORRECT (for v2.2+)
{ "parameters": { "options": { "path": "my-form" } } }
```

**Key Insight:** Toggling workflow off/on does NOT fix this - must move path to correct location.
