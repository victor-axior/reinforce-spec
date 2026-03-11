# TypeScript SDK

The official TypeScript/JavaScript client for ReinforceSpec with full type definitions, automatic retries, and modern async/await support.

---

## Installation

=== "npm"

    ```bash
    npm install @reinforce-spec/sdk
    ```

=== "yarn"

    ```bash
    yarn add @reinforce-spec/sdk
    ```

=== "pnpm"

    ```bash
    pnpm add @reinforce-spec/sdk
    ```

### Requirements

| Requirement | Minimum Version |
|-------------|-----------------|
| Node.js | 18+ |
| TypeScript | 5.0+ (optional) |

---

## Quick Start

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';

const client = new ReinforceSpecClient({
  baseUrl: 'https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com',
  apiKey: process.env.REINFORCE_SPEC_API_KEY,
});

const response = await client.select({
  candidates: [
    { content: '# API Spec A\nOAuth2 authentication...' },
    { content: '# API Spec B\nBasic auth...' },
  ],
});

console.log(`Selected: Spec ${response.selected.index + 1}`);
console.log(`Score: ${response.selected.compositeScore.toFixed(2)}`);

// Don't forget to close the client
await client.close();
```

---

## Client Configuration

### Constructor Options

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';

const client = new ReinforceSpecClient({
  // Required
  baseUrl: 'https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com',
  
  // Optional
  apiKey: 'your-api-key',
  timeout: 30000,           // Request timeout in ms (default: 30000)
  maxRetries: 3,            // Max retry attempts (default: 3)
  retryDelay: 1000,         // Initial retry delay in ms (default: 1000)
  retryMaxDelay: 30000,     // Max retry delay in ms (default: 30000)
  
  // Hooks for logging/debugging
  onRequest: (req) => console.log('Request:', req.url),
  onResponse: (res) => console.log('Response:', res.status),
});
```

### Environment Variables

Create client from environment variables:

```typescript
const client = ReinforceSpecClient.fromEnv();
```

Required environment variables:

| Variable | Description |
|----------|-------------|
| `REINFORCE_SPEC_BASE_URL` | API base URL (required) |
| `REINFORCE_SPEC_API_KEY` | API authentication key |
| `REINFORCE_SPEC_TIMEOUT` | Request timeout in ms |
| `REINFORCE_SPEC_MAX_RETRIES` | Max retry attempts |

---

## Core Methods

### select()

Evaluate and select the best specification from candidates.

```typescript
const response = await client.select({
  candidates: [
    { 
      content: 'spec A content', 
      specType: 'api',
      sourceModel: 'claude-3-opus',
      metadata: { version: '2.0' }
    },
    { content: 'spec B content', specType: 'api' },
  ],
  description: 'API for payment processing',
  selectionMethod: 'hybrid', // 'scoring_only' | 'hybrid' | 'rl_only'
  requestId: 'unique-request-id', // Optional idempotency key
});

console.log(response.requestId);
console.log(response.selected.index);
console.log(response.selected.compositeScore);
console.log(response.allCandidates);
```

### submitFeedback()

Submit human feedback for RL training.

```typescript
const feedbackId = await client.submitFeedback({
  requestId: 'prev-request-id',
  rating: 4.5,           // 1.0 to 5.0
  comment: 'Good result',
  specId: 'selected-spec-id', // Optional
});

console.log(`Feedback submitted: ${feedbackId}`);
```

### getPolicyStatus()

Get RL policy status and metrics.

```typescript
const status = await client.getPolicyStatus();

console.log(`Version: ${status.version}`);
console.log(`Stage: ${status.stage}`);
console.log(`Episodes: ${status.episodeCount}`);
console.log(`Explore Rate: ${status.exploreRate}`);
```

### trainPolicy()

Trigger policy training iteration.

```typescript
const result = await client.trainPolicy(256); // n_steps

console.log(`Job ID: ${result.jobId}`);
console.log(`Status: ${result.status}`);
```

### health() / ready()

Health and readiness checks.

```typescript
const health = await client.health();
console.log(`Status: ${health.status}`);
console.log(`Version: ${health.version}`);

const ready = await client.ready();
console.log(`Ready: ${ready.status === 'healthy'}`);
```

---

## Types

### SelectRequest

```typescript
interface SelectRequest {
  candidates: CandidateInput[];
  description?: string;
  selectionMethod?: 'scoring_only' | 'hybrid' | 'rl_only';
  requestId?: string;
}

interface CandidateInput {
  content: string;        // Required: spec content
  specType?: string;      // Optional: 'api', 'srs', 'prd', etc.
  sourceModel?: string;   // Optional: LLM that generated this
  metadata?: Record<string, unknown>;
}
```

### SelectionResponse

```typescript
interface SelectionResponse {
  requestId: string;
  selected: SelectedCandidate;
  allCandidates: CandidateSummary[];
  selectionMethod: string;
  processingTime: number;
}

interface SelectedCandidate {
  index: number;
  content: string;
  specType?: string;
  format: string;
  compositeScore: number;
  dimensionScores: Record<string, number>;
}
```

---

## Error Handling

```typescript
import {
  ReinforceSpecClient,
  ReinforceSpecError,
  ValidationError,
  RateLimitError,
  AuthenticationError,
} from '@reinforce-spec/sdk';

try {
  const response = await client.select({ candidates: [...] });
} catch (error) {
  if (error instanceof RateLimitError) {
    console.log(`Rate limited. Retry after ${error.retryAfter}s`);
  } else if (error instanceof ValidationError) {
    console.log(`Validation error: ${error.message}`);
    console.log(`Fields: ${error.fields}`);
  } else if (error instanceof AuthenticationError) {
    console.log('Invalid API key');
  } else if (error instanceof ReinforceSpecError) {
    console.log(`API error: ${error.message}`);
  }
}
```

---

## Usage in Different Environments

### Node.js

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';

async function main() {
  const client = ReinforceSpecClient.fromEnv();
  // ... use client
  await client.close();
}

main();
```

### Browser (with bundler)

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';

const client = new ReinforceSpecClient({
  baseUrl: '/api/proxy', // Use backend proxy for API key security
});

const response = await client.select({ candidates: [...] });
```

### Next.js API Route

```typescript
// pages/api/evaluate.ts
import { ReinforceSpecClient } from '@reinforce-spec/sdk';
import type { NextApiRequest, NextApiResponse } from 'next';

const client = ReinforceSpecClient.fromEnv();

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const response = await client.select(req.body);
  res.status(200).json(response);
}
```

---

## See Also

- [Python SDK](python.md)
- [Go SDK](go.md)
- [HTTP/REST API](http.md)
