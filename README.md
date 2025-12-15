# Prompt Learning Loop

An automated meta-learning system that improves Claude Code's performance by iteratively updating its CLAUDE.md file based on test failures.

## Concept

This implements "Meta-Prompting" - instead of fine-tuning models, we improve the instructions they receive. When Claude Code makes a mistake that causes tests to fail, the system:

1. Captures the code diff and error logs
2. Sends them to a "Teacher" LLM (via n8n Cloud)
3. Analyzes the root cause of failure
4. Generates a preventive rule
5. Appends the rule to CLAUDE.md
6. Retries the task with the new knowledge

Over time, CLAUDE.md accumulates learned rules that prevent recurring mistakes.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL (Claude Code)                       │
├─────────────────────────────────────────────────────────────┤
│  1. Task → 2. Claude Attempt → 3. pytest → 4. Pass/Fail     │
│                                                 ↓            │
│                                          [If Fail]          │
│                                                 ↓            │
│  8. Retry ← 7. Append Rule ← 6. Parse ← [n8n Cloud Teacher] │
└─────────────────────────────────────────────────────────────┘
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

```bash
# Basic usage
python orchestrator.py "Your task description" --project-dir ./your-project

# With options
python orchestrator.py "Fix the validation bug" \
  --project-dir ./my-project \
  --max-retries 5 \
  --config ./config.yaml

# Manual retry mode (stops after each failure for review)
python orchestrator.py "Add error handling" --no-auto-retry
```

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
n8n:
  mcp_server: "n8n-teacher"
  tool_name: "analyze_failure"
  timeout: 60

learning:
  max_retries: 3
  auto_retry: true

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
├── orchestrator.py      # Main learning loop script
├── config.yaml          # Configuration options
├── requirements.txt     # Python dependencies
├── N8N_SETUP.md        # n8n workflow setup guide
├── README.md           # This file
└── example_project/    # Sample project with intentional bugs
    ├── calculator.py   # Buggy calculator module
    ├── conftest.py     # Pytest configuration
    └── tests/
        └── test_calculator.py  # Tests that catch the bugs
```

## Limitations

- **n8n Cloud Required**: Uses n8n Cloud for the Teacher LLM workflow
- **Commit-based Diffs**: Requires git; creates temporary commits for diff tracking
- **pytest Only**: Currently supports pytest (other frameworks could be added)
- **MCP Setup**: Requires MCP configuration between Claude Code and n8n

## Security Considerations

- Code diffs are sent to n8n Cloud (review data policies)
- Uses `--dangerously-skip-permissions` for automation
- Store bearer tokens securely (not in version control)

## Contributing

Ideas for improvements:
- Support for Jest/Vitest
- Local LLM option instead of n8n Cloud
- Rule deduplication and categorization
- Metrics and learning analytics

## License

MIT
