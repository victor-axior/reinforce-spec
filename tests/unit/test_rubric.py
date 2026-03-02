"""Unit tests for the 12-dimension rubric definitions."""

from __future__ import annotations

from reinforce_spec._internal._rubric import (
    Dimension,
    format_rubric_for_prompt,
    get_all_dimensions,
    get_default_weights,
    get_dimension_definition,
    validate_weights,
)


class TestRubricDimensions:
    """Test rubric dimension definitions."""

    def test_all_12_dimensions_defined(self) -> None:
        dims = get_all_dimensions()
        assert len(dims) == 12

    def test_each_dimension_has_criteria(self) -> None:
        for dim in Dimension:
            defn = get_dimension_definition(dim)
            assert defn is not None
            assert len(defn.criteria) == 5, f"{dim.value} should have 5 score levels"
            scores = [c.score for c in defn.criteria]
            assert sorted(scores) == [1, 2, 3, 4, 5]

    def test_dimension_enum_values(self) -> None:
        assert Dimension.COMPLIANCE_REGULATORY.value == "compliance_regulatory"
        assert Dimension.SECURITY_ARCHITECTURE.value == "security_architecture"


class TestRubricWeights:
    """Test rubric weight validation."""

    def test_default_weights_sum_to_one(self) -> None:
        weights = get_default_weights()
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01

    def test_validate_weights_accepts_valid(self) -> None:
        weights = get_default_weights()
        assert validate_weights(weights) is True

    def test_validate_weights_rejects_missing(self) -> None:
        weights = {"compliance_regulatory": 1.0}
        assert validate_weights(weights) is False


class TestRubricPrompt:
    """Test rubric prompt formatting."""

    def test_format_rubric_for_prompt_nonempty(self) -> None:
        text = format_rubric_for_prompt()
        assert len(text) > 500
        assert "compliance" in text.lower()
        assert "security" in text.lower()
