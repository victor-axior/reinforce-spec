/**
 * Tests for testing utilities.
 */

import {
  MockClient,
  makeDimensionScore,
  makeCandidate,
  makeSelectionResponse,
  makePolicyStatus,
} from '../src/testing';
import { PolicyStage, SpecFormat } from '../src/types';

describe('MockClient', () => {
  it('should return default select response', async () => {
    const client = new MockClient();
    const response = await client.select({
      candidates: [{ content: 'A' }, { content: 'B' }],
    });
    expect(response.requestId).toBe('test-request-123');
    expect(response.selected.index).toBe(0);
  });

  it('should return custom select response', async () => {
    const custom = makeSelectionResponse({ requestId: 'custom-id', selectedIndex: 1 });
    const client = new MockClient({ selectResponse: custom });
    const response = await client.select({ candidates: [{ content: 'A' }, { content: 'B' }] });
    expect(response.requestId).toBe('custom-id');
    expect(response.selected.index).toBe(1);
  });

  it('should record feedback calls', async () => {
    const client = new MockClient();
    const id1 = await client.submitFeedback({ requestId: 'r1', rating: 4.0 });
    const id2 = await client.submitFeedback({ requestId: 'r2', rating: 5.0 });
    expect(id1).toBe('feedback-1');
    expect(id2).toBe('feedback-2');
    expect(client.getFeedbackCalls()).toHaveLength(2);
  });

  it('should return health response', async () => {
    const client = new MockClient();
    const health = await client.health();
    expect(health.status).toBe('healthy');
  });

  it('should return policy status', async () => {
    const client = new MockClient();
    const status = await client.getPolicyStatus();
    expect(status.version).toBe('v001');
  });
});

describe('Factory functions', () => {
  describe('makeDimensionScore', () => {
    it('should create with defaults', () => {
      const score = makeDimensionScore();
      expect(score.dimension).toBe('Accuracy');
      expect(score.score).toBe(4.0);
    });

    it('should accept overrides', () => {
      const score = makeDimensionScore({ dimension: 'Clarity', score: 3.5 });
      expect(score.dimension).toBe('Clarity');
      expect(score.score).toBe(3.5);
    });
  });

  describe('makeCandidate', () => {
    it('should create with defaults', () => {
      const candidate = makeCandidate();
      expect(candidate.index).toBe(0);
      expect(candidate.format).toBe(SpecFormat.Text);
      expect(candidate.dimensionScores).toHaveLength(3);
    });

    it('should accept overrides', () => {
      const candidate = makeCandidate({ index: 2, compositeScore: 4.5 });
      expect(candidate.index).toBe(2);
      expect(candidate.compositeScore).toBe(4.5);
    });
  });

  describe('makeSelectionResponse', () => {
    it('should create with defaults', () => {
      const resp = makeSelectionResponse();
      expect(resp.allCandidates).toHaveLength(2);
      expect(resp.selected.index).toBe(0);
    });

    it('should create with custom candidate count', () => {
      const resp = makeSelectionResponse({ numCandidates: 5 });
      expect(resp.allCandidates).toHaveLength(5);
    });
  });

  describe('makePolicyStatus', () => {
    it('should create with defaults', () => {
      const status = makePolicyStatus();
      expect(status.version).toBe('v001');
      expect(status.stage).toBe(PolicyStage.Production);
    });

    it('should accept overrides', () => {
      const status = makePolicyStatus({ version: 'v002', stage: PolicyStage.Canary });
      expect(status.version).toBe('v002');
      expect(status.stage).toBe(PolicyStage.Canary);
    });
  });
});
