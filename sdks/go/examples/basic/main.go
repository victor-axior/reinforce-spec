// Command basic demonstrates the core selection workflow.
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

	// Evaluate two candidate outputs
	response, err := client.Select(context.Background(), &reinforcespec.SelectRequest{
		Candidates: []reinforcespec.SpecInput{
			{Content: "First LLM output for API spec", SourceModel: "gpt-4"},
			{Content: "Second LLM output for API spec", SourceModel: "claude-3"},
		},
		SelectionMethod: reinforcespec.SelectionMethodHybrid,
		Description:     "Compare API specification outputs",
	})
	if err != nil {
		log.Fatalf("Selection failed: %v", err)
	}

	fmt.Printf("Request ID:  %s\n", response.RequestID)
	fmt.Printf("Selected:    candidate %d\n", response.Selected.Index)
	fmt.Printf("Score:       %.2f\n", response.Selected.CompositeScore)
	fmt.Printf("Confidence:  %.2f\n", response.SelectionConfidence)
	fmt.Printf("Latency:     %.0fms\n", response.LatencyMs)

	fmt.Println("\nDimension Scores:")
	for _, s := range response.Selected.DimensionScores {
		fmt.Printf("  %-20s %.1f (confidence: %.0f%%)\n",
			s.Dimension, s.Score, s.Confidence*100)
	}
}

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
