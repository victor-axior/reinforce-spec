"""Score calibration for LLM-as-judge consistency.

Two calibration strategies:
1. Anchor-based: include known-score reference specs in each batch,
   compute a scaling factor from anchor scores vs known human scores.
2. Z-score normalization: standardize scores within each session to
   handle cross-session drift.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from reinforce_spec._exceptions import CalibrationError
from reinforce_spec._internal._rubric import Dimension


@dataclass(frozen=True)
class CalibrationAnchor:
    """A reference spec with known human scores for calibration."""

    anchor_id: str
    spec_content: str
    known_scores: dict[str, float]  # dimension_key → known human score (1-5)


@dataclass
class CalibrationResult:
    """Result of calibrating a batch of scores."""

    scaling_factors: dict[str, float]  # dimension → scaling factor
    offset: dict[str, float]  # dimension → offset
    calibration_error: float  # mean absolute error vs anchors
    applied: bool = False


class ScoreCalibrator:
    """Calibrates LLM-as-judge scores using anchor-based and z-score methods.

    Anchor-based calibration:
      For each dimension, compute:
        scale = mean(human_scores) / mean(judge_scores)
        calibrated = judge_score × scale
      This corrects for systematic over/under-scoring.

    Z-score normalization:
      For each dimension, compute:
        z = (score - mean) / std
        calibrated = z × target_std + target_mean
      This handles cross-session drift.
    """

    DEFAULT_TARGET_MEAN = 3.0
    DEFAULT_TARGET_STD = 1.0

    def __init__(
        self,
        anchors: list[CalibrationAnchor] | None = None,
        calibration_data_path: Path | None = None,
    ) -> None:
        self._anchors = anchors or []
        if calibration_data_path and not self._anchors:
            self._anchors = self._load_anchors(calibration_data_path)

    @staticmethod
    def _load_anchors(path: Path) -> list[CalibrationAnchor]:
        """Load calibration anchors from a JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            return [
                CalibrationAnchor(
                    anchor_id=item["anchor_id"],
                    spec_content=item["spec_content"],
                    known_scores=item["known_scores"],
                )
                for item in data
            ]
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logger.warning("calibration_anchors_load_failed | path={path} error={error}", path=str(path), error=str(e))
            return []

    def calibrate_anchor_based(
        self,
        judge_anchor_scores: dict[str, dict[str, float]],
    ) -> CalibrationResult:
        """Compute anchor-based calibration factors.

        Parameters
        ----------
        judge_anchor_scores : dict[str, dict[str, float]]
            Mapping of ``anchor_id`` to ``{dimension_key: judge_score}``.

        Returns
        -------
        CalibrationResult
            Result with per-dimension scaling factors.

        Raises
        ------
        CalibrationError
            If no calibration anchors are available.

        """
        if not self._anchors:
            raise CalibrationError("No calibration anchors available")

        scaling_factors: dict[str, float] = {}
        offsets: dict[str, float] = {}
        errors: list[float] = []

        for dim in Dimension:
            human_scores: list[float] = []
            judge_scores: list[float] = []

            for anchor in self._anchors:
                if anchor.anchor_id in judge_anchor_scores:
                    human_val = anchor.known_scores.get(dim.value)
                    judge_val = judge_anchor_scores[anchor.anchor_id].get(dim.value)
                    if human_val is not None and judge_val is not None:
                        human_scores.append(human_val)
                        judge_scores.append(judge_val)

            if not judge_scores:
                scaling_factors[dim.value] = 1.0
                offsets[dim.value] = 0.0
                continue

            mean_human = sum(human_scores) / len(human_scores)
            mean_judge = sum(judge_scores) / len(judge_scores)

            if mean_judge > 0:
                scale = mean_human / mean_judge
            else:
                scale = 1.0

            scaling_factors[dim.value] = scale
            offsets[dim.value] = 0.0

            # Compute calibration error
            for h, j in zip(human_scores, judge_scores):
                errors.append(abs(h - j * scale))

        calibration_error = sum(errors) / len(errors) if errors else 0.0

        logger.info(
            "anchor_calibration_computed | n_anchors={n_anchors} mean_calibration_error={mean_calibration_error}",
            n_anchors=len(self._anchors),
            mean_calibration_error=round(calibration_error, 3),
        )

        return CalibrationResult(
            scaling_factors=scaling_factors,
            offset=offsets,
            calibration_error=calibration_error,
        )

    @staticmethod
    def calibrate_zscore(
        scores: list[dict[str, float]],
        target_mean: float = 3.0,
        target_std: float = 1.0,
    ) -> list[dict[str, float]]:
        """Apply z-score normalization to a batch of score dicts.

        Parameters
        ----------
        scores : list[dict[str, float]]
            List of ``{dimension_key: raw_score}`` dicts.
        target_mean : float
            Desired mean after normalization.
        target_std : float
            Desired standard deviation after normalization.

        Returns
        -------
        list[dict[str, float]]
            Normalized score dicts, clamped to ``[1.0, 5.0]``.

        """
        if len(scores) < 2:
            return scores

        # Compute per-dimension stats
        dimensions = list(scores[0].keys())
        normalized: list[dict[str, float]] = []

        dim_means: dict[str, float] = {}
        dim_stds: dict[str, float] = {}

        for dim in dimensions:
            vals = [s[dim] for s in scores if dim in s]
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            std = math.sqrt(var) if var > 0 else 1.0
            dim_means[dim] = mean
            dim_stds[dim] = std

        for score_dict in scores:
            norm_dict: dict[str, float] = {}
            for dim in dimensions:
                if dim in score_dict:
                    z = (score_dict[dim] - dim_means[dim]) / dim_stds[dim]
                    calibrated = z * target_std + target_mean
                    norm_dict[dim] = max(1.0, min(5.0, calibrated))
            normalized.append(norm_dict)

        return normalized

    def apply_calibration(
        self,
        scores: dict[str, float],
        calibration: CalibrationResult,
    ) -> dict[str, float]:
        """Apply anchor-based calibration to a score dict.

        Parameters
        ----------
        scores : dict[str, float]
            Mapping of ``dimension_key`` to raw score.
        calibration : CalibrationResult
            Result from :meth:`calibrate_anchor_based`.

        Returns
        -------
        dict[str, float]
            Calibrated scores, clamped to ``[1.0, 5.0]``.

        """
        calibrated: dict[str, float] = {}
        for dim, score in scores.items():
            scale = calibration.scaling_factors.get(dim, 1.0)
            offset = calibration.offset.get(dim, 0.0)
            calibrated[dim] = max(1.0, min(5.0, score * scale + offset))
        return calibrated

    @property
    def has_anchors(self) -> bool:
        return len(self._anchors) > 0

    @property
    def anchor_count(self) -> int:
        return len(self._anchors)

    def get_anchor_specs(self) -> list[str]:
        """Return anchor spec contents for inclusion in judge batches."""
        return [a.spec_content for a in self._anchors]
