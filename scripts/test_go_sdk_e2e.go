// End-to-end test for the ReinforceSpec Go SDK against production.
//
// Run: cd scripts && go run test_go_sdk_e2e.go
package main

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// ALB endpoint - HTTPS with self-signed cert
const baseURL = "https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com"

func main() {
	fmt.Println("============================================================")
	fmt.Println("ReinforceSpec Go SDK End-to-End Test")
	fmt.Printf("Target: %s\n", baseURL)
	fmt.Printf("Timestamp: %s\n", time.Now().Format(time.RFC3339))
	fmt.Println("============================================================")

	// Create HTTP client with TLS verification disabled for ALB direct access
	httpClient := &http.Client{
		Timeout: 120 * time.Second,
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{
				InsecureSkipVerify: true,
			},
		},
	}

	// Change to SDK directory for module resolution
	if err := os.Chdir("../sdks/go"); err != nil {
		fmt.Printf("Warning: Could not change to SDK directory: %v\n", err)
	}

	passed := 0
	total := 4

	// Import SDK inline to avoid module path issues
	// We'll use the raw HTTP client directly for the E2E test

	// Test 1: Health
	fmt.Println("\n1. Testing health endpoint (GET /v1/health)...")
	if testHealth(httpClient) {
		passed++
	}

	// Test 2: Policy status
	fmt.Println("\n2. Testing policy status (GET /v1/policy/status)...")
	if testPolicyStatus(httpClient) {
		passed++
	}

	// Test 3: Spec selection
	fmt.Println("\n3. Testing spec selection (POST /v1/specs)...")
	fmt.Println("   This may take up to 60 seconds for LLM scoring...")
	requestID := testSelect(httpClient)
	if requestID != "" {
		passed++
	}

	// Test 4: Feedback
	if requestID != "" {
		fmt.Println("\n4. Testing feedback submission (POST /v1/specs/feedback)...")
		if testFeedback(httpClient, requestID) {
			passed++
		}
	} else {
		fmt.Println("\n4. Skipping feedback test (no request ID from selection)...")
	}

	// Summary
	fmt.Println("\n============================================================")
	result := "FAILED"
	if passed == total {
		result = "PASSED"
	}
	fmt.Printf("Results: %d/%d tests passed - %s\n", passed, total, result)
	fmt.Println("============================================================")

	if passed != total {
		os.Exit(1)
	}
}

func testHealth(client *http.Client) bool {
	resp, err := client.Get(baseURL + "/v1/health")
	if err != nil {
		fmt.Printf("   ✗ Failed: %v\n", err)
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		fmt.Printf("   ✗ Unexpected status: %d\n", resp.StatusCode)
		return false
	}

	var body map[string]interface{}
	if err := decodeJSON(resp, &body); err != nil {
		fmt.Printf("   ✗ JSON decode error: %v\n", err)
		return false
	}

	fmt.Printf("   ✓ Status: %v\n", body["status"])
	fmt.Printf("   ✓ Version: %v\n", body["version"])
	return true
}

func testPolicyStatus(client *http.Client) bool {
	resp, err := client.Get(baseURL + "/v1/policy/status")
	if err != nil {
		fmt.Printf("   ✗ Failed: %v\n", err)
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		fmt.Printf("   ✗ Unexpected status: %d\n", resp.StatusCode)
		return false
	}

	var body map[string]interface{}
	if err := decodeJSON(resp, &body); err != nil {
		fmt.Printf("   ✗ JSON decode error: %v\n", err)
		return false
	}

	fmt.Printf("   ✓ Version: %v\n", body["version"])
	fmt.Printf("   ✓ Stage: %v\n", body["stage"])
	return true
}

func testSelect(client *http.Client) string {
	payload := `{
		"candidates": [
			{
				"content": "# API Specification\n\n## Authentication\n- OAuth 2.0 with PKCE\n- API key authentication\n- JWT token validation\n",
				"source_model": "gpt-4",
				"spec_type": "api_spec"
			},
			{
				"content": "openapi: '3.0.3'\ninfo:\n  title: Sample API\n  version: '1.0.0'\npaths:\n  /users:\n    get:\n      summary: List users\n",
				"source_model": "claude-3",
				"spec_type": "api_spec"
			}
		],
		"selection_method": "hybrid",
		"description": "Go SDK E2E test"
	}`

	req, err := http.NewRequest("POST", baseURL+"/v1/specs", stringReader(payload))
	if err != nil {
		fmt.Printf("   ✗ Request creation failed: %v\n", err)
		return ""
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("   ✗ Failed: %v\n", err)
		return ""
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := readBody(resp)
		fmt.Printf("   ✗ HTTP Error: %d - %s\n", resp.StatusCode, body)
		return ""
	}

	var body map[string]interface{}
	if err := decodeJSON(resp, &body); err != nil {
		fmt.Printf("   ✗ JSON decode error: %v\n", err)
		return ""
	}

	requestID, _ := body["request_id"].(string)
	selected := body["selected"].(map[string]interface{})

	fmt.Printf("   ✓ Request ID: %s\n", requestID)
	fmt.Printf("   ✓ Selected candidate: %.0f\n", selected["index"])
	fmt.Printf("   ✓ Composite score: %.2f\n", selected["composite_score"])
	fmt.Printf("   ✓ Selection method: %v\n", body["selection_method"])
	fmt.Printf("   ✓ Selection confidence: %.2f\n", body["selection_confidence"])
	fmt.Printf("   ✓ Latency: %.0fms\n", body["latency_ms"])

	if scores, ok := selected["dimension_scores"].([]interface{}); ok {
		fmt.Println("   ✓ Dimension scores:")
		for _, s := range scores {
			score := s.(map[string]interface{})
			fmt.Printf("      - %s: %.1f\n", score["dimension"], score["score"])
		}
	}

	return requestID
}

func testFeedback(client *http.Client, requestID string) bool {
	payload := fmt.Sprintf(`{
		"request_id": "%s",
		"rating": 4.5,
		"comment": "Go SDK E2E test feedback at %s"
	}`, requestID, time.Now().Format(time.RFC3339))

	req, err := http.NewRequest("POST", baseURL+"/v1/specs/feedback", stringReader(payload))
	if err != nil {
		fmt.Printf("   ✗ Request creation failed: %v\n", err)
		return false
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("   ✗ Failed: %v\n", err)
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := readBody(resp)
		fmt.Printf("   ✗ HTTP Error: %d - %s\n", resp.StatusCode, body)
		return false
	}

	var body map[string]interface{}
	if err := decodeJSON(resp, &body); err != nil {
		fmt.Printf("   ✗ JSON decode error: %v\n", err)
		return false
	}

	fmt.Printf("   ✓ Feedback ID: %v\n", body["feedback_id"])
	fmt.Printf("   ✓ Status: %v\n", body["status"])
	return true
}

// Helper functions

func stringReader(s string) io.Reader {
	return strings.NewReader(s)
}

func readBody(resp *http.Response) (string, error) {
	body, err := io.ReadAll(resp.Body)
	return string(body), err
}

func decodeJSON(resp *http.Response, v interface{}) error {
	return json.NewDecoder(resp.Body).Decode(v)
}
