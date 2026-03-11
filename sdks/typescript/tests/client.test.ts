/**
 * Tests for the ReinforceSpecClient.
 */

import { ReinforceSpecClient } from '../src/client';
import { HttpClient } from '../src/http';
import { SelectionMethod } from '../src/types';
import type { ApiSelectionResponse, ApiPolicyStatus, ApiHealthResponse } from '../src/types';

// Mock HttpClient
jest.mock('../src/http');

const MockHttpClient = HttpClient as jest.MockedClass<typeof HttpClient>;

function createClient(): ReinforceSpecClient {
  return new ReinforceSpecClient({
    baseUrl: 'https://api.reinforce-spec.dev',
    apiKey: 'test-key',
  });
}

function mockApiSelectionResponse(): ApiSelectionResponse {
  return {
    request_id: 'test-123',
    selected: {
      index: 0,
      content: 'Test content',
      format: 'text',
      spec_type: 'api_spec',
      source_model: 'gpt-4',
      dimension_scores: [
        { dimension: 'Accuracy', score: 4.0, justification: 'Good', confidence: 0.9 },
      ],
      composite_score: 4.0,
      judge_models: ['claude-3'],
    },
    all_candidates: [],
    selection_method: 'hybrid',
    selection_confidence: 0.85,
    scoring_summary: { Accuracy: 4.0 },
    latency_ms: 150,
    timestamp: '2025-01-01T00:00:00Z',
  };
}

describe('ReinforceSpecClient', () => {
  let client: ReinforceSpecClient;

  beforeEach(() => {
    MockHttpClient.mockClear();
    client = createClient();
  });

  describe('select', () => {
    it('should return a parsed SelectionResponse', async () => {
      const mockResponse = mockApiSelectionResponse();
      MockHttpClient.prototype.post.mockResolvedValueOnce(mockResponse);

      const response = await client.select({
        candidates: [{ content: 'First' }, { content: 'Second' }],
      });

      expect(response.requestId).toBe('test-123');
      expect(response.selected.index).toBe(0);
      expect(response.selectionConfidence).toBe(0.85);
    });

    it('should use default selection method', async () => {
      MockHttpClient.prototype.post.mockResolvedValueOnce(mockApiSelectionResponse());

      await client.select({
        candidates: [{ content: 'A' }, { content: 'B' }],
      });

      expect(MockHttpClient.prototype.post).toHaveBeenCalledWith(
        '/v1/specs',
        expect.objectContaining({
          body: expect.objectContaining({
            selection_method: SelectionMethod.Hybrid,
          }),
        }),
      );
    });

    it('should generate a request ID when not provided', async () => {
      MockHttpClient.prototype.post.mockResolvedValueOnce(mockApiSelectionResponse());

      await client.select({
        candidates: [{ content: 'A' }, { content: 'B' }],
      });

      const callArgs = MockHttpClient.prototype.post.mock.calls[0];
      const body = (callArgs[1] as { body: Record<string, unknown> }).body;
      expect(body.request_id).toBeDefined();
      expect(typeof body.request_id).toBe('string');
    });
  });

  describe('submitFeedback', () => {
    it('should return feedback id', async () => {
      MockHttpClient.prototype.post.mockResolvedValueOnce({
        feedback_id: 'fb-123',
        request_id: 'req-456',
        received_at: '2025-01-01T00:00:00Z',
      });

      const feedbackId = await client.submitFeedback({
        requestId: 'req-456',
        rating: 4.5,
        comment: 'Great result',
      });

      expect(feedbackId).toBe('fb-123');
    });
  });

  describe('getPolicyStatus', () => {
    it('should return parsed policy status', async () => {
      const apiResponse: ApiPolicyStatus = {
        version: 'v001',
        stage: 'production',
        training_episodes: 10000,
        mean_reward: 0.75,
        explore_rate: 0.1,
        drift_psi: 0.05,
      };
      MockHttpClient.prototype.get.mockResolvedValueOnce(apiResponse);

      const status = await client.getPolicyStatus();

      expect(status.version).toBe('v001');
      expect(status.stage).toBe('production');
      expect(status.meanReward).toBe(0.75);
    });
  });

  describe('health', () => {
    it('should return parsed health response', async () => {
      const apiResponse: ApiHealthResponse = {
        status: 'healthy',
        version: '1.0.0',
        uptime_seconds: 3600,
      };
      MockHttpClient.prototype.get.mockResolvedValueOnce(apiResponse);

      const health = await client.health();

      expect(health.status).toBe('healthy');
      expect(health.version).toBe('1.0.0');
      expect(health.uptimeSeconds).toBe(3600);
    });
  });

  describe('close', () => {
    it('should mark client as closed', () => {
      expect(client.closed).toBe(false);
      client.close();
      expect(client.closed).toBe(true);
    });
  });

  describe('fromEnv', () => {
    const originalEnv = process.env;

    afterEach(() => {
      process.env = originalEnv;
    });

    it('should throw when REINFORCE_SPEC_BASE_URL is not set', () => {
      process.env = { ...originalEnv };
      delete process.env.REINFORCE_SPEC_BASE_URL;
      expect(() => ReinforceSpecClient.fromEnv()).toThrow('REINFORCE_SPEC_BASE_URL');
    });

    it('should create client from env vars', () => {
      process.env = {
        ...originalEnv,
        REINFORCE_SPEC_BASE_URL: 'https://api.example.com',
        REINFORCE_SPEC_API_KEY: 'test-key',
      };
      const envClient = ReinforceSpecClient.fromEnv();
      expect(envClient).toBeInstanceOf(ReinforceSpecClient);
    });
  });
});
