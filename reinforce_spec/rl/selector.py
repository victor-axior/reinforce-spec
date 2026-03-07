"""Spec selector — combines scoring and RL for final selection.

Provides a clean interface for the hybrid selection algorithm:
  1. Score candidates via multi-judge ensemble
  2. Apply RL policy for adaptive selection
  3. Blend scores and RL recommendations

Examples
--------
>>> from reinforce_spec.rl.selector import Selector
>>> selector = Selector(config)
>>> chosen = selector.select(scored_candidates)
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger

from reinforce_spec._internal._config import RLConfig
from reinforce_spec._internal._environment import build_observation

if TYPE_CHECKING:
    from reinforce_spec._internal._policy import PPOPolicy
    from reinforce_spec.types import CandidateSpec


@dataclasses.dataclass(frozen=True, slots=True)
class SelectionResult:
    """Result of the spec selection process.

    Attributes
    ----------
    selected_index : int
        Index of the chosen candidate.
    method : str
        Selection method used (``hybrid``, ``scoring_only``, ``rl_only``).
    rl_action : int or None
        Action chosen by the RL policy (if used).
    rl_confidence : float or None
        Probability assigned to the chosen action.
    scoring_rank : int
        Rank of the chosen candidate by scoring alone.

    """

    selected_index: int
    method: str
    rl_action: int | None = None
    rl_confidence: float | None = None
    scoring_rank: int = 0


class Selector:
    """Hybrid RL + scoring spec selector.

    Parameters
    ----------
    config : RLConfig or None
        RL configuration. Uses defaults when ``None``.
    policy : PPOPolicy or None
        Pre-trained policy. When ``None``, falls back to scoring-only.

    """

    def __init__(
        self,
        config: RLConfig | None = None,
        policy: PPOPolicy | None = None,
    ) -> None:
        self._config = config or RLConfig()
        self._policy = policy

    def select(
        self,
        candidates: list[CandidateSpec],
        method: str = "hybrid",
    ) -> SelectionResult:
        """Choose the best candidate.

        Parameters
        ----------
        candidates : list[CandidateSpec]
            Scored candidates (must have ``composite_score`` set).
        method : str
            ``"hybrid"``, ``"scoring_only"``, or ``"rl_only"``.

        Returns
        -------
        SelectionResult
            The selection decision with metadata.

        """
        if not candidates:
            raise ValueError("Cannot select from an empty candidate list")

        # Score-based ranking
        sorted_by_score = sorted(
            enumerate(candidates),
            key=lambda ic: ic[1].composite_score,
            reverse=True,
        )
        scoring_best = sorted_by_score[0][0]

        if method == "scoring_only" or self._policy is None:
            return SelectionResult(
                selected_index=scoring_best,
                method="scoring_only",
                scoring_rank=0,
            )

        # RL-based selection
        obs = build_observation(candidates, max_candidates=self._config.n_candidates)
        action, confidence = self._policy.predict(obs, deterministic=True)
        action = int(min(action, len(candidates) - 1))

        if method == "rl_only":
            scoring_rank = next(
                rank for rank, (idx, _) in enumerate(sorted_by_score) if idx == action
            )
            return SelectionResult(
                selected_index=action,
                method="rl_only",
                rl_action=action,
                rl_confidence=float(confidence),
                scoring_rank=scoring_rank,
            )

        # Hybrid: blend scoring and RL
        rl_weight = self._config.rl_weight
        scores = np.array([c.composite_score for c in candidates])
        scores_norm = scores / scores.max() if scores.max() > 0 else scores

        rl_probs = self._policy.get_action_probabilities(obs)
        blended = (1.0 - rl_weight) * scores_norm + rl_weight * rl_probs[: len(candidates)]
        selected = int(np.argmax(blended))

        scoring_rank = next(
            rank for rank, (idx, _) in enumerate(sorted_by_score) if idx == selected
        )

        logger.debug(
            "hybrid_selection | selected={sel} rl_action={rl} scoring_best={score}",
            sel=selected,
            rl=action,
            score=scoring_best,
        )

        return SelectionResult(
            selected_index=selected,
            method="hybrid",
            rl_action=action,
            rl_confidence=float(confidence),
            scoring_rank=scoring_rank,
        )
