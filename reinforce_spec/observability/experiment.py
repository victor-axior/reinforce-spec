"""MLflow experiment tracking integration.

Provides ``ExperimentTracker`` for logging RL training runs, scoring
metrics, and model artefacts to MLflow.  Falls back to a no-op when
``mlflow`` is not installed.

Examples
--------
>>> from reinforce_spec.observability.experiment import ExperimentTracker
>>> tracker = ExperimentTracker(experiment_name="policy-v3")
>>> tracker.log_training_run(steps=2048, reward=3.8, loss=0.12)
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from reinforce_spec._compat import MLFLOW_AVAILABLE


class ExperimentTracker:
    """MLflow experiment tracker with graceful degradation.

    Parameters
    ----------
    experiment_name : str
        MLflow experiment name (created if missing).
    tracking_uri : str or None
        MLflow tracking server URI.  Uses ``MLFLOW_TRACKING_URI``
        environment variable when ``None``.

    """

    def __init__(
        self,
        experiment_name: str = "reinforce-spec",
        tracking_uri: str | None = None,
    ) -> None:
        self._enabled = MLFLOW_AVAILABLE
        self._experiment_name = experiment_name

        if not self._enabled:
            logger.debug("mlflow_not_installed — experiment tracking disabled")
            return

        import mlflow  # type: ignore[import-untyped]

        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        logger.info(
            "experiment_tracker_ready | experiment={exp}",
            exp=experiment_name,
        )

    def log_training_run(
        self,
        *,
        steps: int,
        reward: float,
        loss: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str | None:
        """Log a training run to MLflow.

        Parameters
        ----------
        steps : int
            Number of training timesteps.
        reward : float
            Mean episode reward.
        loss : float or None
            Training loss (if available).
        extra : dict or None
            Additional metrics to log.

        Returns
        -------
        str or None
            MLflow run ID, or ``None`` when disabled.

        """
        if not self._enabled:
            return None

        import mlflow  # type: ignore[import-untyped]

        with mlflow.start_run() as run:
            mlflow.log_metric("steps", steps)
            mlflow.log_metric("mean_reward", reward)
            if loss is not None:
                mlflow.log_metric("loss", loss)
            if extra:
                mlflow.log_metrics(extra)
            logger.info(
                "experiment_logged | run_id={id} steps={steps} reward={reward}",
                id=run.info.run_id,
                steps=steps,
                reward=round(reward, 4),
            )
            return run.info.run_id  # type: ignore[no-any-return]

    def log_model(self, model_path: str, artifact_path: str = "model") -> None:
        """Log a model artefact to MLflow.

        Parameters
        ----------
        model_path : str
            Local path to the model file.
        artifact_path : str
            Artefact sub-directory in MLflow.

        """
        if not self._enabled:
            return

        import mlflow  # type: ignore[import-untyped]

        mlflow.log_artifact(model_path, artifact_path)
        logger.info("model_artifact_logged | path={path}", path=model_path)
