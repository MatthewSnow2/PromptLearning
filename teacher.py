#!/usr/bin/env python3
"""
Local Teacher LLM Module

Provides AI-powered analysis of test failures and generates preventive rules
for CLAUDE.md using the Anthropic SDK directly.
"""

import os
import re
from typing import Optional

try:
    import anthropic
except ImportError:
    anthropic = None


class TeacherLLM:
    """
    Local Teacher LLM for analyzing failures and generating rules.

    Uses the Anthropic SDK to call Claude directly, bypassing n8n.
    Requires ANTHROPIC_API_KEY environment variable.

    Supports multiple failure types:
    - Test failures (pytest, etc.)
    - Planning errors (wrong approach)
    - Integration errors (missed existing infrastructure)
    - Workflow errors (n8n design issues)
    - Architecture errors (wrong patterns)
    """

    DEFAULT_MODEL = "claude-3-5-haiku-20241022"

    # ============ SYSTEM PROMPTS ============

    # Default system prompt for test failures
    ROOT_CAUSE_SYSTEM = """You are a senior software engineer analyzing test failures.

Given:
- Task Description: What the developer was trying to accomplish
- Code Diff: The changes made to the codebase
- Error Logs: The test failure output

Analyze and explain:
1. What specific error occurred
2. WHY the code failed (root cause)
3. The pattern of mistake (e.g., "forgot null check", "wrong API usage", "missing import")

Be concise and technical. Focus on the actionable root cause."""

    RULE_GENERATOR_SYSTEM = """Based on the root cause analysis provided, write a SINGLE preventive rule
for the developer's CLAUDE.md file. This rule should:

1. Be actionable and specific
2. Prevent this exact type of error in the future
3. Follow this EXACT format (including the markdown formatting):

### [Short Category Name]
- **Rule**: [Clear instruction in imperative form]
- **When**: [Context when this rule applies]
- **Why**: [Brief explanation]

Example output:
### Array Safety
- **Rule**: Always check if array is empty before accessing index 0
- **When**: Working with arrays from API responses or user input
- **Why**: Prevents IndexError on empty results

IMPORTANT: Output ONLY the rule in the format above. No additional text or explanation."""

    # ============ DOMAIN-SPECIFIC PROMPTS ============

    # For planning errors (wrong approach, misunderstood requirements)
    PLANNING_ERROR_SYSTEM = """You are a senior engineer analyzing planning failures.

The AI made a mistake in HOW it approached a task, not in the code itself.
Common causes:
- Assumed blank slate instead of checking existing infrastructure
- Misunderstood requirements or scope
- Chose wrong integration approach
- Over-scoped or under-scoped the solution
- Didn't verify preconditions before acting

Given:
- Task Description: What was being attempted
- Context: What should have happened
- Failure Description: What went wrong

Analyze:
1. WHY the approach was wrong
2. What check or verification was missed
3. The pattern of planning mistake

Be concise and focus on the PROCESS failure, not code."""

    # For integration errors (missed existing systems)
    INTEGRATION_ERROR_SYSTEM = """You are a systems architect analyzing integration failures.

The AI created something new when it should have extended existing infrastructure.
Common causes:
- Didn't check for existing systems before creating new ones
- Assumed blank slate instead of inventory check
- Missed related components that should be extended
- Created duplicate functionality

Given:
- Task Description: What was being attempted
- Context: What existing infrastructure was missed
- Failure Description: What redundant thing was created

Analyze:
1. What check would have found the existing system
2. Why the "create new" approach was wrong
3. The verification pattern that was skipped

Focus on the DISCOVERY failure, not implementation."""

    # For workflow errors (n8n design issues)
    WORKFLOW_ERROR_SYSTEM = """You are an n8n workflow architect analyzing workflow design failures.

The workflow had structural or design issues:
- Wrong node types chosen
- Missing error handling paths
- Incorrect node connections or routing
- Integration with existing workflows missed
- Credential or configuration issues

Given:
- Task Description: The workflow being built
- Context: What should have happened
- Failure Description: The design issue

Analyze:
1. What n8n best practice was violated
2. What verification step was skipped
3. The workflow design pattern that should have been used

Focus on n8n-specific design principles."""

    # For architecture errors (wrong patterns)
    ARCHITECTURE_ERROR_SYSTEM = """You are a software architect analyzing architectural failures.

The AI chose the wrong design pattern or structure:
- Wrong abstraction level
- Incorrect separation of concerns
- Missing or wrong design patterns
- Scalability or maintainability issues

Given:
- Task Description: What was being designed
- Context: What pattern should have been used
- Failure Description: What went wrong

Analyze:
1. What architectural principle was violated
2. What design pattern should have been applied
3. The decision process that led to the wrong choice

Focus on architectural principles and patterns."""

    # Map failure types to prompts
    FAILURE_TYPE_PROMPTS = {
        "test_failure": ROOT_CAUSE_SYSTEM,
        "planning_error": PLANNING_ERROR_SYSTEM,
        "integration_error": INTEGRATION_ERROR_SYSTEM,
        "workflow_error": WORKFLOW_ERROR_SYSTEM,
        "architecture_error": ARCHITECTURE_ERROR_SYSTEM,
        "scope_error": PLANNING_ERROR_SYSTEM,  # Use planning prompt
        "config_error": INTEGRATION_ERROR_SYSTEM,  # Use integration prompt
        "other": ROOT_CAUSE_SYSTEM,  # Default to test failure prompt
    }

    def __init__(self, model: str = None, max_tokens: int = 1024):
        """
        Initialize the Teacher LLM.

        Args:
            model: Anthropic model to use (default: claude-3-5-sonnet-20241022)
            max_tokens: Maximum tokens for responses
        """
        if anthropic is None:
            raise ImportError(
                "anthropic package is required. Install with: pip install anthropic"
            )

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required. "
                "Set it with: set ANTHROPIC_API_KEY=your-key-here (Windows) "
                "or export ANTHROPIC_API_KEY=your-key-here (Linux/Mac)"
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens

    def analyze_root_cause(self, diff: str, errors: str, task: str,
                           failure_type: str = "test_failure") -> str:
        """
        Analyze the root cause of a failure.

        Args:
            diff: Git diff or context information
            errors: Test error output or failure description
            task: Original task description
            failure_type: Type of failure (determines which prompt to use)

        Returns:
            Root cause analysis as a string
        """
        # Select appropriate system prompt based on failure type
        system_prompt = self.FAILURE_TYPE_PROMPTS.get(
            failure_type, self.ROOT_CAUSE_SYSTEM
        )

        # Format user message based on failure type
        if failure_type in ["planning_error", "integration_error", "workflow_error",
                          "architecture_error", "scope_error", "config_error"]:
            # Non-test failures use context/description format
            user_message = f"""## Task Description
{task}

{diff[:8000] if diff else "No context available"}

{errors[:4000] if errors else "No failure description available"}

Analyze the root cause of this failure."""
        else:
            # Test failures use diff/error log format
            user_message = f"""## Task Description
{task}

## Code Diff
```
{diff[:8000] if diff else "No diff available"}
```

## Error Logs
```
{errors[:4000] if errors else "No error logs available"}
```

Analyze the root cause of this test failure."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        return response.content[0].text

    def generate_rule(self, root_cause_analysis: str) -> str:
        """
        Generate a preventive rule based on root cause analysis.

        Args:
            root_cause_analysis: The root cause analysis from analyze_root_cause()

        Returns:
            A formatted rule for CLAUDE.md
        """
        user_message = f"""Based on this root cause analysis, generate a preventive rule:

{root_cause_analysis}

Remember: Output ONLY the rule in the exact format specified. No additional text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            system=self.RULE_GENERATOR_SYSTEM,
            messages=[{"role": "user", "content": user_message}]
        )

        return response.content[0].text.strip()

    def analyze_failure(self, diff: str, errors: str, task: str) -> dict:
        """
        Full analysis pipeline: root cause + rule generation.

        Args:
            diff: Git diff showing code changes
            errors: Test error output
            task: Original task description

        Returns:
            dict with keys: analysis, rule, error_type
        """
        try:
            # Step 1: Root cause analysis
            analysis = self.analyze_root_cause(diff, errors, task)

            # Step 2: Generate rule
            rule = self.generate_rule(analysis)

            # Extract error type from analysis (simple heuristic)
            error_type = self._extract_error_type(analysis, errors)

            return {
                "analysis": analysis,
                "rule": rule,
                "error_type": error_type
            }

        except anthropic.APIError as e:
            return {
                "analysis": f"API error: {e}",
                "rule": "",
                "error_type": "api_error"
            }
        except Exception as e:
            return {
                "analysis": f"Analysis failed: {e}",
                "rule": "",
                "error_type": "analysis_error"
            }

    def _extract_error_type(self, analysis: str, errors: str) -> str:
        """Extract a short error type label from the analysis or errors."""
        # Common Python error patterns
        error_patterns = [
            # Python exceptions
            (r"TypeError", "type_error"),
            (r"ValueError", "value_error"),
            (r"AttributeError", "attribute_error"),
            (r"KeyError", "key_error"),
            (r"IndexError", "index_error"),
            (r"ImportError", "import_error"),
            (r"NameError", "name_error"),
            (r"ZeroDivisionError", "division_error"),
            (r"AssertionError", "assertion_error"),
            (r"SyntaxError", "syntax_error"),
            (r"RuntimeError", "runtime_error"),

            # Planning/process failures
            (r"misunderstood|wrong approach|should have", "planning_error"),
            (r"redundant|duplicate|already exists", "integration_error"),
            (r"scope.*creep|over-engineered|too complex", "scope_error"),

            # Workflow/n8n failures
            (r"n8n|workflow.*design|node.*wrong", "workflow_error"),
            (r"credential|authentication.*missing|config", "config_error"),

            # Architecture failures
            (r"pattern.*wrong|architecture.*mismatch|design.*error", "architecture_error"),
        ]

        combined = f"{analysis} {errors}"
        for pattern, error_type in error_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return error_type

        return "test_failure"


def test_teacher():
    """Quick test of the TeacherLLM."""
    print("Testing TeacherLLM...")

    teacher = TeacherLLM()

    # Sample test data
    diff = """
diff --git a/calculator.py b/calculator.py
--- a/calculator.py
+++ b/calculator.py
@@ -1,5 +1,5 @@
 def safe_divide(a, b):
     if b == 0:
-        return None
+        return 0  # BUG: Should return None
     return a / b
"""

    errors = """
FAILED tests/test_calculator.py::test_safe_divide_by_zero
AssertionError: assert 0 is None
  where 0 = safe_divide(10, 0)
"""

    task = "Fix the safe_divide function to handle division by zero"

    print("\nAnalyzing failure...")
    result = teacher.analyze_failure(diff, errors, task)

    print(f"\n--- Root Cause Analysis ---\n{result['analysis']}")
    print(f"\n--- Generated Rule ---\n{result['rule']}")
    print(f"\n--- Error Type: {result['error_type']}")

    return result


if __name__ == "__main__":
    test_teacher()
