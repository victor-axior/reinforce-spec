// Package reinforcespectest provides testing utilities for the ReinforceSpec SDK.
//
// It includes a mock client, factory functions for test data, and helpers
// that simplify writing unit tests for code that depends on the SDK.
//
// # Mock Client
//
// MockClient implements reinforcespec.Selector and can be configured with
// canned responses:
//
//	mock := reinforcespectest.NewMockClient(
//	    reinforcespectest.WithSelectResponse(response),
//	)
//	result, err := mock.Select(ctx, req)
//
// # Factory Functions
//
// Factory functions create valid test data with sensible defaults:
//
//	spec := reinforcespectest.NewCandidateSpec()
//	response := reinforcespectest.NewSelectionResponse()
package reinforcespectest
