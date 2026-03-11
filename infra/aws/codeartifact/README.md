# AWS CodeArtifact Infrastructure

This directory contains CloudFormation templates for deploying AWS CodeArtifact repositories for private SDK distribution.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              AWS CodeArtifact Domain                     │
│                  (reinforce-spec)                        │
│                                                          │
│  ┌─────────────────┐        ┌─────────────────┐        │
│  │ python-packages │        │   npm-packages  │        │
│  │   (internal)    │        │    (internal)   │        │
│  │                 │        │                 │        │
│  │ reinforce-spec- │        │ @reinforce-spec │        │
│  │ sdk             │        │ /sdk            │        │
│  └────────┬────────┘        └────────┬────────┘        │
│           │                          │                  │
│           ▼                          ▼                  │
│  ┌─────────────────┐        ┌─────────────────┐        │
│  │   pypi-store    │        │   npm-store     │        │
│  │   (upstream)    │        │   (upstream)    │        │
│  │       ↓         │        │       ↓         │        │
│  │   pypi.org      │        │   npmjs.com     │        │
│  └─────────────────┘        └─────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

## Deployment

### Prerequisites

- AWS CLI configured with appropriate credentials
- Permissions to create IAM roles and CodeArtifact resources

### Deploy the Stack

```bash
# Deploy with defaults
aws cloudformation deploy \
  --template-file infra/aws/codeartifact/template.yaml \
  --stack-name reinforce-spec-codeartifact \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy with custom parameters
aws cloudformation deploy \
  --template-file infra/aws/codeartifact/template.yaml \
  --stack-name reinforce-spec-codeartifact \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    DomainName=my-company \
    PythonRepositoryName=internal-python \
    NpmRepositoryName=internal-npm
```

### View Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name reinforce-spec-codeartifact \
  --query 'Stacks[0].Outputs' \
  --output table
```

## Developer Setup

### 1. Attach IAM Policy

Attach the `ReinforceSpecSDKReadAccess` policy to your IAM user or role:

```bash
aws iam attach-user-policy \
  --user-name YOUR_USERNAME \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/ReinforceSpecSDKReadAccess
```

### 2. Configure pip (Python)

```bash
# Login to CodeArtifact (valid for 12 hours)
aws codeartifact login \
  --tool pip \
  --domain reinforce-spec \
  --repository python-packages

# Install the SDK
pip install reinforce-spec-sdk
```

### 3. Configure npm (TypeScript/JavaScript)

```bash
# Login to CodeArtifact
aws codeartifact login \
  --tool npm \
  --domain reinforce-spec \
  --repository npm-packages

# Install the SDK
npm install @reinforce-spec/sdk
```

### 4. Configure Go

Go modules use direct HTTPS authentication. Create a `.netrc` file:

```bash
# Get authorization token
TOKEN=$(aws codeartifact get-authorization-token \
  --domain reinforce-spec \
  --query authorizationToken \
  --output text)

# Add to ~/.netrc
echo "machine reinforce-spec-ACCOUNT_ID.d.codeartifact.REGION.amazonaws.com login aws password $TOKEN" >> ~/.netrc
```

## CI/CD Integration

### GitHub Actions (OIDC)

The template creates a role for GitHub Actions OIDC authentication:

```yaml
# .github/workflows/publish.yml
jobs:
  publish:
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT_ID:role/ReinforceSpecSDKPublishRole
          aws-region: us-east-1
      
      - name: Login to CodeArtifact
        run: aws codeartifact login --tool pip --domain reinforce-spec --repository python-packages
```

### Manual Publish

For CI/CD systems without OIDC, use the `ReinforceSpecSDKPublishAccess` policy with an IAM user.

## Resources Created

| Resource | Type | Description |
|----------|------|-------------|
| `reinforce-spec` | Domain | CodeArtifact domain |
| `python-packages` | Repository | Internal Python packages |
| `npm-packages` | Repository | Internal npm packages |
| `pypi-store` | Repository | Upstream to pypi.org |
| `npm-store` | Repository | Upstream to npmjs.com |
| `ReinforceSpecSDKReadAccess` | IAM Policy | Developer read access |
| `ReinforceSpecSDKPublishAccess` | IAM Policy | CI/CD publish access |
| `ReinforceSpecSDKPublishRole` | IAM Role | GitHub Actions OIDC role |

## Cost Considerations

- **Storage**: $0.05/GB-month for package assets
- **Requests**: $0.05/10,000 requests
- **Data Transfer**: Standard AWS data transfer rates

Typical monthly cost for a small team: < $5/month

## Cleanup

```bash
aws cloudformation delete-stack --stack-name reinforce-spec-codeartifact
```

> **Warning**: Deleting the stack will remove all published packages. Export packages first if needed.
