"""Unit tests for the RL façade layer (rl/ package).

Covers:
  - reinforce_spec.rl.environment (re-exports)
  - reinforce_spec.rl.evaluation
  - reinforce_spec.rl.registry
  - reinforce_spec.rl.selector
  - reinforce_spec.rl.trainer
  - reinforce_spec.rl.__init__ (lazy imports)
  - reinforce_spec.scoring (re-exports & presets)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

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


def _make_candidate(index: int = 0, score: float = 3.0) -> CandidateSpec:
    return CandidateSpec(
        index=index,
        content=f"Spec content {index} with adequate length text here",
        composite_score=score,
        dimension_scores=[DimensionScore(dimension=d, score=score) for d in DIMS],
    )


# ── rl.environment re-exports ────────────────────────────────────────────────


class TestEnvironmentReexports:
    """Verify that rl.environment correctly re-exports internal symbols."""

    def test_spec_selection_env_importable(self) -> None:
        from reinforce_spec.rl.environment import SpecSelectionEnv

        assert SpecSelectionEnv is not None

    def test_build_observation_importable(self) -> None:
        from reinforce_spec.rl.environment import build_observation

        assert callable(build_observation)

    def test_constants_importable(self) -> None:
        from reinforce_spec.rl.environment import N_DIMENSIONS, PER_CANDIDATE_FEATURES

        assert N_DIMENSIONS == 12
        assert PER_CANDIDATE_FEATURES == 19


# ── rl.evaluation ────────────────────────────────────────────────────────────


class TestEvaluation:
    """Test the evaluation façade."""

    def test_imports(self) -> None:
        from reinforce_spec.rl.evaluation import (
            evaluate_policy,
        )

        assert callable(evaluate_policy)

    def test_evaluate_policy_wis(self) -> None:
        from reinforce_spec._internal._replay_buffer import Transition
        from reinforce_spec.rl.evaluation import evaluate_policy

        policy = MagicMock()
        policy.get_action_probabilities.return_value = np.array([0.6, 0.4])

        transitions = [
            Transition(
                observation=np.zeros(10),
                action=0,
                reward=1.0,
                next_observation=np.zeros(10),
                done=True,
            )
        ]
        result = evaluate_policy(transitions, policy, [0.5], method="wis")
        assert hasattr(result, "estimated_value")

    def test_evaluate_policy_is(self) -> None:
        from reinforce_spec._internal._replay_buffer import Transition
        from reinforce_spec.rl.evaluation import evaluate_policy

        policy = MagicMock()
        policy.get_action_probabilities.return_value = np.array([0.7, 0.3])

        transitions = [
            Transition(
                observation=np.zeros(10),
                action=0,
                reward=2.0,
                next_observation=np.zeros(10),
                done=True,
            )
        ]
        result = evaluate_policy(transitions, policy, [0.5], method="is")
        assert hasattr(result, "estimated_value")


# ── rl.selector ──────────────────────────────────────────────────────────────


class TestSelector:
    """Test the Selector façade."""

    def test_import(self) -> None:
        from reinforce_spec.rl.selector import Selector

        assert Selector is not None

    def test_scoring_only(self) -> None:
        from reinforce_spec.rl.selector import Selector

        sel = Selector(policy=None)
        candidates = [_make_candidate(i, score=float(i + 1)) for i in range(3)]
        result = sel.select(candidates, method="scoring_only")
        assert result.selected_index == 2  # highest score
        assert result.method == "scoring_only"

    def test_empty_raises(self) -> None:
        from reinforce_spec.rl.selector import Selector

        sel = Selector()
        with pytest.raises(ValueError, match="empty"):
            sel.select([])

    def test_no_policy_falls_back_to_scoring(self) -> None:
        from reinforce_spec.rl.selector import Selector

        sel = Selector(policy=None)
        candidates = [_make_candidate(0, 2.0), _make_candidate(1, 4.0)]
        result = sel.select(candidates, method="hybrid")
        assert result.method == "scoring_only"

    def test_rl_only_with_policy(self) -> None:
        from reinforce_spec.rl.selector import Selector

        policy = MagicMock()
        policy.predict.return_value = (1, 0.9)
        policy.get_action_probabilities.return_value = np.array(
            [0.1, 0.9, 0.0, 0.0, 0.0],
            dtype=np.float32,
        )

        sel = Selector(policy=policy)
        candidates = [_make_candidate(i, float(i + 1)) for i in range(3)]
        result = sel.select(candidates, method="rl_only")
        assert result.selected_index == 1
        assert result.method == "rl_only"
        assert result.rl_confidence == 0.9

    def test_hybrid_with_policy(self) -> None:
        from reinforce_spec.rl.selector import Selector

        policy = MagicMock()
        policy.predict.return_value = (0, 0.7)
        policy.get_action_probabilities.return_value = np.array(
            [0.7, 0.2, 0.1, 0.0, 0.0],
            dtype=np.float32,
        )

        sel = Selector(policy=policy)
        candidates = [_make_candidate(i, float(i + 1)) for i in range(3)]
        result = sel.select(candidates, method="hybrid")
        assert result.method == "hybrid"
        assert result.rl_action is not None

    def test_selection_result_fields(self) -> None:
        from reinforce_spec.rl.selector import SelectionResult

        r = SelectionResult(
            selected_index=0,
            method="scoring_only",
            rl_action=None,
            rl_confidence=None,
            scoring_rank=0,
        )
        assert r.selected_index == 0


# ── rl.registry ──────────────────────────────────────────────────────────────


class TestPolicyRegistry:
    """Test the PolicyRegistry façade."""

    def test_import(self) -> None:
        from reinforce_spec.rl.registry import PolicyRegistry

        assert PolicyRegistry is not None

    def test_list_versions_empty(self, tmp_path) -> None:
        from reinforce_spec.rl.registry import PolicyRegistry

        with patch("reinforce_spec.rl.registry.PolicyManager"):
            reg = PolicyRegistry(weights_dir=tmp_path / "empty_weights")
            versions = reg.list_versions()
            assert versions == []

    def test_list_versions_with_files(self, tmp_path) -> None:
        from reinforce_spec.rl.registry import PolicyRegistry

        weights_dir = tmp_path / "weights"
        weights_dir.mkdir()
        (weights_dir / "v001.zip").write_bytes(b"fake model")
        (weights_dir / "v002.zip").write_bytes(b"fake model")

        with patch("reinforce_spec.rl.registry.PolicyManager"):
            reg = PolicyRegistry(weights_dir=weights_dir)
            versions = reg.list_versions()
            assert len(versions) == 2
            assert versions[0].version == "v001"

    def test_promote_logs(self, tmp_path) -> None:
        from reinforce_spec.rl.registry import PolicyRegistry

        with patch("reinforce_spec.rl.registry.PolicyManager"):
            reg = PolicyRegistry(weights_dir=tmp_path)
            # promote just logs, doesn't raise
            reg.promote("v001", "canary")

    def test_promote_with_enum(self, tmp_path) -> None:
        from reinforce_spec.rl.registry import PolicyRegistry
        from reinforce_spec.types import PolicyStage

        with patch("reinforce_spec.rl.registry.PolicyManager"):
            reg = PolicyRegistry(weights_dir=tmp_path)
            reg.promote("v001", PolicyStage.PRODUCTION)

    def test_policy_version_dataclass(self) -> None:
        from reinforce_spec.rl.registry import PolicyVersion
        from reinforce_spec.types import PolicyStage

        pv = PolicyVersion(
            version="v001",
            stage=PolicyStage.CANDIDATE,
            path=Path("/tmp/v001.zip"),
            train_steps=100,
        )
        assert pv.version == "v001"
        assert pv.train_steps == 100


# ── rl.trainer ───────────────────────────────────────────────────────────────


class TestTrainer:
    """Test the Trainer façade."""

    def test_import(self) -> None:
        from reinforce_spec.rl.trainer import Trainer

        assert Trainer is not None

    def test_train_result_dataclass(self) -> None:
        from reinforce_spec.rl.trainer import TrainResult

        tr = TrainResult(steps=100, mean_reward=3.5, policy_version="v001")
        assert tr.steps == 100
        assert tr.metrics == {}


# ── rl.__init__ lazy imports ─────────────────────────────────────────────────


class TestRLLazyImports:
    """Test lazy attribute loading from reinforce_spec.rl."""

    def test_spec_selection_env(self) -> None:
        from reinforce_spec.rl import SpecSelectionEnv

        assert SpecSelectionEnv is not None

    def test_policy_manager(self) -> None:
        from reinforce_spec.rl import PolicyManager

        assert PolicyManager is not None

    def test_trainer(self) -> None:
        from reinforce_spec.rl import Trainer

        assert Trainer is not None

    def test_selector(self) -> None:
        from reinforce_spec.rl import Selector

        assert Selector is not None

    def test_policy_registry(self) -> None:
        from reinforce_spec.rl import PolicyRegistry

        assert PolicyRegistry is not None

    def test_evaluate_policy(self) -> None:
        from reinforce_spec.rl import evaluate_policy

        assert callable(evaluate_policy)

    def test_invalid_attr_raises(self) -> None:
        with pytest.raises(AttributeError, match="no attribute"):
            from reinforce_spec import rl

            rl.__getattr__("nonexistent_symbol")


# ── scoring re-exports & presets ─────────────────────────────────────────────


class TestScoringPublicAPI:
    """Test scoring/ public re-exports."""

    def test_dimension_importable(self) -> None:
        from reinforce_spec.scoring import Dimension

        assert len(list(Dimension)) == 12

    def test_enterprise_scorer_lazy(self) -> None:
        from reinforce_spec.scoring import EnterpriseScorer

        assert EnterpriseScorer is not None

    def test_scoring_init_invalid_attr(self) -> None:
        from reinforce_spec import scoring

        with pytest.raises(AttributeError):
            scoring.__getattr__("DoesNotExist")

    def test_get_preset_default(self) -> None:
        from reinforce_spec.scoring.presets import get_preset
        from reinforce_spec.types import CustomerType

        w = get_preset(CustomerType.DEFAULT)
        assert w.validate_sum()

    def test_get_preset_bank(self) -> None:
        from reinforce_spec.scoring.presets import get_preset
        from reinforce_spec.types import CustomerType

        w = get_preset(CustomerType.BANK)
        assert w.validate_sum()

    def test_list_presets(self) -> None:
        from reinforce_spec.scoring.presets import list_presets

        presets = list_presets()
        assert "default" in presets
        assert "bank" in presets
        assert len(presets) >= 4

    def test_get_preset_unknown_returns_default(self) -> None:
        from reinforce_spec.scoring.presets import get_preset
        from reinforce_spec.types import ScoringWeights

        # Use a non-matching enum doesn't exist, pass string to trigger default
        w = get_preset("unknown_type")
        assert isinstance(w, ScoringWeights)


# ── scoring.calibration re-exports ───────────────────────────────────────────


class TestCalibrationReexports:
    def test_imports(self) -> None:
        from reinforce_spec.scoring.calibration import (
            ScoreCalibrator,
        )

        assert ScoreCalibrator is not None


# ── scoring.rubric re-exports ────────────────────────────────────────────────


class TestRubricReexports:
    def test_imports(self) -> None:
        from reinforce_spec.scoring.rubric import (
            RUBRIC,
        )

        assert len(RUBRIC) == 12

    def test_format_rubric_for_prompt(self) -> None:
        from reinforce_spec.scoring.rubric import format_rubric_for_prompt

        text = format_rubric_for_prompt()
        assert isinstance(text, str)
        assert len(text) > 100

    def test_get_all_dimensions(self) -> None:
        from reinforce_spec.scoring.rubric import get_all_dimensions

        dims = get_all_dimensions()
        assert len(dims) == 12

    def test_get_dimension_definition(self) -> None:
        from reinforce_spec.scoring.rubric import Dimension, get_dimension_definition

        defn = get_dimension_definition(Dimension.COMPLIANCE_REGULATORY)
        assert defn is not None
        assert defn.key == "compliance_regulatory"

    def test_get_default_weights(self) -> None:
        from reinforce_spec.scoring.rubric import get_default_weights

        weights = get_default_weights()
        assert isinstance(weights, dict)
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_validate_weights_valid(self) -> None:
        from reinforce_spec.scoring.rubric import get_default_weights, validate_weights

        assert validate_weights(get_default_weights()) is True

    def test_validate_weights_invalid(self) -> None:
        from reinforce_spec.scoring.rubric import validate_weights

        assert validate_weights({"bad": 0.5}) is False


# ── scoring.judge re-export ──────────────────────────────────────────────────


class TestJudgeReexport:
    def test_enterprise_scorer_importable(self) -> None:
        from reinforce_spec.scoring.judge import EnterpriseScorer

        assert EnterpriseScorer is not None
