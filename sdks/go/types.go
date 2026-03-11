package reinforcespec

import "time"

// SelectionMethod specifies how to select the best candidate.
type SelectionMethod string

const (
	// SelectionMethodHybrid combines scoring and RL for selection (recommended).
	SelectionMethodHybrid SelectionMethod = "hybrid"
	// SelectionMethodScoringOnly uses only multi-judge scoring.
	SelectionMethodScoringOnly SelectionMethod = "scoring_only"
	// SelectionMethodRLOnly uses only RL policy.
	SelectionMethodRLOnly SelectionMethod = "rl_only"
)

// SpecFormat is the format of the specification content.
type SpecFormat string

const (
	SpecFormatText     SpecFormat = "text"
	SpecFormatJSON     SpecFormat = "json"
	SpecFormatYAML     SpecFormat = "yaml"
	SpecFormatMarkdown SpecFormat = "markdown"
	SpecFormatOther    SpecFormat = "other"
)

// PolicyStage is the deployment stage of the RL policy.
type PolicyStage string

const (
	PolicyStageCandidate  PolicyStage = "candidate"
	PolicyStageShadow     PolicyStage = "shadow"
	PolicyStageCanary     PolicyStage = "canary"
	PolicyStageProduction PolicyStage = "production"
	PolicyStageArchived   PolicyStage = "archived"
)

// CustomerType is the customer segment for scoring weight customization.
type CustomerType string

const (
	CustomerTypeBank    CustomerType = "bank"
	CustomerTypeSI      CustomerType = "si"
	CustomerTypeBPO     CustomerType = "bpo"
	CustomerTypeSaaS    CustomerType = "saas"
	CustomerTypeDefault CustomerType = "default"
)

// SpecInput is an input specification for evaluation.
type SpecInput struct {
	// Content is the specification content to evaluate.
	Content string
	// SourceModel is the LLM that generated this spec (e.g., "gpt-4").
	SourceModel string
	// Metadata is additional metadata for the spec.
	Metadata map[string]interface{}
}

// SelectRequest is the request for Select().
type SelectRequest struct {
	// Candidates is the list of specs to evaluate (minimum 2).
	Candidates []SpecInput
	// SelectionMethod is the method to use for selection.
	SelectionMethod SelectionMethod
	// RequestID is the idempotency key for the request.
	RequestID string
	// Description is context about what the specs are for.
	Description string
}

// FeedbackRequest is the request for SubmitFeedback().
type FeedbackRequest struct {
	// RequestID is the original request ID to provide feedback for.
	RequestID string
	// Rating is the human rating from 1.0 to 5.0.
	Rating *float64
	// Comment is an optional comment about the selection.
	Comment string
	// SpecID is the ID of the specific spec being rated.
	SpecID string
}

// DimensionScore is a score for a single evaluation dimension.
type DimensionScore struct {
	// Dimension is the name of the scoring dimension.
	Dimension string
	// Score is from 1.0 to 5.0.
	Score float64
	// Justification is the explanation for the score.
	Justification string
	// Confidence is the confidence level of the score (0.0-1.0).
	Confidence float64
}

// CandidateSpec is an evaluated candidate specification.
type CandidateSpec struct {
	// Index is the position of this candidate in the input list.
	Index int
	// Content is the specification content.
	Content string
	// Format is the detected format of the content.
	Format SpecFormat
	// SpecType is the detected type of specification.
	SpecType string
	// SourceModel is the LLM that generated this spec.
	SourceModel string
	// DimensionScores are scores for each evaluation dimension.
	DimensionScores []DimensionScore
	// CompositeScore is the overall weighted score (0.0-5.0).
	CompositeScore float64
	// JudgeModels are the LLMs used for scoring.
	JudgeModels []string
	// Metadata is the original metadata from input.
	Metadata map[string]interface{}
}

// SelectionResponse is the response from Select().
type SelectionResponse struct {
	// RequestID is the unique identifier for this request.
	RequestID string
	// Selected is the selected best candidate.
	Selected CandidateSpec
	// AllCandidates contains all candidates with their scores.
	AllCandidates []CandidateSpec
	// SelectionMethod is the method used for selection.
	SelectionMethod SelectionMethod
	// SelectionConfidence is the confidence in the selection (0.0-1.0).
	SelectionConfidence float64
	// ScoringSummary contains summary scores by dimension.
	ScoringSummary map[string]float64
	// LatencyMs is the processing time in milliseconds.
	LatencyMs float64
	// Timestamp is when the response was generated.
	Timestamp time.Time
}

// FeedbackResponse is the response from SubmitFeedback().
type FeedbackResponse struct {
	// FeedbackID is the unique identifier for the feedback.
	FeedbackID string
	// RequestID is the original request this feedback is for.
	RequestID string
	// ReceivedAt is when the feedback was received.
	ReceivedAt time.Time
}

// PolicyStatus is the RL policy status.
type PolicyStatus struct {
	// Version is the policy version string.
	Version string
	// Stage is the current deployment stage.
	Stage PolicyStage
	// TrainingEpisodes is the number of training episodes completed.
	TrainingEpisodes int
	// MeanReward is the average reward from recent episodes.
	MeanReward float64
	// ExploreRate is the current exploration rate (epsilon).
	ExploreRate float64
	// DriftPSI is the PSI drift metric if available.
	DriftPSI *float64
	// LastTrained is when policy was last trained.
	LastTrained *time.Time
	// LastPromoted is when policy was last promoted.
	LastPromoted *time.Time
}

// HealthResponse is the health check response.
type HealthResponse struct {
	// Status is the health status ("healthy", "degraded", "unhealthy").
	Status string
	// Version is the API version.
	Version string
	// UptimeSeconds is the server uptime in seconds.
	UptimeSeconds *float64
}

// TrainResponse is the response from TrainPolicy().
type TrainResponse struct {
	// JobID is the training job identifier.
	JobID string
	// Status is the job status.
	Status string
}
