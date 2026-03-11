package reinforcespectest

import (
	"context"

	reinforcespec "github.com/reinforce-spec/sdk-go"
)

// MockOption configures a MockClient.
type MockOption func(*MockClient)

// MockClient is a test double for reinforcespec.Client.
// It implements reinforcespec.Selector and returns canned responses.
type MockClient struct {
	selectResponse *reinforcespec.SelectionResponse
	selectError    error
	feedbackID     string
	feedbackError  error
	policyStatus   *reinforcespec.PolicyStatus
	policyError    error
	healthResponse *reinforcespec.HealthResponse
	healthError    error
	closed         bool

	// SelectCalls records arguments to Select for assertions.
	SelectCalls []SelectCall
	// FeedbackCalls records arguments to SubmitFeedback for assertions.
	FeedbackCalls []FeedbackCall
}

// SelectCall records a single call to Select.
type SelectCall struct {
	Ctx context.Context
	Req *reinforcespec.SelectRequest
}

// FeedbackCall records a single call to SubmitFeedback.
type FeedbackCall struct {
	Ctx context.Context
	Req *reinforcespec.FeedbackRequest
}

// Compile-time check that MockClient satisfies Selector.
var _ reinforcespec.Selector = (*MockClient)(nil)

// NewMockClient creates a MockClient with the given options.
// Without options, all methods return zero values and nil errors.
func NewMockClient(opts ...MockOption) *MockClient {
	m := &MockClient{
		selectResponse: NewSelectionResponse(),
		feedbackID:     "mock-feedback-id",
		policyStatus:   NewPolicyStatus(),
		healthResponse: NewHealthResponse(),
	}
	for _, opt := range opts {
		opt(m)
	}
	return m
}

// WithSelectResponse configures the response returned by Select.
func WithSelectResponse(resp *reinforcespec.SelectionResponse) MockOption {
	return func(m *MockClient) {
		m.selectResponse = resp
	}
}

// WithSelectError configures Select to return an error.
func WithSelectError(err error) MockOption {
	return func(m *MockClient) {
		m.selectError = err
	}
}

// WithFeedbackID configures the feedback ID returned by SubmitFeedback.
func WithFeedbackID(id string) MockOption {
	return func(m *MockClient) {
		m.feedbackID = id
	}
}

// WithFeedbackError configures SubmitFeedback to return an error.
func WithFeedbackError(err error) MockOption {
	return func(m *MockClient) {
		m.feedbackError = err
	}
}

// WithPolicyStatus configures the response returned by GetPolicyStatus.
func WithPolicyStatus(status *reinforcespec.PolicyStatus) MockOption {
	return func(m *MockClient) {
		m.policyStatus = status
	}
}

// WithPolicyError configures GetPolicyStatus to return an error.
func WithPolicyError(err error) MockOption {
	return func(m *MockClient) {
		m.policyError = err
	}
}

// WithHealthResponse configures the response returned by Health.
func WithHealthResponse(resp *reinforcespec.HealthResponse) MockOption {
	return func(m *MockClient) {
		m.healthResponse = resp
	}
}

// WithHealthError configures Health to return an error.
func WithHealthError(err error) MockOption {
	return func(m *MockClient) {
		m.healthError = err
	}
}

// Select records the call and returns the configured response.
func (m *MockClient) Select(ctx context.Context, req *reinforcespec.SelectRequest) (*reinforcespec.SelectionResponse, error) {
	m.SelectCalls = append(m.SelectCalls, SelectCall{Ctx: ctx, Req: req})
	if m.selectError != nil {
		return nil, m.selectError
	}
	return m.selectResponse, nil
}

// SubmitFeedback records the call and returns the configured response.
func (m *MockClient) SubmitFeedback(ctx context.Context, req *reinforcespec.FeedbackRequest) (string, error) {
	m.FeedbackCalls = append(m.FeedbackCalls, FeedbackCall{Ctx: ctx, Req: req})
	if m.feedbackError != nil {
		return "", m.feedbackError
	}
	return m.feedbackID, nil
}

// GetPolicyStatus returns the configured response.
func (m *MockClient) GetPolicyStatus(_ context.Context) (*reinforcespec.PolicyStatus, error) {
	if m.policyError != nil {
		return nil, m.policyError
	}
	return m.policyStatus, nil
}

// Health returns the configured response.
func (m *MockClient) Health(_ context.Context) (*reinforcespec.HealthResponse, error) {
	if m.healthError != nil {
		return nil, m.healthError
	}
	return m.healthResponse, nil
}

// Close marks the mock as closed.
func (m *MockClient) Close() {
	m.closed = true
}

// Closed returns whether Close has been called.
func (m *MockClient) Closed() bool {
	return m.closed
}
