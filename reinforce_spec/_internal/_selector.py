"""Hybrid spec selector.

Combines RL policy predictions with scoring-based ranking to select
the best specification. Implements a graceful degradation ladder:

  L0 (full): Multi-judge scoring + RL selection + pairwise comparison
  L1 (reduced): Single-judge scoring + RL selection
  L2 (fallback): Scoring only, no RL
  L3 (emergency): Single candidate, simple scoring

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger

from reinforce_spec._internal._environment import build_observation
from reinforce_spec.types import CandidateSpec, DegradationLevel, SelectionMethod

if TYPE_CHECKING:
    from reinforce_spec._internal._policy import PPOPolicy


class HybridSelector:
    """Select the best spec candidate using a mix of scoring and RL signals.

    Parameters
    ----------
    policy : PPOPolicy or None
        Trained PPO policy (can be ``None`` if RL is disabled).
    rl_weight : float
        Blending weight for the RL signal (0.0–1.0).
        ``0.0`` = pure scoring, ``1.0`` = pure RL.
    confidence_threshold : float
        Minimum RL confidence to trust the policy; below this, fall back
        to scoring-based ranking.
    degradation_level : DegradationLevel
        Current degradation level (L0–L3).

    """

    def __init__(
        self,
        policy: PPOPolicy | None = None,
        rl_weight: float = 0.4,
        confidence_threshold: float = 0.3,
        degradation_level: DegradationLevel = DegradationLevel.L0_FULL,
    ) -> None:
        self._policy = policy
        self._rl_weight = rl_weight
        self._confidence_threshold = confidence_threshold
        self._degradation_level = degradation_level

    @property
    def degradation_level(self) -> DegradationLevel:
        """Return the current degradation level."""
        return self._degradation_level

    @degradation_level.setter
    def degradation_level(self, level: DegradationLevel) -> None:
        if level != self._degradation_level:
            logger.info(
                "degradation_level_changed | old={old} new={new}",
                old=self._degradation_level.value,
                new=level.value,
            )
        self._degradation_level = level

    def select(
        self,
        candidates: list[CandidateSpec],
        method: SelectionMethod = SelectionMethod.HYBRID,
    ) -> tuple[CandidateSpec, dict[str, Any]]:
        """Select the best candidate.

        Parameters
        ----------
        candidates : list[CandidateSpec]
            Scored candidate specifications.
        method : SelectionMethod
            Selection strategy to apply.

        Returns
        -------
        tuple[CandidateSpec, dict[str, Any]]
            The chosen candidate and selection metadata.

        Raises
        ------
        ValueError
            If *candidates* is empty.

        """
        if not candidates:
            raise ValueError("No candidates to select from")

        if len(candidates) == 1:
            return candidates[0], {"method": "single", "reason": "only_one_candidate"}

        # Apply degradation
        effective_method = self._apply_degradation(method)

        if effective_method == SelectionMethod.SCORING_ONLY:
            return self._select_by_scoring(candidates)

        if effective_method == SelectionMethod.RL_ONLY:
            return self._select_by_rl(candidates)

        # Hybrid
        return self._select_hybrid(candidates)

    def _select_by_scoring(
        self,
        candidates: list[CandidateSpec],
    ) -> tuple[CandidateSpec, dict[str, Any]]:
        """Select purely by composite score."""
        best = max(candidates, key=lambda c: c.composite_score)
        return best, {
            "method": SelectionMethod.SCORING_ONLY.value,
            "composite_score": best.composite_score,
            "reason": "highest_composite",
        }

    def _select_by_rl(
        self,
        candidates: list[CandidateSpec],
    ) -> tuple[CandidateSpec, dict[str, Any]]:
        """Select purely by RL policy."""
        if self._policy is None:
            logger.warning("rl_policy_not_available_falling_back_to_scoring")
            return self._select_by_scoring(candidates)

        obs = build_observation(candidates)
        action, confidence = self._policy.predict(obs)

        # Clamp action to valid range
        action = action % len(candidates)

        return candidates[action], {
            "method": SelectionMethod.RL_ONLY.value,
            "action": action,
            "confidence": confidence,
        }

    def _select_hybrid(
        self,
        candidates: list[CandidateSpec],
    ) -> tuple[CandidateSpec, dict[str, Any]]:
        """Blend scoring and RL signals."""
        # Scoring scores (normalized to [0, 1])
        max_score = max(c.composite_score for c in candidates) or 1.0
        scoring_scores = np.array(
            [c.composite_score / max_score for c in candidates],
            dtype=np.float32,
        )

        # RL signal
        rl_scores = np.zeros(len(candidates), dtype=np.float32)
        rl_confidence = 0.0

        if self._policy is not None:
            obs = build_observation(candidates)
            probs = self._policy.get_action_probabilities(obs)
            rl_scores[: min(len(probs), len(candidates))] = probs[: len(candidates)]
            rl_confidence = float(np.max(rl_scores))

        # Determine effective RL weight
        effective_weight = self._rl_weight
        if rl_confidence < self._confidence_threshold:
            effective_weight *= rl_confidence / self._confidence_threshold
            logger.info(
                "rl_confidence_low_reducing_weight | confidence={confidence} effective_weight={effective_weight}",
                confidence=round(rl_confidence, 3),
                effective_weight=round(effective_weight, 3),
            )

        # Blend
        blended = (1.0 - effective_weight) * scoring_scores + effective_weight * rl_scores
        best_idx = int(np.argmax(blended))

        return candidates[best_idx], {
            "method": SelectionMethod.HYBRID.value,
            "scoring_weight": round(1.0 - effective_weight, 3),
            "rl_weight": round(effective_weight, 3),
            "rl_confidence": round(rl_confidence, 3),
            "blended_scores": blended.tolist(),
            "selected_index": best_idx,
        }

    def _apply_degradation(self, method: SelectionMethod) -> SelectionMethod:
        """Downgrade selection method based on degradation level."""
        if self._degradation_level == DegradationLevel.L0_FULL:
            return method
        if self._degradation_level == DegradationLevel.L1_REDUCED:
            return method  # Same method, but scoring engine uses single judge
        if self._degradation_level in (
            DegradationLevel.L2_FALLBACK,
            DegradationLevel.L3_EMERGENCY,
        ):
            return SelectionMethod.SCORING_ONLY
        return method


__all__ = ["HybridSelector"]
