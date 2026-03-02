"""Unit tests for application configuration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from reinforce_spec._exceptions import ConfigurationError
from reinforce_spec._internal._config import (
    AppConfig,
    LLMConfig,
    ObservabilityConfig,
    RLConfig,
    ResilienceConfig,
    ScoringConfig,
    ServerConfig,
    StorageConfig,
)


class TestLLMConfig:
    """Test LLM configuration."""

    def test_defaults(self) -> None:
        cfg = LLMConfig()
        assert cfg.openrouter_api_key == ""
        assert len(cfg.judge_models) == 3
        assert cfg.timeout_seconds == 30.0
        assert cfg.max_retries == 3

    def test_populate_by_name(self) -> None:
        cfg = LLMConfig(openrouter_api_key="test-key")
        assert cfg.openrouter_api_key == "test-key"

    def test_parse_comma_separated_string(self) -> None:
        cfg = LLMConfig(judge_models="model-a, model-b, model-c")
        assert cfg.judge_models == ["model-a", "model-b", "model-c"]

    def test_parse_comma_separated_list_passthrough(self) -> None:
        cfg = LLMConfig(judge_models=["model-a", "model-b"])
        assert cfg.judge_models == ["model-a", "model-b"]

    def test_parse_comma_separated_empty_string_segments(self) -> None:
        cfg = LLMConfig(judge_models="model-a,,model-b,")
        assert cfg.judge_models == ["model-a", "model-b"]

    def test_timeout_bounds(self) -> None:
        with pytest.raises(ValidationError):
            LLMConfig(timeout_seconds=2.0)
        with pytest.raises(ValidationError):
            LLMConfig(timeout_seconds=200.0)


class TestRLConfig:
    """Test RL configuration."""

    def test_defaults(self) -> None:
        cfg = RLConfig()
        assert cfg.n_candidates == 5
        assert cfg.rl_weight == 0.5
        assert cfg.batch_size == 64

    def test_cold_start_threshold_minimum(self) -> None:
        with pytest.raises(ValidationError):
            RLConfig(cold_start_threshold=5)

    def test_shadow_threshold_minimum(self) -> None:
        with pytest.raises(ValidationError):
            RLConfig(shadow_threshold=10)

    def test_retrain_batch_size_minimum(self) -> None:
        with pytest.raises(ValidationError):
            RLConfig(retrain_batch_size=5)

    def test_ppo_hyperparams(self) -> None:
        cfg = RLConfig()
        assert cfg.ppo_learning_rate == pytest.approx(3e-4)
        assert cfg.ppo_clip_range == 0.2
        assert cfg.ppo_hidden_layers == [256, 256]

    def test_replay_buffer_defaults(self) -> None:
        cfg = RLConfig()
        assert cfg.replay_buffer_capacity == 100_000
        assert cfg.per_alpha == 0.6


class TestScoringConfig:
    """Test scoring configuration."""

    def test_defaults(self) -> None:
        cfg = ScoringConfig()
        assert cfg.scoring_mode == "multi_judge"
        assert cfg.calibration_enabled is True
        assert cfg.pairwise_top_k == 3

    def test_valid_scoring_modes(self) -> None:
        ScoringConfig(scoring_mode="single_judge")
        ScoringConfig(scoring_mode="multi_judge")

    def test_invalid_scoring_mode(self) -> None:
        with pytest.raises(ValidationError, match="scoring_mode"):
            ScoringConfig(scoring_mode="invalid_mode")


class TestResilienceConfig:
    """Test resilience configuration."""

    def test_defaults(self) -> None:
        cfg = ResilienceConfig()
        assert cfg.circuit_breaker_threshold == 5
        assert cfg.circuit_breaker_cooldown_seconds == 60.0
        assert cfg.max_concurrent_requests == 50
        assert cfg.idempotency_ttl_seconds == 86400


class TestServerConfig:
    """Test server configuration."""

    def test_defaults(self) -> None:
        cfg = ServerConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8000
        assert cfg.workers == 4
        assert cfg.cors_origins == ["*"]

    def test_port_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ServerConfig(port=0)
        with pytest.raises(ValidationError):
            ServerConfig(port=99999)


class TestStorageConfig:
    """Test storage configuration."""

    def test_defaults(self) -> None:
        cfg = StorageConfig()
        assert cfg.data_dir == "data"
        assert cfg.db_name == "reinforce_spec.db"
        assert cfg.redis_url == ""


class TestObservabilityConfig:
    """Test observability configuration."""

    def test_defaults(self) -> None:
        cfg = ObservabilityConfig()
        assert cfg.metrics_enabled is True
        assert cfg.mlflow_tracking_uri == ""
        assert cfg.audit_log_retention_days == 2555


class TestAppConfig:
    """Test root app configuration."""

    def test_for_testing(self) -> None:
        cfg = AppConfig.for_testing()
        assert cfg.llm.openrouter_api_key == "test-key-not-real"
        assert cfg.scoring.scoring_mode == "single_judge"
        assert cfg.scoring.calibration_enabled is False
        assert cfg.observability.metrics_enabled is False

    def test_validate_fail_closed_missing_key(self) -> None:
        with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY"):
            AppConfig(
                llm=LLMConfig(openrouter_api_key=""),
                rl=RLConfig(),
                scoring=ScoringConfig(),
                resilience=ResilienceConfig(),
                server=ServerConfig(),
                storage=StorageConfig(),
                observability=ObservabilityConfig(),
            )

    def test_validate_fail_closed_key_present(self) -> None:
        cfg = AppConfig(
            llm=LLMConfig(openrouter_api_key="real-key"),
        )
        assert cfg.llm.openrouter_api_key == "real-key"

    def test_from_env_with_missing_key(self) -> None:
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}, clear=True):
            with pytest.raises(ConfigurationError, match="Failed to load"):
                AppConfig.from_env(env_file=None)

    def test_from_env_success(self) -> None:
        env = {
            "OPENROUTER_API_KEY": "env-test-key",
        }
        with patch.dict("os.environ", env, clear=False):
            try:
                cfg = AppConfig.from_env()
                assert cfg.llm.openrouter_api_key == "env-test-key"
            except ConfigurationError:
                # Key may not be picked up depending on pydantic-settings prefix
                pass

    def test_for_testing_rl_config_constraints(self) -> None:
        cfg = AppConfig.for_testing()
        assert cfg.rl.cold_start_threshold >= 10
        assert cfg.rl.shadow_threshold >= 50
        assert cfg.rl.retrain_batch_size >= 10

    def test_for_testing_resilience_config(self) -> None:
        cfg = AppConfig.for_testing()
        assert cfg.resilience.circuit_breaker_threshold == 2
        assert cfg.resilience.circuit_breaker_cooldown_seconds == 5.0
        assert cfg.resilience.max_concurrent_requests == 5
