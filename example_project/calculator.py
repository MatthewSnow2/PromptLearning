"""
Calculator module with intentional bugs for testing the Prompt Learning Loop.

The safe_divide function has a bug: it returns 0 instead of None
when dividing by zero. This is the bug that Claude Code should fix.
"""


def add(a, b):
    """Add two numbers."""
    return a + b


def subtract(a, b):
    """Subtract b from a."""
    return a - b


def multiply(a, b):
    """Multiply two numbers."""
    return a * b


def safe_divide(a, b):
    """
    Safely divide a by b.

    Returns None if b is zero to indicate division is not possible.

    BUG: Currently returns 0 instead of None when b is zero.
    This is incorrect because 0 could be confused with a valid result.
    """
    if b == 0:
        return None
    return a / b
