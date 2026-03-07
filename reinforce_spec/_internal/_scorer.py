"""Multi-judge LLM-as-judge scoring engine.

Scores spec candidates against the 12-dimension enterprise-readiness rubric
using multiple LLM judges with:
  - Chain-of-thought evaluation (reasoning before scoring)
  - Multi-judge ensemble with trimmed mean aggregation
  - Position-swapped pairwise comparison for top-K ranking
  - Anchor-based calibration
  - Bias detection and mitigation
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from loguru import logger

from reinforce_spec._internal._bias import (
    BiasDetector,
    PairwiseComparison,
    aggregate_scores_trimmed_mean,
    check_self_enhancement_risk,
)
from reinforce_spec._internal._calibration import ScoreCalibrator
from reinforce_spec._internal._rubric import Dimension, format_rubric_for_prompt
from reinforce_spec._internal._utils import Timer
from reinforce_spec.types import CandidateSpec, DimensionScore, ScoringWeights

if TYPE_CHECKING:
    from reinforce_spec._internal._client import OpenRouterClient
    from reinforce_spec._internal._config import ScoringConfig

# ── Judge Prompts ─────────────────────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """\
You are an expert enterprise software architecture reviewer conducting a rigorous \
evaluation of a specification against 12 enterprise-readiness dimensions.

Your evaluation must be:
1. OBJECTIVE: Score based solely on the rubric criteria, not your preferences
2. CHAIN-OF-THOUGHT: Provide detailed reasoning BEFORE each score
3. CONSISTENT: Apply the same standards across all evaluations
4. CALIBRATED: Use the full 1-5 range; a score of 3 is average, not bad

Important guidelines:
- Do NOT favor longer specifications over shorter, well-focused ones
- Do NOT inflate scores — a missing dimension is a 1, not a 2
- Justify every score with specific evidence from the specification
- If a dimension is partially addressed, score proportionally (3-4 range)
"""


def _build_pointwise_prompt(spec_content: str) -> str:
    """Build the pointwise scoring prompt."""
    rubric_text = format_rubric_for_prompt()
    return (
        f"## Evaluation Rubric\n\n{rubric_text}\n\n"
        f"## Specification to Evaluate\n\n{spec_content}\n\n"
        "## Instructions\n\n"
        "Evaluate the specification above against ALL 12 dimensions.\n\n"
        "For EACH dimension:\n"
        "1. Quote specific text from the specification that is relevant\n"
        "2. Analyze how well it meets the criteria for each score level\n"
        "3. Assign a score (1-5) with a 2-3 sentence justification\n\n"
        "## Output Format\n\n"
        "Return ONLY valid JSON with this exact structure:\n"
        "```json\n"
        "{\n"
        '  "evaluations": {\n'
        '    "compliance_regulatory": {\n'
        '      "reasoning": "Step-by-step analysis...",\n'
        '      "score": 4,\n'
        '      "justification": "2-3 sentence summary of the score",\n'
        '      "evidence": ["quoted text from spec..."]\n'
        "    },\n"
        "    ... (all 12 dimensions)\n"
        "  },\n"
        '  "composite_score": 3.8,\n'
        '  "top_strengths": ["strength 1", "strength 2"],\n'
        '  "critical_gaps": ["gap 1", "gap 2"]\n'
        "}\n"
        "```\n\n"
        "Return ONLY the JSON. No markdown fences, no explanations."
    )


def _build_pairwise_prompt(spec_a: str, spec_b: str) -> str:
    """Build the pairwise comparison prompt."""
    return (
        "## Task\n\n"
        "Compare these two specifications and determine which is more enterprise-ready.\n\n"
        "## Specification A\n\n"
        f"{spec_a}\n\n"
        "## Specification B\n\n"
        f"{spec_b}\n\n"
        "## Instructions\n\n"
        "For each of the 12 enterprise-readiness dimensions:\n"
        "1. Briefly compare both specs on this dimension\n"
        "2. Declare a winner (A or B) or tie\n\n"
        "Then provide an overall winner.\n\n"
        "Return ONLY valid JSON:\n"
        "```json\n"
        "{\n"
        '  "dimension_comparisons": {\n'
        '    "compliance_regulatory": {"winner": "A", "reasoning": "..."},\n'
        "    ...\n"
        "  },\n"
        '  "overall_winner": "A",\n'
        '  "confidence": 0.8,\n'
        '  "reasoning": "Overall comparison summary"\n'
        "}\n"
        "```"
    )


# ── Scorer ────────────────────────────────────────────────────────────────────


class EnterpriseScorer:
    """Multi-judge enterprise-readiness scorer.

    Scoring pipeline:
    1. Pointwise scoring: score all candidates on all 12 dimensions
       using multi-judge ensemble with CoT
    2. Calibration: apply anchor-based calibration if enabled
    3. Composite: compute weighted composite scores
    4. Pairwise: compare top-K candidates with position-swapped pairs
    5. Final ranking: combine pointwise + pairwise for definitive ranking

    """

    def __init__(
        self,
        client: OpenRouterClient,
        config: ScoringConfig,
        calibrator: ScoreCalibrator | None = None,
    ) -> None:
        self._client = client
        self._config = config
        self._calibrator = calibrator or ScoreCalibrator()
        self._bias_detector = BiasDetector()

    async def score_candidates(
        self,
        candidates: list[CandidateSpec],
        weights: ScoringWeights | None = None,
    ) -> list[CandidateSpec]:
        """Score all candidates and return them with scores populated.

        Parameters
        ----------
        candidates : list[CandidateSpec]
            Specs to score.
        weights : ScoringWeights or None
            Dimension weights.  Uses defaults if ``None``.

        Returns
        -------
        list[CandidateSpec]
            Candidates with ``dimension_scores`` and
            ``composite_score`` populated, sorted by
            ``composite_score`` descending.

        """
        weights = weights or ScoringWeights()

        with Timer() as timer:
            # Phase 1: Pointwise scoring (all candidates, all judges)
            scored_candidates = await self._pointwise_score_all(candidates)

            # Phase 2: Calibration (if enabled and anchors available)
            if self._config.calibration_enabled and self._calibrator.has_anchors:
                scored_candidates = await self._apply_calibration(scored_candidates)

            # Phase 3: Compute composite scores
            for candidate in scored_candidates:
                candidate.composite_score = self._compute_composite(
                    candidate.dimension_scores, weights
                )

            # Sort by composite (descending)
            scored_candidates.sort(key=lambda c: c.composite_score, reverse=True)

            # Phase 4: Pairwise comparison of top-K
            top_k = min(self._config.pairwise_top_k, len(scored_candidates))
            if top_k >= 2:
                pairwise_rankings = await self._pairwise_rank_top_k(scored_candidates[:top_k])
                # Re-rank top-K based on pairwise results
                scored_candidates = self._merge_rankings(
                    scored_candidates, pairwise_rankings, top_k
                )

        logger.info(
            "scoring_completed | n_candidates={n_candidates} top_score={top_score} latency_ms={latency_ms}",
            n_candidates=len(candidates),
            top_score=round(scored_candidates[0].composite_score, 3) if scored_candidates else 0,
            latency_ms=round(timer.elapsed_ms, 1),
        )

        return scored_candidates

    async def _pointwise_score_all(
        self,
        candidates: list[CandidateSpec],
    ) -> list[CandidateSpec]:
        """Score all candidates with pointwise scoring via multi-judge ensemble."""
        judge_models = (
            self._client.judge_models
            if self._config.scoring_mode == "multi_judge"
            else [self._client.judge_models[0]]
        )

        # For each candidate, collect scores from all judges
        tasks = []
        for candidate in candidates:
            for judge_model in judge_models:
                # Check self-enhancement risk
                is_risky = check_self_enhancement_risk(judge_model, candidate.source_model)
                if is_risky and len(judge_models) > 1:
                    logger.info(
                        "skipping_same_family_judge | judge={judge} generator={generator}",
                        judge=judge_model,
                        generator=candidate.source_model,
                    )
                    continue

                # Within-model ensemble: multiple samples
                for sample_idx in range(self._config.judge_samples_per_model):
                    tasks.append(
                        self._score_single(
                            candidate=candidate,
                            judge_model=judge_model,
                            sample_idx=sample_idx,
                        )
                    )

        # Execute all scoring calls in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Group results by candidate index
        scores_by_candidate: dict[int, list[dict[str, float]]] = {}
        judge_models_by_candidate: dict[int, list[str]] = {}

        for result in results:
            if isinstance(result, Exception):
                logger.warning("judge_call_failed | error={error}", error=str(result))
                continue
            candidate_idx, scores, judge_model = result
            scores_by_candidate.setdefault(candidate_idx, []).append(scores)
            judge_models_by_candidate.setdefault(candidate_idx, [])
            if judge_model not in judge_models_by_candidate[candidate_idx]:
                judge_models_by_candidate[candidate_idx].append(judge_model)

        # Aggregate scores per candidate using trimmed mean
        for candidate in candidates:
            judge_scores = scores_by_candidate.get(candidate.index, [])
            if not judge_scores:
                logger.error("no_scores_for_candidate | index={index}", index=candidate.index)
                continue

            # Trimmed mean across all judge samples
            trim_fraction = 0.25 if len(judge_scores) >= 4 else 0.0
            aggregated = aggregate_scores_trimmed_mean(judge_scores, trim_fraction)

            # Convert to DimensionScore objects
            candidate.dimension_scores = [
                DimensionScore(
                    dimension=dim.value,
                    score=aggregated.get(dim.value, 1.0),
                    justification="Aggregated from multi-judge ensemble",
                )
                for dim in Dimension
            ]
            candidate.judge_models = judge_models_by_candidate.get(candidate.index, [])

            # Track for bias detection
            self._bias_detector.record_score(
                sum(aggregated.values()) / len(aggregated) if aggregated else 0,
                len(candidate.content),
            )

        return candidates

    async def _score_single(
        self,
        candidate: CandidateSpec,
        judge_model: str,
        sample_idx: int,
    ) -> tuple[int, dict[str, float], str]:
        """Score a single candidate with a single judge model."""
        prompt = _build_pointwise_prompt(candidate.content)
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        content, metrics = await self._client.complete(
            messages=messages,
            model=judge_model,
            temperature=self._config.judge_temperature,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

        # Parse scores from response
        scores = self._parse_scores(content)
        return candidate.index, scores, judge_model

    @staticmethod
    def _parse_scores(response: str) -> dict[str, float]:
        """Parse dimension scores from judge JSON response."""
        try:
            # Clean response
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            # Extract scores from the evaluations dict
            evaluations = data.get("evaluations", data.get("scores", data))
            scores: dict[str, float] = {}

            for dim in Dimension:
                dim_data = evaluations.get(dim.value, {})
                if isinstance(dim_data, dict):
                    score = float(dim_data.get("score", 1.0))
                elif isinstance(dim_data, int | float):
                    score = float(dim_data)
                else:
                    score = 1.0
                scores[dim.value] = max(1.0, min(5.0, score))

            return scores

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("score_parse_failed | error={error}", error=str(e))
            # Return minimum scores on parse failure
            return {dim.value: 1.0 for dim in Dimension}

    async def _apply_calibration(
        self,
        candidates: list[CandidateSpec],
    ) -> list[CandidateSpec]:
        """Apply anchor-based calibration to all candidate scores."""
        # Score calibration anchors with the same judges
        anchor_specs = self._calibrator.get_anchor_specs()
        if not anchor_specs:
            return candidates

        # TODO: Score anchors and compute calibration factors
        # For now, return candidates unchanged
        logger.info("calibration_skipped_no_anchor_scores")
        return candidates

    @staticmethod
    def _compute_composite(
        dimension_scores: list[DimensionScore],
        weights: ScoringWeights,
    ) -> float:
        """Compute weighted composite score."""
        weight_dict = weights.as_dict()
        total = 0.0
        total_weight = 0.0

        for ds in dimension_scores:
            w = weight_dict.get(ds.dimension, 0.0)
            total += ds.score * w
            total_weight += w

        if total_weight == 0:
            return 0.0
        return total / total_weight * total_weight  # = total

    async def _pairwise_rank_top_k(
        self,
        top_candidates: list[CandidateSpec],
    ) -> list[PairwiseComparison]:
        """Run position-swapped pairwise comparisons on top-K candidates."""
        comparisons: list[PairwiseComparison] = []
        tasks = []

        for i in range(len(top_candidates)):
            for j in range(i + 1, len(top_candidates)):
                tasks.append(self._pairwise_compare(top_candidates[i], top_candidates[j]))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, PairwiseComparison):
                comparisons.append(result)
                continue

            logger.warning("pairwise_comparison_failed | error={error}", error=str(result))

        return comparisons

    async def _pairwise_compare(
        self,
        spec_a: CandidateSpec,
        spec_b: CandidateSpec,
    ) -> PairwiseComparison:
        """Compare two specs with position swapping."""
        judge_model = self._client.judge_models[0]

        # Forward order: A then B
        forward_prompt = _build_pairwise_prompt(spec_a.content, spec_b.content)
        forward_messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": forward_prompt},
        ]

        # Reversed order: B then A
        reversed_prompt = _build_pairwise_prompt(spec_b.content, spec_a.content)
        reversed_messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": reversed_prompt},
        ]

        # Run both in parallel
        forward_result, reversed_result = await asyncio.gather(
            self._client.complete(
                messages=forward_messages,
                model=judge_model,
                temperature=0.1,
                response_format={"type": "json_object"},
            ),
            self._client.complete(
                messages=reversed_messages,
                model=judge_model,
                temperature=0.1,
                response_format={"type": "json_object"},
            ),
        )

        # Parse results
        forward_winner = self._parse_pairwise_winner(forward_result[0])
        reversed_winner = self._parse_pairwise_winner(reversed_result[0])

        # In reversed order, A and B labels are swapped
        # Forward: "A" means spec_a, "B" means spec_b
        # Reversed: "A" means spec_b, "B" means spec_a
        return PairwiseComparison(
            spec_a_index=spec_a.index,
            spec_b_index=spec_b.index,
            a_preferred_forward=(forward_winner == "A"),
            b_preferred_forward=(forward_winner == "B"),
            a_preferred_reversed=(reversed_winner == "B"),  # B in reversed = A in original
            b_preferred_reversed=(reversed_winner == "A"),  # A in reversed = B in original
        )

    @staticmethod
    def _parse_pairwise_winner(response: str) -> str:
        """Parse winner from pairwise comparison response."""
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            data = json.loads(cleaned.strip())
            winner = data.get("overall_winner", "A")
            return winner.upper()
        except (json.JSONDecodeError, ValueError):
            return "A"

    @staticmethod
    def _merge_rankings(
        all_candidates: list[CandidateSpec],
        pairwise_results: list[PairwiseComparison],
        top_k: int,
    ) -> list[CandidateSpec]:
        """Merge pointwise ranking with pairwise comparison results.

        Uses a simple win-count from consistent pairwise comparisons
        to re-rank the top-K candidates.
        """
        # Count pairwise wins for top-K candidates
        win_counts: dict[int, int] = {}
        for comp in pairwise_results:
            if comp.is_consistent and comp.winner_index is not None:
                win_counts[comp.winner_index] = win_counts.get(comp.winner_index, 0) + 1

        if not win_counts:
            return all_candidates

        # Re-rank top-K by (pairwise_wins DESC, composite_score DESC)
        top_section = all_candidates[:top_k]
        rest = all_candidates[top_k:]

        top_section.sort(
            key=lambda c: (win_counts.get(c.index, 0), c.composite_score),
            reverse=True,
        )

        return top_section + rest


# ── Public Calibration Interface ──────────────────────────────────────────────

__all__ = ["EnterpriseScorer"]
