# Quickstart

Get ReinforceSpec running and evaluate your first specifications in under 5 minutes.

---

## Step 1: Install the SDK

=== "Python (pip)"

    ```bash
    pip install reinforce-spec-sdk
    ```

=== "TypeScript (npm)"

    ```bash
    npm install @reinforce-spec/sdk
    ```

=== "Go"

    ```bash
    go get github.com/reinforce-spec/reinforce-spec/sdks/go
    ```

---

## Step 2: Set Your API Key

ReinforceSpec uses [OpenRouter](https://openrouter.ai) to access multiple LLM providers. Get your API key and set it as an environment variable:

=== "Linux/macOS"

    ```bash
    export OPENROUTER_API_KEY="sk-or-v1-your-key-here"
    ```

=== "Windows (PowerShell)"

    ```powershell
    $env:OPENROUTER_API_KEY = "sk-or-v1-your-key-here"
    ```

=== ".env file"

    ```bash title=".env"
    OPENROUTER_API_KEY=sk-or-v1-your-key-here
    ```

!!! tip "Using a `.env` file"
    ReinforceSpec automatically loads environment variables from a `.env` file in your project root.

---

## Step 3: Evaluate Your First Specs

=== "Python"

    ```python title="quickstart.py"
    import asyncio
    from reinforce_spec_sdk import ReinforceSpecClient


    async def main():
        # Initialize the client
        async with ReinforceSpecClient(
            base_url="https://reinforce-spec-alb-1758221004.us-east-1.elb.amazonaws.com",
            api_key="your-api-key",  # or use .from_env()
        ) as client:
            # Define your specification candidates
            candidates = [
                {
                    "content": """
                    # Payment API v2
                    
                    ## Security
                    - OAuth 2.0 with PKCE
                    - mTLS for service-to-service
                    - AES-256 encryption at rest
                    
                    ## Compliance
                    - PCI DSS Level 1
                    - SOC 2 Type II
                    """,
                    "spec_type": "api",
                },
                {
                    "content": """
                    # Payment API v1
                    
                    ## Security
                    - API key authentication
                    - HTTPS only
                    
                    ## Compliance
                    - Basic SSL/TLS
                    """,
                    "spec_type": "api",
                },
            ]
            
            # Evaluate and select the best spec
            result = await client.select(
                candidates=candidates,
                description="Payment API security comparison",
            )
            
            # Print results
            print(f"Selected spec index: {result.selected.index}")
            print(f"Composite score: {result.selected.composite_score:.3f}")
            
            print("\nDimension Scores:")
            for dim, score in result.selected.dimension_scores.items():
                print(f"   {dim}: {score:.2f}")


    if __name__ == "__main__":
        asyncio.run(main())
    ```

    Run it:

    ```bash
    python quickstart.py
    ```

=== "TypeScript"

    ```typescript title="quickstart.ts"
    import { ReinforceSpecClient } from '@reinforce-spec/sdk';

    async function main() {
      const client = new ReinforceSpecClient({
        baseUrl: process.env.REINFORCE_SPEC_BASE_URL!,
        apiKey: process.env.REINFORCE_SPEC_API_KEY,
      });

      const result = await client.select({
        candidates: [
          {
            content: `# Payment API v2\n## Security\n- OAuth 2.0 with PKCE`,
            specType: 'api',
          },
          {
            content: `# Payment API v1\n## Security\n- API key only`,
            specType: 'api',
          },
        ],
        description: 'Payment API security comparison',
      });

      console.log(`Selected: ${result.selected.index}`);
      console.log(`Score: ${result.selected.compositeScore.toFixed(3)}`);
    }

    main();
    ```

    Run it:

    ```bash
    npx ts-node quickstart.ts
    ```

=== "Go"

    ```go title="quickstart.go"
    package main

    import (
        "context"
        "fmt"
        "os"

        reinforce "github.com/reinforce-spec/reinforce-spec/sdks/go"
    )

    func main() {
        client := reinforce.NewClient(
            reinforce.WithBaseURL(os.Getenv("REINFORCE_SPEC_BASE_URL")),
            reinforce.WithAPIKey(os.Getenv("REINFORCE_SPEC_API_KEY")),
        )

        resp, err := client.Select(context.Background(), &reinforce.SelectRequest{
            Candidates: []reinforce.Candidate{
                {Content: "# Payment API v2\n- OAuth 2.0", SpecType: "api"},
                {Content: "# Payment API v1\n- API key", SpecType: "api"},
            },
            Description: "Payment API security comparison",
        })
        if err != nil {
            panic(err)
        }

        fmt.Printf("Selected: %d\n", resp.Selected.Index)
        fmt.Printf("Score: %.3f\n", resp.Selected.CompositeScore)
    }
    ```

    Run it:

    ```bash
    go run quickstart.go
    ```

---

## Step 4: View the Results

You'll see output like this:

```
✅ Selected spec index: 0
📊 Composite score: 0.847
⏱️  Latency: 2847ms

📈 Dimension Scores:
   security: 0.95
   compliance: 0.92
   scalability: 0.78
   maintainability: 0.85
   testability: 0.82
   ...
```

The first spec (Payment API v2) was selected because it scored higher on security and compliance dimensions.

---

## Step 5: Submit Feedback (Optional)

Help improve the RL model by submitting feedback on selections:

```python
# After reviewing the result, submit feedback
await rs.feedback(
    request_id=result.request_id,
    rating=5,  # 1-5 scale
    comment="Selected spec met all security requirements",
)
```

---

## What Just Happened?

1. **Multi-Judge Scoring** — Three LLMs (Claude, GPT-4, Gemini) evaluated each spec across 12 enterprise dimensions
2. **Score Aggregation** — Dimension scores were weighted and aggregated into a composite score
3. **Hybrid Selection** — The RL policy combined with scoring to select the best candidate
4. **Audit Trail** — The evaluation was logged for compliance and debugging

---

## Next Steps

<div class="grid cards" markdown>

-   **[:material-scale-balance: Scoring Dimensions](../concepts/scoring-dimensions.md)**
    
    Understand the 12 dimensions used for evaluation

-   **[:material-robot: Selection Methods](../concepts/selection-methods.md)**
    
    Learn about `scoring_only`, `hybrid`, and `rl_only` modes

-   **[:material-api: API Reference](../api-reference/specs.md)**
    
    Full REST API documentation

-   **[:material-shield-check: Best Practices](../guides/best-practices.md)**
    
    Production deployment recommendations

</div>

---

## Need Help?

- :material-github: [GitHub Issues](https://github.com/reinforce-spec/reinforce-spec/issues)
- :material-book: [API Reference](../api-reference/index.md)
- :material-chat: [Discord Community](https://discord.gg/reinforce-spec)
