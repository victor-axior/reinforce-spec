"""Synchronous usage example for the ReinforceSpec SDK."""

from reinforce_spec_sdk import ReinforceSpecClient


def main() -> None:
    with ReinforceSpecClient.sync(
        base_url="https://api.reinforce-spec.dev",
        api_key="your-api-key",
    ) as client:
        # Evaluate candidates
        response = client.select_sync(
            candidates=[
                {"content": "Option A"},
                {"content": "Option B"},
            ],
        )
        print(f"Selected: {response.selected.index}")

        # Submit feedback
        feedback_id = client.submit_feedback_sync(
            request_id=response.request_id,
            rating=4.5,
            comment="Great result",
        )
        print(f"Feedback submitted: {feedback_id}")

        # Check policy
        status = client.get_policy_status_sync()
        print(f"Policy: {status.version} ({status.stage.value})")


if __name__ == "__main__":
    main()
