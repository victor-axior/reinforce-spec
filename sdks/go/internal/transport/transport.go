// Package transport provides a low-level HTTP transport client with automatic
// retry, exponential backoff, and request/response hooks.
//
// This package is internal to the SDK and should not be imported directly.
package transport

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"math/rand"
	"net/http"
	"strconv"
	"strings"
	"time"
)

// Config holds transport configuration.
type Config struct {
	BaseURL       string
	APIKey        string
	Timeout       time.Duration
	MaxRetries    int
	RetryDelay    time.Duration
	RetryMaxDelay time.Duration
	HTTPClient    *http.Client
	UserAgent     string
	OnRequest     func(*http.Request)
	OnResponse    func(*http.Response)
}

// Response holds raw HTTP response data for non-success responses.
type Response struct {
	StatusCode int
	Body       []byte
	Header     http.Header
}

// Client is a low-level HTTP transport with automatic retry support.
type Client struct {
	baseURL       string
	apiKey        string
	timeout       time.Duration
	maxRetries    int
	retryDelay    time.Duration
	retryMaxDelay time.Duration
	client        *http.Client
	userAgent     string
	onRequest     func(*http.Request)
	onResponse    func(*http.Response)
}

// New creates a new transport Client from the given configuration.
func New(cfg Config) *Client {
	httpClient := cfg.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{Timeout: cfg.Timeout}
	}

	return &Client{
		baseURL:       strings.TrimSuffix(cfg.BaseURL, "/"),
		apiKey:        cfg.APIKey,
		timeout:       cfg.Timeout,
		maxRetries:    cfg.MaxRetries,
		retryDelay:    cfg.RetryDelay,
		retryMaxDelay: cfg.RetryMaxDelay,
		client:        httpClient,
		userAgent:     cfg.UserAgent,
		onRequest:     cfg.OnRequest,
		onResponse:    cfg.OnResponse,
	}
}

// Do executes an HTTP request with retry support.
//
// On success (2xx): unmarshals the response body into result (if non-nil)
// and returns (nil, nil).
//
// On HTTP error (4xx/5xx) after retries exhausted: returns (*Response, nil)
// containing the error response body and headers.
//
// On network failure after retries exhausted: returns (nil, error).
func (c *Client) Do(ctx context.Context, method, path string, body, result interface{}, idempotencyKey string) (*Response, error) {
	url := c.baseURL + path

	var lastResp *Response
	var lastErr error

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		resp, err := c.doOnce(ctx, method, url, body, result, idempotencyKey)
		if err != nil {
			lastErr = err
			lastResp = nil

			if !isRetryableError(err) || attempt >= c.maxRetries {
				return nil, lastErr
			}
		} else if resp != nil {
			// HTTP error response
			lastResp = resp
			lastErr = nil

			if !isRetryableStatus(resp.StatusCode) || attempt >= c.maxRetries {
				return lastResp, nil
			}
		} else {
			// Success
			return nil, nil
		}

		delay := c.getRetryDelay(attempt, lastResp)
		select {
		case <-ctx.Done():
			if lastResp != nil {
				return lastResp, nil
			}
			return nil, ctx.Err()
		case <-time.After(delay):
		}
	}

	if lastResp != nil {
		return lastResp, nil
	}
	return nil, lastErr
}

// Close releases resources held by the transport.
func (c *Client) Close() {
	if c.client != nil {
		c.client.CloseIdleConnections()
	}
}

func (c *Client) doOnce(ctx context.Context, method, url string, body, result interface{}, idempotencyKey string) (*Response, error) {
	var bodyReader io.Reader
	if body != nil {
		jsonBody, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(jsonBody)
	}

	req, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	if c.userAgent != "" {
		req.Header.Set("User-Agent", c.userAgent)
	}
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
	if idempotencyKey != "" && (method == http.MethodPost || method == http.MethodPut || method == http.MethodPatch) {
		req.Header.Set("Idempotency-Key", idempotencyKey)
	}

	// Call request hook
	if c.onRequest != nil {
		c.onRequest(req)
	}

	// Execute request
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	// Call response hook
	if c.onResponse != nil {
		c.onResponse(resp)
	}

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	// Success: unmarshal into result
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		if result != nil && len(respBody) > 0 {
			if err := json.Unmarshal(respBody, result); err != nil {
				return nil, fmt.Errorf("failed to unmarshal response: %w", err)
			}
		}
		return nil, nil
	}

	// Error response: return raw data for caller to interpret
	return &Response{
		StatusCode: resp.StatusCode,
		Body:       respBody,
		Header:     resp.Header,
	}, nil
}

func isRetryableStatus(code int) bool {
	return code == 429 || code >= 500
}

func isRetryableError(err error) bool {
	// Context cancellation is not retryable
	if err == context.Canceled {
		return false
	}
	// All other errors (network, http.Client timeout) are retryable
	return true
}

func (c *Client) getRetryDelay(attempt int, lastResp *Response) time.Duration {
	// Check for Retry-After header on rate limit responses
	if lastResp != nil && lastResp.StatusCode == 429 {
		if v := lastResp.Header.Get("Retry-After"); v != "" {
			if secs, err := strconv.ParseFloat(v, 64); err == nil {
				return time.Duration(secs * float64(time.Second))
			}
		}
	}

	// Exponential backoff with jitter
	delay := float64(c.retryDelay) * math.Pow(2, float64(attempt))
	if delay > float64(c.retryMaxDelay) {
		delay = float64(c.retryMaxDelay)
	}

	jitter := rand.Float64() * float64(time.Second)
	return time.Duration(delay + jitter)
}
