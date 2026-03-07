"""Application configuration using pydantic-settings.

Follows the 'day-zero safe by default' principle: if a required configuration
is missing, the system fails closed (raises ConfigurationError) rather than
falling back to insecure defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from reinforce_spec._exceptions import ConfigurationError


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(
        env_prefix="RS_",
        populate_by_name=True,
        enable_decoding=False,
        extra="ignore",
    )

    openrouter_api_key: str = Field(
        default="",
        alias="OPENROUTER_API_KEY",
        description="OpenRouter API key (required)",
    )
    judge_models: list[str] = Field(
        default_factory=lambda: [
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
            "google/gemini-2.0-flash-001",
        ],
        description="Models for multi-judge ensemble",
    )
    fallback_models: list[str] = Field(
        default_factory=lambda: [
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
            "google/gemini-2.0-flash-001",
        ],
        description="Fallback model chain",
    )
    timeout_seconds: float = Field(default=30.0, ge=5.0, le=120.0)
    max_retries: int = Field(default=3, ge=0, le=10)

    @field_validator("judge_models", "fallback_models", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v  # type: ignore[return-value]


class RLConfig(BaseSettings):
    """Reinforcement learning configuration."""

    model_config = SettingsConfigDict(env_prefix="RS_", populate_by_name=True, extra="ignore")

    n_candidates: int = Field(default=5, ge=2, le=20, description="Number of spec candidates")
    rl_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="RL vs scoring blend")
    batch_size: int = Field(default=64, ge=16, description="Training batch size")
    feedback_reward_scale: float = Field(default=0.5, ge=0.0, le=2.0)
    policy_weights_dir: Path = Field(default=Path("data/weights"))
    cold_start_threshold: int = Field(default=200, ge=10, description="Episodes before shadow mode")
    shadow_threshold: int = Field(
        default=500, ge=50, description="Episodes before canary promotion"
    )
    explore_rate_initial: float = Field(default=0.15, ge=0.0, le=1.0)
    explore_rate_min: float = Field(default=0.02, ge=0.0, le=0.5)
    explore_decay: float = Field(default=0.995, ge=0.9, le=1.0)
    retrain_batch_size: int = Field(default=50, ge=10)

    # PPO hyperparameters
    ppo_learning_rate: float = Field(default=3e-4, ge=1e-6, le=1e-1)
    ppo_n_steps: int = Field(default=2048, ge=64)
    ppo_batch_size: int = Field(default=64, ge=16)
    ppo_n_epochs: int = Field(default=10, ge=1)
    ppo_clip_range: float = Field(default=0.2, ge=0.05, le=0.5)
    ppo_ent_coef: float = Field(default=0.01, ge=0.0)
    ppo_vf_coef: float = Field(default=0.5, ge=0.0, le=1.0)
    ppo_gae_lambda: float = Field(default=0.95, ge=0.0, le=1.0)
    ppo_gamma: float = Field(default=0.99, ge=0.0, le=1.0)
    ppo_hidden_layers: list[int] = Field(default_factory=lambda: [256, 256])

    # Replay buffer
    replay_buffer_capacity: int = Field(default=100_000, ge=1000)
    per_alpha: float = Field(default=0.6, ge=0.0, le=1.0)
    per_beta_start: float = Field(default=0.4, ge=0.0, le=1.0)
    per_beta_end: float = Field(default=1.0, ge=0.0, le=1.0)
    per_epsilon: float = Field(default=0.01, ge=0.0)


class ScoringConfig(BaseSettings):
    """Scoring engine configuration."""

    model_config = SettingsConfigDict(env_prefix="RS_", extra="ignore")

    scoring_mode: str = Field(
        default="multi_judge",
        description="single_judge or multi_judge",
    )
    calibration_enabled: bool = Field(default=True)
    pairwise_top_k: int = Field(default=3, ge=2, le=10)
    judge_temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    judge_samples_per_model: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Within-model ensemble samples",
    )

    @field_validator("scoring_mode")
    @classmethod
    def validate_scoring_mode(cls, v: str) -> str:
        allowed = {"single_judge", "multi_judge"}
        if v not in allowed:
            raise ValueError(f"scoring_mode must be one of {allowed}")
        return v


class ResilienceConfig(BaseSettings):
    """Circuit breaker, backpressure, degradation configuration."""

    model_config = SettingsConfigDict(env_prefix="RS_", extra="ignore")

    circuit_breaker_threshold: int = Field(default=5, ge=1)
    circuit_breaker_cooldown_seconds: float = Field(default=60.0, ge=5.0)
    max_concurrent_requests: int = Field(default=50, ge=1)
    backpressure_p99_slo_seconds: float = Field(default=30.0, ge=5.0)
    idempotency_ttl_seconds: int = Field(default=86400, ge=60)


class ServerConfig(BaseSettings):
    """Server configuration."""

    model_config = SettingsConfigDict(env_prefix="RS_", extra="ignore")

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=32)
    log_level: str = Field(default="info")
    log_format: str = Field(default="json")
    api_key: str = Field(default="", description="Leave empty to disable auth in dev")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    max_concurrent_requests: int = Field(default=50, ge=1)


class StorageConfig(BaseSettings):
    """Storage and persistence configuration."""

    model_config = SettingsConfigDict(env_prefix="RS_", extra="ignore")

    data_dir: str = Field(default="data", description="Root data directory")
    db_name: str = Field(default="reinforce_spec.db", description="SQLite database filename")
    database_url: str = Field(default="sqlite+aiosqlite:///data/db/reinforce_spec.db")
    redis_url: str = Field(default="", description="Empty for in-memory fallback")


class ObservabilityConfig(BaseSettings):
    """Observability configuration."""

    model_config = SettingsConfigDict(env_prefix="RS_", extra="ignore")

    metrics_enabled: bool = Field(default=True)
    mlflow_tracking_uri: str = Field(default="")
    audit_log_retention_days: int = Field(default=2555)


class AppConfig(BaseSettings):
    """Root application configuration.

    Aggregates all sub-configs and validates cross-cutting concerns.
    """

    model_config = SettingsConfigDict(
        env_prefix="RS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    rl: RLConfig = Field(default_factory=RLConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    @model_validator(mode="after")
    def validate_fail_closed(self) -> AppConfig:
        """Day-zero safe by default: fail closed on missing critical config."""
        if not self.llm.openrouter_api_key:
            raise ConfigurationError(
                "OPENROUTER_API_KEY is required. Set it in .env or as an environment variable. "
                "The system fails closed when critical configuration is missing."
            )
        return self

    @classmethod
    def from_env(cls, env_file: str | None = ".env") -> AppConfig:
        """Load configuration from environment variables and ``.env`` file.

        Returns
        -------
        AppConfig
            Validated application configuration.

        Raises
        ------
        ConfigurationError
            If required values are missing or invalid.

        """
        try:
            settings_kwargs: dict[str, Any] = {
                "_env_file": env_file,
                "_env_file_encoding": "utf-8",
            }
            return cast(AppConfig, cast(Any, cls)(**settings_kwargs))
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration: {e}. "
                "Copy .env.example to .env and fill in required values."
            ) from e

    @classmethod
    def for_testing(cls) -> AppConfig:
        """Return a configuration suitable for testing.

        Returns
        -------
        AppConfig
            Configuration with no external dependencies.

        """
        return cls(
            llm=LLMConfig.model_validate(
                {
                    "OPENROUTER_API_KEY": "test-key-not-real",
                    "judge_models": ["test/judge"],
                    "fallback_models": ["test/model"],
                    "timeout_seconds": 5.0,
                    "max_retries": 0,
                }
            ),
            rl=RLConfig(
                policy_weights_dir=Path("/tmp/reinforce-spec-test-weights"),
                cold_start_threshold=10,
                shadow_threshold=50,
                retrain_batch_size=10,
            ),
            scoring=ScoringConfig(
                scoring_mode="single_judge",
                calibration_enabled=False,
            ),
            resilience=ResilienceConfig(
                circuit_breaker_threshold=2,
                circuit_breaker_cooldown_seconds=5.0,
                max_concurrent_requests=5,
            ),
            server=ServerConfig(api_key=""),
            storage=StorageConfig(
                database_url="sqlite+aiosqlite:///tmp/reinforce_spec_test.db",
                redis_url="",
            ),
            observability=ObservabilityConfig(
                metrics_enabled=False,
                mlflow_tracking_uri="",
            ),
        )
