# AWS ECS Fargate Deployment

This directory contains an implementation scaffold to deploy ReinforceSpec to AWS ECS Fargate with:

- Internet-facing ALB (HTTPS)
- ECS Fargate service
- EFS-backed persistent volume mounted at `/app/data`
- Secrets Manager integration for `OPENROUTER_API_KEY`
- Target-tracking autoscaling on CPU

## Files

- `stack.yaml` — CloudFormation stack for infrastructure and service
- `scripts/aws/deploy_ecs_fargate.sh` — build/push image to ECR and deploy/update stack

## Prerequisites

- AWS CLI v2 configured (`aws configure`)
- Docker available locally
- Existing VPC with at least:
  - 2 public subnets (ALB)
  - 2 private subnets (ECS tasks + EFS mount targets)
- ACM certificate in the same region
- Secrets Manager secret containing your OpenRouter API key
- (Optional) Route 53 public hosted zone if you want a custom API URL

Create a secret if needed:

```bash
aws secretsmanager create-secret \
  --name reinforce-spec/openrouter \
  --secret-string 'YOUR_OPENROUTER_API_KEY'
```

## Deploy

From repository root:

```bash
chmod +x scripts/aws/deploy_ecs_fargate.sh

scripts/aws/deploy_ecs_fargate.sh \
  --region us-east-1 \
  --vpc-id vpc-xxxxxxxx \
  --public-subnets subnet-public-a,subnet-public-b \
  --private-subnets subnet-private-a,subnet-private-b \
  --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/xxxx \
  --openrouter-secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:reinforce-spec/openrouter-xxxx
```

Custom domain example:

```bash
scripts/aws/deploy_ecs_fargate.sh \
  --region us-east-1 \
  --vpc-id vpc-xxxxxxxx \
  --public-subnets subnet-public-a,subnet-public-b \
  --private-subnets subnet-private-a,subnet-private-b \
  --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/xxxx \
  --openrouter-secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:reinforce-spec/openrouter-xxxx \
  --hosted-zone-id Z1234567890ABCDE \
  --api-domain api.example.com
```

The script will:

1. Ensure ECR repository exists
2. Build and push the container image
3. Deploy/update CloudFormation stack
4. Print endpoint and resource outputs

When `--hosted-zone-id` and `--api-domain` are provided, CloudFormation also creates
an alias A-record to the ALB and emits `CustomDomainUrl` in stack outputs.

## Post-deploy smoke checks

Use the ALB URL from stack outputs:

```bash
curl -sSf https://<alb-dns>/v1/health
curl -sSf https://<alb-dns>/v1/health/ready
```

Then run an API selection request from [openapi.yml](../../../openapi.yml).

## Notes

- Persistent state is stored on EFS at `/app/data`.
- The container entrypoint seeds default policy registry files on first boot when missing.
- For tighter security, restrict `IngressCidr` in `stack.yaml` from `0.0.0.0/0` to known CIDRs.
- Ensure your ACM certificate includes the custom domain (or wildcard) used in `--api-domain`.