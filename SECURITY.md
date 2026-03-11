# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.x     | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in ReinforceSpec, please report it
responsibly:

1. **Do NOT** open a public GitHub issue.
2. Email **security@reinforce-spec.dev** with:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Any suggested fixes (optional)

## Response Timeline

- **Acknowledgement**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Fix release**: Targeting 14 days for critical issues

## Security Considerations

### API Keys
- Never commit API keys or secrets to the repository
- Use environment variables or `.env` files (excluded from git)
- The `AppConfig` system validates required secrets at startup

### LLM Interactions
- All LLM prompts are logged for audit purposes
- User-provided spec content is not stored beyond the request lifecycle
  unless feedback is submitted
- Rate limiting is enforced at the middleware level

### Data Storage
- PostgreSQL stores evaluation history and audit logs
- Idempotency keys expire after 24 hours (configurable)
- No PII is collected by default

### Dependencies
- Dependencies are pinned via `uv.lock`
- Dependabot is configured for automated security updates
- `safety` checks run in the CI pipeline
