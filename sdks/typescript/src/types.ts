/**
 * Type definitions for the ReinforceSpec SDK.
 */

// =============================================================================
// Enums
// =============================================================================

/**
 * Method used to select the best candidate.
 */
export enum SelectionMethod {
  /** Combine scoring and RL for selection (recommended) */
  Hybrid = 'hybrid',
  /** Use only multi-judge scoring */
  ScoringOnly = 'scoring_only',
  /** Use only RL policy */
  RLOnly = 'rl_only',
}

/**
 * Format of the specification content.
 */
export enum SpecFormat {
  Text = 'text',
  JSON = 'json',
  YAML = 'yaml',
  Markdown = 'markdown',
  Other = 'other',
}

/**
 * Deployment stage of the RL policy.
 */
export enum PolicyStage {
  Candidate = 'candidate',
  Shadow = 'shadow',
  Canary = 'canary',
  Production = 'production',
  Archived = 'archived',
}

/**
 * Customer segment for scoring weight customization.
 */
export enum CustomerType {
  Bank = 'bank',
  SI = 'si',
  BPO = 'bpo',
  SaaS = 'saas',
  Default = 'default',
}

// =============================================================================
// Request Types
// =============================================================================

/**
 * Input specification for evaluation.
 */
export interface SpecInput {
  /** The specification content to evaluate */
  content: string;
  /** The LLM that generated this spec (e.g., "gpt-4") */
  sourceModel?: string;
  /** Additional metadata for the spec */
  metadata?: Record<string, unknown>;
}

/**
 * Request body for the select() method.
 */
export interface SelectRequest {
  /** List of specs to evaluate (minimum 2) */
  candidates: SpecInput[];
  /** Method to use for selection */
  selectionMethod?: SelectionMethod | string;
  /** Idempotency key for the request */
  requestId?: string;
  /** Context about what the specs are for */
  description?: string;
}

/**
 * Request body for the submitFeedback() method.
 */
export interface FeedbackRequest {
  /** The original request ID to provide feedback for */
  requestId: string;
  /** Human rating from 1.0 to 5.0 */
  rating?: number;
  /** Optional comment about the selection */
  comment?: string;
  /** ID of the specific spec being rated */
  specId?: string;
}

// =============================================================================
// Response Types
// =============================================================================

/**
 * Score for a single evaluation dimension.
 */
export interface DimensionScore {
  /** Name of the scoring dimension */
  dimension: string;
  /** Score from 1.0 to 5.0 */
  score: number;
  /** Explanation for the score */
  justification: string;
  /** Confidence level of the score (0.0-1.0) */
  confidence: number;
}

/**
 * Evaluated candidate specification.
 */
export interface CandidateSpec {
  /** Position of this candidate in the input list */
  index: number;
  /** The specification content */
  content: string;
  /** Detected format of the content */
  format: SpecFormat | string;
  /** Detected type of specification */
  specType: string;
  /** The LLM that generated this spec */
  sourceModel?: string;
  /** Scores for each evaluation dimension */
  dimensionScores: DimensionScore[];
  /** Overall weighted score (0.0-5.0) */
  compositeScore: number;
  /** LLMs used for scoring */
  judgeModels: string[];
  /** Original metadata from input */
  metadata?: Record<string, unknown>;
}

/**
 * Response from the select() method.
 */
export interface SelectionResponse {
  /** Unique identifier for this request */
  requestId: string;
  /** The selected best candidate */
  selected: CandidateSpec;
  /** All candidates with their scores */
  allCandidates: CandidateSpec[];
  /** Method used for selection */
  selectionMethod: SelectionMethod | string;
  /** Confidence in the selection (0.0-1.0) */
  selectionConfidence: number;
  /** Summary scores by dimension */
  scoringSummary: Record<string, number>;
  /** Processing time in milliseconds */
  latencyMs: number;
  /** When the response was generated */
  timestamp: string;
}

/**
 * Response from the submitFeedback() method.
 */
export interface FeedbackResponse {
  /** Unique identifier for the feedback */
  feedbackId: string;
  /** The original request this feedback is for */
  requestId: string;
  /** When the feedback was received */
  receivedAt: string;
}

/**
 * RL policy status.
 */
export interface PolicyStatus {
  /** Policy version string */
  version: string;
  /** Current deployment stage */
  stage: PolicyStage | string;
  /** Number of training episodes completed */
  trainingEpisodes: number;
  /** Average reward from recent episodes */
  meanReward: number;
  /** Current exploration rate (epsilon) */
  exploreRate: number;
  /** PSI drift metric if available */
  driftPsi?: number;
  /** When policy was last trained */
  lastTrained?: string;
  /** When policy was last promoted */
  lastPromoted?: string;
}

/**
 * Health check response.
 */
export interface HealthResponse {
  /** Health status ("healthy", "degraded", "unhealthy") */
  status: string;
  /** API version */
  version: string;
  /** Server uptime in seconds */
  uptimeSeconds?: number;
}

// =============================================================================
// Internal API Response Types (snake_case from API)
// =============================================================================

/** @internal */
export interface ApiDimensionScore {
  dimension: string;
  score: number;
  justification: string;
  confidence: number;
}

/** @internal */
export interface ApiCandidateSpec {
  index: number;
  content: string;
  format: string;
  spec_type: string;
  source_model?: string;
  dimension_scores: ApiDimensionScore[];
  composite_score: number;
  judge_models: string[];
  metadata?: Record<string, unknown>;
}

/** @internal */
export interface ApiSelectionResponse {
  request_id: string;
  selected: ApiCandidateSpec;
  all_candidates: ApiCandidateSpec[];
  selection_method: string;
  selection_confidence: number;
  scoring_summary: Record<string, number>;
  latency_ms: number;
  timestamp: string;
}

/** @internal */
export interface ApiFeedbackResponse {
  feedback_id: string;
  request_id: string;
  received_at: string;
}

/** @internal */
export interface ApiPolicyStatus {
  version: string;
  stage: string;
  training_episodes: number;
  mean_reward: number;
  explore_rate: number;
  drift_psi?: number;
  last_trained?: string;
  last_promoted?: string;
}

/** @internal */
export interface ApiHealthResponse {
  status: string;
  version: string;
  uptime_seconds?: number;
}

// =============================================================================
// Type Converters
// =============================================================================

/**
 * Convert API response to SDK types (snake_case to camelCase).
 * @internal
 */
export function convertCandidateSpec(api: ApiCandidateSpec): CandidateSpec {
  return {
    index: api.index,
    content: api.content,
    format: api.format as SpecFormat,
    specType: api.spec_type,
    sourceModel: api.source_model,
    dimensionScores: api.dimension_scores,
    compositeScore: api.composite_score,
    judgeModels: api.judge_models,
    metadata: api.metadata,
  };
}

/**
 * Convert API response to SDK types.
 * @internal
 */
export function convertSelectionResponse(api: ApiSelectionResponse): SelectionResponse {
  return {
    requestId: api.request_id,
    selected: convertCandidateSpec(api.selected),
    allCandidates: api.all_candidates.map(convertCandidateSpec),
    selectionMethod: api.selection_method as SelectionMethod,
    selectionConfidence: api.selection_confidence,
    scoringSummary: api.scoring_summary,
    latencyMs: api.latency_ms,
    timestamp: api.timestamp,
  };
}

/**
 * Convert API response to SDK types.
 * @internal
 */
export function convertFeedbackResponse(api: ApiFeedbackResponse): FeedbackResponse {
  return {
    feedbackId: api.feedback_id,
    requestId: api.request_id,
    receivedAt: api.received_at,
  };
}

/**
 * Convert API response to SDK types.
 * @internal
 */
export function convertPolicyStatus(api: ApiPolicyStatus): PolicyStatus {
  return {
    version: api.version,
    stage: api.stage as PolicyStage,
    trainingEpisodes: api.training_episodes,
    meanReward: api.mean_reward,
    exploreRate: api.explore_rate,
    driftPsi: api.drift_psi,
    lastTrained: api.last_trained,
    lastPromoted: api.last_promoted,
  };
}

/**
 * Convert API response to SDK types.
 * @internal
 */
export function convertHealthResponse(api: ApiHealthResponse): HealthResponse {
  return {
    status: api.status,
    version: api.version,
    uptimeSeconds: api.uptime_seconds,
  };
}
