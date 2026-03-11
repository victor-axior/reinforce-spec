package reinforcespectest

import (
	"context"
	"errors"
	"testing"

	reinforcespec "github.com/reinforce-spec/sdk-go"
)

func TestMockClientDefaultsReturnValidData(t *testing.T) {
	mock := NewMockClient()

	ctx := context.Background()

	resp, err := mock.Select(ctx, NewSelectRequest())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.RequestID == "" {
		t.Error("expected non-empty request ID")
	}

	fbID, err := mock.SubmitFeedback(ctx, NewFeedbackRequest("req-1"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if fbID == "" {
		t.Error("expected non-empty feedback ID")
	}

	status, err := mock.GetPolicyStatus(ctx)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if status.Version == "" {
		t.Error("expected non-empty version")
	}

	health, err := mock.Health(ctx)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if health.Status != "healthy" {
		t.Errorf("expected healthy, got %s", health.Status)
	}
}

func TestMockClientRecordsCalls(t *testing.T) {
	mock := NewMockClient()
	ctx := context.Background()

	_, _ = mock.Select(ctx, NewSelectRequest())
	_, _ = mock.Select(ctx, NewSelectRequest())

	if len(mock.SelectCalls) != 2 {
		t.Errorf("expected 2 select calls, got %d", len(mock.SelectCalls))
	}

	_, _ = mock.SubmitFeedback(ctx, NewFeedbackRequest("req-1"))
	if len(mock.FeedbackCalls) != 1 {
		t.Errorf("expected 1 feedback call, got %d", len(mock.FeedbackCalls))
	}
}

func TestMockClientWithSelectError(t *testing.T) {
	wantErr := errors.New("selection failed")
	mock := NewMockClient(WithSelectError(wantErr))

	_, err := mock.Select(context.Background(), NewSelectRequest())
	if !errors.Is(err, wantErr) {
		t.Errorf("expected %v, got %v", wantErr, err)
	}
}

func TestMockClientWithCustomResponse(t *testing.T) {
	custom := &reinforcespec.SelectionResponse{
		RequestID:           "custom-id",
		SelectionConfidence: 0.99,
	}
	mock := NewMockClient(WithSelectResponse(custom))

	resp, err := mock.Select(context.Background(), NewSelectRequest())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.RequestID != "custom-id" {
		t.Errorf("expected custom-id, got %s", resp.RequestID)
	}
	if resp.SelectionConfidence != 0.99 {
		t.Errorf("expected 0.99, got %f", resp.SelectionConfidence)
	}
}

func TestMockClientClose(t *testing.T) {
	mock := NewMockClient()

	if mock.Closed() {
		t.Error("expected not closed")
	}

	mock.Close()

	if !mock.Closed() {
		t.Error("expected closed after Close()")
	}
}

func TestFactoryNewSelectionResponse(t *testing.T) {
	resp := NewSelectionResponse()

	if resp.RequestID == "" {
		t.Error("expected non-empty request ID")
	}
	if len(resp.AllCandidates) < 2 {
		t.Error("expected at least 2 candidates")
	}
	if resp.SelectionConfidence <= 0 {
		t.Error("expected positive confidence")
	}
	if resp.Selected.CompositeScore <= 0 {
		t.Error("expected positive composite score")
	}
}

func TestFactoryNewCandidateSpec(t *testing.T) {
	spec := NewCandidateSpec()

	if spec.Content == "" {
		t.Error("expected non-empty content")
	}
	if len(spec.DimensionScores) == 0 {
		t.Error("expected dimension scores")
	}
	if spec.Format != reinforcespec.SpecFormatText {
		t.Errorf("expected text format, got %s", spec.Format)
	}
}

func TestFactoryNewPolicyStatus(t *testing.T) {
	status := NewPolicyStatus()

	if status.Version == "" {
		t.Error("expected non-empty version")
	}
	if status.Stage != reinforcespec.PolicyStageProduction {
		t.Errorf("expected production, got %s", status.Stage)
	}
	if status.LastTrained == nil {
		t.Error("expected non-nil LastTrained")
	}
}

func TestFactoryNewHealthResponse(t *testing.T) {
	health := NewHealthResponse()

	if health.Status != "healthy" {
		t.Errorf("expected healthy, got %s", health.Status)
	}
	if health.UptimeSeconds == nil {
		t.Error("expected non-nil uptime")
	}
}
