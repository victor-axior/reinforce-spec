/**
 * Testing utilities for the ReinforceSpec SDK.
 */

import type {
  CandidateSpec,
  DimensionScore,
  FeedbackRequest,
  HealthResponse,
  PolicyStatus,
  SelectionResponse,
  SelectRequest,
} from './types';
import { PolicyStage, SelectionMethod, SpecFormat } from './types';

/**
 * Mock responses for MockClient.
 */
export interface MockResponses {
  selectResponse?: SelectionResponse;
  policyStatus?: PolicyStatus;
  healthResponse?: HealthResponse;
}

/**
 * Mock client for testing applications that use the ReinforceSpec SDK.
 *
 * This class provides a test double that mimics the ReinforceSpecClient
 * interface without making actual HTTP requests.
 *
 * @example
 * ```typescript
 * import { MockClient, makeSelectionResponse } from '@reinforce-spec/sdk/testing';
 *
 * const client = new MockClient({
 *   selectResponse: makeSelectionResponse({ selectedIndex: 0 }),
 * });
 *
 * const response = await client.select({ candidates: [...] });
 * expect(response.selected.index).toBe(0);
 * ```
 */
export class MockClient {
  private readonly selectResponse: SelectionResponse;
  private readonly policyStatus: PolicyStatus;
  private readonly healthResponse: HealthResponse;
  private readonly feedbackCalls: FeedbackRequest[] = [];

  constructor(responses?: MockResponses) {
    this.selectResponse = responses?.selectResponse ?? makeSelectionResponse();
    this.policyStatus = responses?.policyStatus ?? makePolicyStatus();
    this.healthResponse = responses?.healthResponse ?? {
      status: 'healthy',
      version: '1.0.0',
      uptimeSeconds: 3600,
    };
  }

  async select(_request: SelectRequest): Promise<SelectionResponse> {
    return this.selectResponse;
  }

  async submitFeedback(request: FeedbackRequest): Promise<string> {
    this.feedbackCalls.push(request);
    return `feedback-${this.feedbackCalls.length}`;
  }

  async getPolicyStatus(): Promise<PolicyStatus> {
    return this.policyStatus;
  }

  async trainPolicy(_nSteps?: number): Promise<{ jobId: string; status: string }> {
    return { jobId: 'job-123', status: 'started' };
  }

  async health(): Promise<HealthResponse> {
    return this.healthResponse;
  }

  async ready(): Promise<HealthResponse> {
    return this.healthResponse;
  }

  /**
   * Get all recorded feedback calls.
   */
  getFeedbackCalls(): FeedbackRequest[] {
    return [...this.feedbackCalls];
  }
}

/**
 * Create a DimensionScore for testing.
 */
export function makeDimensionScore(overrides?: Partial<DimensionScore>): DimensionScore {
  return {
    dimension: 'Accuracy',
    score: 4.0,
    justification: 'Good accuracy',
    confidence: 0.85,
    ...overrides,
  };
}

/**
 * Create a CandidateSpec for testing.
 */
export function makeCandidate(overrides?: Partial<CandidateSpec>): CandidateSpec {
  return {
    index: 0,
    content: 'Test content',
    format: SpecFormat.Text,
    specType: 'api_spec',
    sourceModel: 'gpt-4',
    dimensionScores: [
      makeDimensionScore({ dimension: 'Accuracy', score: 4.0 }),
      makeDimensionScore({ dimension: 'Completeness', score: 4.2 }),
      makeDimensionScore({ dimension: 'Clarity', score: 3.8 }),
    ],
    compositeScore: 4.0,
    judgeModels: ['anthropic/claude-3-opus', 'openai/gpt-4-turbo'],
    metadata: undefined,
    ...overrides,
  };
}

/**
 * Options for makeSelectionResponse.
 */
export interface SelectionResponseOptions {
  requestId?: string;
  selectedIndex?: number;
  selectionMethod?: SelectionMethod;
  numCandidates?: number;
}

/**
 * Create a SelectionResponse for testing.
 */
export function makeSelectionResponse(options?: SelectionResponseOptions): SelectionResponse {
  const requestId = options?.requestId ?? 'test-request-123';
  const numCandidates = options?.numCandidates ?? 2;
  const selectedIndex = options?.selectedIndex ?? 0;

  const candidates: CandidateSpec[] = [];
  for (let i = 0; i < numCandidates; i++) {
    candidates.push(
      makeCandidate({
        index: i,
        content: `Content ${i}`,
        compositeScore: 4.0 - i * 0.5,
      })
    );
  }

  return {
    requestId,
    selected: candidates[selectedIndex],
    allCandidates: candidates,
    selectionMethod: options?.selectionMethod ?? SelectionMethod.Hybrid,
    selectionConfidence: 0.85,
    scoringSummary: { Accuracy: 4.0, Completeness: 4.2, Clarity: 3.8 },
    latencyMs: 150,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Create a PolicyStatus for testing.
 */
export function makePolicyStatus(overrides?: Partial<PolicyStatus>): PolicyStatus {
  return {
    version: 'v001',
    stage: PolicyStage.Production,
    trainingEpisodes: 10000,
    meanReward: 0.75,
    exploreRate: 0.1,
    driftPsi: 0.05,
    lastTrained: new Date().toISOString(),
    lastPromoted: new Date().toISOString(),
    ...overrides,
  };
}
