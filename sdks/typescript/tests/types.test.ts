/**
 * Tests for type converters.
 */

import {
  convertCandidateSpec,
  convertSelectionResponse,
  convertFeedbackResponse,
  convertPolicyStatus,
  convertHealthResponse,
  SelectionMethod,
  SpecFormat,
  PolicyStage,
} from '../src/types';
import type {
  ApiCandidateSpec,
  ApiSelectionResponse,
  ApiFeedbackResponse,
  ApiPolicyStatus,
  ApiHealthResponse,
} from '../src/types';

describe('Type converters', () => {
  describe('convertCandidateSpec', () => {
    it('should convert snake_case to camelCase', () => {
      const api: ApiCandidateSpec = {
        index: 0,
        content: 'test',
        format: 'text',
        spec_type: 'api_spec',
        source_model: 'gpt-4',
        dimension_scores: [
          { dimension: 'Accuracy', score: 4.0, justification: 'Good', confidence: 0.9 },
        ],
        composite_score: 4.0,
        judge_models: ['claude-3'],
        metadata: { key: 'value' },
      };

      const result = convertCandidateSpec(api);

      expect(result.specType).toBe('api_spec');
      expect(result.sourceModel).toBe('gpt-4');
      expect(result.dimensionScores).toHaveLength(1);
      expect(result.compositeScore).toBe(4.0);
      expect(result.judgeModels).toEqual(['claude-3']);
      expect(result.format).toBe(SpecFormat.Text);
    });
  });

  describe('convertSelectionResponse', () => {
    it('should convert all nested fields', () => {
      const api: ApiSelectionResponse = {
        request_id: 'test-123',
        selected: {
          index: 0,
          content: 'test',
          format: 'text',
          spec_type: 'api_spec',
          dimension_scores: [],
          composite_score: 4.0,
          judge_models: [],
        },
        all_candidates: [],
        selection_method: 'hybrid',
        selection_confidence: 0.85,
        scoring_summary: { Accuracy: 4.0 },
        latency_ms: 150,
        timestamp: '2025-01-01T00:00:00Z',
      };

      const result = convertSelectionResponse(api);

      expect(result.requestId).toBe('test-123');
      expect(result.selectionMethod).toBe(SelectionMethod.Hybrid);
      expect(result.selectionConfidence).toBe(0.85);
      expect(result.latencyMs).toBe(150);
    });
  });

  describe('convertFeedbackResponse', () => {
    it('should convert feedback fields', () => {
      const api: ApiFeedbackResponse = {
        feedback_id: 'fb-123',
        request_id: 'req-456',
        received_at: '2025-01-01T00:00:00Z',
      };

      const result = convertFeedbackResponse(api);

      expect(result.feedbackId).toBe('fb-123');
      expect(result.requestId).toBe('req-456');
      expect(result.receivedAt).toBe('2025-01-01T00:00:00Z');
    });
  });

  describe('convertPolicyStatus', () => {
    it('should convert policy fields', () => {
      const api: ApiPolicyStatus = {
        version: 'v001',
        stage: 'production',
        training_episodes: 10000,
        mean_reward: 0.75,
        explore_rate: 0.1,
        drift_psi: 0.05,
        last_trained: '2025-01-01T00:00:00Z',
      };

      const result = convertPolicyStatus(api);

      expect(result.version).toBe('v001');
      expect(result.stage).toBe(PolicyStage.Production);
      expect(result.trainingEpisodes).toBe(10000);
      expect(result.meanReward).toBe(0.75);
      expect(result.exploreRate).toBe(0.1);
      expect(result.driftPsi).toBe(0.05);
      expect(result.lastTrained).toBe('2025-01-01T00:00:00Z');
    });
  });

  describe('convertHealthResponse', () => {
    it('should convert health fields', () => {
      const api: ApiHealthResponse = {
        status: 'healthy',
        version: '1.0.0',
        uptime_seconds: 3600,
      };

      const result = convertHealthResponse(api);

      expect(result.status).toBe('healthy');
      expect(result.version).toBe('1.0.0');
      expect(result.uptimeSeconds).toBe(3600);
    });
  });
});
