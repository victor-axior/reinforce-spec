package transport

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func TestDoSetsStandardHeaders(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Content-Type"); got != "application/json" {
			t.Errorf("Content-Type = %q, want application/json", got)
		}
		if got := r.Header.Get("Accept"); got != "application/json" {
			t.Errorf("Accept = %q, want application/json", got)
		}
		if got := r.Header.Get("User-Agent"); got != "test-agent/1.0" {
			t.Errorf("User-Agent = %q, want test-agent/1.0", got)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	c := New(Config{
		BaseURL:   server.URL,
		UserAgent: "test-agent/1.0",
	})

	var result map[string]string
	_, err := c.Do(context.Background(), "GET", "/test", nil, &result, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result["status"] != "ok" {
		t.Errorf("expected status ok, got %s", result["status"])
	}
}

func TestDoSetsAuthHeader(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer secret-key" {
			t.Errorf("Authorization = %q, want Bearer secret-key", got)
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	c := New(Config{BaseURL: server.URL, APIKey: "secret-key"})

	_, err := c.Do(context.Background(), "GET", "/test", nil, nil, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestDoSetsIdempotencyKeyOnPost(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Idempotency-Key"); got != "idem-123" {
			t.Errorf("Idempotency-Key = %q, want idem-123", got)
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	c := New(Config{BaseURL: server.URL})

	_, err := c.Do(context.Background(), "POST", "/test", map[string]string{"key": "val"}, nil, "idem-123")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestDoOmitsIdempotencyKeyOnGet(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Idempotency-Key"); got != "" {
			t.Errorf("Idempotency-Key should be empty for GET, got %q", got)
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	c := New(Config{BaseURL: server.URL})

	_, err := c.Do(context.Background(), "GET", "/test", nil, nil, "idem-123")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestDoCallsRequestHook(t *testing.T) {
	var hookCalled atomic.Bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	c := New(Config{
		BaseURL: server.URL,
		OnRequest: func(req *http.Request) {
			hookCalled.Store(true)
		},
	})

	_, err := c.Do(context.Background(), "GET", "/test", nil, nil, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !hookCalled.Load() {
		t.Error("request hook was not called")
	}
}

func TestDoCallsResponseHook(t *testing.T) {
	var hookStatus atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	c := New(Config{
		BaseURL: server.URL,
		OnResponse: func(resp *http.Response) {
			hookStatus.Store(int32(resp.StatusCode))
		},
	})

	_, err := c.Do(context.Background(), "GET", "/test", nil, nil, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if hookStatus.Load() != 200 {
		t.Errorf("response hook got status %d, want 200", hookStatus.Load())
	}
}

func TestDoReturnsResponseOnClientError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"detail": "bad input"})
	}))
	defer server.Close()

	c := New(Config{BaseURL: server.URL, MaxRetries: 0})

	resp, err := c.Do(context.Background(), "GET", "/test", nil, nil, "")
	if err != nil {
		t.Fatalf("expected no transport error, got: %v", err)
	}
	if resp == nil {
		t.Fatal("expected error response, got nil")
	}
	if resp.StatusCode != 400 {
		t.Errorf("expected status 400, got %d", resp.StatusCode)
	}
}

func TestDoRetriesOnServerError(t *testing.T) {
	var attempts atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := attempts.Add(1)
		if n < 3 {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"detail": "temporary"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	c := New(Config{
		BaseURL:       server.URL,
		MaxRetries:    3,
		RetryDelay:    10 * time.Millisecond,
		RetryMaxDelay: 50 * time.Millisecond,
	})

	var result map[string]string
	resp, err := c.Do(context.Background(), "GET", "/test", nil, &result, "")
	if err != nil {
		t.Fatalf("expected success after retry, got error: %v", err)
	}
	if resp != nil {
		t.Fatalf("expected nil response (success), got status %d", resp.StatusCode)
	}
	if result["status"] != "ok" {
		t.Errorf("expected ok, got %s", result["status"])
	}
	if got := attempts.Load(); got < 3 {
		t.Errorf("expected at least 3 attempts, got %d", got)
	}
}

func TestDoNoRetryOnClientError(t *testing.T) {
	var attempts atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts.Add(1)
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`{"detail": "bad request"}`))
	}))
	defer server.Close()

	c := New(Config{
		BaseURL:       server.URL,
		MaxRetries:    3,
		RetryDelay:    10 * time.Millisecond,
		RetryMaxDelay: 50 * time.Millisecond,
	})

	resp, err := c.Do(context.Background(), "GET", "/test", nil, nil, "")
	if err != nil {
		t.Fatalf("expected HTTP error response, got transport error: %v", err)
	}
	if resp == nil || resp.StatusCode != 400 {
		t.Fatal("expected 400 response")
	}
	if got := attempts.Load(); got != 1 {
		t.Errorf("expected exactly 1 attempt for client error, got %d", got)
	}
}

func TestDoRetriesOnRateLimit(t *testing.T) {
	var attempts atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := attempts.Add(1)
		if n < 2 {
			w.Header().Set("Retry-After", "0")
			w.WriteHeader(http.StatusTooManyRequests)
			w.Write([]byte(`{"detail": "rate limited"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	c := New(Config{
		BaseURL:       server.URL,
		MaxRetries:    3,
		RetryDelay:    10 * time.Millisecond,
		RetryMaxDelay: 50 * time.Millisecond,
	})

	var result map[string]string
	resp, err := c.Do(context.Background(), "GET", "/test", nil, &result, "")
	if err != nil {
		t.Fatalf("expected success, got error: %v", err)
	}
	if resp != nil {
		t.Fatalf("expected success, got status %d", resp.StatusCode)
	}
	if got := attempts.Load(); got < 2 {
		t.Errorf("expected at least 2 attempts, got %d", got)
	}
}

func TestDoContextCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(2 * time.Second)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	c := New(Config{
		BaseURL:    server.URL,
		MaxRetries: 0,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	_, err := c.Do(ctx, "GET", "/test", nil, nil, "")
	if err == nil {
		t.Fatal("expected error on context timeout, got nil")
	}
}

func TestDoMarshalsBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]string
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		if body["key"] != "value" {
			t.Errorf("expected key=value, got key=%s", body["key"])
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"received": "ok"})
	}))
	defer server.Close()

	c := New(Config{BaseURL: server.URL})

	var result map[string]string
	_, err := c.Do(context.Background(), "POST", "/test", map[string]string{"key": "value"}, &result, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result["received"] != "ok" {
		t.Errorf("expected received=ok, got %v", result)
	}
}

func TestCloseIdempotent(t *testing.T) {
	c := New(Config{BaseURL: "http://localhost"})
	c.Close()
	c.Close() // Should not panic
}
