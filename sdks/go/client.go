package reinforcespec

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/reinforce-spec/sdk-go/internal/transport"
)

// Client is the ReinforceSpec API client.
type Client struct {
	transport *transport.Client
	timeout   time.Duration
}

// NewClient creates a new ReinforceSpec client with the given options.
func NewClient(opts ...ClientOption) *Client {
	cfg := defaultConfig()

	for _, opt := range opts {
		opt(cfg)
	}

	return &Client{
		transport: transport.New(transport.Config{
			BaseURL:       strings.TrimSuffix(cfg.baseURL, "/"),
			APIKey:        cfg.apiKey,
			Timeout:       cfg.timeout,
			MaxRetries:    cfg.maxRetries,
			RetryDelay:    cfg.retryDelay,
			RetryMaxDelay: cfg.retryMaxDelay,
			HTTPClient:    cfg.httpClient,
			UserAgent:     "reinforce-spec-sdk-go/" + Version,
			OnRequest:     cfg.onRequest,
			OnResponse:    cfg.onResponse,
		}),
		timeout: cfg.timeout,
	}
}

// Close releases resources held by the client.
// After calling Close, the client should not be used.
func (c *Client) Close() {
	if c.transport != nil {
		c.transport.Close()
	}
}

// NewClientFromEnv creates a client from environment variables.
//
// Environment variables:
//   - REINFORCE_SPEC_BASE_URL: Base URL of the API (required)
//   - REINFORCE_SPEC_API_KEY: API key for authentication (optional)
func NewClientFromEnv() (*Client, error) {
	baseURL := os.Getenv("REINFORCE_SPEC_BASE_URL")
	if baseURL == "" {
		return nil, &ConfigurationError{
			ReinforceSpecError: ReinforceSpecError{
				Message: "REINFORCE_SPEC_BASE_URL environment variable is required",
			},
		}
	}

	return NewClient(
		WithBaseURL(baseURL),
		WithAPIKey(os.Getenv("REINFORCE_SPEC_API_KEY")),
	), nil
}

// Select evaluates candidates and selects the best one.
//
// This is the main method for evaluating LLM outputs. It scores each
// candidate across 12 dimensions using multi-judge ensemble and selects
// the best one using the specified selection method.
func (c *Client) Select(ctx context.Context, req *SelectRequest) (*SelectionResponse, error) {
	requestID := req.RequestID
	if requestID == "" {
		requestID = uuid.New().String()
	}

	apiReq := apiSelectRequest{
		Candidates:      make([]apiSpecInput, len(req.Candidates)),
		SelectionMethod: string(req.SelectionMethod),
		RequestID:       requestID,
		Description:     req.Description,
	}

	if apiReq.SelectionMethod == "" {
		apiReq.SelectionMethod = string(SelectionMethodHybrid)
	}

	for i, cand := range req.Candidates {
		apiReq.Candidates[i] = apiSpecInput{
			Content:     cand.Content,
			SourceModel: cand.SourceModel,
			Metadata:    cand.Metadata,
		}
	}

	var apiResp apiSelectionResponse
	resp, err := c.transport.Do(ctx, "POST", "/v1/specs", apiReq, &apiResp, requestID)
	if err != nil {
		return nil, c.wrapTransportError(err)
	}
	if resp != nil {
		return nil, parseAPIError(resp)
	}

	return convertSelectionResponse(&apiResp), nil
}

// SubmitFeedback submits feedback for a previous evaluation.
//
// Feedback is used to train the reinforcement learning policy,
// improving future selections based on human preferences.
func (c *Client) SubmitFeedback(ctx context.Context, req *FeedbackRequest) (string, error) {
	apiReq := apiFeedbackRequest{
		RequestID: req.RequestID,
		Rating:    req.Rating,
		Comment:   req.Comment,
		SpecID:    req.SpecID,
	}

	var apiResp apiFeedbackResponse
	resp, err := c.transport.Do(ctx, "POST", "/v1/specs/feedback", apiReq, &apiResp, "")
	if err != nil {
		return "", c.wrapTransportError(err)
	}
	if resp != nil {
		return "", parseAPIError(resp)
	}

	return apiResp.FeedbackID, nil
}

// GetPolicyStatus gets the current RL policy status.
func (c *Client) GetPolicyStatus(ctx context.Context) (*PolicyStatus, error) {
	var apiResp apiPolicyStatus
	resp, err := c.transport.Do(ctx, "GET", "/v1/policy/status", nil, &apiResp, "")
	if err != nil {
		return nil, c.wrapTransportError(err)
	}
	if resp != nil {
		return nil, parseAPIError(resp)
	}

	return convertPolicyStatus(&apiResp), nil
}

// TrainPolicy triggers policy training.
func (c *Client) TrainPolicy(ctx context.Context, nSteps *int) (*TrainResponse, error) {
	apiReq := make(map[string]interface{})
	if nSteps != nil {
		apiReq["n_steps"] = *nSteps
	}

	var apiResp struct {
		JobID  string `json:"job_id"`
		Status string `json:"status"`
	}
	resp, err := c.transport.Do(ctx, "POST", "/v1/policy/train", apiReq, &apiResp, "")
	if err != nil {
		return nil, c.wrapTransportError(err)
	}
	if resp != nil {
		return nil, parseAPIError(resp)
	}

	return &TrainResponse{
		JobID:  apiResp.JobID,
		Status: apiResp.Status,
	}, nil
}

// Health checks API health status.
func (c *Client) Health(ctx context.Context) (*HealthResponse, error) {
	var apiResp apiHealthResponse
	resp, err := c.transport.Do(ctx, "GET", "/v1/health", nil, &apiResp, "")
	if err != nil {
		return nil, c.wrapTransportError(err)
	}
	if resp != nil {
		return nil, parseAPIError(resp)
	}

	return convertHealthResponse(&apiResp), nil
}

// Ready checks API readiness status.
func (c *Client) Ready(ctx context.Context) (*HealthResponse, error) {
	var apiResp apiHealthResponse
	resp, err := c.transport.Do(ctx, "GET", "/v1/health/ready", nil, &apiResp, "")
	if err != nil {
		return nil, c.wrapTransportError(err)
	}
	if resp != nil {
		return nil, parseAPIError(resp)
	}

	return convertHealthResponse(&apiResp), nil
}

// parseAPIError converts a transport error response into a typed SDK error.
func parseAPIError(resp *transport.Response) error {
	var errorBody struct {
		Detail  string                 `json:"detail"`
		Message string                 `json:"message"`
		Details map[string]interface{} `json:"details"`
	}

	if err := json.Unmarshal(resp.Body, &errorBody); err != nil {
		errorBody.Detail = string(resp.Body)
	}

	message := errorBody.Detail
	if message == "" {
		message = errorBody.Message
	}
	if message == "" {
		message = fmt.Sprintf("HTTP %d", resp.StatusCode)
	}

	details := errorBody.Details
	if details == nil {
		details = make(map[string]interface{})
	}

	// Extract rate limit info from headers
	if resp.StatusCode == 429 {
		if v := resp.Header.Get("Retry-After"); v != "" {
			if secs, err := strconv.ParseFloat(v, 64); err == nil {
				details["retry_after"] = secs
			}
		}
		if v := resp.Header.Get("X-RateLimit-Limit"); v != "" {
			if limit, err := strconv.Atoi(v); err == nil {
				details["limit"] = float64(limit)
			}
		}
		if v := resp.Header.Get("X-RateLimit-Remaining"); v != "" {
			if remaining, err := strconv.Atoi(v); err == nil {
				details["remaining"] = float64(remaining)
			}
		}
	}

	return errorFromResponse(resp.StatusCode, message, details)
}

// wrapTransportError converts a transport-level error into a typed SDK error.
func (c *Client) wrapTransportError(err error) error {
	if errors.Is(err, context.DeadlineExceeded) {
		return &TimeoutError{
			ReinforceSpecError: ReinforceSpecError{
				Message: fmt.Sprintf("request timed out after %v", c.timeout),
				Err:     err,
			},
			Timeout: c.timeout,
		}
	}
	if errors.Is(err, context.Canceled) {
		return err
	}
	return &NetworkError{
		ReinforceSpecError: ReinforceSpecError{
			Message: fmt.Sprintf("request failed: %v", err),
			Err:     err,
		},
	}
}
