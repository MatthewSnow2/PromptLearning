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
    """

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    # System prompts for the two-step analysis
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

    def analyze_root_cause(self, diff: str, errors: str, task: str) -> str:
        """
        Analyze the root cause of a test failure.

        Args:
            diff: Git diff showing code changes
            errors: Test error output
            task: Original task description

        Returns:
            Root cause analysis as a string
        """
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
            system=self.ROOT_CAUSE_SYSTEM,
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
