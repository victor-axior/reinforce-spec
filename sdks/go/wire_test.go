package reinforcespec

import "testing"

func TestConvertCandidateSpec(t *testing.T) {
	api := &apiCandidateSpec{
		Index:       0,
		Content:     "test",
		Format:      "text",
		SpecType:    "api_spec",
		SourceModel: "gpt-4",
		DimensionScores: []apiDimensionScore{
			{Dimension: "Accuracy", Score: 4.0, Justification: "Good", Confidence: 0.9},
		},
		CompositeScore: 4.0,
		JudgeModels:    []string{"claude-3"},
	}

	result := convertCandidateSpec(api)

	if result.Index != 0 {
		t.Errorf("expected index 0, got %d", result.Index)
	}
	if result.Format != SpecFormatText {
		t.Errorf("expected format text, got %s", result.Format)
	}
	if len(result.DimensionScores) != 1 {
		t.Errorf("expected 1 dimension score, got %d", len(result.DimensionScores))
	}
	if result.CompositeScore != 4.0 {
		t.Errorf("expected score 4.0, got %f", result.CompositeScore)
	}
}

func TestConvertSelectionResponse(t *testing.T) {
	api := &apiSelectionResponse{
		RequestID: "test-123",
		Selected: apiCandidateSpec{
			Index:           0,
			Content:         "test",
			Format:          "text",
			SpecType:        "api_spec",
			DimensionScores: []apiDimensionScore{},
			JudgeModels:     []string{},
		},
		AllCandidates:       []apiCandidateSpec{},
		SelectionMethod:     "hybrid",
		SelectionConfidence: 0.85,
		ScoringSummary:      map[string]float64{"Accuracy": 4.0},
		LatencyMs:           150.0,
		Timestamp:           "2025-01-01T00:00:00Z",
	}

	result := convertSelectionResponse(api)

	if result.RequestID != "test-123" {
		t.Errorf("expected request ID test-123, got %s", result.RequestID)
	}
	if result.SelectionMethod != SelectionMethodHybrid {
		t.Errorf("expected hybrid, got %s", result.SelectionMethod)
	}
	if result.Timestamp.IsZero() {
		t.Error("expected non-zero timestamp")
	}
}

func TestConvertPolicyStatus(t *testing.T) {
	lastTrained := "2025-01-01T00:00:00Z"
	api := &apiPolicyStatus{
		Version:          "v001",
		Stage:            "production",
		TrainingEpisodes: 10000,
		MeanReward:       0.75,
		ExploreRate:      0.1,
		LastTrained:      &lastTrained,
	}

	result := convertPolicyStatus(api)

	if result.Version != "v001" {
		t.Errorf("expected version v001, got %s", result.Version)
	}
	if result.Stage != PolicyStageProduction {
		t.Errorf("expected production, got %s", result.Stage)
	}
	if result.LastTrained == nil {
		t.Error("expected non-nil LastTrained")
	}
}

func TestConvertHealthResponse(t *testing.T) {
	uptime := 3600.0
	api := &apiHealthResponse{
		Status:        "healthy",
		Version:       "1.0.0",
		UptimeSeconds: &uptime,
	}

	result := convertHealthResponse(api)

	if result.Status != "healthy" {
		t.Errorf("expected healthy, got %s", result.Status)
	}
	if result.UptimeSeconds == nil || *result.UptimeSeconds != 3600.0 {
		t.Error("expected uptime 3600")
	}
}
