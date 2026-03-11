package reinforcespectest

import (
	"time"

	reinforcespec "github.com/reinforce-spec/sdk-go"
)

// NewSpecInput creates a SpecInput with sensible defaults.
func NewSpecInput(content string) reinforcespec.SpecInput {
	return reinforcespec.SpecInput{
		Content:     content,
		SourceModel: "gpt-4",
	}
}

// NewSelectRequest creates a SelectRequest with two candidates.
func NewSelectRequest() *reinforcespec.SelectRequest {
	return &reinforcespec.SelectRequest{
		Candidates: []reinforcespec.SpecInput{
			NewSpecInput("First candidate output"),
			NewSpecInput("Second candidate output"),
		},
		SelectionMethod: reinforcespec.SelectionMethodHybrid,
		Description:     "Test evaluation",
	}
}

// NewDimensionScore creates a DimensionScore with reasonable values.
func NewDimensionScore(dimension string, score float64) reinforcespec.DimensionScore {
	return reinforcespec.DimensionScore{
		Dimension:     dimension,
		Score:         score,
		Justification: "Good quality for " + dimension,
		Confidence:    0.9,
	}
}

// NewCandidateSpec creates a CandidateSpec with all fields populated.
func NewCandidateSpec() reinforcespec.CandidateSpec {
	return reinforcespec.CandidateSpec{
		Index:       0,
		Content:     "Selected spec content",
		Format:      reinforcespec.SpecFormatText,
		SpecType:    "api_spec",
		SourceModel: "gpt-4",
		DimensionScores: []reinforcespec.DimensionScore{
			NewDimensionScore("Accuracy", 4.2),
			NewDimensionScore("Completeness", 3.8),
			NewDimensionScore("Clarity", 4.5),
		},
		CompositeScore: 4.17,
		JudgeModels:    []string{"claude-3", "gpt-4"},
	}
}

// NewSelectionResponse creates a complete SelectionResponse.
func NewSelectionResponse() *reinforcespec.SelectionResponse {
	selected := NewCandidateSpec()
	runner := NewCandidateSpec()
	runner.Index = 1
	runner.Content = "Runner-up spec content"
	runner.CompositeScore = 3.8

	return &reinforcespec.SelectionResponse{
		RequestID:           "test-request-id",
		Selected:            selected,
		AllCandidates:       []reinforcespec.CandidateSpec{selected, runner},
		SelectionMethod:     reinforcespec.SelectionMethodHybrid,
		SelectionConfidence: 0.85,
		ScoringSummary: map[string]float64{
			"Accuracy":     4.2,
			"Completeness": 3.8,
			"Clarity":      4.5,
		},
		LatencyMs: 150.0,
		Timestamp: time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC),
	}
}

// NewFeedbackRequest creates a FeedbackRequest with defaults.
func NewFeedbackRequest(requestID string) *reinforcespec.FeedbackRequest {
	rating := 4.5
	return &reinforcespec.FeedbackRequest{
		RequestID: requestID,
		Rating:    &rating,
		Comment:   "Good selection",
	}
}

// NewPolicyStatus creates a PolicyStatus with production values.
func NewPolicyStatus() *reinforcespec.PolicyStatus {
	lastTrained := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)
	return &reinforcespec.PolicyStatus{
		Version:          "v001",
		Stage:            reinforcespec.PolicyStageProduction,
		TrainingEpisodes: 10000,
		MeanReward:       0.75,
		ExploreRate:      0.1,
		LastTrained:      &lastTrained,
	}
}

// NewHealthResponse creates a healthy HealthResponse.
func NewHealthResponse() *reinforcespec.HealthResponse {
	uptime := 3600.0
	return &reinforcespec.HealthResponse{
		Status:        "healthy",
		Version:       "1.0.0",
		UptimeSeconds: &uptime,
	}
}
