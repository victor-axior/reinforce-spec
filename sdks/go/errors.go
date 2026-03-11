package reinforcespec

import (
	"errors"
	"fmt"
	"time"
)

// Error types for the ReinforceSpec SDK.

var (
	// ErrValidation is returned when request validation fails.
	ErrValidation = errors.New("validation error")
	// ErrAuthentication is returned when authentication fails.
	ErrAuthentication = errors.New("authentication error")
	// ErrAuthorization is returned when authorization fails.
	ErrAuthorization = errors.New("authorization error")
	// ErrNotFound is returned when a resource is not found.
	ErrNotFound = errors.New("not found")
	// ErrConflict is returned when there's a resource conflict.
	ErrConflict = errors.New("conflict")
	// ErrRateLimit is returned when rate limit is exceeded.
	ErrRateLimit = errors.New("rate limit exceeded")
	// ErrServer is returned on server errors.
	ErrServer = errors.New("server error")
	// ErrNetwork is returned on network errors.
	ErrNetwork = errors.New("network error")
	// ErrTimeout is returned when request times out.
	ErrTimeout = errors.New("timeout")
	// ErrConfiguration is returned for configuration errors.
	ErrConfiguration = errors.New("configuration error")
)

// ReinforceSpecError is the base error type for all SDK errors.
type ReinforceSpecError struct {
	// Message is the human-readable error message.
	Message string
	// StatusCode is the HTTP status code if from API response.
	StatusCode int
	// Details contains structured error details from the API.
	Details map[string]interface{}
	// Err is the underlying error.
	Err error
}

func (e *ReinforceSpecError) Error() string {
	if e.StatusCode > 0 {
		return fmt.Sprintf("[%d] %s", e.StatusCode, e.Message)
	}
	return e.Message
}

func (e *ReinforceSpecError) Unwrap() error {
	return e.Err
}

// ValidationError is returned when request validation fails (400).
type ValidationError struct {
	ReinforceSpecError
	// Field is the field that failed validation.
	Field string
	// Value is the invalid value.
	Value interface{}
}

func (e *ValidationError) Error() string {
	if e.Field != "" {
		return fmt.Sprintf("validation error: %s (field: %s)", e.Message, e.Field)
	}
	return fmt.Sprintf("validation error: %s", e.Message)
}

func (e *ValidationError) Unwrap() error {
	return ErrValidation
}

// AuthenticationError is returned when authentication fails (401).
type AuthenticationError struct {
	ReinforceSpecError
}

func (e *AuthenticationError) Error() string {
	return fmt.Sprintf("authentication error: %s", e.Message)
}

func (e *AuthenticationError) Unwrap() error {
	return ErrAuthentication
}

// AuthorizationError is returned when authorization fails (403).
type AuthorizationError struct {
	ReinforceSpecError
}

func (e *AuthorizationError) Error() string {
	return fmt.Sprintf("authorization error: %s", e.Message)
}

func (e *AuthorizationError) Unwrap() error {
	return ErrAuthorization
}

// NotFoundError is returned when a resource is not found (404).
type NotFoundError struct {
	ReinforceSpecError
	// ResourceType is the type of resource that wasn't found.
	ResourceType string
	// ResourceID is the ID of the resource.
	ResourceID string
}

func (e *NotFoundError) Error() string {
	if e.ResourceType != "" && e.ResourceID != "" {
		return fmt.Sprintf("%s not found: %s", e.ResourceType, e.ResourceID)
	}
	return fmt.Sprintf("not found: %s", e.Message)
}

func (e *NotFoundError) Unwrap() error {
	return ErrNotFound
}

// ConflictError is returned when there's a resource conflict (409).
type ConflictError struct {
	ReinforceSpecError
}

func (e *ConflictError) Error() string {
	return fmt.Sprintf("conflict: %s", e.Message)
}

func (e *ConflictError) Unwrap() error {
	return ErrConflict
}

// RateLimitError is returned when rate limit is exceeded (429).
type RateLimitError struct {
	ReinforceSpecError
	// RetryAfter is when to retry the request.
	RetryAfter time.Duration
	// Limit is the rate limit that was exceeded.
	Limit int
	// Remaining is requests remaining (usually 0).
	Remaining int
	// ResetAt is when the limit resets.
	ResetAt time.Time
}

func (e *RateLimitError) Error() string {
	if e.RetryAfter > 0 {
		return fmt.Sprintf("rate limit exceeded, retry after %v", e.RetryAfter)
	}
	return fmt.Sprintf("rate limit exceeded: %s", e.Message)
}

func (e *RateLimitError) Unwrap() error {
	return ErrRateLimit
}

// ServerError is returned on server errors (5xx).
type ServerError struct {
	ReinforceSpecError
}

func (e *ServerError) Error() string {
	return fmt.Sprintf("server error [%d]: %s", e.StatusCode, e.Message)
}

func (e *ServerError) Unwrap() error {
	return ErrServer
}

// NetworkError is returned on network connectivity errors.
type NetworkError struct {
	ReinforceSpecError
}

func (e *NetworkError) Error() string {
	return fmt.Sprintf("network error: %s", e.Message)
}

func (e *NetworkError) Unwrap() error {
	return ErrNetwork
}

// TimeoutError is returned when request times out.
type TimeoutError struct {
	ReinforceSpecError
	// Timeout is the configured timeout duration.
	Timeout time.Duration
}

func (e *TimeoutError) Error() string {
	return fmt.Sprintf("request timed out after %v", e.Timeout)
}

func (e *TimeoutError) Unwrap() error {
	return ErrTimeout
}

// ConfigurationError is returned for configuration errors.
type ConfigurationError struct {
	ReinforceSpecError
}

func (e *ConfigurationError) Error() string {
	return fmt.Sprintf("configuration error: %s", e.Message)
}

func (e *ConfigurationError) Unwrap() error {
	return ErrConfiguration
}

// errorFromResponse creates the appropriate error from an API response.
func errorFromResponse(statusCode int, message string, details map[string]interface{}) error {
	base := ReinforceSpecError{
		Message:    message,
		StatusCode: statusCode,
		Details:    details,
	}

	switch statusCode {
	case 400:
		return &ValidationError{ReinforceSpecError: base}
	case 401:
		return &AuthenticationError{ReinforceSpecError: base}
	case 403:
		return &AuthorizationError{ReinforceSpecError: base}
	case 404:
		return &NotFoundError{ReinforceSpecError: base}
	case 409:
		return &ConflictError{ReinforceSpecError: base}
	case 429:
		err := &RateLimitError{ReinforceSpecError: base}
		if v, ok := details["retry_after"].(float64); ok {
			err.RetryAfter = time.Duration(v) * time.Second
		}
		if v, ok := details["limit"].(float64); ok {
			err.Limit = int(v)
		}
		if v, ok := details["remaining"].(float64); ok {
			err.Remaining = int(v)
		}
		return err
	case 500, 502, 503, 504:
		return &ServerError{ReinforceSpecError: base}
	default:
		return &base
	}
}
