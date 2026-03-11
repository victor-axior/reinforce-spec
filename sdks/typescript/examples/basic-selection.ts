/**
 * Basic selection example using the ReinforceSpec SDK.
 *
 * Usage:
 *   npx ts-node examples/basic-selection.ts
 */

import { ReinforceSpecClient, SelectionMethod } from '@reinforce-spec/sdk';

async function main() {
  const client = new ReinforceSpecClient({
    baseUrl: 'https://api.reinforce-spec.dev',
    apiKey: 'your-api-key',
  });

  try {
    const response = await client.select({
      candidates: [
        { content: 'First LLM output', sourceModel: 'gpt-4' },
        { content: 'Second LLM output', sourceModel: 'claude-3' },
      ],
      selectionMethod: SelectionMethod.Hybrid,
      description: 'Compare LLM outputs for quality',
    });

    console.log(`Selected candidate: ${response.selected.index}`);
    console.log(`Composite score: ${response.selected.compositeScore.toFixed(2)}`);
    console.log(`Confidence: ${response.selectionConfidence.toFixed(2)}`);

    for (const score of response.selected.dimensionScores) {
      console.log(`  ${score.dimension}: ${score.score.toFixed(1)} (${(score.confidence * 100).toFixed(0)}%)`);
    }
  } finally {
    client.close();
  }
}

main().catch(console.error);
