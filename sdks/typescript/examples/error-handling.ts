/**
 * Error handling example.
 *
 * Usage:
 *   npx ts-node examples/error-handling.ts
 */

import {
  ReinforceSpecClient,
  ReinforceSpecError,
  ValidationError,
  RateLimitError,
  AuthenticationError,
  NetworkError,
} from '@reinforce-spec/sdk';

async function main() {
  const client = new ReinforceSpecClient({
    baseUrl: 'https://api.reinforce-spec.dev',
    apiKey: 'your-api-key',
  });

  try {
    const response = await client.select({
      candidates: [{ content: 'A' }, { content: 'B' }],
    });
    console.log(`Selected: ${response.selected.index}`);
  } catch (error) {
    if (error instanceof ValidationError) {
      console.error(`Validation failed: ${error.message}`);
      console.error(`Field: ${error.field}`);
    } else if (error instanceof RateLimitError) {
      console.error(`Rate limited. Retry after ${error.retryAfter}ms`);
    } else if (error instanceof AuthenticationError) {
      console.error('Invalid API key');
    } else if (error instanceof NetworkError) {
      console.error(`Network error: ${error.message}`);
    } else if (error instanceof ReinforceSpecError) {
      console.error(`API error [${error.statusCode}]: ${error.message}`);
    } else {
      throw error;
    }
  } finally {
    client.close();
  }
}

main().catch(console.error);
