"""Unit tests for SpecSelectionEnv and feature engineering."""

from __future__ import annotations

import numpy as np

from reinforce_spec._internal._config import RLConfig
from reinforce_spec._internal._environment import (
    PER_CANDIDATE_FEATURES,
    SpecSelectionEnv,
    _candidate_to_features,
    build_observation,
)
from reinforce_spec.types import CandidateSpec, DimensionScore

# ── Helpers ──────────────────────────────────────────────────────────────────

DIMS = [
    "compliance_regulatory",
    "identity_access",
    "deployment_topology",
    "data_governance",
    "observability_monitoring",
    "incident_workflow",
    "security_architecture",
    "vendor_model_abstraction",
    "scalability_performance",
    "finops_cost",
    "developer_experience",
    "onboarding_production_path",
]


def _make_candidate(
    index: int = 0,
    content: str = "A" * 100,
    composite: float = 3.0,
    spec_type: str = "api",
    dim_score: float = 3.0,
) -> CandidateSpec:
    return CandidateSpec(
        index=index,
        content=content,
        spec_type=spec_type,
        composite_score=composite,
        dimension_scores=[DimensionScore(dimension=d, score=dim_score) for d in DIMS],
    )


# ── Feature engineering ──────────────────────────────────────────────────────


class TestCandidateToFeatures:
    """Test _candidate_to_features."""

    def test_output_shape(self) -> None:
        c = _make_candidate()
        features = _candidate_to_features(c)
        assert features.shape == (PER_CANDIDATE_FEATURES,)
        assert features.dtype == np.float32

    def test_dimension_scores_normalised(self) -> None:
        c = _make_candidate(dim_score=5.0)
        features = _candidate_to_features(c)
        # First 12 features = dim scores / 5.0 → should be 1.0
        for i in range(12):
            assert abs(features[i] - 1.0) < 1e-5

    def test_composite_normalised(self) -> None:
        c = _make_candidate(composite=4.0)
        features = _candidate_to_features(c)
        assert abs(features[12] - 0.8) < 1e-5  # 4.0 / 5.0

    def test_short_content_bucket(self) -> None:
        c = _make_candidate(content="short")
        features = _candidate_to_features(c)
        assert features[13] == 0.0  # short < 500

    def test_medium_content_bucket(self) -> None:
        c = _make_candidate(content="x" * 1000)
        features = _candidate_to_features(c)
        assert features[13] == 0.5  # 500 ≤ medium < 2000

    def test_long_content_bucket(self) -> None:
        c = _make_candidate(content="x" * 3000)
        features = _candidate_to_features(c)
        assert features[13] == 1.0  # ≥ 2000

    def test_format_onehot_text(self) -> None:
        c = _make_candidate(content="plain text content here")
        features = _candidate_to_features(c)
        # format one-hot starts at index 14; text → index 0
        assert features[14] == 1.0
        assert sum(features[14:19]) == 1.0  # exactly one bit set

    def test_format_onehot_json(self) -> None:
        c = _make_candidate(content='{"key": "value"}')
        features = _candidate_to_features(c)
        # json → SPEC_FORMAT_INDEX["json"] = 1
        assert features[15] == 1.0


class TestBuildObservation:
    """Test the observation builder."""

    def test_shape_matches_max_candidates(self) -> None:
        candidates = [_make_candidate(index=i) for i in range(3)]
        obs = build_observation(candidates, max_candidates=5)
        assert obs.shape == (5 * PER_CANDIDATE_FEATURES,)

    def test_padding_zeros(self) -> None:
        candidates = [_make_candidate()]
        obs = build_observation(candidates, max_candidates=3)
        # Slots 1 and 2 should be all zeros
        slot2_start = 2 * PER_CANDIDATE_FEATURES
        assert np.all(obs[slot2_start:] == 0.0)

    def test_truncation(self) -> None:
        candidates = [_make_candidate(index=i) for i in range(10)]
        obs = build_observation(candidates, max_candidates=3)
        assert obs.shape == (3 * PER_CANDIDATE_FEATURES,)

    def test_empty_candidates(self) -> None:
        obs = build_observation([], max_candidates=2)
        assert np.all(obs == 0.0)


# ── Gym environment ──────────────────────────────────────────────────────────


class TestSpecSelectionEnv:
    """Test the gymnasium environment."""

    def _make_env(self, n_candidates: int = 5) -> SpecSelectionEnv:
        config = RLConfig(n_candidates=n_candidates)
        return SpecSelectionEnv(config=config)

    def test_observation_space(self) -> None:
        env = self._make_env(n_candidates=5)
        assert env.observation_space.shape == (5 * PER_CANDIDATE_FEATURES,)

    def test_action_space(self) -> None:
        env = self._make_env(n_candidates=5)
        assert env.action_space.n == 5

    def test_reset_returns_obs_and_info(self) -> None:
        env = self._make_env()
        candidates = [_make_candidate(index=i) for i in range(3)]
        env.set_candidates(candidates)
        obs, info = env.reset()
        assert obs.shape == env.observation_space.shape
        assert "episode" in info
        assert "n_candidates" in info
        assert info["n_candidates"] == 3

    def test_step_valid_action(self) -> None:
        env = self._make_env(n_candidates=3)
        candidates = [_make_candidate(index=i, composite=float(i + 1)) for i in range(3)]
        env.set_candidates(candidates)
        env.reset()

        obs, reward, terminated, truncated, info = env.step(1)
        assert obs.shape == env.observation_space.shape
        assert reward == 2.0  # composite of candidate 1
        assert terminated is True
        assert truncated is False
        assert info["action"] == 1

    def test_step_action_clamped(self) -> None:
        env = self._make_env(n_candidates=3)
        candidates = [_make_candidate(index=i, composite=2.0) for i in range(3)]
        env.set_candidates(candidates)
        env.reset()

        # Action=10 → 10 % 3 = 1
        obs, reward, terminated, truncated, info = env.step(10)
        assert info["action"] == 10 % 3

    def test_step_with_feedback_signal(self) -> None:
        env = self._make_env(n_candidates=3)
        config = RLConfig(n_candidates=3, feedback_reward_scale=2.0)
        env._config = config

        candidates = [_make_candidate(index=i, composite=3.0) for i in range(3)]
        env.set_candidates(candidates)
        env.reset()

        env.set_feedback_signal(0.5)
        obs, reward, terminated, truncated, info = env.step(0)
        # base_reward=3.0 + feedback(0.5 * 2.0) = 4.0
        assert abs(reward - 4.0) < 1e-5

    def test_feedback_signal_consumed_after_step(self) -> None:
        env = self._make_env(n_candidates=3)
        candidates = [_make_candidate(index=i, composite=2.0) for i in range(3)]
        env.set_candidates(candidates)
        env.reset()

        env.set_feedback_signal(1.0)
        env.step(0)
        # Second step should have no feedback
        _, reward2, _, _, _ = env.step(0)
        assert reward2 == 2.0  # just base reward

    def test_set_candidates(self) -> None:
        env = self._make_env(n_candidates=2)
        candidates = [_make_candidate(index=i) for i in range(5)]
        env.set_candidates(candidates)
        # Should truncate to max_candidates
        assert len(env._candidates) == 2

    def test_render_returns_string(self) -> None:
        env = self._make_env(n_candidates=3)
        candidates = [_make_candidate(index=i, composite=float(i + 1)) for i in range(3)]
        env.set_candidates(candidates)
        env.reset()

        output = env.render()
        assert isinstance(output, str)
        assert "Episode" in output

    def test_multiple_episodes(self) -> None:
        env = self._make_env(n_candidates=3)
        candidates = [_make_candidate(index=i, composite=2.0) for i in range(3)]
        env.set_candidates(candidates)

        _, info1 = env.reset()
        env.step(0)
        _, info2 = env.reset()

        assert info2["episode"] == info1["episode"] + 1
