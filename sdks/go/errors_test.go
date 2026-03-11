package reinforcespec

import (
	"errors"
	"testing"
	"time"
)

func TestErrorHierarchy(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		sentinel error
	}{
		{"ValidationError", &ValidationError{ReinforceSpecError: ReinforceSpecError{Message: "bad"}}, ErrValidation},
		{"AuthenticationError", &AuthenticationError{ReinforceSpecError: ReinforceSpecError{Message: "unauthorized"}}, ErrAuthentication},
		{"AuthorizationError", &AuthorizationError{ReinforceSpecError: ReinforceSpecError{Message: "forbidden"}}, ErrAuthorization},
		{"NotFoundError", &NotFoundError{ReinforceSpecError: ReinforceSpecError{Message: "missing"}}, ErrNotFound},
		{"ConflictError", &ConflictError{ReinforceSpecError: ReinforceSpecError{Message: "conflict"}}, ErrConflict},
		{"RateLimitError", &RateLimitError{ReinforceSpecError: ReinforceSpecError{Message: "throttled"}}, ErrRateLimit},
		{"ServerError", &ServerError{ReinforceSpecError: ReinforceSpecError{Message: "internal"}}, ErrServer},
		{"NetworkError", &NetworkError{ReinforceSpecError: ReinforceSpecError{Message: "conn"}}, ErrNetwork},
		{"TimeoutError", &TimeoutError{ReinforceSpecError: ReinforceSpecError{Message: "timeout"}}, ErrTimeout},
		{"ConfigurationError", &ConfigurationError{ReinforceSpecError: ReinforceSpecError{Message: "config"}}, ErrConfiguration},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if !errors.Is(tt.err, tt.sentinel) {
				t.Errorf("%s should wrap %v", tt.name, tt.sentinel)
			}
		})
	}
}

func TestErrorFromResponse(t *testing.T) {
	tests := []struct {
		status   int
		expected string
	}{
		{400, "*reinforcespec.ValidationError"},
		{401, "*reinforcespec.AuthenticationError"},
		{403, "*reinforcespec.AuthorizationError"},
		{404, "*reinforcespec.NotFoundError"},
		{409, "*reinforcespec.ConflictError"},
		{429, "*reinforcespec.RateLimitError"},
		{500, "*reinforcespec.ServerError"},
		{502, "*reinforcespec.ServerError"},
		{503, "*reinforcespec.ServerError"},
		{504, "*reinforcespec.ServerError"},
	}

	for _, tt := range tests {
		t.Run(tt.expected, func(t *testing.T) {
			err := errorFromResponse(tt.status, "test", nil)
			if err == nil {
				t.Fatal("expected error, got nil")
			}
		})
	}
}

func TestErrorFromResponseRateLimitDetails(t *testing.T) {
	details := map[string]interface{}{
		"retry_after": float64(30),
		"limit":       float64(100),
		"remaining":   float64(0),
	}
	err := errorFromResponse(429, "rate limited", details)

	rle, ok := err.(*RateLimitError)
	if !ok {
		t.Fatalf("expected *RateLimitError, got %T", err)
	}
	if rle.RetryAfter != 30*time.Second {
		t.Errorf("expected retry after 30s, got %v", rle.RetryAfter)
	}
	if rle.Limit != 100 {
		t.Errorf("expected limit 100, got %d", rle.Limit)
	}
}

func TestReinforceSpecErrorFormat(t *testing.T) {
	err := &ReinforceSpecError{
		Message:    "test error",
		StatusCode: 500,
	}
	want := "[500] test error"
	if got := err.Error(); got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestReinforceSpecErrorFormatNoStatus(t *testing.T) {
	err := &ReinforceSpecError{Message: "test error"}
	if got := err.Error(); got != "test error" {
		t.Errorf("got %q, want %q", got, "test error")
	}
}

func TestValidationErrorFormat(t *testing.T) {
	err := &ValidationError{
		ReinforceSpecError: ReinforceSpecError{Message: "bad input"},
		Field:              "candidates",
	}
	got := err.Error()
	if got != "validation error: bad input (field: candidates)" {
		t.Errorf("got %q", got)
	}
}

func TestNotFoundErrorFormat(t *testing.T) {
	err := &NotFoundError{
		ReinforceSpecError: ReinforceSpecError{Message: "missing"},
		ResourceType:       "policy",
		ResourceID:         "v001",
	}
	got := err.Error()
	if got != "policy not found: v001" {
		t.Errorf("got %q", got)
	}
}
