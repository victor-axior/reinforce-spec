"""ReinforceSpec — top-level client orchestrator.

This is the primary user-facing entry-point. It wires together:
  - Enterprise scoring (multi-judge LLM evaluation)
  - RL-based selection (PPO via Gym environment)
  - Persistence + audit
  - Observability hooks

Users provide 2+ specification candidates (in any format — text, JSON, YAML,
Markdown, etc.) and the framework scores them on 12 enterprise-readiness
dimensions, then selects the best one using a hybrid RL + scoring approach.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from reinforce_spec._exceptions import InsufficientCandidatesError
from reinforce_spec._internal._client import OpenRouterClient
from reinforce_spec._internal._config import AppConfig
from reinforce_spec._internal._drift import DriftDetector
from reinforce_spec._internal._environment import SpecSelectionEnv, build_observation
from reinforce_spec._internal._persistence import Storage
from reinforce_spec._internal._policy import PolicyManager
from reinforce_spec._internal._replay_buffer import PrioritizedReplayBuffer, Transition
from reinforce_spec._internal._scorer import EnterpriseScorer
from reinforce_spec._internal._selector import HybridSelector
from reinforce_spec._internal._utils import Timer, generate_request_id, utc_now
from reinforce_spec.scoring.presets import get_preset
from reinforce_spec.types import (
    CandidateSpec,
    CustomerType,
    PolicyStage,
    PolicyStatus,
    SelectionMethod,
    SelectionResponse,
)


class ReinforceSpec:
    """High-level SDK interface for RL-optimized spec selection.

    The framework accepts user-provided specification candidates (in any textual
    format) and selects the best one by:

    1. Scoring each spec on 12 enterprise-readiness dimensions (multi-judge LLM)
    2. Selecting the best via hybrid RL + scoring
    3. Persisting results and recording RL transitions for continuous learning

    Example::

        from reinforce_spec import ReinforceSpec
        from reinforce_spec.types import CandidateSpec

        async with ReinforceSpec.from_env() as rs:
            response = await rs.select(
                candidates=[
                    CandidateSpec(content="# Payment API Spec\\n..."),
                    CandidateSpec(content='{"openapi": "3.1.0", ...}'),
                    CandidateSpec(content="service:\\n  name: payments\\n..."),
                    CandidateSpec(content="The payment service shall..."),
                    CandidateSpec(content="## Architecture\\n..."),
                ],
                customer_type="bank",
            )
            print(response.selected.content)

    """

    def __init__(self, config: AppConfig | None = None) -> None:
        """Initialise the SDK.

        Parameters
        ----------
        config : AppConfig or None
            Application configuration.  Loaded from environment variables
            when ``None``.

        """
        self._config = config or AppConfig.from_env()

        # Core components (lazy-initialized in connect())
        self._client: OpenRouterClient | None = None
        self._scorer: EnterpriseScorer | None = None
        self._selector: HybridSelector | None = None
        self._env: SpecSelectionEnv | None = None
        self._policy_manager: PolicyManager | None = None
        self._replay_buffer: PrioritizedReplayBuffer | None = None
        self._drift_detector: DriftDetector | None = None
        self._storage: Storage | None = None
        self._connected = False

    @classmethod
    def from_env(cls) -> ReinforceSpec:
        """Create instance from environment variables."""
        return cls(AppConfig.from_env())

    async def connect(self) -> None:
        """Initialize all sub-components."""
        if self._connected:
            return

        cfg = self._config

        # LLM client (used for scoring judges only)
        self._client = OpenRouterClient(cfg.llm)

        # Scorer
        self._scorer = EnterpriseScorer(
            client=self._client,
            config=cfg.scoring,
        )

        # RL environment
        self._env = SpecSelectionEnv(config=cfg.rl)

        # Policy manager
        policy_dir = Path(cfg.storage.data_dir) / "policies"
        self._policy_manager = PolicyManager(
            storage_dir=policy_dir,
            config=cfg.rl,
        )

        # Replay buffer
        self._replay_buffer = PrioritizedReplayBuffer(
            capacity=cfg.rl.replay_buffer_capacity,
            alpha=cfg.rl.per_alpha,
            beta_start=cfg.rl.per_beta_start,
        )

        # Selector
        production_policy = self._policy_manager.get_production_policy()
        self._selector = HybridSelector(
            policy=production_policy,
            rl_weight=cfg.rl.rl_weight,
        )

        # Drift detector
        self._drift_detector = DriftDetector()

        # Persistence
        self._storage = Storage(
            database_url=cfg.storage.database_url,
        )
        await self._storage.connect()

        self._connected = True
        logger.info("reinforce_spec_connected")

    async def close(self) -> None:
        """Shut down all components."""
        if self._storage:
            await self._storage.close()
        self._connected = False
        logger.info("reinforce_spec_closed")

    async def __aenter__(self) -> ReinforceSpec:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ── Core API ─────────────────────────────────────────────────────────

    async def select(
        self,
        candidates: list[CandidateSpec],
        *,
        customer_type: str | CustomerType | None = None,
        selection_method: str | SelectionMethod = SelectionMethod.HYBRID,
        request_id: str | None = None,
        description: str = "",
    ) -> SelectionResponse:
        """Score and select the best spec from user-provided candidates.

        This is the main entry-point. Pipeline:
        1. Validate and index candidate specs
        2. Score each on 12 enterprise dimensions (multi-judge)
        3. Select the best via hybrid RL + scoring
        4. Persist results + record RL transition

        Parameters
        ----------
        candidates : list[CandidateSpec]
            List of specification candidates (min 2, recommended ≥ 5).
            Each candidate can be plain text, JSON, YAML, Markdown, etc.
        customer_type : str or CustomerType or None
            Enterprise customer archetype for weight presets.
        selection_method : str or SelectionMethod
            How to pick the winner (hybrid/scoring_only/rl_only).
        request_id : str or None
            Idempotency key. Auto-generated if not provided.
        description : str
            Optional context for audit/logging.

        Returns
        -------
        SelectionResponse
            Selected spec, all candidates ranked, and metadata.

        Raises
        ------
        InsufficientCandidatesError
            If fewer than 2 candidates are provided.

        """
        await self._ensure_connected()

        # Validate
        if len(candidates) < 2:
            raise InsufficientCandidatesError(
                required=2,
                received=len(candidates),
            )

        # Auto-index candidates
        for i, c in enumerate(candidates):
            object.__setattr__(c, "index", i)

        request_id = request_id or generate_request_id()
        assert self._scorer is not None
        assert self._selector is not None
        assert self._storage is not None
        assert self._env is not None

        # Resolve customer type and weights
        ct = (
            CustomerType(customer_type)
            if isinstance(customer_type, str) and customer_type
            else None
        )
        weights = get_preset(ct or CustomerType.DEFAULT)

        # Parse selection method
        if isinstance(selection_method, str):
            selection_method = SelectionMethod(selection_method)

        with Timer() as timer:
            # 1. Persist request
            await self._storage.save_request(
                request_id=request_id,
                n_specs=len(candidates),
                description=description,
                customer_type=ct.value if ct else None,
            )

            # 2. Score candidates
            scored = await self._scorer.score_candidates(candidates, weights)

            # 3. Select best
            selected, selection_meta = self._selector.select(scored, method=selection_method)

            # 4. Persist candidates
            for c in scored:
                spec_id = f"{request_id}_{c.index}"
                await self._storage.save_candidate(
                    request_id=request_id,
                    spec_id=spec_id,
                    index_pos=c.index,
                    spec_type=c.spec_type,
                    spec_format=c.format.value,
                    content=c.content,
                    source_model=c.source_model,
                    composite_score=c.composite_score,
                    is_selected=(c.index == selected.index),
                )
                # Save dimension scores
                await self._storage.save_dimension_scores(
                    spec_id=spec_id,
                    scores=[
                        {
                            "dimension": ds.dimension,
                            "score": ds.score,
                            "justification": ds.justification,
                        }
                        for ds in c.dimension_scores
                    ],
                )

            # 5. Record RL transition
            obs = build_observation(scored)
            self._env.set_candidates(scored)
            await self._storage.save_episode(
                request_id=request_id,
                observation=obs.tolist(),
                action=selected.index,
                reward=selected.composite_score,
            )

            # Add to replay buffer
            if self._replay_buffer is not None:
                # Store per-candidate composite scores so the RL env can
                # provide action-dependent rewards during PPO training.
                candidate_rewards = np.array(
                    [c.composite_score for c in scored]
                    + [0.0] * (self._config.rl.n_candidates - len(scored)),
                    dtype=np.float32,
                )
                transition = Transition(
                    observation=obs,
                    action=selected.index,
                    reward=selected.composite_score,
                    next_observation=obs,  # terminal
                    done=True,
                    candidate_rewards=candidate_rewards,
                )
                self._replay_buffer.add(transition)

            # 6. Track drift
            if self._drift_detector is not None:
                self._drift_detector.add_score(selected.composite_score)

            await self._storage.complete_request(request_id)

        # Build scoring summary
        scoring_summary: dict[str, float] = {}
        if scored:
            all_dims: dict[str, list[float]] = {}
            for c in scored:
                for ds in c.dimension_scores:
                    all_dims.setdefault(ds.dimension, []).append(ds.score)
            scoring_summary = {dim: sum(scores) / len(scores) for dim, scores in all_dims.items()}

        response = SelectionResponse(
            request_id=request_id,
            selected=selected,
            all_candidates=sorted(scored, key=lambda c: c.composite_score, reverse=True),
            selection_method=selection_method.value,
            selection_confidence=selection_meta.get("rl_confidence", 1.0),
            scoring_summary=scoring_summary,
            latency_ms=round(timer.elapsed_ms, 1),
            timestamp=utc_now(),
        )

        logger.info(
            "selection_completed | request_id={request_id} n_candidates={n_candidates} selected_score={selected_score} latency_ms={latency_ms}",
            request_id=request_id,
            n_candidates=len(scored),
            selected_score=round(selected.composite_score, 3),
            latency_ms=round(timer.elapsed_ms, 1),
        )

        return response

    async def submit_feedback(
        self,
        request_id: str,
        rating: float | None = None,
        comment: str | None = None,
        spec_id: str | None = None,
    ) -> str:
        """Submit human feedback for a generation result.

        The feedback is stored and used to shape RL rewards
        in subsequent training iterations.

        Parameters
        ----------
        request_id : str
            Request to provide feedback for.
        rating : float or None
            Numeric rating (1–5 scale).
        comment : str or None
            Free-text comment.
        spec_id : str or None
            Specific candidate the feedback targets.

        Returns
        -------
        str
            The generated feedback identifier.

        """
        await self._ensure_connected()
        assert self._storage is not None

        feedback_id = await self._storage.save_feedback(
            request_id=request_id,
            rating=rating,
            comment=comment,
            spec_id=spec_id,
        )

        # Shape RL reward if env available
        if self._env is not None and rating is not None:
            # Normalize rating to [-1, 1]
            normalized = (rating - 3.0) / 2.0  # assuming 1-5 scale
            self._env.set_feedback_signal(normalized)

        await self._storage.append_audit_log(
            "feedback_submitted",
            {"request_id": request_id, "rating": rating, "feedback_id": feedback_id},
        )

        return feedback_id

    async def get_policy_status(self) -> PolicyStatus:
        """Get current RL policy status.

        Returns
        -------
        PolicyStatus
            Snapshot of the active policy state.

        """
        await self._ensure_connected()
        assert self._policy_manager is not None

        production = None
        for meta in self._policy_manager.list_policies():
            if meta.stage == PolicyStage.PRODUCTION:
                production = meta
                break

        drift_results = []
        if self._drift_detector and self._drift_detector.has_sufficient_data:
            drift_results = self._drift_detector.check_drift()

        drift_psi = next(
            (
                result.statistic
                for result in drift_results
                if getattr(result, "test_name", None) == "PSI"
            ),
            None,
        )

        return PolicyStatus(
            version=production.policy_id if production else "none",
            stage=production.stage if production else PolicyStage.CANDIDATE,
            training_episodes=production.train_steps if production else 0,
            mean_reward=(float(production.metrics.get("mean_reward", 0.0)) if production else 0.0),
            explore_rate=self._config.rl.explore_rate_initial,
            drift_psi=drift_psi,
            last_trained=production.created_at if production else None,
            last_promoted=production.promoted_at if production else None,
        )

    async def train_policy(
        self,
        n_steps: int | None = None,
    ) -> dict[str, Any]:
        """Trigger a policy training iteration.

        Samples from the replay buffer and trains the PPO policy.

        Parameters
        ----------
        n_steps : int or None
            Training timesteps.  Defaults to the configured batch size.

        Returns
        -------
        dict[str, Any]
            Training metrics or status message.

        """
        await self._ensure_connected()
        assert self._policy_manager is not None
        assert self._replay_buffer is not None

        if self._replay_buffer.size <= 0:
            return {
                "status": "insufficient_data",
                "buffer_size": self._replay_buffer.size,
                "required": 1,
            }

        sample_size = min(self._config.rl.batch_size, self._replay_buffer.size)

        # Sample from replay buffer
        transitions, _is_weights, _tree_indices = self._replay_buffer.sample(sample_size)

        if not transitions:
            return {"status": "empty_buffer"}

        # Get or create a policy
        policy = self._policy_manager.get_production_policy()
        if policy is None:
            policy, meta = self._policy_manager.create_policy(env=self._env)
            # Auto-promote to production if first policy
            self._policy_manager.promote(meta.policy_id)  # candidate → shadow
            self._policy_manager.promote(meta.policy_id)  # shadow → canary
            self._policy_manager.promote(meta.policy_id)  # canary → production

        # Train
        metrics = policy.train_on_batch(
            transitions,
            total_timesteps=n_steps or sample_size,
        )

        # Save checkpoint
        production_meta = None
        for m in self._policy_manager.list_policies():
            if m.stage == PolicyStage.PRODUCTION:
                production_meta = m
                break
        if production_meta:
            self._policy_manager.save_checkpoint(production_meta.policy_id, policy)

        # Refresh the selector's policy reference so that in-process RL
        # requests immediately use the newly promoted policy without requiring
        # a server restart.
        if self._selector is not None:
            self._selector._policy = policy

        return {"status": "trained", **metrics}

    async def _ensure_connected(self) -> None:
        if not self._connected:
            await self.connect()


__all__ = ["ReinforceSpec"]
