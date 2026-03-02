"""Unit tests for utility functions."""

from __future__ import annotations

import time

from reinforce_spec._internal._utils import (
    Timer,
    clamp,
    generate_request_id,
    hash_content,
    hash_dict,
    safe_divide,
    utc_now,
)


class TestGenerateRequestId:
    """Test request ID generation."""

    def test_format(self) -> None:
        rid = generate_request_id()
        assert isinstance(rid, str)
        assert len(rid) > 10

    def test_uniqueness(self) -> None:
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100


class TestUtcNow:
    """Test UTC timestamp generation."""

    def test_has_timezone(self) -> None:
        now = utc_now()
        assert now.tzinfo is not None


class TestHashing:
    """Test content and dict hashing."""

    def test_hash_content_deterministic(self) -> None:
        h1 = hash_content("hello")
        h2 = hash_content("hello")
        assert h1 == h2
        assert hash_content("world") != h1

    def test_hash_dict_order_independent(self) -> None:
        h1 = hash_dict({"a": 1, "b": 2})
        h2 = hash_dict({"b": 2, "a": 1})
        assert h1 == h2


class TestClamp:
    """Test value clamping."""

    def test_within_range(self) -> None:
        assert clamp(5, 0, 10) == 5

    def test_below_minimum(self) -> None:
        assert clamp(-1, 0, 10) == 0

    def test_above_maximum(self) -> None:
        assert clamp(15, 0, 10) == 10


class TestSafeDivide:
    """Test safe division."""

    def test_normal_division(self) -> None:
        assert safe_divide(10, 2) == 5.0

    def test_zero_denominator_default(self) -> None:
        assert safe_divide(10, 0) == 0.0

    def test_zero_denominator_custom(self) -> None:
        assert safe_divide(10, 0, default=-1.0) == -1.0


class TestTimer:
    """Test context-manager timer."""

    def test_elapsed_ms(self) -> None:
        with Timer() as t:
            time.sleep(0.05)
        assert t.elapsed_ms >= 40

    def test_timer_has_elapsed(self) -> None:
        t = Timer()
        # Timer starts on construction — elapsed_ms is always > 0
        assert isinstance(t.elapsed_ms, float)


class TestHashDictEdgeCases:
    """Test hash_dict with various input types."""

    def test_nested_dict(self) -> None:
        h1 = hash_dict({"outer": {"inner": 1}})
        h2 = hash_dict({"outer": {"inner": 1}})
        assert h1 == h2

    def test_different_nested_values(self) -> None:
        h1 = hash_dict({"a": {"b": 1}})
        h2 = hash_dict({"a": {"b": 2}})
        assert h1 != h2

    def test_empty_dict(self) -> None:
        h = hash_dict({})
        assert isinstance(h, str)
        assert len(h) > 0

    def test_with_list_values(self) -> None:
        h1 = hash_dict({"items": [1, 2, 3]})
        h2 = hash_dict({"items": [1, 2, 3]})
        assert h1 == h2
