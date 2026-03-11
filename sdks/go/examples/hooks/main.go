// Command hooks demonstrates request/response hooks for logging.
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	reinforcespec "github.com/reinforce-spec/sdk-go"
)

func main() {
	client := reinforcespec.NewClient(
		reinforcespec.WithBaseURL(envOrDefault("REINFORCE_SPEC_BASE_URL", "http://localhost:8000")),
		reinforcespec.WithAPIKey(os.Getenv("REINFORCE_SPEC_API_KEY")),
		reinforcespec.WithTimeout(60*time.Second),
		reinforcespec.WithMaxRetries(5),
		reinforcespec.WithOnRequest(func(req *http.Request) {
			log.Printf("-> %s %s", req.Method, req.URL.Path)
		}),
		reinforcespec.WithOnResponse(func(resp *http.Response) {
			log.Printf("<- %d %s (%s)", resp.StatusCode, resp.Request.URL.Path,
				resp.Header.Get("Content-Type"))
		}),
	)
	defer client.Close()

	response, err := client.Select(context.Background(), &reinforcespec.SelectRequest{
		Candidates: []reinforcespec.SpecInput{
			{Content: "Output A"},
			{Content: "Output B"},
		},
		SelectionMethod: reinforcespec.SelectionMethodHybrid,
	})
	if err != nil {
		log.Fatalf("Selection failed: %v", err)
	}

	fmt.Printf("Selected candidate %d with score %.2f\n",
		response.Selected.Index, response.Selected.CompositeScore)
}

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
