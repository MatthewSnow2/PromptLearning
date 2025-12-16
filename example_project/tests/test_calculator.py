"""
Test suite for the calculator module.

These tests verify correct behavior, including the safe_divide function
which should return None when dividing by zero.
"""

import pytest
from calculator import add, subtract, multiply, safe_divide


class TestBasicOperations:
    """Test basic arithmetic operations."""

    def test_add(self):
        assert add(2, 3) == 5
        assert add(-1, 1) == 0
        assert add(0, 0) == 0

    def test_subtract(self):
        assert subtract(5, 3) == 2
        assert subtract(1, 1) == 0
        assert subtract(0, 5) == -5

    def test_multiply(self):
        assert multiply(3, 4) == 12
        assert multiply(-2, 3) == -6
        assert multiply(0, 100) == 0


class TestSafeDivide:
    """Test the safe_divide function."""

    def test_normal_division(self):
        """Test that normal division works correctly."""
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(9, 3) == 3.0
        assert safe_divide(7, 2) == 3.5

    def test_divide_by_zero_returns_none(self):
        """
        Test that dividing by zero returns None, not 0.

        This is the key test that catches the bug.
        Returning None clearly indicates "no valid result"
        whereas returning 0 could be confused with a legitimate answer.
        """
        result = safe_divide(10, 0)
        assert result is None, f"Expected None when dividing by zero, got {result}"

    def test_divide_zero_by_number(self):
        """Test that 0 divided by a number returns 0."""
        assert safe_divide(0, 5) == 0.0

    def test_negative_division(self):
        """Test division with negative numbers."""
        assert safe_divide(-10, 2) == -5.0
        assert safe_divide(10, -2) == -5.0
        assert safe_divide(-10, -2) == 5.0
