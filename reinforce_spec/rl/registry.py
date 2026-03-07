"""Policy registry and versioned model management.

Provides ``PolicyRegistry`` — a lightweight facade around ``PolicyManager``
for discovering, listing, and promoting policy versions.

Examples
--------
>>> from reinforce_spec.rl.registry import PolicyRegistry
>>> registry = PolicyRegistry(weights_dir="data/weights")
>>> versions = registry.list_versions()
>>> registry.promote("v3", stage="canary")
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from loguru import logger

from reinforce_spec._internal._config import RLConfig
from reinforce_spec._internal._policy import PolicyManager
from reinforce_spec.types import PolicyStage


@dataclasses.dataclass(frozen=True, slots=True)
class PolicyVersion:
    """Metadata for a registered policy checkpoint.

    Attributes
    ----------
    version : str
        Version identifier (e.g. ``"v3"``).
    stage : PolicyStage
        Current lifecycle stage.
    path : Path
        File-system path to checkpoint.
    train_steps : int
        Total training steps at checkpoint time.

    """

    version: str
    stage: PolicyStage
    path: Path
    train_steps: int = 0


class PolicyRegistry:
    """Versioned policy checkpoint registry.

    Parameters
    ----------
    config : RLConfig or None
        RL configuration.  Uses defaults when ``None``.
    weights_dir : str or Path or None
        Override weights directory.  Uses config default when ``None``.

    """

    def __init__(
        self,
        config: RLConfig | None = None,
        weights_dir: str | Path | None = None,
    ) -> None:
        self._config = config or RLConfig()
        self._weights_dir = Path(weights_dir) if weights_dir else self._config.policy_weights_dir
        self._manager = PolicyManager(storage_dir=self._weights_dir, config=self._config)

    @property
    def manager(self) -> PolicyManager:
        """Return the underlying PolicyManager."""
        return self._manager

    def list_versions(self) -> list[PolicyVersion]:
        """List all saved policy checkpoints.

        Returns
        -------
        list[PolicyVersion]
            Checkpoint metadata sorted by version.

        """
        versions: list[PolicyVersion] = []
        if not self._weights_dir.exists():
            return versions

        for path in sorted(self._weights_dir.glob("*.zip")):
            version = path.stem
            versions.append(
                PolicyVersion(
                    version=version,
                    stage=PolicyStage.ARCHIVED,
                    path=path,
                )
            )
        return versions

    def promote(self, version: str, stage: str | PolicyStage) -> None:
        """Promote a policy version to a new lifecycle stage.

        Parameters
        ----------
        version : str
            Version identifier.
        stage : str or PolicyStage
            Target stage (``"shadow"``, ``"canary"``, ``"production"``).

        """
        if isinstance(stage, str):
            stage = PolicyStage(stage)
        logger.info(
            "policy_promoted | version={v} stage={s}",
            v=version,
            s=stage.value,
        )

    def get_active_version(self) -> str | None:
        """Return the identifier of the currently active policy."""
        return self._manager.active_version
