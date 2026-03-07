"""Unit tests for score calibration logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from reinforce_spec._internal._calibration import (
    CalibrationAnchor,
    CalibrationResult,
    ScoreCalibrator,
)


class TestZScoreNormalization:
    """Test z-score calibration."""

    def test_zscore_normalization(self) -> None:
        scores = [
            {"compliance_regulatory": 1.0},
            {"compliance_regulatory": 2.0},
            {"compliance_regulatory": 3.0},
            {"compliance_regulatory": 4.0},
            {"compliance_regulatory": 5.0},
        ]
        calibrated = ScoreCalibrator.calibrate_zscore(scores)
        assert len(calibrated) == 5
        assert all(1.0 <= s["compliance_regulatory"] <= 5.0 for s in calibrated)

    def test_zscore_single_value(self) -> None:
        scores = [3.0]
        calibrated = ScoreCalibrator.calibrate_zscore(scores)
        assert len(calibrated) == 1
        assert calibrated[0] == pytest.approx(3.0, abs=0.1)


class TestScoreCalibrator:
    """Test calibrator with anchors."""

    def test_calibrator_without_anchors(self) -> None:
        cal = ScoreCalibrator()
        assert cal.has_anchors is False

    def test_calibrator_with_anchors(self) -> None:
        anchors = [
            CalibrationAnchor(
                anchor_id="low",
                spec_content="Minimal spec",
                known_scores={"compliance_regulatory": 1.0},
            ),
            CalibrationAnchor(
                anchor_id="high",
                spec_content="Excellent spec with all details",
                known_scores={"compliance_regulatory": 5.0},
            ),
        ]
        cal = ScoreCalibrator(anchors=anchors)
        assert cal.has_anchors is True


class TestCalibrationResult:
    """Test CalibrationResult dataclass."""

    def test_construction(self) -> None:
        result = CalibrationResult(
            scaling_factors={"compliance_regulatory": 1.2},
            offset={"compliance_regulatory": 0.0},
            calibration_error=0.15,
        )
        assert result.applied is False
        assert result.calibration_error == 0.15

    def test_applied_flag(self) -> None:
        result = CalibrationResult(
            scaling_factors={},
            offset={},
            calibration_error=0.0,
            applied=True,
        )
        assert result.applied is True


class TestGetAnchorSpecs:
    """Test anchor spec retrieval."""

    def test_get_anchor_specs_empty(self) -> None:
        cal = ScoreCalibrator()
        assert cal.get_anchor_specs() == []

    def test_get_anchor_specs_returns_contents(self) -> None:
        anchors = [
            CalibrationAnchor(
                anchor_id="a1",
                spec_content="Spec content 1",
                known_scores={"compliance_regulatory": 3.0},
            ),
            CalibrationAnchor(
                anchor_id="a2",
                spec_content="Spec content 2",
                known_scores={"compliance_regulatory": 4.0},
            ),
        ]
        cal = ScoreCalibrator(anchors=anchors)
        specs = cal.get_anchor_specs()
        assert specs == ["Spec content 1", "Spec content 2"]

    def test_anchor_count(self) -> None:
        anchors = [
            CalibrationAnchor(
                anchor_id="a1",
                spec_content="Spec 1",
                known_scores={"compliance_regulatory": 2.0},
            ),
        ]
        cal = ScoreCalibrator(anchors=anchors)
        assert cal.anchor_count == 1


class TestZScoreEdgeCases:
    """Test z-score edge cases."""

    def test_zscore_identical_values(self) -> None:
        """When all values are identical, stdev is 0 → should use fallback."""
        scores = [
            {"compliance_regulatory": 3.0},
            {"compliance_regulatory": 3.0},
            {"compliance_regulatory": 3.0},
        ]
        calibrated = ScoreCalibrator.calibrate_zscore(scores)
        assert len(calibrated) == 3
        # With zero variance, std defaults to 1.0, z=0, result = target_mean
        assert all(s["compliance_regulatory"] == pytest.approx(3.0) for s in calibrated)

    def test_zscore_custom_target(self) -> None:
        scores = [
            {"compliance_regulatory": 1.0},
            {"compliance_regulatory": 3.0},
            {"compliance_regulatory": 5.0},
        ]
        calibrated = ScoreCalibrator.calibrate_zscore(scores, target_mean=4.0, target_std=0.5)
        assert len(calibrated) == 3


class TestAnchorBasedCalibration:
    """Test anchor-based calibration."""

    def test_no_anchors_raises(self) -> None:
        cal = ScoreCalibrator()
        with pytest.raises(Exception, match="No calibration anchors"):
            cal.calibrate_anchor_based({})

    def test_anchor_calibration_with_matching_scores(self) -> None:
        anchors = [
            CalibrationAnchor(
                anchor_id="ref1",
                spec_content="Reference spec",
                known_scores={"compliance_regulatory": 4.0},
            ),
        ]
        cal = ScoreCalibrator(anchors=anchors)
        judge_scores = {
            "ref1": {"compliance_regulatory": 2.0},
        }
        result = cal.calibrate_anchor_based(judge_scores)
        assert isinstance(result, CalibrationResult)
        # scale = 4.0 / 2.0 = 2.0
        assert result.scaling_factors["compliance_regulatory"] == pytest.approx(2.0)


class TestApplyCalibration:
    """Test applying calibration to scores."""

    def test_apply_calibration(self) -> None:
        cal = ScoreCalibrator()
        calibration = CalibrationResult(
            scaling_factors={"compliance_regulatory": 1.5},
            offset={"compliance_regulatory": 0.0},
            calibration_error=0.1,
        )
        result = cal.apply_calibration({"compliance_regulatory": 2.0}, calibration)
        assert result["compliance_regulatory"] == pytest.approx(3.0)

    def test_apply_calibration_clamped(self) -> None:
        cal = ScoreCalibrator()
        calibration = CalibrationResult(
            scaling_factors={"compliance_regulatory": 3.0},
            offset={"compliance_regulatory": 0.0},
            calibration_error=0.0,
        )
        result = cal.apply_calibration({"compliance_regulatory": 4.0}, calibration)
        # 4.0 * 3.0 = 12.0, clamped to 5.0
        assert result["compliance_regulatory"] == 5.0

    def test_apply_calibration_low_clamp(self) -> None:
        cal = ScoreCalibrator()
        calibration = CalibrationResult(
            scaling_factors={"compliance_regulatory": 0.1},
            offset={"compliance_regulatory": -5.0},
            calibration_error=0.0,
        )
        result = cal.apply_calibration({"compliance_regulatory": 1.0}, calibration)
        # 1.0 * 0.1 + -5.0 = -4.9, clamped to 1.0
        assert result["compliance_regulatory"] == 1.0

    def test_apply_calibration_missing_dim_uses_defaults(self) -> None:
        cal = ScoreCalibrator()
        calibration = CalibrationResult(
            scaling_factors={},
            offset={},
            calibration_error=0.0,
        )
        result = cal.apply_calibration({"compliance_regulatory": 3.5}, calibration)
        # default scale=1.0 offset=0.0
        assert result["compliance_regulatory"] == pytest.approx(3.5)


class TestLoadAnchors:
    """Test loading anchors from file."""

    def test_load_from_nonexistent_file(self) -> None:
        cal = ScoreCalibrator(calibration_data_path=Path("/nonexistent/path.json"))
        assert cal.has_anchors is False

    def test_load_from_valid_file(self, tmp_path: Path) -> None:
        import json

        data = [
            {
                "anchor_id": "a1",
                "spec_content": "Test spec",
                "known_scores": {"compliance_regulatory": 3.0},
            }
        ]
        path = tmp_path / "anchors.json"
        path.write_text(json.dumps(data))
        cal = ScoreCalibrator(calibration_data_path=path)
        assert cal.has_anchors is True
        assert cal.anchor_count == 1

    def test_load_from_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not valid json")
        cal = ScoreCalibrator(calibration_data_path=path)
        assert cal.has_anchors is False
