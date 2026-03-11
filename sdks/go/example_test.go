package reinforcespec_test

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"time"

	reinforcespec "github.com/reinforce-spec/sdk-go"
)

func ExampleNewClient() {
	client := reinforcespec.NewClient(
		reinforcespec.WithBaseURL("https://api.reinforce-spec.dev"),
		reinforcespec.WithAPIKey("your-api-key"),
	)
	defer client.Close()

	response, err := client.Select(context.Background(), &reinforcespec.SelectRequest{
		Candidates: []reinforcespec.SpecInput{
			{Content: "First LLM output", SourceModel: "gpt-4"},
			{Content: "Second LLM output", SourceModel: "claude-3"},
		},
		SelectionMethod: reinforcespec.SelectionMethodHybrid,
		Description:     "Compare outputs for quality",
	})
	if err != nil {
		log.Fatal(err)
	}

	fmt.Printf("Selected candidate: %d\n", response.Selected.Index)
	fmt.Printf("Score: %.2f\n", response.Selected.CompositeScore)
}

func ExampleNewClient_withOptions() {
	client := reinforcespec.NewClient(
		reinforcespec.WithBaseURL("https://api.reinforce-spec.dev"),
		reinforcespec.WithAPIKey("your-api-key"),
		reinforcespec.WithTimeout(60*time.Second),
		reinforcespec.WithMaxRetries(5),
		reinforcespec.WithOnRequest(func(req *http.Request) {
			log.Printf("-> %s %s", req.Method, req.URL)
		}),
		reinforcespec.WithOnResponse(func(resp *http.Response) {
			log.Printf("<- %d %s", resp.StatusCode, resp.Request.URL)
		}),
	)
	defer client.Close()

	_ = client // Use client...
}

func ExampleClient_SubmitFeedback() {
	client := reinforcespec.NewClient(
		reinforcespec.WithBaseURL("https://api.reinforce-spec.dev"),
		reinforcespec.WithAPIKey("your-api-key"),
	)
	defer client.Close()

	rating := 4.5
	feedbackID, err := client.SubmitFeedback(context.Background(), &reinforcespec.FeedbackRequest{
		RequestID: "request-123",
		Rating:    &rating,
		Comment:   "Good result",
	})
	if err != nil {
		log.Fatal(err)
	}

	fmt.Printf("Feedback submitted: %s\n", feedbackID)
}
