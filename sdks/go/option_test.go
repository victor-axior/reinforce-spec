package reinforcespec

import (
	"net/http"
	"testing"
	"time"
)

func TestDefaultConfig(t *testing.T) {
	cfg := defaultConfig()

	if cfg.timeout != 30*time.Second {
		t.Errorf("expected default timeout 30s, got %v", cfg.timeout)
	}
	if cfg.maxRetries != 3 {
		t.Errorf("expected default maxRetries 3, got %d", cfg.maxRetries)
	}
	if cfg.retryDelay != time.Second {
		t.Errorf("expected default retryDelay 1s, got %v", cfg.retryDelay)
	}
	if cfg.retryMaxDelay != 30*time.Second {
		t.Errorf("expected default retryMaxDelay 30s, got %v", cfg.retryMaxDelay)
	}
	if cfg.baseURL != "" {
		t.Errorf("expected empty baseURL, got %q", cfg.baseURL)
	}
	if cfg.apiKey != "" {
		t.Errorf("expected empty apiKey, got %q", cfg.apiKey)
	}
}

func TestWithBaseURL(t *testing.T) {
	cfg := defaultConfig()
	WithBaseURL("https://api.example.com")(cfg)

	if cfg.baseURL != "https://api.example.com" {
		t.Errorf("expected baseURL https://api.example.com, got %q", cfg.baseURL)
	}
}

func TestWithAPIKey(t *testing.T) {
	cfg := defaultConfig()
	WithAPIKey("secret-key")(cfg)

	if cfg.apiKey != "secret-key" {
		t.Errorf("expected apiKey secret-key, got %q", cfg.apiKey)
	}
}

func TestWithTimeout(t *testing.T) {
	cfg := defaultConfig()
	WithTimeout(5 * time.Second)(cfg)

	if cfg.timeout != 5*time.Second {
		t.Errorf("expected timeout 5s, got %v", cfg.timeout)
	}
}

func TestWithMaxRetries(t *testing.T) {
	cfg := defaultConfig()
	WithMaxRetries(5)(cfg)

	if cfg.maxRetries != 5 {
		t.Errorf("expected maxRetries 5, got %d", cfg.maxRetries)
	}
}

func TestWithHTTPClient(t *testing.T) {
	cfg := defaultConfig()
	custom := &http.Client{Timeout: 10 * time.Second}
	WithHTTPClient(custom)(cfg)

	if cfg.httpClient != custom {
		t.Error("expected custom HTTP client to be set")
	}
}

func TestWithHooks(t *testing.T) {
	cfg := defaultConfig()

	reqHook := RequestHook(func(req *http.Request) {})
	respHook := ResponseHook(func(resp *http.Response) {})

	WithOnRequest(reqHook)(cfg)
	WithOnResponse(respHook)(cfg)

	if cfg.onRequest == nil {
		t.Error("expected onRequest hook to be set")
	}
	if cfg.onResponse == nil {
		t.Error("expected onResponse hook to be set")
	}
}
