package reinforcespec

import (
	"net/http"
	"time"
)

// RequestHook is called before each HTTP request.
type RequestHook func(req *http.Request)

// ResponseHook is called after each HTTP response.
type ResponseHook func(resp *http.Response)

// ClientOption configures a Client.
type ClientOption func(*clientConfig)

type clientConfig struct {
	baseURL       string
	apiKey        string
	timeout       time.Duration
	maxRetries    int
	retryDelay    time.Duration
	retryMaxDelay time.Duration
	httpClient    *http.Client
	onRequest     RequestHook
	onResponse    ResponseHook
}

func defaultConfig() *clientConfig {
	return &clientConfig{
		timeout:       30 * time.Second,
		maxRetries:    3,
		retryDelay:    time.Second,
		retryMaxDelay: 30 * time.Second,
	}
}

// WithBaseURL sets the base URL for the API.
func WithBaseURL(url string) ClientOption {
	return func(c *clientConfig) {
		c.baseURL = url
	}
}

// WithAPIKey sets the API key for authentication.
func WithAPIKey(key string) ClientOption {
	return func(c *clientConfig) {
		c.apiKey = key
	}
}

// WithTimeout sets the request timeout.
func WithTimeout(timeout time.Duration) ClientOption {
	return func(c *clientConfig) {
		c.timeout = timeout
	}
}

// WithMaxRetries sets the maximum number of retry attempts.
func WithMaxRetries(retries int) ClientOption {
	return func(c *clientConfig) {
		c.maxRetries = retries
	}
}

// WithRetryDelay sets the initial delay between retries.
func WithRetryDelay(delay time.Duration) ClientOption {
	return func(c *clientConfig) {
		c.retryDelay = delay
	}
}

// WithRetryMaxDelay sets the maximum delay between retries.
func WithRetryMaxDelay(delay time.Duration) ClientOption {
	return func(c *clientConfig) {
		c.retryMaxDelay = delay
	}
}

// WithHTTPClient sets a custom HTTP client.
func WithHTTPClient(client *http.Client) ClientOption {
	return func(c *clientConfig) {
		c.httpClient = client
	}
}

// WithOnRequest sets a hook called before each request.
func WithOnRequest(hook RequestHook) ClientOption {
	return func(c *clientConfig) {
		c.onRequest = hook
	}
}

// WithOnResponse sets a hook called after each response.
func WithOnResponse(hook ResponseHook) ClientOption {
	return func(c *clientConfig) {
		c.onResponse = hook
	}
}
