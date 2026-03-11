"""Main client for the ReinforceSpec SDK."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Callable

import httpx

from reinforce_spec_sdk._http import HTTPClient, PoolLimits, TimeoutConfig
from reinforce_spec_sdk.types import (
    HealthResponse,
    PolicyStatus,
    SelectionMethod,
    SelectionResponse,
    SpecInput,
)

# Type aliases
RequestHook = Callable[[httpx.Request], None]
ResponseHook = Callable[[httpx.Response], None]


class ReinforceSpecClient:
    """Client for the ReinforceSpec API.

    This is the main entry point for interacting with the ReinforceSpec API.
    It provides methods for evaluating specs, submitting feedback, and
    checking policy status.

    The client supports both async and sync usage patterns:

    Async usage (recommended):
        >>> async with ReinforceSpecClient.from_env() as client:
        ...     response = await client.select(candidates=[...])

    Sync usage:
        >>> with ReinforceSpecClient.sync(base_url="...", api_key="...") as client:
        ...     response = client.select_sync(candidates=[...])

    Attributes:
        base_url: Base URL of the API.
        api_key: API key for authentication.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float | TimeoutConfig = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_max_delay: float = 30.0,
        retry_jitter: float = 5.0,
        pool_limits: PoolLimits | None = None,
        on_request: RequestHook | None = None,
        on_response: ResponseHook | None = None,
    ) -> None:
        """Initialize the ReinforceSpec client.

        Args:
            base_url: Base URL of the ReinforceSpec API.
            api_key: API key for authentication (optional if API is public).
            timeout: Request timeout in seconds or TimeoutConfig for granular control.
            max_retries: Maximum number of retry attempts. Default: 3.
            retry_delay: Initial delay between retries in seconds. Default: 1.
            retry_max_delay: Maximum delay between retries. Default: 30.
            retry_jitter: Random jitter added to retry delays. Default: 5.
            pool_limits: Connection pool configuration. Default: PoolLimits().
            on_request: Hook called before each request (for logging/debugging).
            on_response: Hook called after each response (for logging/debugging).
        """
        self._http = HTTPClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            retry_max_delay=retry_max_delay,
            retry_jitter=retry_jitter,
            pool_limits=pool_limits,
            on_request=on_request,
            on_response=on_response,
        )

    @classmethod
    def from_env(cls) -> ReinforceSpecClient:
        """Create a client from environment variables.

        Environment variables:
            REINFORCE_SPEC_BASE_URL: Base URL of the API (required).
            REINFORCE_SPEC_API_KEY: API key for authentication (optional).
            REINFORCE_SPEC_TIMEOUT: Request timeout in seconds (default: 30).
            REINFORCE_SPEC_MAX_RETRIES: Maximum retry attempts (default: 3).

        Returns:
            Configured ReinforceSpecClient instance.

        Raises:
            ValueError: If REINFORCE_SPEC_BASE_URL is not set.
        """
        base_url = os.environ.get("REINFORCE_SPEC_BASE_URL")
        if not base_url:
            raise ValueError("REINFORCE_SPEC_BASE_URL environment variable is required")

        return cls(
            base_url=base_url,
            api_key=os.environ.get("REINFORCE_SPEC_API_KEY"),
            timeout=float(os.environ.get("REINFORCE_SPEC_TIMEOUT", "30")),
            max_retries=int(os.environ.get("REINFORCE_SPEC_MAX_RETRIES", "3")),
        )

    async def __aenter__(self) -> ReinforceSpecClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._http.close()

    @classmethod
    @contextmanager
    def sync(
        cls,
        base_url: str,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> Iterator[ReinforceSpecClient]:
        """Create a synchronous context manager for the client.

        Example:
            >>> with ReinforceSpecClient.sync(base_url="...", api_key="...") as client:
            ...     response = client.select_sync(candidates=[...])

        Args:
            base_url: Base URL of the API.
            api_key: API key for authentication.
            **kwargs: Additional arguments passed to __init__.

        Yields:
            Configured ReinforceSpecClient instance.
        """
        client = cls(base_url=base_url, api_key=api_key, **kwargs)
        try:
            yield client
        finally:
            # Use a dedicated thread to run async cleanup safely
            def _run_close() -> None:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(client.close())
                finally:
                    loop.close()

            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(_run_close).result(timeout=5.0)

    # =========================================================================
    # API Methods
    # =========================================================================

    async def select(
        self,
        candidates: list[dict[str, Any] | SpecInput],
        *,
        selection_method: str | SelectionMethod = SelectionMethod.HYBRID,
        request_id: str | None = None,
        description: str | None = None,
    ) -> SelectionResponse:
        """Evaluate candidates and select the best one.

        This is the main method for evaluating LLM outputs. It scores each
        candidate across 12 dimensions using multi-judge ensemble and selects
        the best one using the specified selection method.

        Args:
            candidates: List of candidate specs to evaluate. Each candidate
                should have at least a "content" field. Minimum 2 candidates.
            selection_method: Selection method to use:
                - "hybrid": Combine scoring and RL (default)
                - "scoring_only": Use only multi-judge scoring
                - "rl_only": Use only RL policy
            request_id: Idempotency key. If not provided, a UUID is generated.
            description: Context about what the specs are for (max 2000 chars).

        Returns:
            SelectionResponse containing the selected candidate and all scores.

        Raises:
            ValidationError: If fewer than 2 candidates provided.
            ServerError: If the API encounters an error.

        Example:
            >>> response = await client.select(
            ...     candidates=[
            ...         {"content": "Output from GPT-4", "source_model": "gpt-4"},
            ...         {"content": "Output from Claude", "source_model": "claude-3"},
            ...     ],
            ...     selection_method="hybrid",
            ...     description="API specification for user endpoint",
            ... )
            >>> print(f"Selected: {response.selected.index}")
            >>> print(f"Score: {response.selected.composite_score}")
        """
        # Normalize candidates to dict format
        normalized_candidates = []
        for c in candidates:
            if isinstance(c, SpecInput):
                normalized_candidates.append(c.model_dump(exclude_none=True))
            else:
                normalized_candidates.append(c)

        # Generate request_id if not provided
        if request_id is None:
            request_id = str(uuid.uuid4())

        # Normalize selection_method
        if isinstance(selection_method, SelectionMethod):
            selection_method = selection_method.value

        payload = {
            "candidates": normalized_candidates,
            "selection_method": selection_method,
            "request_id": request_id,
        }
        if description is not None:
            payload["description"] = description

        response = await self._http.post(
            "/v1/specs",
            json=payload,
            idempotency_key=request_id,
        )

        return SelectionResponse.model_validate(response)

    async def submit_feedback(
        self,
        request_id: str,
        *,
        rating: float | None = None,
        comment: str | None = None,
        spec_id: str | None = None,
    ) -> str:
        """Submit feedback for a previous evaluation.

        Feedback is used to train the reinforcement learning policy,
        improving future selections based on human preferences.

        Args:
            request_id: The request_id from the original select() call.
            rating: Human rating from 1.0 (poor) to 5.0 (excellent).
            comment: Optional comment explaining the rating (max 2000 chars).
            spec_id: ID of the specific candidate being rated.

        Returns:
            Feedback ID for tracking.

        Raises:
            NotFoundError: If request_id doesn't exist.
            ValidationError: If rating is out of range.

        Example:
            >>> feedback_id = await client.submit_feedback(
            ...     request_id="abc-123",
            ...     rating=4.5,
            ...     comment="Good structure but missing error handling",
            ... )
        """
        payload: dict[str, Any] = {"request_id": request_id}
        if rating is not None:
            payload["rating"] = rating
        if comment is not None:
            payload["comment"] = comment
        if spec_id is not None:
            payload["spec_id"] = spec_id

        response = await self._http.post("/v1/specs/feedback", json=payload)
        return response["feedback_id"]

    async def get_policy_status(self) -> PolicyStatus:
        """Get the current RL policy status.

        Returns information about the current policy version, deployment
        stage, training statistics, and drift metrics.

        Returns:
            PolicyStatus with version, stage, and metrics.

        Example:
            >>> status = await client.get_policy_status()
            >>> print(f"Policy version: {status.version}")
            >>> print(f"Stage: {status.stage}")
            >>> print(f"Mean reward: {status.mean_reward:.3f}")
        """
        response = await self._http.get("/v1/policy/status")
        return PolicyStatus.model_validate(response)

    async def train_policy(self, n_steps: int | None = None) -> dict[str, Any]:
        """Trigger policy training.

        Starts a background training job for the RL policy using
        accumulated feedback data.

        Args:
            n_steps: Number of training steps (default: auto).

        Returns:
            Job information including job_id.

        Example:
            >>> job = await client.train_policy(n_steps=1000)
            >>> print(f"Training job started: {job['job_id']}")
        """
        payload: dict[str, Any] = {}
        if n_steps is not None:
            payload["n_steps"] = n_steps

        return await self._http.post("/v1/policy/train", json=payload)

    async def health(self) -> HealthResponse:
        """Check API health status.

        Returns:
            HealthResponse with status and version.

        Example:
            >>> health = await client.health()
            >>> print(f"Status: {health.status}")
            >>> print(f"Version: {health.version}")
        """
        response = await self._http.get("/v1/health")
        return HealthResponse.model_validate(response)

    async def ready(self) -> HealthResponse:
        """Check API readiness status.

        Returns:
            HealthResponse indicating if the API is ready to accept requests.
        """
        response = await self._http.get("/v1/health/ready")
        return HealthResponse.model_validate(response)

    # =========================================================================
    # Sync Wrappers
    # =========================================================================

    def select_sync(
        self,
        candidates: list[dict[str, Any] | SpecInput],
        **kwargs: Any,
    ) -> SelectionResponse:
        """Synchronous wrapper for select()."""
        return asyncio.run(self.select(candidates, **kwargs))

    def submit_feedback_sync(
        self,
        request_id: str,
        **kwargs: Any,
    ) -> str:
        """Synchronous wrapper for submit_feedback()."""
        return asyncio.run(self.submit_feedback(request_id, **kwargs))

    def get_policy_status_sync(self) -> PolicyStatus:
        """Synchronous wrapper for get_policy_status()."""
        return asyncio.run(self.get_policy_status())

    def train_policy_sync(self, n_steps: int | None = None) -> dict[str, Any]:
        """Synchronous wrapper for train_policy()."""
        return asyncio.run(self.train_policy(n_steps))

    def health_sync(self) -> HealthResponse:
        """Synchronous wrapper for health()."""
        return asyncio.run(self.health())

    def ready_sync(self) -> HealthResponse:
        """Synchronous wrapper for ready()."""
        return asyncio.run(self.ready())
