/**
 * Error classes for the ReinforceSpec SDK.
 */

/**
 * Base error class for all ReinforceSpec SDK errors.
 */
export class ReinforceSpecError extends Error {
  /** HTTP status code if from API response */
  statusCode?: number;
  /** Structured error details from the API */
  details: Record<string, unknown>;
  /** The underlying cause of the error */
  cause?: Error;

  constructor(
    message: string,
    options?: {
      statusCode?: number;
      details?: Record<string, unknown>;
      cause?: Error;
    }
  ) {
    super(message);
    this.name = 'ReinforceSpecError';
    this.statusCode = options?.statusCode;
    this.details = options?.details ?? {};
    this.cause = options?.cause;

    // Maintains proper stack trace for where error was thrown (V8 only)
    if (typeof Error.captureStackTrace === 'function') {
      Error.captureStackTrace(this, this.constructor);
    }
  }
}

// =============================================================================
// Client-Side Errors (4xx)
// =============================================================================

/**
 * Request validation failed (400).
 *
 * Thrown when the request payload is invalid (e.g., missing required fields,
 * invalid values, fewer than 2 candidates).
 */
export class ValidationError extends ReinforceSpecError {
  /** The field that failed validation */
  field?: string;
  /** The invalid value */
  value?: unknown;

  constructor(
    message: string,
    options?: {
      details?: Record<string, unknown>;
      field?: string;
      value?: unknown;
    }
  ) {
    super(message, { statusCode: 400, details: options?.details });
    this.name = 'ValidationError';
    this.field = options?.field;
    this.value = options?.value;
  }
}

/**
 * Authentication failed (401).
 *
 * Thrown when API key is missing, invalid, or expired.
 */
export class AuthenticationError extends ReinforceSpecError {
  constructor(message = 'Authentication failed', details?: Record<string, unknown>) {
    super(message, { statusCode: 401, details });
    this.name = 'AuthenticationError';
  }
}

/**
 * Authorization failed (403).
 *
 * Thrown when the authenticated user doesn't have permission
 * for the requested operation.
 */
export class AuthorizationError extends ReinforceSpecError {
  constructor(message = 'Not authorized for this operation', details?: Record<string, unknown>) {
    super(message, { statusCode: 403, details });
    this.name = 'AuthorizationError';
  }
}

/**
 * Resource not found (404).
 *
 * Thrown when a requested resource (e.g., request_id, policy) doesn't exist.
 */
export class NotFoundError extends ReinforceSpecError {
  /** Type of resource that wasn't found */
  resourceType?: string;
  /** ID of the resource */
  resourceId?: string;

  constructor(
    message = 'Resource not found',
    options?: {
      details?: Record<string, unknown>;
      resourceType?: string;
      resourceId?: string;
    }
  ) {
    super(message, { statusCode: 404, details: options?.details });
    this.name = 'NotFoundError';
    this.resourceType = options?.resourceType;
    this.resourceId = options?.resourceId;
  }
}

/**
 * Resource conflict (409).
 *
 * Thrown when there's a conflict with the current state (e.g., idempotency
 * key already used with different parameters).
 */
export class ConflictError extends ReinforceSpecError {
  constructor(message = 'Request conflicts with existing state', details?: Record<string, unknown>) {
    super(message, { statusCode: 409, details });
    this.name = 'ConflictError';
  }
}

/**
 * Rate limit exceeded (429).
 *
 * Thrown when too many requests have been made. Check `retryAfter`
 * for when to retry.
 */
export class RateLimitError extends ReinforceSpecError {
  /** Milliseconds to wait before retrying */
  retryAfter?: number;
  /** The rate limit that was exceeded */
  limit?: number;
  /** Requests remaining (usually 0) */
  remaining?: number;
  /** Unix timestamp when the limit resets */
  resetAt?: number;

  constructor(
    message = 'Rate limit exceeded',
    options?: {
      details?: Record<string, unknown>;
      retryAfter?: number;
      limit?: number;
      remaining?: number;
      resetAt?: number;
    }
  ) {
    super(message, { statusCode: 429, details: options?.details });
    this.name = 'RateLimitError';
    this.retryAfter = options?.retryAfter;
    this.limit = options?.limit;
    this.remaining = options?.remaining;
    this.resetAt = options?.resetAt;
  }
}

/**
 * Request payload too large (413).
 *
 * Thrown when the request body exceeds the maximum allowed size.
 */
export class PayloadTooLargeError extends ReinforceSpecError {
  /** Maximum allowed size in bytes */
  maxSize?: number;

  constructor(message = 'Request payload too large', options?: { maxSize?: number }) {
    super(message, { statusCode: 413 });
    this.name = 'PayloadTooLargeError';
    this.maxSize = options?.maxSize;
  }
}

// =============================================================================
// Server-Side Errors (5xx)
// =============================================================================

/**
 * Server error (5xx).
 *
 * Thrown when the server encounters an internal error. These are typically
 * transient and can be retried.
 */
export class ServerError extends ReinforceSpecError {
  constructor(
    message = 'Internal server error',
    statusCode = 500,
    details?: Record<string, unknown>
  ) {
    super(message, { statusCode, details });
    this.name = 'ServerError';
  }
}

/**
 * Service temporarily unavailable (503).
 *
 * Thrown when the service is overloaded or under maintenance.
 * Check `retryAfter` for when to retry.
 */
export class ServiceUnavailableError extends ReinforceSpecError {
  /** Milliseconds to wait before retrying */
  retryAfter?: number;

  constructor(
    message = 'Service temporarily unavailable',
    options?: {
      details?: Record<string, unknown>;
      retryAfter?: number;
    }
  ) {
    super(message, { statusCode: 503, details: options?.details });
    this.name = 'ServiceUnavailableError';
    this.retryAfter = options?.retryAfter;
  }
}

// =============================================================================
// Network/Transport Errors
// =============================================================================

/**
 * Network connectivity error.
 *
 * Thrown when unable to connect to the API server.
 */
export class NetworkError extends ReinforceSpecError {
  constructor(message = 'Failed to connect to API', cause?: Error) {
    super(message, { cause });
    this.name = 'NetworkError';
  }
}

/**
 * Request timeout.
 *
 * Thrown when the request takes longer than the configured timeout.
 */
export class TimeoutError extends ReinforceSpecError {
  /** Configured timeout in milliseconds */
  timeout?: number;

  constructor(message = 'Request timed out', timeout?: number) {
    super(message);
    this.name = 'TimeoutError';
    this.timeout = timeout;
  }
}

// =============================================================================
// Error Factory
// =============================================================================

/**
 * Create the appropriate error from an API response.
 * @internal
 */
export function errorFromResponse(
  statusCode: number,
  message: string,
  details?: Record<string, unknown>,
  headers?: Headers
): ReinforceSpecError {
  // Extract rate limit info from headers
  const rateLimitInfo = headers
    ? {
        retryAfter: headers.get('Retry-After')
          ? parseInt(headers.get('Retry-After')!, 10) * 1000
          : undefined,
        limit: headers.get('X-RateLimit-Limit')
          ? parseInt(headers.get('X-RateLimit-Limit')!, 10)
          : undefined,
        remaining: headers.get('X-RateLimit-Remaining')
          ? parseInt(headers.get('X-RateLimit-Remaining')!, 10)
          : undefined,
        resetAt: headers.get('X-RateLimit-Reset')
          ? parseInt(headers.get('X-RateLimit-Reset')!, 10)
          : undefined,
      }
    : {};

  switch (statusCode) {
    case 400:
      return new ValidationError(message, { details });
    case 401:
      return new AuthenticationError(message, details);
    case 403:
      return new AuthorizationError(message, details);
    case 404:
      return new NotFoundError(message, { details });
    case 409:
      return new ConflictError(message, details);
    case 413:
      return new PayloadTooLargeError(message);
    case 429:
      return new RateLimitError(message, { details, ...rateLimitInfo });
    case 503:
      return new ServiceUnavailableError(message, {
        details,
        retryAfter: rateLimitInfo.retryAfter,
      });
    case 500:
    case 502:
    case 504:
      return new ServerError(message, statusCode, details);
    default:
      return new ReinforceSpecError(message, { statusCode, details });
  }
}
