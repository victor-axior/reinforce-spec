// Command feedback demonstrates the selection + feedback loop.
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	reinforcespec "github.com/reinforce-spec/sdk-go"
)

func main() {
	client := reinforcespec.NewClient(
		reinforcespec.WithBaseURL(envOrDefault("REINFORCE_SPEC_BASE_URL", "http://localhost:8000")),
		reinforcespec.WithAPIKey(os.Getenv("REINFORCE_SPEC_API_KEY")),
	)
	defer client.Close()

	ctx := context.Background()

	// Step 1: Select best candidate
	response, err := client.Select(ctx, &reinforcespec.SelectRequest{
		Candidates: []reinforcespec.SpecInput{
			{Content: "First output"},
			{Content: "Second output"},
		},
		SelectionMethod: reinforcespec.SelectionMethodHybrid,
	})
	if err != nil {
		log.Fatalf("Selection failed: %v", err)
	}

	fmt.Printf("Selected candidate %d (score: %.2f)\n",
		response.Selected.Index, response.Selected.CompositeScore)

	// Step 2: Submit human feedback
	rating := 4.5
	feedbackID, err := client.SubmitFeedback(ctx, &reinforcespec.FeedbackRequest{
		RequestID: response.RequestID,
		Rating:    &rating,
		Comment:   "Selected output was accurate and well-structured",
	})
	if err != nil {
		log.Fatalf("Feedback failed: %v", err)
	}

	fmt.Printf("Feedback submitted: %s\n", feedbackID)

	// Step 3: Check policy status
	status, err := client.GetPolicyStatus(ctx)
	if err != nil {
		log.Fatalf("Policy status failed: %v", err)
	}

	fmt.Printf("\nPolicy Status:\n")
	fmt.Printf("  Version:    %s\n", status.Version)
	fmt.Printf("  Stage:      %s\n", status.Stage)
	fmt.Printf("  Episodes:   %d\n", status.TrainingEpisodes)
	fmt.Printf("  Mean Reward: %.3f\n", status.MeanReward)
}

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
