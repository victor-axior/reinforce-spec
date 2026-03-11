"""Async OpenRouter client with circuit breaker, retry, and cost tracking.

This wraps the OpenAI Python SDK with:
- Circuit breaker (closed → open → half-open → closed)
- Exponential backoff + jitter via tenacity
- Request/response structured logging (no PII)
- Cost tracking from OpenRouter response metadata
- Model fallback chain
"""

from __future__ import annotations

import asyncio
import enum
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from reinforce_spec._exceptions import (
    CircuitBreakerOpenError,
    UpstreamError,
)
from reinforce_spec._exceptions import (
    RateLimitError as RSRateLimitError,
)

if TYPE_CHECKING:
    from reinforce_spec._internal._config import LLMConfig

# ── Circuit Breaker ───────────────────────────────────────────────────────────


class CircuitState(enum.StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Simple circuit breaker state machine.

    State transitions:
      CLOSED ──(threshold failures)──► OPEN ──(cooldown)──► HALF_OPEN ──(success)──► CLOSED
                                                                      ──(failure)──► OPEN
    """

    threshold: int = 5
    cooldown_seconds: float = 60.0

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_open(self) -> bool:
        if self._state == CircuitState.OPEN:
            # Check if cooldown has elapsed → transition to half-open
            if time.monotonic() - self._last_failure_time >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                return False
            return True
        return False

    @property
    def cooldown_remaining(self) -> float:
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        return max(0.0, self.cooldown_seconds - elapsed)

    async def record_success(self) -> None:
        """Record a successful call and reset the failure count."""
        async with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    async def record_failure(self) -> None:
        """Record a failed call and open the circuit if threshold is reached."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    (
                        "circuit_breaker_opened | "
                        "failure_count={failure_count} "
                        "cooldown_seconds={cooldown_seconds}"
                    ),
                    failure_count=self._failure_count,
                    cooldown_seconds=self.cooldown_seconds,
                )

    async def check(self) -> None:
        """Raise if circuit is open."""
        if self.is_open:
            raise CircuitBreakerOpenError(
                "Circuit breaker is open — upstream service is unhealthy",
                provider="openrouter",
                cooldown_remaining=self.cooldown_remaining,
            )


# ── Cost Tracker ──────────────────────────────────────────────────────────────


@dataclass
class LLMCallMetrics:
    """Metrics from a single LLM call."""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float | None = None
    status: str = "success"


# ── Client ────────────────────────────────────────────────────────────────────


class OpenRouterClient:
    """Production-grade async OpenRouter client.

    Features:
    - Circuit breaker with configurable threshold and cooldown
    - Retry with exponential backoff + jitter
    - Structured logging of every call (no content logged for PII safety)
    - Cost and token usage tracking
    - Model fallback chain
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = AsyncOpenAI(
            base_url=self.BASE_URL,
            api_key=config.openrouter_api_key,
            timeout=config.timeout_seconds,
            max_retries=0,  # We handle retries ourselves via tenacity
        )
        self._circuit = CircuitBreaker(
            threshold=5,
            cooldown_seconds=60.0,
        )
        self._total_cost_usd: float = 0.0
        self._total_calls: int = 0

    @property
    def judge_models(self) -> list[str]:
        return self._config.judge_models

    @property
    def circuit_state(self) -> CircuitState:
        return self._circuit.state

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost_usd

    @property
    def total_calls(self) -> int:
        return self._total_calls

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
        json_schema: dict[str, Any] | None = None,
        stop: list[str] | None = None,
    ) -> tuple[str, LLMCallMetrics]:
        """Send a chat completion request to OpenRouter.

        Parameters
        ----------
        messages : list[dict[str, str]]
            Chat messages in OpenAI format.
        model : str or None
            Model to use.  Falls back to the first judge model.
        temperature : float
            Sampling temperature.
        max_tokens : int
            Maximum tokens in the response.
        response_format : dict[str, Any] or None
            Response format specification.
        json_schema : dict[str, Any] or None
            JSON schema for structured output.
        stop : list[str] or None
            Stop sequences.

        Returns
        -------
        tuple[str, LLMCallMetrics]
            The response content and call metrics.

        Raises
        ------
        CircuitBreakerOpenError
            If the circuit breaker is open.
        UpstreamError
            If the request fails after all retries.

        """
        await self._circuit.check()

        model = model or self._config.judge_models[0]
        start_time = time.perf_counter()

        try:
            content, metrics = await self._complete_with_retry(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                json_schema=json_schema,
                stop=stop,
            )
            await self._circuit.record_success()
            metrics.latency_ms = (time.perf_counter() - start_time) * 1000
            self._total_calls += 1
            if metrics.cost_usd:
                self._total_cost_usd += metrics.cost_usd

            logger.info(
                (
                    "llm_call_success | "
                    "model={model} "
                    "prompt_tokens={prompt_tokens} "
                    "completion_tokens={completion_tokens} "
                    "latency_ms={latency_ms} "
                    "cost_usd={cost_usd}"
                ),
                model=model,
                prompt_tokens=metrics.prompt_tokens,
                completion_tokens=metrics.completion_tokens,
                latency_ms=round(metrics.latency_ms, 1),
                cost_usd=metrics.cost_usd,
            )
            return content, metrics

        except RetryError as e:
            await self._circuit.record_failure()
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "llm_call_exhausted_retries | model={model} latency_ms={latency_ms} error={error}",
                model=model,
                latency_ms=round(latency_ms, 1),
                error=str(e),
            )
            raise UpstreamError(
                f"OpenRouter request failed after {self._config.max_retries} retries: {e}",
                provider="openrouter",
            ) from e

    async def _complete_with_retry(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: dict[str, Any] | None,
        json_schema: dict[str, Any] | None,
        stop: list[str] | None,
    ) -> tuple[str, LLMCallMetrics]:
        """Inner completion with tenacity retry."""

        @retry(
            retry=retry_if_exception_type((APIConnectionError, APIStatusError)),
            stop=stop_after_attempt(self._config.max_retries + 1),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
            before_sleep=before_sleep_log(logger, "warning"),  # type: ignore[arg-type]
            reraise=True,
        )
        async def _call() -> tuple[str, LLMCallMetrics]:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format
            if json_schema:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": json_schema,
                }
            if stop:
                kwargs["stop"] = stop

            try:
                response = await self._client.chat.completions.create(**kwargs)
            except RateLimitError as e:
                retry_after = None
                if hasattr(e, "response") and e.response is not None:
                    retry_header = e.response.headers.get("retry-after")
                    if retry_header:
                        retry_after = float(retry_header)
                raise RSRateLimitError(
                    f"Rate limited by OpenRouter: {e}",
                    provider="openrouter",
                    status_code=429,
                    retry_after=retry_after,
                ) from e

            # Extract metrics
            usage = response.usage
            metrics = LLMCallMetrics(
                model=model,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            )

            content = response.choices[0].message.content or ""
            return content, metrics

        return await _call()

    async def complete_with_fallback(
        self,
        messages: list[dict[str, str]],
        *,
        models: list[str] | None = None,
        temperature: float = 0.8,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> tuple[str, LLMCallMetrics]:
        """Try models in sequence until one succeeds.

        Parameters
        ----------
        messages : list[dict[str, str]]
            Chat messages.
        models : list[str] or None
            Ordered list of models to try.  Falls back to
            ``config.fallback_models``.
        temperature : float
            Sampling temperature.
        max_tokens : int
            Maximum tokens in the response.
        response_format : dict[str, Any] or None
            Response format specification.
        json_schema : dict[str, Any] or None
            JSON schema for structured output.

        Returns
        -------
        tuple[str, LLMCallMetrics]
            Response content and metrics from the first successful model.

        Raises
        ------
        UpstreamError
            If all fallback models are exhausted.

        """
        models = models or self._config.fallback_models
        last_error: Exception | None = None

        for model in models:
            try:
                return await self.complete(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    json_schema=json_schema,
                )
            except (UpstreamError, CircuitBreakerOpenError) as e:
                last_error = e
                logger.warning(
                    (
                        "model_fallback | "
                        "failed_model={failed_model} "
                        "error={error} "
                        "remaining_models={remaining_models}"
                    ),
                    failed_model=model,
                    error=str(e),
                    remaining_models=len(models) - models.index(model) - 1,
                )
                continue

        raise UpstreamError(
            f"All fallback models exhausted: {last_error}",
            provider="openrouter",
        )

    async def complete_parallel(
        self,
        messages_list: list[list[dict[str, str]]],
        *,
        model: str | None = None,
        temperatures: list[float] | None = None,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> list[tuple[str, LLMCallMetrics] | Exception]:
        """Send multiple completion requests in parallel.

        Parameters
        ----------
        messages_list : list[list[dict[str, str]]]
            List of message lists, one per request.
        model : str or None
            Model to use for all requests.
        temperatures : list[float] or None
            Temperature per request.  If ``None``, uses ``0.8`` for all.
        max_tokens : int
            Maximum tokens in each response.
        response_format : dict[str, Any] or None
            Response format specification.
        json_schema : dict[str, Any] or None
            JSON schema for structured output.

        Returns
        -------
        list[tuple[str, LLMCallMetrics] | Exception]
            Results or exceptions, one per input.  Partial failures
            do not block successful results.

        """
        if temperatures is None:
            temperatures = [0.8] * len(messages_list)

        tasks = [
            self.complete(
                messages=msgs,
                model=model,
                temperature=temp,
                max_tokens=max_tokens,
                response_format=response_format,
                json_schema=json_schema,
            )
            for msgs, temp in zip(messages_list, temperatures, strict=True)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return list(results)  # type: ignore[arg-type]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()

    async def __aenter__(self) -> OpenRouterClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
