package reinforcespec

import "context"

// Selector defines the interface for evaluating and selecting LLM outputs.
// Both Client and mock implementations satisfy this interface.
type Selector interface {
	// Select evaluates candidates and selects the best one.
	Select(ctx context.Context, req *SelectRequest) (*SelectionResponse, error)
	// SubmitFeedback submits human feedback for a previous evaluation.
	SubmitFeedback(ctx context.Context, req *FeedbackRequest) (string, error)
	// GetPolicyStatus returns the current RL policy status.
	GetPolicyStatus(ctx context.Context) (*PolicyStatus, error)
	// Health checks API health status.
	Health(ctx context.Context) (*HealthResponse, error)
	// Close releases resources held by the client.
	Close()
}

// Compile-time check that Client satisfies Selector.
var _ Selector = (*Client)(nil)
