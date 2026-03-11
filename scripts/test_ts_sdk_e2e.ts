/**
 * End-to-end test for the ReinforceSpec TypeScript SDK against production.
 *
 * Run: npx ts-node scripts/test_ts_sdk_e2e.ts
 * Or:  cd sdks/typescript && npm run build && cd ../.. && node scripts/test_ts_sdk_e2e.js
 */

// ALB endpoint - HTTPS with self-signed cert
const BASE_URL = 'https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com';

// Disable TLS verification for ALB direct access
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

interface TestResult {
  passed: boolean;
  requestId?: string;
}

async function main(): Promise<void> {
  console.log('============================================================');
  console.log('ReinforceSpec TypeScript SDK End-to-End Test');
  console.log(`Target: ${BASE_URL}`);
  console.log(`Timestamp: ${new Date().toISOString()}`);
  console.log('============================================================');

  let passed = 0;
  const total = 4;
  let requestId: string | undefined;

  // Test 1: Health
  console.log('\n1. Testing health endpoint (GET /v1/health)...');
  if (await testHealth()) {
    passed++;
  }

  // Test 2: Policy status
  console.log('\n2. Testing policy status (GET /v1/policy/status)...');
  if (await testPolicyStatus()) {
    passed++;
  }

  // Test 3: Spec selection
  console.log('\n3. Testing spec selection (POST /v1/specs)...');
  console.log('   This may take up to 60 seconds for LLM scoring...');
  const selectResult = await testSelect();
  if (selectResult.passed) {
    passed++;
    requestId = selectResult.requestId;
  }

  // Test 4: Feedback
  if (requestId) {
    console.log('\n4. Testing feedback submission (POST /v1/specs/feedback)...');
    if (await testFeedback(requestId)) {
      passed++;
    }
  } else {
    console.log('\n4. Skipping feedback test (no request ID from selection)...');
  }

  // Summary
  console.log('\n============================================================');
  const result = passed === total ? 'PASSED' : 'FAILED';
  console.log(`Results: ${passed}/${total} tests passed - ${result}`);
  console.log('============================================================');

  if (passed !== total) {
    process.exit(1);
  }
}

async function testHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/v1/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    if (!response.ok) {
      console.log(`   ✗ Unexpected status: ${response.status}`);
      return false;
    }

    const data = (await response.json()) as { status: string; version: string };
    console.log(`   ✓ Status: ${data.status}`);
    console.log(`   ✓ Version: ${data.version}`);
    return true;
  } catch (err) {
    console.log(`   ✗ Failed: ${err}`);
    return false;
  }
}

async function testPolicyStatus(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/v1/policy/status`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    if (!response.ok) {
      console.log(`   ✗ Unexpected status: ${response.status}`);
      return false;
    }

    const data = (await response.json()) as { version: string; stage: string };
    console.log(`   ✓ Version: ${data.version}`);
    console.log(`   ✓ Stage: ${data.stage}`);
    return true;
  } catch (err) {
    console.log(`   ✗ Failed: ${err}`);
    return false;
  }
}

async function testSelect(): Promise<TestResult> {
  try {
    const payload = {
      candidates: [
        {
          content:
            '# API Specification\n\n## Authentication\n- OAuth 2.0 with PKCE\n- API key authentication\n- JWT token validation\n',
          source_model: 'gpt-4',
          spec_type: 'api_spec',
        },
        {
          content:
            "openapi: '3.0.3'\ninfo:\n  title: Sample API\n  version: '1.0.0'\npaths:\n  /users:\n    get:\n      summary: List users\n",
          source_model: 'claude-3',
          spec_type: 'api_spec',
        },
      ],
      selection_method: 'hybrid',
      description: 'TypeScript SDK E2E test',
    };

    const response = await fetch(`${BASE_URL}/v1/specs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const body = await response.text();
      console.log(`   ✗ HTTP Error: ${response.status} - ${body}`);
      return { passed: false };
    }

    const data = (await response.json()) as {
      request_id: string;
      selected: {
        index: number;
        composite_score: number;
        dimension_scores?: Array<{ dimension: string; score: number }>;
      };
      selection_method: string;
      selection_confidence: number;
      latency_ms: number;
    };

    console.log(`   ✓ Request ID: ${data.request_id}`);
    console.log(`   ✓ Selected candidate: ${data.selected.index}`);
    console.log(`   ✓ Composite score: ${data.selected.composite_score.toFixed(2)}`);
    console.log(`   ✓ Selection method: ${data.selection_method}`);
    console.log(`   ✓ Selection confidence: ${data.selection_confidence.toFixed(2)}`);
    console.log(`   ✓ Latency: ${data.latency_ms.toFixed(0)}ms`);

    if (data.selected.dimension_scores) {
      console.log('   ✓ Dimension scores:');
      for (const score of data.selected.dimension_scores) {
        console.log(`      - ${score.dimension}: ${score.score.toFixed(1)}`);
      }
    }

    return { passed: true, requestId: data.request_id };
  } catch (err) {
    console.log(`   ✗ Failed: ${err}`);
    return { passed: false };
  }
}

async function testFeedback(requestId: string): Promise<boolean> {
  try {
    const payload = {
      request_id: requestId,
      rating: 4.5,
      comment: `TypeScript SDK E2E test feedback at ${new Date().toISOString()}`,
    };

    const response = await fetch(`${BASE_URL}/v1/specs/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const body = await response.text();
      console.log(`   ✗ HTTP Error: ${response.status} - ${body}`);
      return false;
    }

    const data = (await response.json()) as { feedback_id: string; status: string };
    console.log(`   ✓ Feedback ID: ${data.feedback_id}`);
    console.log(`   ✓ Status: ${data.status}`);
    return true;
  } catch (err) {
    console.log(`   ✗ Failed: ${err}`);
    return false;
  }
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
