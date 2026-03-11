# ReinforceSpec SDKs

Official client libraries for the ReinforceSpec API, available in Python, TypeScript/JavaScript, and Go.

## Available SDKs

| Language | Package | Version | Docs |
|----------|---------|---------|------|
| Python | [`reinforce-spec-sdk`](python/) | 1.0.0 | [Python SDK Guide](https://docs.reinforce-spec.dev/sdks/python) |
| TypeScript | [`@reinforce-spec/sdk`](typescript/) | 1.0.0 | [TypeScript SDK Guide](https://docs.reinforce-spec.dev/sdks/typescript) |
| Go | [`github.com/reinforce-spec/sdk-go`](go/) | 1.0.0 | [Go SDK Guide](https://docs.reinforce-spec.dev/sdks/go) |

## Quick Start

### Python

```bash
pip install reinforce-spec-sdk
```

```python
import asyncio
from reinforce_spec_sdk import ReinforceSpecClient

async def main():
    async with ReinforceSpecClient.from_env() as client:
        response = await client.select(
            candidates=[
                {"content": "Output from GPT-4", "source_model": "gpt-4"},
                {"content": "Output from Claude", "source_model": "claude-3"},
            ],
            description="Compare LLM outputs",
        )
        print(f"Selected: {response.selected.index}")
        print(f"Score: {response.selected.composite_score:.2f}")

asyncio.run(main())
```

### TypeScript

```bash
npm install @reinforce-spec/sdk
```

```typescript
import { ReinforceSpecClient } from '@reinforce-spec/sdk';

const client = new ReinforceSpecClient({
  baseUrl: process.env.REINFORCE_SPEC_BASE_URL!,
  apiKey: process.env.REINFORCE_SPEC_API_KEY,
});

const response = await client.select({
  candidates: [
    { content: 'Output from GPT-4', sourceModel: 'gpt-4' },
    { content: 'Output from Claude', sourceModel: 'claude-3' },
  ],
  description: 'Compare LLM outputs',
});

console.log(`Selected: ${response.selected.index}`);
console.log(`Score: ${response.selected.compositeScore.toFixed(2)}`);

client.close();
```

### Go

```bash
go get github.com/reinforce-spec/sdk-go
```

```go
package main

import (
    "context"
    "fmt"
    "log"

    reinforcespec "github.com/reinforce-spec/sdk-go"
)

func main() {
    client, err := reinforcespec.NewClientFromEnv()
    if err != nil {
        log.Fatal(err)
    }
    defer client.Close()

    response, err := client.Select(context.Background(), &reinforcespec.SelectRequest{
        Candidates: []reinforcespec.SpecInput{
            {Content: "Output from GPT-4", SourceModel: "gpt-4"},
            {Content: "Output from Claude", SourceModel: "claude-3"},
        },
        Description: "Compare LLM outputs",
    })
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("Selected: %d\n", response.Selected.Index)
    fmt.Printf("Score: %.2f\n", response.Selected.CompositeScore)
}
```

## Project Structure

```
sdks/
├── .editorconfig          # Shared editor configuration
├── CONTRIBUTING.md        # Contribution guidelines
├── README.md              # This file
├── python/
│   ├── CHANGELOG.md
│   ├── LICENSE
│   ├── Makefile
│   ├── README.md
│   ├── pyproject.toml
│   ├── examples/
│   ├── src/reinforce_spec_sdk/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── types.py
│   │   ├── exceptions.py
│   │   ├── _http.py
│   │   └── testing.py
│   └── tests/
├── typescript/
│   ├── CHANGELOG.md
│   ├── LICENSE
│   ├── Makefile
│   ├── README.md
│   ├── package.json
│   ├── tsconfig.json
│   ├── jest.config.ts
│   ├── .eslintrc.json
│   ├── .prettierrc.json
│   ├── examples/
│   ├── src/
│   │   ├── index.ts
│   │   ├── client.ts
│   │   ├── types.ts
│   │   ├── errors.ts
│   │   ├── http.ts
│   │   └── testing.ts
│   └── tests/
└── go/
    ├── CHANGELOG.md
    ├── LICENSE
    ├── Makefile
    ├── README.md
    ├── go.mod
    ├── .golangci.yml
    ├── doc.go
    ├── client.go
    ├── types.go
    ├── errors.go
    ├── http.go
    ├── version.go
    ├── client_test.go
    ├── errors_test.go
    ├── types_test.go
    └── example_test.go
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

Each SDK has a `Makefile` with common targets:

```bash
make dev         # Install dev dependencies (Python)
make install     # Install dependencies (TypeScript)
make test        # Run tests
make lint        # Run linter
make typecheck   # Run type checker
make format      # Auto-format code
make build       # Build for distribution
make clean       # Remove build artifacts
```

## CI/CD

- **Testing**: Runs on every push/PR touching `sdks/**` — tests all three SDKs across multiple runtime versions
- **Publishing**: Triggered by `sdk-v*` tags or manual dispatch — publishes to AWS CodeArtifact

## License

MIT — see individual SDK `LICENSE` files.
