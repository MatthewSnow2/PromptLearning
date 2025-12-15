# Prompt Learning Loop - Project Blueprint

## Project Status: Ready for Testing

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

## Pending Phases

- [ ] **Phase 5: End-to-End Testing**
  - Test complete flow with example project
  - Verify rules are correctly appended
  - Validate retry mechanism

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

1. Follow N8N_SETUP.md to create the n8n workflow
2. Configure Claude Code MCP settings
3. Test with example project:
   ```bash
   python orchestrator.py "Fix the safe_divide function" --project-dir ./example_project
   ```

## Key Decisions Made

- **Architecture**: Claude Code as Orchestrator (n8n for Teacher LLM only)
- **MCP Trigger**: Using n8n's MCP Server Trigger (not webhook)
- **Test Framework**: pytest only
- **Diff Strategy**: Commit-based (git diff HEAD~1)
- **Retry Mode**: Configurable (auto/manual)
