/**
 * Main client for the ReinforceSpec SDK.
 */

import { HttpClient, type RequestHook, type ResponseHook, type TimeoutConfig } from './http';
import {
  type ApiHealthResponse,
  type ApiFeedbackResponse,
  type ApiPolicyStatus,
  type ApiSelectionResponse,
  type FeedbackRequest,
  type HealthResponse,
  type PolicyStatus,
  type SelectionResponse,
  type SelectRequest,
  convertHealthResponse,
  convertPolicyStatus,
  convertSelectionResponse,
  SelectionMethod,
} from './types';

/**
 * Options for configuring the ReinforceSpec client.
 */
export interface ClientOptions {
  /** Base URL of the ReinforceSpec API */
  baseUrl: string;
  /** API key for authentication */
  apiKey?: string;
  /** Request timeout in milliseconds or TimeoutConfig (default: 30000) */
  timeout?: number | TimeoutConfig;
  /** Maximum number of retry attempts (default: 3) */
  maxRetries?: number;
  /** Initial delay between retries in ms (default: 1000) */
  retryDelay?: number;
  /** Maximum delay between retries in ms (default: 30000) */
  retryMaxDelay?: number;
  /** Hook called before each request (for logging/debugging) */
  onRequest?: RequestHook;
  /** Hook called after each response (for logging/debugging) */
  onResponse?: ResponseHook;
}

/**
 * Options for individual requests.
 */
export interface RequestOptions {
  /** AbortSignal for request cancellation */
  signal?: AbortSignal;
}

/**
 * Generate a UUID v4.
 */
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older environments
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Client for the ReinforceSpec API.
 *
 * This is the main entry point for interacting with the ReinforceSpec API.
 * It provides methods for evaluating specs, submitting feedback, and
 * checking policy status.
 *
 * @example
 * ```typescript
 * const client = new ReinforceSpecClient({
 *   baseUrl: 'https://api.reinforce-spec.dev',
 *   apiKey: 'your-api-key',
 * });
 *
 * const response = await client.select({
 *   candidates: [
 *     { content: 'First output' },
 *     { content: 'Second output' },
 *   ],
 * });
 *
 * console.log(`Selected: ${response.selected.index}`);
 * ```
 */
export class ReinforceSpecClient {
  private readonly http: HttpClient;
  private _closed = false;

  /**
   * Create a new ReinforceSpec client.
   *
   * @param options - Client configuration options
   */
  constructor(options: ClientOptions) {
    this.http = new HttpClient({
      baseUrl: options.baseUrl,
      apiKey: options.apiKey,
      timeout: options.timeout,
      maxRetries: options.maxRetries,
      retryDelay: options.retryDelay,
      retryMaxDelay: options.retryMaxDelay,
      onRequest: options.onRequest,
      onResponse: options.onResponse,
    });
  }

  /**
   * Close the client and release resources.
   *
   * For fetch-based clients, this is a no-op but provided for
   * API consistency and future compatibility.
   */
  close(): void {
    this._closed = true;
  }

  /**
   * Check if the client has been closed.
   */
  get closed(): boolean {
    return this._closed;
  }

  /**
   * Create a client from environment variables.
   *
   * Environment variables:
   * - `REINFORCE_SPEC_BASE_URL`: Base URL of the API (required)
   * - `REINFORCE_SPEC_API_KEY`: API key for authentication (optional)
   * - `REINFORCE_SPEC_TIMEOUT`: Request timeout in ms (default: 30000)
   * - `REINFORCE_SPEC_MAX_RETRIES`: Maximum retry attempts (default: 3)
   *
   * @returns Configured ReinforceSpecClient instance
   * @throws Error if REINFORCE_SPEC_BASE_URL is not set
   */
  static fromEnv(): ReinforceSpecClient {
    const baseUrl = process.env.REINFORCE_SPEC_BASE_URL;
    if (!baseUrl) {
      throw new Error('REINFORCE_SPEC_BASE_URL environment variable is required');
    }

    return new ReinforceSpecClient({
      baseUrl,
      apiKey: process.env.REINFORCE_SPEC_API_KEY,
      timeout: process.env.REINFORCE_SPEC_TIMEOUT
        ? parseInt(process.env.REINFORCE_SPEC_TIMEOUT, 10)
        : undefined,
      maxRetries: process.env.REINFORCE_SPEC_MAX_RETRIES
        ? parseInt(process.env.REINFORCE_SPEC_MAX_RETRIES, 10)
        : undefined,
    });
  }

  /**
   * Evaluate candidates and select the best one.
   *
   * This is the main method for evaluating LLM outputs. It scores each
   * candidate across 12 dimensions using multi-judge ensemble and selects
   * the best one using the specified selection method.
   *
   * @param request - Selection request parameters
   * @param request.candidates - List of candidate specs to evaluate (minimum 2)
   * @param request.selectionMethod - Selection method: "hybrid", "scoring_only", or "rl_only"
   * @param request.requestId - Idempotency key (auto-generated if not provided)
   * @param request.description - Context about what the specs are for
   * @param options - Request options (e.g., AbortSignal)
   * @returns SelectionResponse containing the selected candidate and all scores
   *
   * @example
   * ```typescript
   * const response = await client.select({
   *   candidates: [
   *     { content: 'Output from GPT-4', sourceModel: 'gpt-4' },
   *     { content: 'Output from Claude', sourceModel: 'claude-3' },
   *   ],
   *   selectionMethod: 'hybrid',
   *   description: 'API specification for user endpoint',
   * });
   *
   * console.log(`Selected: ${response.selected.index}`);
   * console.log(`Score: ${response.selected.compositeScore}`);
   * ```
   */
  async select(request: SelectRequest, options?: RequestOptions): Promise<SelectionResponse> {
    // Normalize candidates
    const candidates = request.candidates.map((c) => ({
      content: c.content,
      source_model: c.sourceModel,
      metadata: c.metadata,
    }));

    // Generate request ID if not provided
    const requestId = request.requestId ?? generateUUID();

    // Normalize selection method
    const selectionMethod =
      typeof request.selectionMethod === 'string'
        ? request.selectionMethod
        : (request.selectionMethod ?? SelectionMethod.Hybrid);

    const body: Record<string, unknown> = {
      candidates,
      selection_method: selectionMethod,
      request_id: requestId,
    };

    if (request.description) {
      body.description = request.description;
    }

    const response = await this.http.post<ApiSelectionResponse>('/v1/specs', {
      body,
      idempotencyKey: requestId,
      signal: options?.signal,
    });

    return convertSelectionResponse(response);
  }

  /**
   * Submit feedback for a previous evaluation.
   *
   * Feedback is used to train the reinforcement learning policy,
   * improving future selections based on human preferences.
   *
   * @param request - Feedback request parameters
   * @param request.requestId - The request_id from the original select() call
   * @param request.rating - Human rating from 1.0 (poor) to 5.0 (excellent)
   * @param request.comment - Optional comment explaining the rating
   * @param request.specId - ID of the specific candidate being rated
   * @param options - Request options
   * @returns Feedback ID for tracking
   *
   * @example
   * ```typescript
   * const feedbackId = await client.submitFeedback({
   *   requestId: 'abc-123',
   *   rating: 4.5,
   *   comment: 'Good structure but missing error handling',
   * });
   * ```
   */
  async submitFeedback(request: FeedbackRequest, options?: RequestOptions): Promise<string> {
    const body: Record<string, unknown> = {
      request_id: request.requestId,
    };

    if (request.rating !== undefined) {
      body.rating = request.rating;
    }
    if (request.comment) {
      body.comment = request.comment;
    }
    if (request.specId) {
      body.spec_id = request.specId;
    }

    const response = await this.http.post<ApiFeedbackResponse>('/v1/specs/feedback', {
      body,
      signal: options?.signal,
    });

    return response.feedback_id;
  }

  /**
   * Get the current RL policy status.
   *
   * Returns information about the current policy version, deployment
   * stage, training statistics, and drift metrics.
   *
   * @param options - Request options
   * @returns PolicyStatus with version, stage, and metrics
   *
   * @example
   * ```typescript
   * const status = await client.getPolicyStatus();
   * console.log(`Policy version: ${status.version}`);
   * console.log(`Stage: ${status.stage}`);
   * console.log(`Mean reward: ${status.meanReward.toFixed(3)}`);
   * ```
   */
  async getPolicyStatus(options?: RequestOptions): Promise<PolicyStatus> {
    const response = await this.http.get<ApiPolicyStatus>('/v1/policy/status', {
      signal: options?.signal,
    });

    return convertPolicyStatus(response);
  }

  /**
   * Trigger policy training.
   *
   * Starts a background training job for the RL policy using
   * accumulated feedback data.
   *
   * @param nSteps - Number of training steps (optional)
   * @param options - Request options
   * @returns Job information including job_id
   *
   * @example
   * ```typescript
   * const job = await client.trainPolicy(1000);
   * console.log(`Training job started: ${job.jobId}`);
   * ```
   */
  async trainPolicy(
    nSteps?: number,
    options?: RequestOptions
  ): Promise<{ jobId: string; status: string }> {
    const body: Record<string, unknown> = {};
    if (nSteps !== undefined) {
      body.n_steps = nSteps;
    }

    const response = await this.http.post<{ job_id: string; status: string }>('/v1/policy/train', {
      body,
      signal: options?.signal,
    });

    return {
      jobId: response.job_id,
      status: response.status,
    };
  }

  /**
   * Check API health status.
   *
   * @param options - Request options
   * @returns HealthResponse with status and version
   *
   * @example
   * ```typescript
   * const health = await client.health();
   * console.log(`Status: ${health.status}`);
   * console.log(`Version: ${health.version}`);
   * ```
   */
  async health(options?: RequestOptions): Promise<HealthResponse> {
    const response = await this.http.get<ApiHealthResponse>('/v1/health', {
      signal: options?.signal,
    });

    return convertHealthResponse(response);
  }

  /**
   * Check API readiness status.
   *
   * @param options - Request options
   * @returns HealthResponse indicating if the API is ready
   */
  async ready(options?: RequestOptions): Promise<HealthResponse> {
    const response = await this.http.get<ApiHealthResponse>('/v1/health/ready', {
      signal: options?.signal,
    });

    return convertHealthResponse(response);
  }
}
