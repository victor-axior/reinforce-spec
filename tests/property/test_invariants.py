"""Property-based tests using Hypothesis.

These tests verify invariants for arbitrary inputs, catching
edge cases that example-based tests might miss.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from reinforce_spec._internal._utils import clamp, safe_divide
from reinforce_spec.types import CandidateSpec, SpecFormat, detect_format


class TestClampProperties:
    """Property-based tests for clamp()."""

    @given(
        value=st.floats(allow_nan=False, allow_infinity=False),
        lo=st.floats(min_value=-1e6, max_value=0, allow_nan=False, allow_infinity=False),
        hi=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    def test_result_always_in_bounds(self, value: float, lo: float, hi: float) -> None:
        """clamp() output must always be within [lo, hi]."""
        if lo > hi:
            lo, hi = hi, lo
        result = clamp(value, lo, hi)
        assert lo <= result <= hi

    @given(
        value=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
    )
    def test_clamp_identity_within_range(self, value: float) -> None:
        """When value is already in range, clamp returns it unchanged."""
        result = clamp(value, -200, 200)
        assert result == value


class TestSafeDivideProperties:
    """Property-based tests for safe_divide()."""

    @given(
        a=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        b=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    def test_never_raises(self, a: float, b: float) -> None:
        """safe_divide() must never raise an exception."""
        result = safe_divide(a, b)
        assert isinstance(result, float)


class TestDetectFormatProperties:
    """Property-based tests for format detection."""

    @given(content=st.text(min_size=1, max_size=1000))
    @settings(max_examples=200)
    def test_always_returns_valid_format(self, content: str) -> None:
        """detect_format() must always return a valid SpecFormat."""
        fmt = detect_format(content)
        assert isinstance(fmt, SpecFormat)

    @given(
        data=st.dictionaries(
            keys=st.text(min_size=1, max_size=10),
            values=st.integers(),
            min_size=1,
            max_size=5,
        ),
    )
    def test_json_dicts_detected_as_json(self, data: dict) -> None:
        """JSON-serializable dicts should be detected as JSON."""
        import json

        content = json.dumps(data)
        fmt = detect_format(content)
        assert fmt == SpecFormat.JSON
