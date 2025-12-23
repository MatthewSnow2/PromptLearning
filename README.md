# Prompt Learning Loop

An automated meta-learning system that improves Claude Code's performance by iteratively updating its CLAUDE.md file based on failures from multiple sources.

## Concept

This implements "Meta-Prompting" - instead of fine-tuning models, we improve the instructions they receive. When Claude Code makes a mistake, the system:

1. Captures the failure context (from tests, manual reports, or semantic analysis)
2. Sends them to a "Teacher" LLM (local Anthropic SDK or n8n webhook)
3. Analyzes the root cause using domain-specific prompts
4. Generates a preventive rule
5. Appends the rule to CLAUDE.md
6. (For test failures) Retries the task with the new knowledge

Over time, CLAUDE.md accumulates learned rules that prevent recurring mistakes.

## Failure Sources

The system supports multiple failure sources:

| Source | Type | Description |
|--------|------|-------------|
| **pytest** | Automated | Test failures captured automatically |
| **manual** | User Reported | Planning errors, integration mistakes, workflow issues |
| **semantic** | LLM Analysis | (Future) LLM reviews Claude output for quality issues |

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                       FAILURE SOURCES                          │
├────────────────┬─────────────────┬────────────────────────────┤
│    pytest      │     Manual      │        Semantic            │
│   (tests)      │  (user input)   │     (LLM analysis)         │
└───────┬────────┴────────┬────────┴─────────────┬──────────────┘
        │                 │                      │
        └─────────────────┼──────────────────────┘
                          ▼
                  ┌───────────────┐
                  │ Failure Router│
                  │ (categorize)  │
                  └───────┬───────┘
                          ▼
                  ┌───────────────┐
                  │  Teacher LLM  │
                  │(domain-aware) │
                  └───────┬───────┘
                          ▼
                  ┌───────────────┐
                  │  Append Rule  │
                  │  (CLAUDE.md)  │
                  └───────────────┘
```

## Quick Start

### Prerequisites

- Python 3.9+
- Claude Code CLI installed and configured
- n8n Cloud account (for the Teacher workflow)
- Git

### Installation

```bash
# Clone or navigate to the project
cd Projects/PromptLearning

# Install dependencies
pip install -r requirements.txt
```

### Setup n8n Workflow

Follow the detailed guide in [N8N_SETUP.md](./N8N_SETUP.md) to:

1. Create the `prompt-learning-teacher` workflow
2. Configure the MCP Server Trigger
3. Add Claude Code MCP configuration

### Usage

#### Test-Based Learning (Automated)

```bash
# Basic usage - run learning loop with pytest
python orchestrator.py run "Your task description" --project-dir ./your-project

# With options
python orchestrator.py run "Fix the validation bug" \
  --project-dir ./my-project \
  --max-retries 5 \
  --config ./config.yaml

# Manual retry mode (stops after each failure for review)
python orchestrator.py run "Add error handling" --no-auto-retry

# Legacy mode (without subcommand) still works
python orchestrator.py "Your task description" --project-dir ./your-project
```

#### Manual Failure Reporting

Report planning errors, integration mistakes, or workflow issues that aren't caught by tests:

```bash
# Report a planning error
python orchestrator.py report-failure \
  --failure-type planning_error \
  --description "Created new infrastructure instead of extending existing" \
  --context "Should have checked for existing systems first" \
  --task "Integrate new feature into codebase"

# Report an integration error
python orchestrator.py report-failure \
  --failure-type integration_error \
  --description "Created redundant n8n workflow instead of extending Command Parser" \
  --context "Should have run n8n_list_workflows before creating new workflows" \
  --task "Import Design Wizard workflows to n8n"

# Report a workflow design error
python orchestrator.py report-failure \
  --failure-type workflow_error \
  --description "Wrong node type used for error handling" \
  --context "Should use Error Trigger node, not regular IF node" \
  --task "Add error handling to webhook workflow"
```

**Available failure types:**
- `planning_error` - Wrong approach, misunderstood requirements
- `integration_error` - Missed existing infrastructure, created duplicates
- `workflow_error` - n8n workflow design issues
- `architecture_error` - Wrong design patterns
- `scope_error` - Over/under-scoped solutions
- `config_error` - Configuration or credential issues
- `other` - General failures

### Try the Example

```bash
# The example project has intentional bugs
cd example_project

# Run the learning loop
python ../orchestrator.py "Fix the safe_divide function to return None when dividing by zero"

# Watch the loop:
# 1. Claude attempts the fix
# 2. Tests run
# 3. If tests fail, Teacher analyzes
# 4. Rule added to CLAUDE.md
# 5. Retry with new knowledge
```

## Configuration

Edit `config.yaml` to customize:

```yaml
# Teacher LLM mode: "local" (Anthropic SDK) or "webhook" (n8n)
teacher:
  mode: "local"
  model: "claude-3-5-sonnet-20241022"
  max_tokens: 1024

# n8n webhook (only used if teacher.mode is "webhook")
n8n:
  webhook_url: "https://your-instance.app.n8n.cloud/webhook/prompt-learning-teacher"
  timeout: 60

learning:
  max_retries: 3
  auto_retry: true

# Failure sources configuration
failure_sources:
  - name: "pytest"
    type: "automated"
    enabled: true

  - name: "manual"
    type: "user_reported"
    enabled: true

  - name: "semantic"
    type: "llm_analysis"
    enabled: false  # Future feature

# Maps failure types to specialized prompts
failure_prompts:
  test_failure: "default"
  planning_error: "planning_error_system"
  integration_error: "integration_error_system"
  workflow_error: "workflow_error_system"
  architecture_error: "architecture_error_system"

tests:
  framework: "pytest"
  command: "pytest tests/ -v --tb=short"
  timeout: 120

claude:
  max_turns: 15
  output_format: "json"
```

## How It Works

### 1. Task Execution
The orchestrator runs Claude Code in headless mode:
```bash
claude -p "Your task" --output-format json --dangerously-skip-permissions
```

### 2. Test Verification
After Claude makes changes, pytest runs:
```bash
pytest tests/ -v --tb=short
```

### 3. Failure Analysis
If tests fail, the diff and errors are sent to n8n:
```json
{
  "diff": "git diff output...",
  "error_logs": "pytest failure output...",
  "task_description": "Original task"
}
```

### 4. Rule Generation
The Teacher LLM (Claude 3.5 Sonnet in n8n) analyzes the failure and generates a rule:
```markdown
- **Rule**: Always return None (not 0) when a function should indicate "no valid result"
- **When**: Implementing safe/fallback versions of operations that can fail
- **Why**: Returning 0 can be confused with a valid result; None clearly indicates absence
```

### 5. Knowledge Accumulation
Rules are appended to `~/.claude/CLAUDE.md` under "Learned Rules & Patterns":
```markdown
## Learned Rules & Patterns

- **Rule**: Always return None (not 0) when a function should indicate "no valid result"
- **When**: Implementing safe/fallback versions of operations that can fail
- **Why**: Returning 0 can be confused with a valid result; None clearly indicates absence
  - **Source**: Learned on 2024-12-07 from test failure
```

## Project Structure

```
PromptLearning/
├── orchestrator.py      # Main learning loop and CLI
├── teacher.py           # Local Teacher LLM (Anthropic SDK)
├── config.yaml          # Configuration options
├── requirements.txt     # Python dependencies
├── N8N_SETUP.md        # n8n workflow setup guide (webhook mode)
├── README.md           # This file
└── example_project/    # Sample project with intentional bugs
    ├── calculator.py   # Buggy calculator module
    ├── conftest.py     # Pytest configuration
    └── tests/
        └── test_calculator.py  # Tests that catch the bugs
```

## Limitations

- **Anthropic API Key Required**: Local mode requires `ANTHROPIC_API_KEY` environment variable
- **Commit-based Diffs**: Requires git; creates temporary commits for diff tracking
- **pytest Only**: Currently supports pytest (other frameworks could be added)
- **n8n Cloud Optional**: Webhook mode requires n8n Cloud setup (see N8N_SETUP.md)

## Security Considerations

- Code diffs are sent to n8n Cloud (review data policies)
- Uses `--dangerously-skip-permissions` for automation
- Store bearer tokens securely (not in version control)

## Contributing

Ideas for improvements:
- Support for Jest/Vitest
- Semantic analysis mode (LLM reviews Claude output quality)
- Rule deduplication and categorization
- Metrics and learning analytics
- Web UI for failure reporting

## License

MIT
