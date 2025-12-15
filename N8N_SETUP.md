# n8n Workflow Setup Guide

This guide explains how to set up the n8n Cloud workflow that acts as the "Teacher" LLM for the Prompt Learning Loop.

## Overview

The n8n workflow receives failure data from Claude Code via MCP, analyzes the root cause using Claude 3.5 Sonnet, and generates a preventive rule to add to CLAUDE.md.

## Architecture

```
Claude Code (local)
    ↓ MCP Call
n8n Cloud [MCP Server Trigger]
    ↓
[Anthropic Node: Root Cause Analysis]
    ↓
[Anthropic Node: Rule Generator]
    ↓
[Return to MCP Client]
```

## Step 1: Create the Workflow in n8n Cloud

1. Log into your n8n Cloud instance
2. Click **Create Workflow**
3. Name it: `prompt-learning-teacher`

## Step 2: Add MCP Server Trigger Node

1. Add a new node → Search for **MCP Server Trigger**
2. Configure the node:

   **Basic Settings:**
   - **Tool Name**: `analyze_failure`
   - **Tool Description**: `Analyze a test failure and generate a preventive rule for CLAUDE.md`

   **Input Schema** (JSON Schema):
   ```json
   {
     "type": "object",
     "properties": {
       "diff": {
         "type": "string",
         "description": "Git diff showing the code changes that caused the failure"
       },
       "error_logs": {
         "type": "string",
         "description": "Test failure output including error messages and stack traces"
       },
       "task_description": {
         "type": "string",
         "description": "The original task that Claude was attempting"
       }
     },
     "required": ["diff", "error_logs", "task_description"]
   }
   ```

3. **Authentication:**
   - Click on **Credential** → Create new **Header Auth** credential
   - Header Name: `Authorization`
   - Header Value: `Bearer YOUR_SECURE_TOKEN_HERE`
   - Save the credential and note the token

4. **Get the MCP URL:**
   - After configuring, the node will show an MCP URL
   - It will look like: `https://your-instance.app.n8n.cloud/mcp/xxxx`
   - Save this URL for Claude Code configuration

## Step 3: Add Root Cause Analysis Node

1. Add a new node → **Anthropic** (or **AI** → **Anthropic**)
2. Connect it to the MCP Server Trigger output
3. Configure:

   **Credential:** Add your Anthropic API key

   **Resource:** Text

   **Operation:** Message a Model

   **Model:** `claude-3-5-sonnet-20241022`

   **System Prompt:**
   ```
   You are a senior software engineer analyzing test failures.

   Given:
   - Task Description: What the developer was trying to accomplish
   - Code Diff: The changes made to the codebase
   - Error Logs: The test failure output

   Analyze and explain:
   1. What specific error occurred (be precise about the error type)
   2. WHY the code failed (identify the root cause)
   3. The pattern of mistake (e.g., "forgot null check", "wrong API usage", "missing error handling")

   Be concise and technical. Focus on actionable insights.
   ```

   **User Message:**
   ```
   Task Description:
   {{ $json.task_description }}

   Code Diff:
   {{ $json.diff }}

   Error Logs:
   {{ $json.error_logs }}

   Please analyze this test failure.
   ```

## Step 4: Add Rule Generator Node

1. Add another **Anthropic** node
2. Connect it to the Root Cause Analysis output
3. Configure:

   **Model:** `claude-3-5-sonnet-20241022`

   **System Prompt:**
   ```
   Based on the root cause analysis provided, write a SINGLE preventive rule
   for the developer's CLAUDE.md file. This rule should:

   1. Be actionable and specific
   2. Prevent this exact type of error in the future
   3. Follow this exact format:

   - **Rule**: [Clear instruction in imperative form]
   - **When**: [Context when this rule applies]
   - **Why**: [Brief explanation]

   Example:
   - **Rule**: Always check if array is empty before accessing index 0
   - **When**: Working with arrays from API responses or user input
   - **Why**: Prevents IndexError on empty results

   Only output the rule in this format. No additional text.
   ```

   **User Message:**
   ```
   Root Cause Analysis:
   {{ $json.message.content }}

   Generate a preventive rule based on this analysis.
   ```

## Step 5: Add Set Node for Response Formatting

1. Add a **Set** node
2. Connect it to the Rule Generator output
3. Configure fields:

   **Field 1:**
   - Name: `analysis`
   - Value: `{{ $('Root Cause Analysis').item.json.message.content }}`

   **Field 2:**
   - Name: `rule`
   - Value: `{{ $json.message.content }}`

   **Field 3:**
   - Name: `error_type`
   - Value: `test_failure`

## Step 6: Configure MCP Response

The MCP Server Trigger automatically returns the output of the last connected node.
Ensure the Set node is the final node in the workflow.

## Step 7: Activate and Test

1. Click **Save** to save the workflow
2. Toggle the workflow to **Active**
3. Test manually:
   - Click **Test Workflow**
   - Provide sample input data
   - Verify the output contains `analysis` and `rule`

## Configure Claude Code MCP Settings

Add the n8n MCP server to Claude Code's configuration:

### Location
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### Configuration
```json
{
  "mcpServers": {
    "n8n-teacher": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote-client",
        "https://your-instance.app.n8n.cloud/mcp/xxxx"
      ],
      "env": {
        "MCP_HEADERS": "Authorization: Bearer YOUR_SECURE_TOKEN_HERE"
      }
    }
  }
}
```

**Note:** Replace:
- `https://your-instance.app.n8n.cloud/mcp/xxxx` with your actual MCP URL
- `YOUR_SECURE_TOKEN_HERE` with the bearer token you created

## Alternative: SSE-based Connection

If using the SSE transport, you may need the mcp-sse-client:

```json
{
  "mcpServers": {
    "n8n-teacher": {
      "command": "npx",
      "args": [
        "-y",
        "@anthropic-ai/mcp-sse-client@latest",
        "https://your-instance.app.n8n.cloud/mcp/xxxx"
      ],
      "env": {
        "MCP_AUTH_TOKEN": "YOUR_SECURE_TOKEN_HERE"
      }
    }
  }
}
```

## Verify MCP Connection

After configuring, restart Claude Code and verify the connection:

1. Open Claude Code
2. Type: "What MCP tools are available?"
3. You should see `analyze_failure` from the `n8n-teacher` server

## Troubleshooting

### MCP Connection Issues

1. **Check n8n workflow is active:**
   - Go to n8n Cloud → Workflows → Ensure toggle is ON

2. **Verify MCP URL:**
   - Check the MCP Server Trigger node for the correct URL

3. **Check authentication:**
   - Ensure the bearer token matches in both n8n and Claude config

4. **Check logs:**
   - n8n Cloud: Executions → View recent executions
   - Claude Code: Check terminal output for MCP errors

### Workflow Execution Issues

1. **Timeout errors:**
   - Increase timeout in config.yaml
   - Check Anthropic API key is valid

2. **Empty responses:**
   - Check node connections in n8n
   - Verify the Set node includes all fields

## Security Notes

1. **Bearer Token:**
   - Use a strong, random token (32+ characters)
   - Never commit tokens to version control
   - Rotate tokens periodically

2. **Network Access:**
   - n8n Cloud requires internet access
   - Consider IP whitelisting if available

3. **Data Privacy:**
   - Code diffs are sent to n8n Cloud
   - Review your organization's data policies

## Next Steps

1. Test the complete flow:
   ```bash
   cd Projects/PromptLearning/example_project
   python ../orchestrator.py "Fix the divide by zero bug in calculator.py"
   ```

2. Monitor n8n executions to verify data flow

3. Check CLAUDE.md for new learned rules
