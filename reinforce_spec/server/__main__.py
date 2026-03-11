"""CLI entry point for ``reinforce-spec-server``."""

from __future__ import annotations

import argparse
import signal
import sys

from loguru import logger


def handle_sigterm(signum: int, frame: object) -> None:
    """Handle SIGTERM gracefully for Fargate task shutdown."""
    logger.info("Received SIGTERM (signal {}), initiating graceful shutdown", signum)
    sys.exit(0)


def main() -> None:
    """Run the ReinforceSpec API server."""
    # Register SIGTERM handler for graceful Fargate shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)

    parser = argparse.ArgumentParser(
        description="ReinforceSpec — RL-optimized enterprise spec server"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    parser.add_argument("--log-level", default="info", help="Log level")
    args = parser.parse_args()

    try:
        import uvicorn  # type: ignore[import-untyped]
    except ImportError:
        logger.error("uvicorn is required: pip install 'reinforce-spec[server]'")
        sys.exit(1)

    uvicorn.run(
        "reinforce_spec.server.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
