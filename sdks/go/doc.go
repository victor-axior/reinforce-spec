// Package reinforcespec provides a Go SDK for the ReinforceSpec API.
//
// ReinforceSpec evaluates and selects the best LLM output using
// multi-judge scoring and reinforcement learning.
//
// # Quick Start
//
//	client := reinforcespec.NewClient(
//	    reinforcespec.WithBaseURL("https://api.reinforce-spec.dev"),
//	    reinforcespec.WithAPIKey("your-api-key"),
//	)
//	defer client.Close()
//
//	response, err := client.Select(ctx, &reinforcespec.SelectRequest{
//	    Candidates: []reinforcespec.SpecInput{
//	        {Content: "First output"},
//	        {Content: "Second output"},
//	    },
//	})
//	if err != nil {
//	    log.Fatal(err)
//	}
//	fmt.Printf("Selected: %d (score: %.2f)\n",
//	    response.Selected.Index, response.Selected.CompositeScore)
//
// # Error Handling
//
// All errors returned by the client are typed. Use errors.Is or errors.As
// to check for specific error conditions:
//
//	_, err := client.Select(ctx, req)
//	if errors.Is(err, reinforcespec.ErrRateLimit) {
//	    // Handle rate limiting
//	}
//
//	var validationErr *reinforcespec.ValidationError
//	if errors.As(err, &validationErr) {
//	    fmt.Printf("Field: %s\n", validationErr.Field)
//	}
//
// # Configuration
//
// Use functional options to configure the client:
//
//	client := reinforcespec.NewClient(
//	    reinforcespec.WithBaseURL("https://api.reinforce-spec.dev"),
//	    reinforcespec.WithAPIKey("your-api-key"),
//	    reinforcespec.WithTimeout(60 * time.Second),
//	    reinforcespec.WithMaxRetries(5),
//	    reinforcespec.WithHTTPClient(customHTTPClient),
//	)
//
// # Testing
//
// For unit testing, use the reinforcespectest sub-package which provides
// a MockClient implementing the Selector interface:
//
//	import "github.com/reinforce-spec/sdk-go/reinforcespectest"
//
//	mock := reinforcespectest.NewMockClient()
//	// Use mock wherever reinforcespec.Selector is accepted
package reinforcespec
