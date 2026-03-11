/**
 * ReinforceSpec TypeScript SDK
 *
 * Official TypeScript/JavaScript SDK for the ReinforceSpec API - LLM output
 * evaluation and selection using multi-judge scoring and reinforcement learning.
 *
 * @example
 * ```typescript
 * import { ReinforceSpecClient } from '@reinforce-spec/sdk';
 *
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
 *
 * @packageDocumentation
 */

export { ReinforceSpecClient } from './client';
export type { ClientOptions, RequestOptions } from './client';
export type { RequestHook, ResponseHook, TimeoutConfig } from './http';
export { VERSION } from './version';

export {
  ReinforceSpecError,
  ValidationError,
  AuthenticationError,
  AuthorizationError,
  NotFoundError,
  ConflictError,
  RateLimitError,
  PayloadTooLargeError,
  ServerError,
  ServiceUnavailableError,
  NetworkError,
  TimeoutError,
} from './errors';

export {
  SelectionMethod,
  SpecFormat,
  PolicyStage,
  CustomerType,
} from './types';

export type {
  SpecInput,
  SelectRequest,
  FeedbackRequest,
  DimensionScore,
  CandidateSpec,
  SelectionResponse,
  FeedbackResponse,
  PolicyStatus,
  HealthResponse,
} from './types';
