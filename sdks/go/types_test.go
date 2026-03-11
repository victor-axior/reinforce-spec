package reinforcespec

import (
	"testing"
	"time"
)

func TestSelectionMethodConstants(t *testing.T) {
	if SelectionMethodHybrid != "hybrid" {
		t.Errorf("expected hybrid, got %s", SelectionMethodHybrid)
	}
	if SelectionMethodScoringOnly != "scoring_only" {
		t.Errorf("expected scoring_only, got %s", SelectionMethodScoringOnly)
	}
	if SelectionMethodRLOnly != "rl_only" {
		t.Errorf("expected rl_only, got %s", SelectionMethodRLOnly)
	}
}

func TestPolicyStageConstants(t *testing.T) {
	stages := []PolicyStage{
		PolicyStageCandidate,
		PolicyStageShadow,
		PolicyStageCanary,
		PolicyStageProduction,
		PolicyStageArchived,
	}
	for _, s := range stages {
		if s == "" {
			t.Error("stage constant should not be empty")
		}
	}
}

// Ensure time.Time fields round-trip correctly
func TestTimeParsing(t *testing.T) {
	ts := "2025-06-15T10:30:00Z"
	parsed, err := time.Parse(time.RFC3339, ts)
	if err != nil {
		t.Fatalf("failed to parse timestamp: %v", err)
	}
	if parsed.Year() != 2025 || parsed.Month() != 6 || parsed.Day() != 15 {
		t.Errorf("unexpected parsed time: %v", parsed)
	}
}
