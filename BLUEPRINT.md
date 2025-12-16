# Prompt Learning Loop - Project Blueprint

## Project Status: Testing Complete (Partial)

## Completed Phases

- [x] **Phase 1: Project Setup**
  - Created project directory structure
  - Created orchestrator.py with main learning loop
  - Created requirements.txt and config.yaml
  - Added "Learned Rules & Patterns" section to CLAUDE.md

- [x] **Phase 2: Example Project**
  - Created example_project with intentional bugs
  - Set up pytest test suite
  - Initialized git repository

- [x] **Phase 3: Documentation**
  - Created N8N_SETUP.md with detailed workflow instructions
  - Created README.md with usage guide

- [x] **Phase 4: n8n Workflow Deployment**
  - Workflow created and activated in n8n Cloud
  - Webhook URL: https://im4tlai.app.n8n.cloud/webhook/prompt-learning-teacher
  - Anthropic credentials configured
  - orchestrator.py updated to use webhook

- [x] **Phase 5: End-to-End Testing** (2025-12-15)
  - Orchestrator runs successfully
  - Claude Code fixed the `safe_divide` bug on first attempt
  - All tests passed after fix
  - Git commit created: "Learning Loop Attempt 1"
  - **Note**: No rules generated (no failure occurred to trigger Teacher LLM)

## Test Results (2025-12-15)

| Test | Result | Notes |
|------|--------|-------|
| Orchestrator execution | ✓ Pass | Ran with `--teacher webhook` mode |
| Claude Code task attempt | ✓ Pass | Fixed bug: `return 0` → `return None` |
| Git commit tracking | ✓ Pass | Commit created for diff tracking |
| pytest verification | ✓ Pass | 7/7 tests passed after fix |
| Teacher LLM feedback | ⚠ Not tested | Bug fixed on first attempt |
| Rule appending | ⚠ Not tested | No failure occurred |

## Pending Phases

- [ ] **Phase 6: Full Feedback Loop Testing**
  - Create a more complex bug that Claude initially gets wrong
  - Verify n8n webhook receives failure data
  - Confirm rule generation and CLAUDE.md appending
  - Test retry mechanism with learned rules

## Files Created

| File | Purpose |
|------|---------|
| `orchestrator.py` | Main Python script for the learning loop |
| `config.yaml` | Configuration options |
| `requirements.txt` | Python dependencies |
| `N8N_SETUP.md` | n8n workflow setup guide |
| `README.md` | Project documentation |
| `example_project/` | Test project with intentional bugs |

## Next Steps

1. Create a more challenging example that Claude initially gets wrong
2. Run orchestrator to trigger Teacher LLM feedback
3. Verify rule generation and CLAUDE.md appending

## Key Decisions Made

- **Architecture**: Claude Code as Orchestrator (n8n for Teacher LLM only)
- **Teacher Mode**: Webhook (n8n) or Local (Anthropic SDK)
- **Test Framework**: pytest only
- **Diff Strategy**: Commit-based (git diff HEAD~1)
- **Retry Mode**: Configurable (auto/manual)

## Usage

```bash
# Basic usage (uses webhook mode by default)
python3 orchestrator.py "Fix the safe_divide function" --project-dir ./example_project

# With explicit teacher mode
python3 orchestrator.py "Fix the bug" --project-dir ./example_project --teacher webhook

# With local Anthropic SDK (requires ANTHROPIC_API_KEY)
python3 orchestrator.py "Fix the bug" --project-dir ./example_project --teacher local
```
