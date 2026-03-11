/**
 * Low-level HTTP client with retry logic.
 * @internal
 */

import {
  NetworkError,
  RateLimitError,
  ServerError,
  TimeoutError,
  errorFromResponse,
} from './errors';
import { VERSION } from './version';

/**
 * Hook called before each request.
 */
export type RequestHook = (url: string, init: globalThis.RequestInit) => void;

/**
 * Hook called after each response.
 */
export type ResponseHook = (response: Response) => void;

/**
 * Granular timeout configuration.
 */
export interface TimeoutConfig {
  /** Timeout for the entire request in milliseconds */
  request?: number;
  /** Connect timeout is not directly supported by fetch, use request timeout */
}

export interface HttpClientOptions {
  baseUrl: string;
  apiKey?: string;
  timeout?: number | TimeoutConfig;
  maxRetries?: number;
  retryDelay?: number;
  retryMaxDelay?: number;
  /** Hook called before each request (for logging/debugging) */
  onRequest?: RequestHook;
  /** Hook called after each response (for logging/debugging) */
  onResponse?: ResponseHook;
}

export interface RequestInit {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  signal?: AbortSignal;
}

const DEFAULT_TIMEOUT = 30000;
const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_RETRY_DELAY = 1000;
const DEFAULT_RETRY_MAX_DELAY = 30000;

/**
 * Low-level HTTP client with retry logic and error handling.
 * @internal
 */
export class HttpClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly timeout: number;
  private readonly maxRetries: number;
  private readonly retryDelay: number;
  private readonly retryMaxDelay: number;
  private readonly onRequest?: RequestHook;
  private readonly onResponse?: ResponseHook;

  constructor(options: HttpClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.apiKey = options.apiKey;
    this.maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.retryDelay = options.retryDelay ?? DEFAULT_RETRY_DELAY;
    this.retryMaxDelay = options.retryMaxDelay ?? DEFAULT_RETRY_MAX_DELAY;
    this.onRequest = options.onRequest;
    this.onResponse = options.onResponse;

    // Handle timeout configuration
    if (typeof options.timeout === 'object') {
      this.timeout = options.timeout.request ?? DEFAULT_TIMEOUT;
    } else {
      this.timeout = options.timeout ?? DEFAULT_TIMEOUT;
    }
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'User-Agent': `reinforce-spec-sdk-typescript/${VERSION}`,
    };

    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    return headers;
  }

  private shouldRetry(error: unknown): boolean {
    if (error instanceof TimeoutError) return true;
    if (error instanceof NetworkError) return true;
    if (error instanceof ServerError && [502, 503, 504].includes(error.statusCode ?? 0)) {
      return true;
    }
    if (error instanceof RateLimitError) return true;
    return false;
  }

  private getRetryDelay(attempt: number, error?: unknown): number {
    // Check for Retry-After in rate limit errors
    if (error instanceof RateLimitError && error.retryAfter) {
      return error.retryAfter;
    }

    // Exponential backoff with jitter
    const base = this.retryDelay * Math.pow(2, attempt);
    const capped = Math.min(base, this.retryMaxDelay);
    const jitter = Math.random() * 1000;
    return capped + jitter;
  }

  async request<T>(
    method: string,
    path: string,
    options?: {
      body?: Record<string, unknown>;
      params?: Record<string, string>;
      headers?: Record<string, string>;
      idempotencyKey?: string;
      signal?: AbortSignal;
    }
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);

    if (options?.params) {
      for (const [key, value] of Object.entries(options.params)) {
        url.searchParams.set(key, value);
      }
    }

    const headers: Record<string, string> = {
      ...this.getHeaders(),
      ...options?.headers,
    };

    if (options?.idempotencyKey && ['POST', 'PUT', 'PATCH'].includes(method)) {
      headers['Idempotency-Key'] = options.idempotencyKey;
    }

    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        // Combine user signal with timeout
        const signal = options?.signal
          ? anySignal([options.signal, controller.signal])
          : controller.signal;

        const fetchInit: globalThis.RequestInit = {
          method,
          headers,
          body: options?.body ? JSON.stringify(options.body) : undefined,
          signal,
        };

        // Call request hook before fetch
        if (this.onRequest) {
          this.onRequest(url.toString(), fetchInit);
        }

        const response = await fetch(url.toString(), fetchInit);

        clearTimeout(timeoutId);

        // Call response hook after fetch
        if (this.onResponse) {
          this.onResponse(response);
        }

        // Success
        if (response.ok) {
          if (response.status === 204) {
            return {} as T;
          }
          return (await response.json()) as T;
        }

        // Error response
        let errorBody: { detail?: string; message?: string; details?: Record<string, unknown> };
        try {
          errorBody = await response.json();
        } catch {
          errorBody = { detail: response.statusText };
        }

        const message = errorBody.detail ?? errorBody.message ?? `HTTP ${response.status}`;
        throw errorFromResponse(response.status, message, errorBody.details, response.headers);
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          if (options?.signal?.aborted) {
            throw error; // User cancelled, don't retry
          }
          lastError = new TimeoutError(`Request timed out after ${this.timeout}ms`, this.timeout);
        } else if (error instanceof TypeError && error.message.includes('fetch')) {
          lastError = new NetworkError(`Failed to connect to ${this.baseUrl}`, error);
        } else if (error instanceof Error) {
          lastError = error;
        } else {
          lastError = new Error(String(error));
        }

        // Don't retry if not retryable or last attempt
        if (!this.shouldRetry(lastError) || attempt >= this.maxRetries) {
          throw lastError;
        }

        // Wait before retry
        const delay = this.getRetryDelay(attempt, lastError);
        await sleep(delay);
      }
    }

    throw lastError ?? new NetworkError('Request failed after all retries');
  }

  async get<T>(
    path: string,
    options?: { params?: Record<string, string>; signal?: AbortSignal }
  ): Promise<T> {
    return this.request<T>('GET', path, options);
  }

  async post<T>(
    path: string,
    options?: {
      body?: Record<string, unknown>;
      idempotencyKey?: string;
      signal?: AbortSignal;
    }
  ): Promise<T> {
    return this.request<T>('POST', path, options);
  }

  async put<T>(
    path: string,
    options?: {
      body?: Record<string, unknown>;
      idempotencyKey?: string;
      signal?: AbortSignal;
    }
  ): Promise<T> {
    return this.request<T>('PUT', path, options);
  }

  async delete<T>(path: string, options?: { signal?: AbortSignal }): Promise<T> {
    return this.request<T>('DELETE', path, options);
  }
}

/**
 * Sleep for a given number of milliseconds.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Create an AbortSignal that aborts when any of the given signals abort.
 */
function anySignal(signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController();

  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      return controller.signal;
    }

    signal.addEventListener('abort', () => controller.abort(signal.reason), {
      signal: controller.signal,
    });
  }

  return controller.signal;
}
