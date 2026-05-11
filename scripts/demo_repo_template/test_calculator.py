"""Basic tests for the calculator module."""

import pytest

from calculator import add, divide, multiply, subtract


class TestArithmetic:
    def test_add(self):
        assert add(2, 3) == 5
        assert add(-1, 1) == 0

    def test_subtract(self):
        assert subtract(10, 4) == 6
        assert subtract(0, 5) == -5

    def test_multiply(self):
        assert multiply(6, 7) == 42
        assert multiply(-3, 2) == -6

    def test_divide(self):
        assert divide(20, 4) == 5.0
        assert divide(1, 2) == 0.5

    def test_divide_by_zero_raises(self):
        with pytest.raises(ValueError):
            divide(10, 0)
