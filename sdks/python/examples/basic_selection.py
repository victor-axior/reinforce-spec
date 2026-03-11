"""Basic selection example using the ReinforceSpec SDK."""

import asyncio

from reinforce_spec_sdk import ReinforceSpecClient, SelectionMethod


async def main() -> None:
    async with ReinforceSpecClient(
        base_url="https://api.reinforce-spec.dev",
        api_key="your-api-key",
    ) as client:
        response = await client.select(
            candidates=[
                {"content": "First LLM output", "source_model": "gpt-4"},
                {"content": "Second LLM output", "source_model": "claude-3"},
            ],
            selection_method=SelectionMethod.HYBRID,
            description="Compare LLM outputs for quality",
        )

        print(f"Selected candidate: {response.selected.index}")
        print(f"Composite score: {response.selected.composite_score:.2f}")
        print(f"Confidence: {response.selection_confidence:.2f}")

        for score in response.selected.dimension_scores:
            print(f"  {score.dimension}: {score.score:.1f} ({score.confidence:.0%})")


if __name__ == "__main__":
    asyncio.run(main())
