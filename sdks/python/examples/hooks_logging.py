"""Example using request/response hooks for logging."""

import asyncio
import logging
import time

import httpx

from reinforce_spec_sdk import ReinforceSpecClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_request(request: httpx.Request) -> None:
    logger.info("-> %s %s", request.method, request.url)


def log_response(response: httpx.Response) -> None:
    logger.info("<- %d %s (%.0fms)", response.status_code, response.url, response.elapsed.total_seconds() * 1000 if response.elapsed else 0)


async def main() -> None:
    client = ReinforceSpecClient(
        base_url="https://api.reinforce-spec.dev",
        api_key="your-api-key",
        on_request=log_request,
        on_response=log_response,
    )

    async with client:
        health = await client.health()
        logger.info("API status: %s (v%s)", health.status, health.version)


if __name__ == "__main__":
    asyncio.run(main())
