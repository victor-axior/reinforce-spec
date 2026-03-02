"""PPO policy wrapper and policy lifecycle registry.

Provides:
  - ``PPOPolicy`` — thin wrapper around stable-baselines3 PPO, adapted for
    the contextual-bandit spec-selection problem.
  - ``PolicyManager`` — lifecycle management with promotion stages:
      candidate → shadow → canary → production → archived.
  - Persistent weight checkpointing and loading.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from reinforce_spec._compat import SB3_AVAILABLE, require_dependency
from reinforce_spec._exceptions import PolicyNotFoundError, PolicyTrainingError
from reinforce_spec._internal._config import RLConfig
from reinforce_spec._internal._environment import PER_CANDIDATE_FEATURES, SpecSelectionEnv
from reinforce_spec._internal._replay_buffer import Transition
from reinforce_spec._internal._utils import utc_now
from reinforce_spec.types import PolicyStage


# ── PPO Policy ────────────────────────────────────────────────────────────────


class PPOPolicy:
    """Wrapper around stable-baselines3 PPO for spec selection.

    Provides a simplified interface for:
      - Training on replay-buffer transitions
      - Predicting the best action for a given observation
      - Saving/loading model checkpoints

    """

    def __init__(
        self,
        config: RLConfig | None = None,
        env: SpecSelectionEnv | None = None,
    ) -> None:
        """Initialize a PPO policy.

        Parameters
        ----------
        config : RLConfig or None
            RL hyperparameters.  Uses defaults when ``None``.
        env : SpecSelectionEnv or None
            Gymnasium environment.  A default environment is created
            when ``None``.

        """
        require_dependency("stable_baselines3", "rl")

        from stable_baselines3 import PPO  # type: ignore[import-untyped]

        self._config = config or RLConfig()
        self._env = env or SpecSelectionEnv(config=self._config)

        # Build PPO with configured hyperparameters
        policy_kwargs: dict[str, Any] = {
            "net_arch": list(self._config.ppo_hidden_layers),
        }

        self._model = PPO(
            policy="MlpPolicy",
            env=self._env,
            learning_rate=self._config.ppo_learning_rate,
            gamma=self._config.ppo_gamma,
            gae_lambda=self._config.ppo_gae_lambda,
            clip_range=self._config.ppo_clip_range,
            ent_coef=self._config.ppo_ent_coef,
            n_steps=self._config.ppo_batch_size,  # steps per env before update
            batch_size=self._config.ppo_batch_size,
            n_epochs=self._config.ppo_n_epochs,
            verbose=0,
            policy_kwargs=policy_kwargs,
        )

        self._train_steps: int = 0

    @property
    def train_steps(self) -> int:
        """Return the total number of training steps completed."""
        return self._train_steps

    def predict(
        self,
        observation: np.ndarray,
        deterministic: bool = True,
    ) -> tuple[int, float]:
        """Predict the best action for an observation.

        Parameters
        ----------
        observation : np.ndarray
            Flat feature vector from :func:`build_observation`.
        deterministic : bool
            If ``True``, use the greedy action.

        Returns
        -------
        tuple[int, float]
            ``(action_index, confidence)`` where *confidence* is the
            softmax probability of the selected action.

        """
        action, _states = self._model.predict(observation, deterministic=deterministic)
        action_int = int(action)

        # Get action probabilities for confidence
        obs_tensor = self._model.policy.obs_to_tensor(observation)[0]
        distribution = self._model.policy.get_distribution(obs_tensor)
        probs = distribution.distribution.probs.detach().cpu().numpy().flatten()
        confidence = float(probs[action_int]) if action_int < len(probs) else 0.0

        return action_int, confidence

    def train_on_batch(
        self,
        transitions: list[Transition],
        total_timesteps: int | None = None,
    ) -> dict[str, float]:
        """Train the policy on a batch of transitions.

        Feeds the transitions through the environment and runs
        ``PPO.learn()``.

        Parameters
        ----------
        transitions : list[Transition]
            Replay-buffer transitions to train on.
        total_timesteps : int or None
            Override for the number of training steps.  Defaults to
            ``max(len(transitions), ppo_batch_size)``.

        Returns
        -------
        dict[str, float]
            Training metrics (``loss``, ``n_transitions``,
            ``total_steps``).

        Raises
        ------
        PolicyTrainingError
            If PPO training fails.

        """
        if not transitions:
            return {"loss": 0.0, "n_transitions": 0}

        steps = total_timesteps or max(len(transitions), self._config.ppo_batch_size)

        try:
            # Prime the env with real (observation, reward) pairs from the
            # PER buffer so PPO trains on authentic signal instead of
            # rolling out on empty candidates (reward=0 every step).
            self._env.load_transitions(transitions)
            self._model.learn(total_timesteps=steps, reset_num_timesteps=False)
            self._train_steps += steps
        except Exception as e:
            raise PolicyTrainingError(f"PPO training failed: {e}") from e
        finally:
            # Always exit replay mode so live inference is unaffected.
            self._env.clear_replay()

        return {
            "loss": 0.0,  # SB3 doesn't expose loss easily
            "n_transitions": len(transitions),
            "total_steps": self._train_steps,
        }

    def save(self, path: str | Path) -> Path:
        """Save model weights to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._model.save(str(path))
        logger.info("policy_saved | path={path} steps={steps}", path=str(path), steps=self._train_steps)
        return path

    def load(self, path: str | Path) -> None:
        """Load model weights from disk."""
        from stable_baselines3 import PPO  # type: ignore[import-untyped]

        path = Path(path)
        self._model = PPO.load(str(path), env=self._env)
        logger.info("policy_loaded | path={path}", path=str(path))

    def get_action_probabilities(self, observation: np.ndarray) -> np.ndarray:
        """Get action probability distribution for an observation."""
        obs_tensor = self._model.policy.obs_to_tensor(observation)[0]
        distribution = self._model.policy.get_distribution(obs_tensor)
        return distribution.distribution.probs.detach().cpu().numpy().flatten()


# ── Policy Metadata ──────────────────────────────────────────────────────────


@dataclasses.dataclass
class PolicyMetadata:
    """Metadata for a versioned policy checkpoint."""

    policy_id: str
    version: int
    stage: PolicyStage
    created_at: datetime
    promoted_at: datetime | None = None
    archived_at: datetime | None = None
    train_steps: int = 0
    metrics: dict[str, float] = dataclasses.field(default_factory=dict)
    checksum: str = ""
    parent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata to a JSON-compatible dictionary."""
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "stage": self.stage.value,
            "created_at": self.created_at.isoformat(),
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "train_steps": self.train_steps,
            "metrics": self.metrics,
            "checksum": self.checksum,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyMetadata:
        """Deserialize metadata from a dictionary.

        Parameters
        ----------
        data : dict[str, Any]
            Dictionary produced by :meth:`to_dict`.

        Returns
        -------
        PolicyMetadata
            Reconstructed metadata instance.

        """
        return cls(
            policy_id=data["policy_id"],
            version=data["version"],
            stage=PolicyStage(data["stage"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            promoted_at=(
                datetime.fromisoformat(data["promoted_at"])
                if data.get("promoted_at")
                else None
            ),
            archived_at=(
                datetime.fromisoformat(data["archived_at"])
                if data.get("archived_at")
                else None
            ),
            train_steps=data.get("train_steps", 0),
            metrics=data.get("metrics", {}),
            checksum=data.get("checksum", ""),
            parent_id=data.get("parent_id"),
        )


# ── Policy Manager ───────────────────────────────────────────────────────────


class PolicyManager:
    """Lifecycle manager for versioned PPO policies.

    Manages the promotion pipeline:
        candidate → shadow → canary → production → archived

    Directory layout::

        policies/
        ├── registry.json          # version → metadata
        ├── v001/
        │   ├── model.zip
        │   └── metadata.json
        ├── v002/
        │   ├── model.zip
        │   └── metadata.json
        └── production -> v002/    # symlink to current production

    """

    PROMOTION_ORDER = [
        PolicyStage.CANDIDATE,
        PolicyStage.SHADOW,
        PolicyStage.CANARY,
        PolicyStage.PRODUCTION,
    ]

    def __init__(
        self,
        storage_dir: str | Path,
        config: RLConfig | None = None,
    ) -> None:
        """Initialize the policy manager.

        Parameters
        ----------
        storage_dir : str or Path
            Root directory for policy checkpoints and registry.
        config : RLConfig or None
            RL configuration shared with created policies.

        """
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._config = config or RLConfig()
        self._registry: dict[str, PolicyMetadata] = {}
        self._active_policy: PPOPolicy | None = None
        self._load_registry()

    def _load_registry(self) -> None:
        """Load the registry from disk."""
        registry_path = self._storage_dir / "registry.json"
        if registry_path.exists():
            with open(registry_path) as f:
                data = json.load(f)
            self._registry = {
                k: PolicyMetadata.from_dict(v) for k, v in data.items()
            }

    def _save_registry(self) -> None:
        """Persist the registry to disk."""
        registry_path = self._storage_dir / "registry.json"
        data = {k: v.to_dict() for k, v in self._registry.items()}
        with open(registry_path, "w") as f:
            json.dump(data, f, indent=2)

    @property
    def active_policy(self) -> PPOPolicy | None:
        """Return the currently loaded production policy, if any."""
        return self._active_policy

    def create_policy(
        self,
        env: SpecSelectionEnv | None = None,
        parent_id: str | None = None,
    ) -> tuple[PPOPolicy, PolicyMetadata]:
        """Create a new policy version in CANDIDATE stage.

        Parameters
        ----------
        env : SpecSelectionEnv or None
            Environment for the new policy.
        parent_id : str or None
            Policy ID of the parent version, if any.

        Returns
        -------
        tuple[PPOPolicy, PolicyMetadata]
            The new policy and its metadata.

        """
        version = len(self._registry) + 1
        policy_id = f"v{version:03d}"

        policy = PPOPolicy(config=self._config, env=env)

        metadata = PolicyMetadata(
            policy_id=policy_id,
            version=version,
            stage=PolicyStage.CANDIDATE,
            created_at=utc_now(),
            parent_id=parent_id,
        )

        # Save initial checkpoint
        version_dir = self._storage_dir / policy_id
        version_dir.mkdir(parents=True, exist_ok=True)
        model_path = policy.save(version_dir / "model")
        metadata.checksum = self._compute_checksum(model_path)

        # Persist metadata
        meta_path = version_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        self._registry[policy_id] = metadata
        self._save_registry()

        logger.info(
            "policy_created | policy_id={policy_id} stage={stage}",
            policy_id=policy_id,
            stage=metadata.stage.value,
        )

        return policy, metadata

    def promote(self, policy_id: str) -> PolicyMetadata:
        """Promote a policy to the next stage.

        Parameters
        ----------
        policy_id : str
            Identifier of the policy to promote.

        Returns
        -------
        PolicyMetadata
            Updated metadata after promotion.

        Raises
        ------
        PolicyNotFoundError
            If *policy_id* does not exist in the registry.

        """
        if policy_id not in self._registry:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        meta = self._registry[policy_id]
        current_idx = self.PROMOTION_ORDER.index(meta.stage)

        if current_idx >= len(self.PROMOTION_ORDER) - 1:
            logger.warning("policy_already_at_max_stage | policy_id={policy_id}", policy_id=policy_id)
            return meta

        new_stage = self.PROMOTION_ORDER[current_idx + 1]

        # If promoting to production, archive current production
        if new_stage == PolicyStage.PRODUCTION:
            self._archive_current_production()

        meta.stage = new_stage
        meta.promoted_at = utc_now()

        # Update production symlink
        if new_stage == PolicyStage.PRODUCTION:
            self._update_production_link(policy_id)
            self._active_policy = self._load_policy(policy_id)

        self._save_registry()

        logger.info(
            "policy_promoted | policy_id={policy_id} new_stage={new_stage}",
            policy_id=policy_id,
            new_stage=new_stage.value,
        )

        return meta

    def rollback(self, to_policy_id: str) -> PolicyMetadata:
        """Roll back production to a specific policy version.

        Parameters
        ----------
        to_policy_id : str
            Target policy version (must be ``ARCHIVED`` or
            ``PRODUCTION``).

        Returns
        -------
        PolicyMetadata
            Updated metadata of the restored policy.

        Raises
        ------
        PolicyNotFoundError
            If *to_policy_id* does not exist in the registry.

        """
        if to_policy_id not in self._registry:
            raise PolicyNotFoundError(f"Policy {to_policy_id} not found")

        self._archive_current_production()

        meta = self._registry[to_policy_id]
        meta.stage = PolicyStage.PRODUCTION
        meta.promoted_at = utc_now()

        self._update_production_link(to_policy_id)
        self._active_policy = self._load_policy(to_policy_id)
        self._save_registry()

        logger.info("policy_rollback | to_policy_id={to_policy_id}", to_policy_id=to_policy_id)
        return meta

    def get_production_policy(self) -> PPOPolicy | None:
        """Load and return the current production policy."""
        for meta in self._registry.values():
            if meta.stage == PolicyStage.PRODUCTION:
                if self._active_policy is None:
                    self._active_policy = self._load_policy(meta.policy_id)
                return self._active_policy
        return None

    def list_policies(
        self,
        stage: PolicyStage | None = None,
    ) -> list[PolicyMetadata]:
        """List all policies, optionally filtered by stage."""
        policies = list(self._registry.values())
        if stage is not None:
            policies = [p for p in policies if p.stage == stage]
        return sorted(policies, key=lambda p: p.version, reverse=True)

    def save_checkpoint(self, policy_id: str, policy: PPOPolicy) -> None:
        """Save a policy checkpoint to its version directory."""
        if policy_id not in self._registry:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        version_dir = self._storage_dir / policy_id
        model_path = policy.save(version_dir / "model")

        meta = self._registry[policy_id]
        meta.checksum = self._compute_checksum(model_path)
        meta.train_steps = policy.train_steps
        self._save_registry()

    def _load_policy(self, policy_id: str) -> PPOPolicy:
        """Load a policy from its version directory."""
        version_dir = self._storage_dir / policy_id
        model_path = version_dir / "model.zip"

        policy = PPOPolicy(config=self._config)
        policy.load(model_path)
        return policy

    def _archive_current_production(self) -> None:
        """Move current production policy to ARCHIVED."""
        for meta in self._registry.values():
            if meta.stage == PolicyStage.PRODUCTION:
                meta.stage = PolicyStage.ARCHIVED
                meta.archived_at = utc_now()
                logger.info("policy_archived | policy_id={policy_id}", policy_id=meta.policy_id)

    def _update_production_link(self, policy_id: str) -> None:
        """Create/update the 'production' symlink."""
        link = self._storage_dir / "production"
        target = self._storage_dir / policy_id

        if link.is_symlink() or link.exists():
            link.unlink()

        try:
            link.symlink_to(target)
        except OSError:
            # Symlinks not supported (Windows without dev mode)
            logger.warning("symlink_not_supported | fallback={fallback}", fallback="copy")
            if link.exists():
                shutil.rmtree(link)
            shutil.copytree(target, link)

    @staticmethod
    def _compute_checksum(path: Path) -> str:
        """Compute SHA-256 of a model file."""
        if not path.exists():
            # SB3 appends .zip
            path = path.with_suffix(".zip")
        if not path.exists():
            return ""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]


__all__ = ["PPOPolicy", "PolicyManager", "PolicyMetadata"]
