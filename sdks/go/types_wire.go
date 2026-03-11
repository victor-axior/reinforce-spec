package reinforcespec

import "time"

// Internal API types for JSON wire format.

type apiSpecInput struct {
	Content     string                 `json:"content"`
	SourceModel string                 `json:"source_model,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

type apiSelectRequest struct {
	Candidates      []apiSpecInput `json:"candidates"`
	SelectionMethod string         `json:"selection_method"`
	RequestID       string         `json:"request_id"`
	Description     string         `json:"description,omitempty"`
}

type apiFeedbackRequest struct {
	RequestID string   `json:"request_id"`
	Rating    *float64 `json:"rating,omitempty"`
	Comment   string   `json:"comment,omitempty"`
	SpecID    string   `json:"spec_id,omitempty"`
}

type apiDimensionScore struct {
	Dimension     string  `json:"dimension"`
	Score         float64 `json:"score"`
	Justification string  `json:"justification"`
	Confidence    float64 `json:"confidence"`
}

type apiCandidateSpec struct {
	Index           int                    `json:"index"`
	Content         string                 `json:"content"`
	Format          string                 `json:"format"`
	SpecType        string                 `json:"spec_type"`
	SourceModel     string                 `json:"source_model,omitempty"`
	DimensionScores []apiDimensionScore    `json:"dimension_scores"`
	CompositeScore  float64                `json:"composite_score"`
	JudgeModels     []string               `json:"judge_models"`
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
}

type apiSelectionResponse struct {
	RequestID           string             `json:"request_id"`
	Selected            apiCandidateSpec   `json:"selected"`
	AllCandidates       []apiCandidateSpec `json:"all_candidates"`
	SelectionMethod     string             `json:"selection_method"`
	SelectionConfidence float64            `json:"selection_confidence"`
	ScoringSummary      map[string]float64 `json:"scoring_summary"`
	LatencyMs           float64            `json:"latency_ms"`
	Timestamp           string             `json:"timestamp"`
}

type apiFeedbackResponse struct {
	FeedbackID string `json:"feedback_id"`
	RequestID  string `json:"request_id"`
	ReceivedAt string `json:"received_at"`
}

type apiPolicyStatus struct {
	Version          string   `json:"version"`
	Stage            string   `json:"stage"`
	TrainingEpisodes int      `json:"training_episodes"`
	MeanReward       float64  `json:"mean_reward"`
	ExploreRate      float64  `json:"explore_rate"`
	DriftPSI         *float64 `json:"drift_psi,omitempty"`
	LastTrained      *string  `json:"last_trained,omitempty"`
	LastPromoted     *string  `json:"last_promoted,omitempty"`
}

type apiHealthResponse struct {
	Status        string   `json:"status"`
	Version       string   `json:"version"`
	UptimeSeconds *float64 `json:"uptime_seconds,omitempty"`
}

// Wire-to-domain conversion functions.

func convertCandidateSpec(api *apiCandidateSpec) CandidateSpec {
	scores := make([]DimensionScore, len(api.DimensionScores))
	for i, s := range api.DimensionScores {
		scores[i] = DimensionScore{
			Dimension:     s.Dimension,
			Score:         s.Score,
			Justification: s.Justification,
			Confidence:    s.Confidence,
		}
	}

	return CandidateSpec{
		Index:           api.Index,
		Content:         api.Content,
		Format:          SpecFormat(api.Format),
		SpecType:        api.SpecType,
		SourceModel:     api.SourceModel,
		DimensionScores: scores,
		CompositeScore:  api.CompositeScore,
		JudgeModels:     api.JudgeModels,
		Metadata:        api.Metadata,
	}
}

func convertSelectionResponse(api *apiSelectionResponse) *SelectionResponse {
	candidates := make([]CandidateSpec, len(api.AllCandidates))
	for i, c := range api.AllCandidates {
		candidates[i] = convertCandidateSpec(&c)
	}

	timestamp, _ := time.Parse(time.RFC3339, api.Timestamp)

	return &SelectionResponse{
		RequestID:           api.RequestID,
		Selected:            convertCandidateSpec(&api.Selected),
		AllCandidates:       candidates,
		SelectionMethod:     SelectionMethod(api.SelectionMethod),
		SelectionConfidence: api.SelectionConfidence,
		ScoringSummary:      api.ScoringSummary,
		LatencyMs:           api.LatencyMs,
		Timestamp:           timestamp,
	}
}

func convertPolicyStatus(api *apiPolicyStatus) *PolicyStatus {
	status := &PolicyStatus{
		Version:          api.Version,
		Stage:            PolicyStage(api.Stage),
		TrainingEpisodes: api.TrainingEpisodes,
		MeanReward:       api.MeanReward,
		ExploreRate:      api.ExploreRate,
		DriftPSI:         api.DriftPSI,
	}

	if api.LastTrained != nil {
		t, _ := time.Parse(time.RFC3339, *api.LastTrained)
		status.LastTrained = &t
	}
	if api.LastPromoted != nil {
		t, _ := time.Parse(time.RFC3339, *api.LastPromoted)
		status.LastPromoted = &t
	}

	return status
}

func convertHealthResponse(api *apiHealthResponse) *HealthResponse {
	return &HealthResponse{
		Status:        api.Status,
		Version:       api.Version,
		UptimeSeconds: api.UptimeSeconds,
	}
}
