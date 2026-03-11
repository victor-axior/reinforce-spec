"""
ReinforceSpec Python SDK

Official Python SDK for the ReinforceSpec API - LLM output evaluation
and selection using multi-judge scoring and reinforcement learning.

Example:
    >>> import asyncio
    >>> from reinforce_spec_sdk import ReinforceSpecClient
    >>>
    >>> async def main():
    ...     async with ReinforceSpecClient.from_env() as client:
    ...         response = await client.select(
    ...             candidates=[
    ...                 {"content": "First output"},
    ...                 {"content": "Second output"},
    ...             ]
    ...         )
    ...         print(f"Selected: {response.selected.index}")
    ...
    >>> asyncio.run(main())
"""

from reinforce_spec_sdk._http import PoolLimits, TimeoutConfig
from reinforce_spec_sdk.client import ReinforceSpecClient
from reinforce_spec_sdk.exceptions import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
    ReinforceSpecError,
    ServerError,
    TimeoutError,
    ValidationError,
)
from reinforce_spec_sdk.types import (
    CandidateSpec,
    DimensionScore,
    HealthResponse,
    PolicyStage,
    PolicyStatus,
    SelectionMethod,
    SelectionResponse,
    SpecFormat,
    SpecInput,
)

__version__ = "1.0.0"

__all__ = [
    # Client
    "ReinforceSpecClient",
    # Configuration
    "TimeoutConfig",
    "PoolLimits",
    # Types
    "SelectionMethod",
    "SpecFormat",
    "PolicyStage",
    "SpecInput",
    "SelectionResponse",
    "CandidateSpec",
    "DimensionScore",
    "PolicyStatus",
    "HealthResponse",
    # Exceptions
    "ReinforceSpecError",
    "ValidationError",
    "AuthenticationError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    "TimeoutError",
]
