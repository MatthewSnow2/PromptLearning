#!/usr/bin/env python3
"""
Prompt Learning Loop Orchestrator

An automated meta-learning system where Claude Code attempts coding tasks,
verifies them via pytest, and when failures occur, uses a Teacher LLM
to analyze errors and generate rules that get appended to CLAUDE.md.

Supports two Teacher modes:
- local: Uses Anthropic SDK directly (requires ANTHROPIC_API_KEY)
- webhook: Uses n8n Cloud webhook (fallback option)

Now also supports manual failure reporting for non-test failures:
- Planning errors
- Workflow design errors
- Architecture decisions
- Integration mistakes

Usage:
    # Run learning loop (test-based)
    python orchestrator.py run "Fix the bug" --project-dir ./my-project
    python orchestrator.py run "Add validation" --max-retries 5 --no-auto-retry

    # Report manual failure (non-test)
    python orchestrator.py report-failure \\
        --failure-type "integration_error" \\
        --description "Created redundant workflow instead of extending existing" \\
        --context "Should have checked existing infrastructure first" \\
        --task "Deploy new n8n workflow"
"""

import subprocess
import json
import sys
import yaml
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Union

# Default n8n webhook URL - used if teacher mode is "webhook"
DEFAULT_N8N_WEBHOOK_URL = "https://im4tlai.app.n8n.cloud/webhook/prompt-learning-teacher"

# Windows shell handling
IS_WINDOWS = sys.platform == "win32"


def run_command(cmd: Union[List[str], str], cwd: Path = None, timeout: int = 120,
                capture_output: bool = True, text: bool = True) -> subprocess.CompletedProcess:
    """Run a command with cross-platform support."""
    if IS_WINDOWS and isinstance(cmd, list):
        # Convert list to shell string for Windows
        cmd_str = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)
        return subprocess.run(cmd_str, cwd=cwd, timeout=timeout,
                              capture_output=capture_output, text=text, shell=True)
    else:
        return subprocess.run(cmd, cwd=cwd, timeout=timeout,
                              capture_output=capture_output, text=text)


class PromptLearningLoop:
    """Orchestrates the prompt learning feedback loop."""

    def __init__(
        self,
        project_dir: str,
        max_retries: int = 3,
        auto_retry: bool = True,
        config_path: Optional[str] = None
    ):
        self.project_dir = Path(project_dir).resolve()
        self.max_retries = max_retries
        self.auto_retry = auto_retry
        self.claude_md_path = Path.home() / ".claude" / "CLAUDE.md"

        # Load config if provided
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from YAML file."""
        default_config = {
            "teacher": {
                "mode": "local",  # "local" or "webhook"
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 1024
            },
            "n8n": {
                "webhook_url": DEFAULT_N8N_WEBHOOK_URL,
                "timeout": 60
            },
            "tests": {
                "framework": "pytest",
                "command": "pytest tests/ -v --tb=short",
                "timeout": 120
            },
            "claude": {
                "max_turns": 15,
                "output_format": "json"
            }
        }

        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                user_config = yaml.safe_load(f)
                # Merge with defaults
                for key in user_config:
                    if key in default_config and isinstance(default_config[key], dict):
                        default_config[key].update(user_config[key])
                    else:
                        default_config[key] = user_config[key]

        return default_config

    def attempt_task(self, task: str) -> dict:
        """Run Claude Code in headless mode to attempt the task."""
        cmd = [
            "claude", "-p", task,
            "--output-format", self.config["claude"]["output_format"],
            "--dangerously-skip-permissions",
            "--max-turns", str(self.config["claude"]["max_turns"])
        ]

        print(f"  Command: {' '.join(cmd[:3])}...")

        result = run_command(cmd, cwd=self.project_dir, timeout=600)

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "code": result.returncode
        }

    def run_tests(self) -> dict:
        """Execute pytest test suite."""
        test_cmd = self.config["tests"]["command"].split()

        result = run_command(test_cmd, cwd=self.project_dir,
                             timeout=self.config["tests"]["timeout"])

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "code": result.returncode
        }

    def get_diff(self) -> str:
        """Get git diff of changes (commit-based)."""
        result = run_command(["git", "diff", "HEAD~1"], cwd=self.project_dir)
        return result.stdout

    def analyze_failure(self, diff: str, errors: str, task: str) -> dict:
        """
        Analyze failure using configured Teacher mode.

        Routes to either local (Anthropic SDK) or webhook (n8n) based on config.
        """
        mode = self.config["teacher"]["mode"]

        if mode == "local":
            return self.analyze_failure_local(diff, errors, task)
        else:
            return self.analyze_failure_via_webhook(diff, errors, task)

    def analyze_failure_local(self, diff: str, errors: str, task: str) -> dict:
        """
        Analyze failure using local Anthropic SDK.

        Requires ANTHROPIC_API_KEY environment variable.
        """
        try:
            from teacher import TeacherLLM

            model = self.config["teacher"]["model"]
            max_tokens = self.config["teacher"]["max_tokens"]

            teacher = TeacherLLM(model=model, max_tokens=max_tokens)
            return teacher.analyze_failure(diff, errors, task)

        except ImportError as e:
            print(f"  [WARN] Teacher module not available: {e}")
            print("  [WARN] Falling back to webhook mode...")
            return self.analyze_failure_via_webhook(diff, errors, task)
        except ValueError as e:
            # Missing API key
            print(f"  [WARN] {e}")
            print("  [WARN] Falling back to webhook mode...")
            return self.analyze_failure_via_webhook(diff, errors, task)
        except Exception as e:
            print(f"  [WARN] Local analysis failed: {e}")
            return {"analysis": "", "rule": "", "error_type": "local_analysis_error"}

    def analyze_failure_via_webhook(self, diff: str, errors: str, task: str) -> dict:
        """
        Call n8n webhook for Teacher LLM analysis.

        Sends the diff, error logs, and task description to the n8n workflow
        which uses Claude to analyze the failure and generate a preventive rule.
        """
        webhook_url = self.config["n8n"]["webhook_url"]
        timeout = self.config["n8n"]["timeout"]

        # Truncate large inputs to avoid payload issues
        payload = {
            "diff": diff[:10000] if diff else "",
            "error_logs": errors[:5000] if errors else "",
            "task_description": task
        }

        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()

            # Handle the response format from n8n
            return {
                "analysis": result.get("analysis", ""),
                "rule": result.get("rule", ""),
                "error_type": result.get("error_type", "test_failure")
            }

        except requests.exceptions.Timeout:
            print(f"  [WARN] Webhook timeout after {timeout}s")
            return {"analysis": "", "rule": "", "error_type": "timeout"}
        except requests.exceptions.RequestException as e:
            print(f"  [WARN] Webhook request failed: {e}")
            return {"analysis": "", "rule": "", "error_type": "request_failed"}
        except json.JSONDecodeError:
            print(f"  [WARN] Invalid JSON response from webhook")
            return {"analysis": "", "rule": "", "error_type": "invalid_response"}

    def append_rule(self, rule: str, error_type: str = "Unknown"):
        """Append learned rule to CLAUDE.md with metadata."""
        if not rule.strip():
            print("  [WARN] No rule to append (empty)")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Format the entry
        entry = f"""
{rule}
  - **Source**: Learned on {timestamp} from {error_type}
"""

        # Read existing content to check for Learned Rules section
        content = ""
        if self.claude_md_path.exists():
            content = self.claude_md_path.read_text()

        # Check if Learned Rules section exists
        if "## Learned Rules & Patterns" not in content:
            # Add the section header first
            entry = f"""
## Learned Rules & Patterns

Rules automatically generated from the Prompt Learning Loop.

{entry}"""

        with open(self.claude_md_path, "a") as f:
            f.write(entry)

        print(f"  [OK] Rule appended to {self.claude_md_path}")

    def commit_attempt(self, attempt_num: int) -> bool:
        """Commit changes for diff tracking."""
        # Stage all changes
        run_command(["git", "add", "."], cwd=self.project_dir)

        # Check if there are changes to commit
        status = run_command(["git", "status", "--porcelain"], cwd=self.project_dir)

        if not status.stdout.strip():
            print("  [WARN] No changes to commit")
            return False

        # Commit
        result = run_command(
            ["git", "commit", "-m", f"Learning Loop Attempt {attempt_num}"],
            cwd=self.project_dir
        )

        return result.returncode == 0

    def reset_attempt(self):
        """Reset to before the failed attempt."""
        run_command(["git", "reset", "--hard", "HEAD~1"], cwd=self.project_dir)

    def report_manual_failure(
        self,
        failure_type: str,
        description: str,
        context: str,
        task: str
    ) -> bool:
        """
        Process manually reported failures (not from tests).

        This is for capturing lessons from planning errors, integration mistakes,
        workflow design issues, and other non-test failures.

        Args:
            failure_type: Category of failure (e.g., 'planning_error', 'integration_error')
            description: What went wrong
            context: Additional context about what should have happened
            task: The original task that was being attempted

        Returns:
            True if rule was successfully generated and appended
        """
        print(f"\n{'='*60}")
        print("MANUAL FAILURE REPORT")
        print(f"{'='*60}")
        print(f"Type: {failure_type}")
        print(f"Task: {task[:80]}{'...' if len(task) > 80 else ''}")
        print(f"{'='*60}")

        # Use context as "diff" and description as "errors" for the Teacher LLM
        print("\n> Analyzing failure with Teacher LLM...")
        analysis = self.analyze_failure(
            diff=f"## Context\n{context}",
            errors=f"## Failure Description\n{description}",
            task=task
        )

        if analysis.get("analysis"):
            print(f"  [OK] Analysis: {analysis['analysis'][:100]}...")

        # Append rule to CLAUDE.md
        print("\n> Learning from failure...")
        rule = analysis.get("rule", "")
        if rule:
            print(f"  New Rule: {rule[:100]}...")
            # Use provided failure_type, not extracted one
            self.append_rule(rule, f"{failure_type} (manual report)")
            print(f"\n{'='*60}")
            print("[OK] SUCCESS: Rule appended to CLAUDE.md")
            print(f"{'='*60}")
            return True
        else:
            print("  [WARN] No rule generated")
            print(f"\n{'='*60}")
            print("[FAIL] No rule could be generated")
            print(f"{'='*60}")
            return False

    def run(self, task: str) -> bool:
        """Main learning loop."""
        print(f"\n{'='*60}")
        print("PROMPT LEARNING LOOP")
        print(f"{'='*60}")
        print(f"Task: {task[:80]}{'...' if len(task) > 80 else ''}")
        print(f"Project: {self.project_dir}")
        print(f"Max Retries: {self.max_retries}")
        print(f"Auto-Retry: {self.auto_retry}")
        print(f"{'='*60}")

        for attempt in range(1, self.max_retries + 1):
            print(f"\n{'-'*50}")
            print(f"ATTEMPT {attempt}/{self.max_retries}")
            print(f"{'-'*50}")

            # Step 1: Attempt the task
            print("\n> Step 1: Executing task with Claude Code...")
            try:
                self.attempt_task(task)
                print("  [OK] Task execution completed")
            except subprocess.TimeoutExpired:
                print("  [FAIL] Task execution timed out")
                continue
            except Exception as e:
                print(f"  [FAIL] Task execution failed: {e}")
                continue

            # Step 2: Commit changes for diff
            print("\n> Step 2: Committing changes...")
            if not self.commit_attempt(attempt):
                print("  [WARN] No changes were made by Claude")
                # Continue anyway to run tests

            # Step 3: Run pytest
            print("\n> Step 3: Running tests...")
            try:
                test_result = self.run_tests()
            except subprocess.TimeoutExpired:
                print("  [FAIL] Tests timed out")
                continue

            if test_result["code"] == 0:
                print("\n" + "="*50)
                print("[OK] SUCCESS: All tests passed!")
                print("="*50)
                return True

            print(f"  [FAIL] Tests failed (exit code: {test_result['code']})")

            # Show test output summary
            output = test_result["stderr"] or test_result["stdout"]
            if output:
                lines = output.strip().split('\n')
                print(f"  Last 5 lines of output:")
                for line in lines[-5:]:
                    print(f"    {line[:80]}")

            # Step 4: Analyze failure with Teacher LLM
            teacher_mode = self.config["teacher"]["mode"]
            print(f"\n> Step 4: Analyzing failure with Teacher LLM ({teacher_mode} mode)...")
            try:
                diff = self.get_diff()
                analysis = self.analyze_failure(
                    diff=diff,
                    errors=output,
                    task=task
                )
                print(f"  [OK] Analysis received")

                if analysis.get("analysis"):
                    print(f"  Root Cause: {analysis['analysis'][:100]}...")
            except Exception as e:
                print(f"  [FAIL] Analysis failed: {e}")
                analysis = {"rule": "", "error_type": "analysis_failed"}

            # Step 5: Append rule to CLAUDE.md
            print("\n> Step 5: Learning from failure...")
            rule = analysis.get("rule", "")
            if rule:
                print(f"  New Rule: {rule[:100]}...")
                self.append_rule(rule, analysis.get("error_type", "test failure"))
            else:
                print("  [WARN] No rule generated")

            # Step 6: Reset for retry
            print("\n> Step 6: Resetting for next attempt...")
            self.reset_attempt()
            print("  [OK] Reset complete")

            if not self.auto_retry:
                print("\n[WARN] Auto-retry disabled. Stopping for manual review.")
                return False

        print(f"\n{'='*50}")
        print(f"[FAIL] FAILED: Max retries ({self.max_retries}) exceeded")
        print(f"{'='*50}")
        return False


def main():
    """CLI entry point with subcommands."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Prompt Learning Loop - Automated meta-learning for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run test-based learning loop
    python orchestrator.py run "Fix the validation bug" --project-dir ./my-project
    python orchestrator.py run "Add error handling" --max-retries 5 --teacher webhook

    # Report manual failure (non-test)
    python orchestrator.py report-failure \\
        --failure-type "integration_error" \\
        --description "Created redundant workflow" \\
        --context "Should have checked existing infrastructure first" \\
        --task "Deploy n8n workflow"

    # Legacy mode (without subcommand, defaults to 'run')
    python orchestrator.py "Fix the bug" --project-dir ./my-project
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ========== 'run' subcommand ==========
    run_parser = subparsers.add_parser(
        "run",
        help="Run the test-based learning loop",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    run_parser.add_argument(
        "task",
        help="Task description for Claude Code to attempt"
    )
    run_parser.add_argument(
        "--project-dir", "-d",
        default=".",
        help="Project directory (default: current directory)"
    )
    run_parser.add_argument(
        "--max-retries", "-r",
        type=int,
        default=3,
        help="Maximum retry attempts (default: 3)"
    )
    run_parser.add_argument(
        "--no-auto-retry",
        action="store_true",
        help="Disable automatic retry after failure"
    )
    run_parser.add_argument(
        "--teacher", "-t",
        choices=["local", "webhook"],
        default=None,
        help="Teacher LLM mode: 'local' (Anthropic SDK) or 'webhook' (n8n)"
    )
    run_parser.add_argument(
        "--config", "-c",
        help="Path to config.yaml file"
    )

    # ========== 'report-failure' subcommand ==========
    report_parser = subparsers.add_parser(
        "report-failure",
        help="Report a manual (non-test) failure for learning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Failure Types:
    planning_error      - Misunderstood requirements or wrong approach
    integration_error   - Missed existing infrastructure, created duplicates
    workflow_error      - n8n workflow design issues
    architecture_error  - Wrong design patterns or structure
    scope_error         - Over-engineered or under-scoped solution
    config_error        - Missing or wrong configuration

Example:
    python orchestrator.py report-failure \\
        --failure-type "integration_error" \\
        --description "Created standalone workflow instead of extending existing Command Parser" \\
        --context "Should have run n8n_list_workflows before creating new workflows" \\
        --task "Import Design Wizard workflows to n8n"
        """
    )
    report_parser.add_argument(
        "--failure-type", "-f",
        required=True,
        choices=[
            "planning_error", "integration_error", "workflow_error",
            "architecture_error", "scope_error", "config_error", "other"
        ],
        help="Type of failure"
    )
    report_parser.add_argument(
        "--description", "-D",
        required=True,
        help="What went wrong"
    )
    report_parser.add_argument(
        "--context", "-C",
        required=True,
        help="Additional context (what should have happened)"
    )
    report_parser.add_argument(
        "--task", "-T",
        required=True,
        help="The original task being attempted"
    )
    report_parser.add_argument(
        "--teacher", "-t",
        choices=["local", "webhook"],
        default=None,
        help="Teacher LLM mode: 'local' (Anthropic SDK) or 'webhook' (n8n)"
    )
    report_parser.add_argument(
        "--config", "-c",
        help="Path to config.yaml file"
    )

    args = parser.parse_args()

    # Handle legacy mode (no subcommand, task as first positional arg)
    if args.command is None:
        # Check if there's a positional arg that looks like a task
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            # Legacy mode: treat first arg as task
            args.command = "run"
            args.task = sys.argv[1]
            # Re-parse remaining args for run command
            remaining = sys.argv[2:]
            legacy_parser = argparse.ArgumentParser()
            legacy_parser.add_argument("--project-dir", "-d", default=".")
            legacy_parser.add_argument("--max-retries", "-r", type=int, default=3)
            legacy_parser.add_argument("--no-auto-retry", action="store_true")
            legacy_parser.add_argument("--teacher", "-t", choices=["local", "webhook"], default=None)
            legacy_parser.add_argument("--config", "-c", default=None)
            legacy_args = legacy_parser.parse_args(remaining)
            args.project_dir = legacy_args.project_dir
            args.max_retries = legacy_args.max_retries
            args.no_auto_retry = legacy_args.no_auto_retry
            args.teacher = legacy_args.teacher
            args.config = legacy_args.config
        else:
            parser.print_help()
            sys.exit(1)

    # ========== Execute command ==========
    if args.command == "run":
        # Validate project directory
        project_path = Path(args.project_dir).resolve()
        if not project_path.exists():
            print(f"Error: Project directory does not exist: {project_path}")
            sys.exit(1)

        # Check for git repo
        git_dir = project_path / ".git"
        if not git_dir.exists():
            print(f"Error: Project directory is not a git repository: {project_path}")
            print("Initialize with: git init")
            sys.exit(1)

        # Run the learning loop
        loop = PromptLearningLoop(
            project_dir=str(project_path),
            max_retries=args.max_retries,
            auto_retry=not args.no_auto_retry,
            config_path=args.config
        )

        # Override teacher mode if specified via CLI
        if args.teacher:
            loop.config["teacher"]["mode"] = args.teacher
            print(f"Teacher mode: {args.teacher}")

        success = loop.run(args.task)
        sys.exit(0 if success else 1)

    elif args.command == "report-failure":
        # Create loop instance (no project_dir needed for manual reports)
        loop = PromptLearningLoop(
            project_dir=".",  # Not used for manual reports
            config_path=args.config
        )

        # Override teacher mode if specified via CLI
        if args.teacher:
            loop.config["teacher"]["mode"] = args.teacher
            print(f"Teacher mode: {args.teacher}")

        success = loop.report_manual_failure(
            failure_type=args.failure_type,
            description=args.description,
            context=args.context,
            task=args.task
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
