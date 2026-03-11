/**
 * Tests for the error hierarchy.
 */

import {
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
  errorFromResponse,
} from '../src/errors';

describe('Error classes', () => {
  it('all errors should extend ReinforceSpecError', () => {
    const errors = [
      new ValidationError('test'),
      new AuthenticationError(),
      new AuthorizationError(),
      new NotFoundError(),
      new ConflictError(),
      new RateLimitError(),
      new PayloadTooLargeError(),
      new ServerError(),
      new ServiceUnavailableError(),
      new NetworkError(),
      new TimeoutError(),
    ];

    for (const err of errors) {
      expect(err).toBeInstanceOf(ReinforceSpecError);
      expect(err).toBeInstanceOf(Error);
    }
  });

  it('ReinforceSpecError should set properties', () => {
    const err = new ReinforceSpecError('test message', {
      statusCode: 500,
      details: { key: 'value' },
    });
    expect(err.message).toBe('test message');
    expect(err.statusCode).toBe(500);
    expect(err.details).toEqual({ key: 'value' });
  });

  it('ValidationError should set field and value', () => {
    const err = new ValidationError('bad input', {
      field: 'candidates',
      value: [],
    });
    expect(err.field).toBe('candidates');
    expect(err.value).toEqual([]);
    expect(err.statusCode).toBe(400);
  });

  it('RateLimitError should set retry info', () => {
    const err = new RateLimitError('rate limited', {
      retryAfter: 30000,
      limit: 100,
      remaining: 0,
      resetAt: 1700000000,
    });
    expect(err.retryAfter).toBe(30000);
    expect(err.limit).toBe(100);
    expect(err.remaining).toBe(0);
    expect(err.statusCode).toBe(429);
  });

  it('NotFoundError should set resource info', () => {
    const err = new NotFoundError('not found', {
      resourceType: 'policy',
      resourceId: 'v001',
    });
    expect(err.resourceType).toBe('policy');
    expect(err.resourceId).toBe('v001');
    expect(err.statusCode).toBe(404);
  });

  it('TimeoutError should set timeout', () => {
    const err = new TimeoutError('timed out', 30000);
    expect(err.timeout).toBe(30000);
  });

  it('NetworkError should set cause', () => {
    const cause = new TypeError('fetch failed');
    const err = new NetworkError('connection failed', cause);
    expect(err.cause).toBe(cause);
  });
});

describe('errorFromResponse', () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const testCases: Array<[number, any]> = [
    [400, ValidationError],
    [401, AuthenticationError],
    [403, AuthorizationError],
    [404, NotFoundError],
    [409, ConflictError],
    [413, PayloadTooLargeError],
    [429, RateLimitError],
    [500, ServerError],
    [502, ServerError],
    [503, ServiceUnavailableError],
    [504, ServerError],
  ];

  it.each(testCases)('status %i should produce %s', (status, ErrorClass) => {
    const err = errorFromResponse(status, 'test error');
    expect(err).toBeInstanceOf(ErrorClass);
  });

  it('unknown status should produce base error', () => {
    const err = errorFromResponse(418, "I'm a teapot");
    expect(err).toBeInstanceOf(ReinforceSpecError);
    expect(err.statusCode).toBe(418);
  });

  it('429 should extract rate limit headers', () => {
    const headers = new Headers({
      'Retry-After': '30',
      'X-RateLimit-Limit': '100',
      'X-RateLimit-Remaining': '0',
    });
    const err = errorFromResponse(429, 'rate limited', undefined, headers);
    expect(err).toBeInstanceOf(RateLimitError);
    const rle = err as RateLimitError;
    expect(rle.retryAfter).toBe(30000);
    expect(rle.limit).toBe(100);
    expect(rle.remaining).toBe(0);
  });
});
