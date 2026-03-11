# ReinforceSpec TypeScript SDK

Official TypeScript/JavaScript SDK for the [ReinforceSpec API](https://docs.reinforce-spec.dev) - LLM output evaluation and selection using multi-judge scoring and reinforcement learning.

## Installation

### From AWS CodeArtifact (Private)

```bash
# Login to CodeArtifact
aws codeartifact login --tool npm --domain reinforce-spec --repository npm-packages

# Install
npm install @reinforce-spec/sdk
```

### From Source

```bash
git clone https://github.com/reinforce-spec/sdk-typescript.git
cd sdk-typescript
npm install
npm run build
```

## Quick Start

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';

const client = new ReinforceSpecClient({
  baseUrl: 'https://api.reinforce-spec.dev',
  apiKey: 'your-api-key',
});

// Evaluate and select best spec
const response = await client.select({
  candidates: [
    { content: 'First LLM output...' },
    { content: 'Second LLM output...' },
  ],
  selectionMethod: 'hybrid',
});

console.log(`Selected: ${response.selected.index}`);
console.log(`Score: ${response.selected.compositeScore}`);
console.log(`Confidence: ${response.selectionConfidence}`);
```

## Configuration

### Environment Variables

```bash
export REINFORCE_SPEC_BASE_URL="https://api.reinforce-spec.dev"
export REINFORCE_SPEC_API_KEY="your-api-key"
export REINFORCE_SPEC_TIMEOUT="30000"
```

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';

// Loads from environment
const client = ReinforceSpecClient.fromEnv();
```

### Client Options

```typescript
const client = new ReinforceSpecClient({
  baseUrl: 'https://api.reinforce-spec.dev',
  apiKey: 'your-api-key',
  timeout: 30000,           // Request timeout in ms
  maxRetries: 3,            // Max retry attempts
  retryDelay: 1000,         // Initial retry delay in ms
  retryMaxDelay: 30000,     // Max retry delay in ms
});
```

## API Reference

### `client.select()`

Evaluate candidates and select the best one.

```typescript
const response = await client.select({
  candidates: [
    { content: '...', sourceModel: 'gpt-4', metadata: {} },
    { content: '...', sourceModel: 'claude-3' },
  ],
  selectionMethod: 'hybrid',  // 'hybrid' | 'scoring_only' | 'rl_only'
  requestId: 'unique-id',     // Idempotency key
  description: 'API spec...', // Context for scoring
});
```

**Returns:** `SelectionResponse`

### `client.submitFeedback()`

Submit human feedback for reinforcement learning.

```typescript
const feedbackId = await client.submitFeedback({
  requestId: 'original-request-id',
  rating: 4.5,                // 1.0-5.0
  comment: 'Good structure',
  specId: 'selected-spec-id',
});
```

**Returns:** `string` (feedback ID)

### `client.getPolicyStatus()`

Get the current RL policy status.

```typescript
const status = await client.getPolicyStatus();
console.log(`Version: ${status.version}`);
console.log(`Stage: ${status.stage}`);
console.log(`Mean Reward: ${status.meanReward}`);
```

**Returns:** `PolicyStatus`

### `client.health()`

Check API health.

```typescript
const health = await client.health();
console.log(`Status: ${health.status}`);
```

**Returns:** `HealthResponse`

## Error Handling

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';
import {
  ReinforceSpecError,
  ValidationError,
  RateLimitError,
  ServerError,
} from '@reinforce-spec/sdk/errors';

const client = new ReinforceSpecClient({ ... });

try {
  const response = await client.select({ candidates: [...] });
} catch (error) {
  if (error instanceof ValidationError) {
    console.log(`Invalid input: ${error.message}`);
    console.log(`Details: ${JSON.stringify(error.details)}`);
  } else if (error instanceof RateLimitError) {
    console.log(`Rate limited. Retry after: ${error.retryAfter}ms`);
  } else if (error instanceof ServerError) {
    console.log(`Server error: ${error.statusCode}`);
  } else if (error instanceof ReinforceSpecError) {
    console.log(`API error: ${error.message}`);
  }
}
```

## Types

All request and response types are fully typed:

```typescript
import {
  // Enums
  SelectionMethod,
  SpecFormat,
  PolicyStage,
  
  // Request types
  SpecInput,
  SelectRequest,
  FeedbackRequest,
  
  // Response types
  SelectionResponse,
  CandidateSpec,
  DimensionScore,
  PolicyStatus,
  HealthResponse,
} from '@reinforce-spec/sdk';
```

## Browser Usage

The SDK works in both Node.js and browser environments:

```typescript
// Browser with fetch (default)
const client = new ReinforceSpecClient({
  baseUrl: 'https://api.reinforce-spec.dev',
  apiKey: 'your-api-key',
});

// Request cancellation with AbortController
const controller = new AbortController();
const response = await client.select({
  candidates: [...],
}, { signal: controller.signal });

// Cancel request
controller.abort();
```

## Testing

```typescript
import { MockClient } from '@reinforce-spec/sdk/testing';

// Create mock client for tests
const client = new MockClient({
  selectResponse: {
    requestId: 'test-123',
    selected: { index: 0, compositeScore: 4.5, ... },
    ...
  },
});

// Use in tests
const response = await client.select({ candidates: [...] });
expect(response.selected.index).toBe(0);
```

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Run tests
npm test

# Type checking
npm run typecheck

# Linting
npm run lint
```

## License

MIT License - see [LICENSE](LICENSE) for details.
