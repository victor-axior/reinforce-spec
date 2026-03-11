package reinforcespec

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestClientSelect(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/v1/specs" {
			t.Errorf("expected /v1/specs, got %s", r.URL.Path)
		}

		response := apiSelectionResponse{
			RequestID: "test-123",
			Selected: apiCandidateSpec{
				Index:          0,
				Content:        "Test content",
				Format:         "text",
				SpecType:       "api_spec",
				CompositeScore: 4.0,
				DimensionScores: []apiDimensionScore{
					{Dimension: "Accuracy", Score: 4.0, Justification: "Good", Confidence: 0.9},
				},
				JudgeModels: []string{"claude-3"},
			},
			AllCandidates:       []apiCandidateSpec{},
			SelectionMethod:     "hybrid",
			SelectionConfidence: 0.85,
			ScoringSummary:      map[string]float64{"Accuracy": 4.0},
			LatencyMs:           150.0,
			Timestamp:           "2025-01-01T00:00:00Z",
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient(
		WithBaseURL(server.URL),
		WithAPIKey("test-key"),
	)

	response, err := client.Select(context.Background(), &SelectRequest{
		Candidates: []SpecInput{
			{Content: "First"},
			{Content: "Second"},
		},
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if response.RequestID != "test-123" {
		t.Errorf("expected request ID test-123, got %s", response.RequestID)
	}
	if response.Selected.Index != 0 {
		t.Errorf("expected selected index 0, got %d", response.Selected.Index)
	}
	if response.SelectionConfidence != 0.85 {
		t.Errorf("expected confidence 0.85, got %f", response.SelectionConfidence)
	}
}

func TestClientValidationError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"detail":  "At least 2 candidates required",
			"details": map[string]interface{}{"field": "candidates", "min": 2},
		})
	}))
	defer server.Close()

	client := NewClient(WithBaseURL(server.URL))

	_, err := client.Select(context.Background(), &SelectRequest{
		Candidates: []SpecInput{{Content: "Only one"}},
	})

	if err == nil {
		t.Fatal("expected error, got nil")
	}

	validationErr, ok := err.(*ValidationError)
	if !ok {
		t.Fatalf("expected ValidationError, got %T", err)
	}

	if validationErr.StatusCode != 400 {
		t.Errorf("expected status 400, got %d", validationErr.StatusCode)
	}
}

func TestClientRateLimitError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Retry-After", "30")
		w.Header().Set("X-RateLimit-Limit", "100")
		w.Header().Set("X-RateLimit-Remaining", "0")
		w.WriteHeader(http.StatusTooManyRequests)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"detail": "Rate limit exceeded",
		})
	}))
	defer server.Close()

	client := NewClient(
		WithBaseURL(server.URL),
		WithMaxRetries(0), // Disable retries for this test
	)

	_, err := client.Select(context.Background(), &SelectRequest{
		Candidates: []SpecInput{{Content: "A"}, {Content: "B"}},
	})

	if err == nil {
		t.Fatal("expected error, got nil")
	}

	rateLimitErr, ok := err.(*RateLimitError)
	if !ok {
		t.Fatalf("expected RateLimitError, got %T", err)
	}

	if rateLimitErr.StatusCode != 429 {
		t.Errorf("expected status 429, got %d", rateLimitErr.StatusCode)
	}
	if rateLimitErr.Limit != 100 {
		t.Errorf("expected limit 100, got %d", rateLimitErr.Limit)
	}
}

func TestClientSubmitFeedback(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/v1/specs/feedback" {
			t.Errorf("expected /v1/specs/feedback, got %s", r.URL.Path)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"feedback_id": "fb-123",
			"request_id":  "req-456",
			"received_at": "2025-01-01T00:00:00Z",
		})
	}))
	defer server.Close()

	client := NewClient(WithBaseURL(server.URL))

	rating := 4.5
	feedbackID, err := client.SubmitFeedback(context.Background(), &FeedbackRequest{
		RequestID: "req-456",
		Rating:    &rating,
		Comment:   "Good result",
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if feedbackID != "fb-123" {
		t.Errorf("expected feedback ID fb-123, got %s", feedbackID)
	}
}

func TestClientGetPolicyStatus(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("expected GET, got %s", r.Method)
		}
		if r.URL.Path != "/v1/policy/status" {
			t.Errorf("expected /v1/policy/status, got %s", r.URL.Path)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"version":           "v001",
			"stage":             "production",
			"training_episodes": 10000,
			"mean_reward":       0.75,
			"explore_rate":      0.1,
			"drift_psi":         0.05,
		})
	}))
	defer server.Close()

	client := NewClient(WithBaseURL(server.URL))

	status, err := client.GetPolicyStatus(context.Background())

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if status.Version != "v001" {
		t.Errorf("expected version v001, got %s", status.Version)
	}
	if status.Stage != PolicyStageProduction {
		t.Errorf("expected stage production, got %s", status.Stage)
	}
	if status.MeanReward != 0.75 {
		t.Errorf("expected mean reward 0.75, got %f", status.MeanReward)
	}
}

func TestClientHealth(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("expected GET, got %s", r.Method)
		}
		if r.URL.Path != "/v1/health" {
			t.Errorf("expected /v1/health, got %s", r.URL.Path)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":         "healthy",
			"version":        "1.0.0",
			"uptime_seconds": 3600.0,
		})
	}))
	defer server.Close()

	client := NewClient(WithBaseURL(server.URL))

	health, err := client.Health(context.Background())

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if health.Status != "healthy" {
		t.Errorf("expected status healthy, got %s", health.Status)
	}
	if health.Version != "1.0.0" {
		t.Errorf("expected version 1.0.0, got %s", health.Version)
	}
}

func TestNewClientFromEnvMissingURL(t *testing.T) {
	// Ensure env var is not set
	t.Setenv("REINFORCE_SPEC_BASE_URL", "")

	_, err := NewClientFromEnv()

	if err == nil {
		t.Fatal("expected error, got nil")
	}

	configErr, ok := err.(*ConfigurationError)
	if !ok {
		t.Fatalf("expected ConfigurationError, got %T", err)
	}

	if configErr.Message == "" {
		t.Error("expected non-empty error message")
	}
}

func TestNewClientFromEnvSuccess(t *testing.T) {
	t.Setenv("REINFORCE_SPEC_BASE_URL", "https://api.example.com")
	t.Setenv("REINFORCE_SPEC_API_KEY", "test-key")

	client, err := NewClientFromEnv()

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if client == nil {
		t.Fatal("expected client, got nil")
	}
}
