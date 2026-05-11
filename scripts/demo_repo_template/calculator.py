"""Simple calculator with basic arithmetic operations.

This is the baseline module of the CodeScribe demo repository. New features
land in separate modules (see ``advanced_ops.py``) via pull requests so the
CodeScribe agents have something concrete to review.
"""

from __future__ import annotations


def add(a: float, b: float) -> float:
    """Return the sum of two numbers."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Return the difference between two numbers."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of two numbers."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return the quotient of two numbers.

    Raises:
        ValueError: if the denominator is zero.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def main() -> None:
    print("CodeScribe Calculator")
    print(f"  2 + 3  = {add(2, 3)}")
    print(f"  10 - 4 = {subtract(10, 4)}")
    print(f"  6 * 7  = {multiply(6, 7)}")
    print(f"  20 / 4 = {divide(20, 4)}")


if __name__ == "__main__":
    main()
