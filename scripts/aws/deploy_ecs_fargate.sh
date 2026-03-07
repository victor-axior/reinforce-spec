#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Deploy ReinforceSpec to ECS Fargate via CloudFormation.

Required:
  --vpc-id <vpc-...>
  --public-subnets <subnet-a,subnet-b>
  --private-subnets <subnet-c,subnet-d>
  --certificate-arn <acm-certificate-arn>
  --openrouter-secret-arn <secretsmanager-secret-arn>

Optional:
  --hosted-zone-id <route53-zone-id>      (optional, for custom DNS)
  --api-domain <fqdn>                      (optional, e.g. api.example.com)
  --stack-name <name>                 (default: reinforce-spec-api)
  --project-name <name>               (default: reinforce-spec)
  --region <aws-region>               (default: aws configure value)
  --ecr-repo <name>                   (default: reinforce-spec)
  --image-tag <tag>                   (default: git short sha)
  --desired-count <n>                 (default: 2)
  --min-count <n>                     (default: 2)
  --max-count <n>                     (default: 6)
  --task-cpu <256|512|1024|2048|4096> (default: 1024)
  --task-memory <MiB>                 (default: 2048)
  --workers <n>                       (default: 2)
  --log-level <level>                 (default: info)

Example:
  scripts/aws/deploy_ecs_fargate.sh \
    --vpc-id vpc-123 \
    --public-subnets subnet-a,subnet-b \
    --private-subnets subnet-c,subnet-d \
    --certificate-arn arn:aws:acm:... \
    --openrouter-secret-arn arn:aws:secretsmanager:...
EOF
}

STACK_NAME="reinforce-spec-api"
PROJECT_NAME="reinforce-spec"
REGION="${AWS_REGION:-}"
ECR_REPO="reinforce-spec"
IMAGE_TAG="$(git rev-parse --short HEAD)"
DESIRED_COUNT="2"
MIN_COUNT="2"
MAX_COUNT="6"
TASK_CPU="1024"
TASK_MEMORY="2048"
WORKERS="2"
LOG_LEVEL="info"

VPC_ID=""
PUBLIC_SUBNETS=""
PRIVATE_SUBNETS=""
CERTIFICATE_ARN=""
OPENROUTER_SECRET_ARN=""
HOSTED_ZONE_ID=""
API_DOMAIN_NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vpc-id)
      VPC_ID="$2"; shift 2 ;;
    --public-subnets)
      PUBLIC_SUBNETS="$2"; shift 2 ;;
    --private-subnets)
      PRIVATE_SUBNETS="$2"; shift 2 ;;
    --certificate-arn)
      CERTIFICATE_ARN="$2"; shift 2 ;;
    --openrouter-secret-arn)
      OPENROUTER_SECRET_ARN="$2"; shift 2 ;;
    --hosted-zone-id)
      HOSTED_ZONE_ID="$2"; shift 2 ;;
    --api-domain)
      API_DOMAIN_NAME="$2"; shift 2 ;;
    --stack-name)
      STACK_NAME="$2"; shift 2 ;;
    --project-name)
      PROJECT_NAME="$2"; shift 2 ;;
    --region)
      REGION="$2"; shift 2 ;;
    --ecr-repo)
      ECR_REPO="$2"; shift 2 ;;
    --image-tag)
      IMAGE_TAG="$2"; shift 2 ;;
    --desired-count)
      DESIRED_COUNT="$2"; shift 2 ;;
    --min-count)
      MIN_COUNT="$2"; shift 2 ;;
    --max-count)
      MAX_COUNT="$2"; shift 2 ;;
    --task-cpu)
      TASK_CPU="$2"; shift 2 ;;
    --task-memory)
      TASK_MEMORY="$2"; shift 2 ;;
    --workers)
      WORKERS="$2"; shift 2 ;;
    --log-level)
      LOG_LEVEL="$2"; shift 2 ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ -z "$VPC_ID" || -z "$PUBLIC_SUBNETS" || -z "$PRIVATE_SUBNETS" || -z "$CERTIFICATE_ARN" || -z "$OPENROUTER_SECRET_ARN" ]]; then
  echo "Missing required arguments." >&2
  usage
  exit 1
fi

if [[ -n "$HOSTED_ZONE_ID" && -z "$API_DOMAIN_NAME" ]]; then
  echo "--api-domain is required when --hosted-zone-id is provided." >&2
  exit 1
fi

if [[ -z "$HOSTED_ZONE_ID" && -n "$API_DOMAIN_NAME" ]]; then
  echo "--hosted-zone-id is required when --api-domain is provided." >&2
  exit 1
fi

if [[ -z "$REGION" ]]; then
  REGION="$(aws configure get region)"
fi

if [[ -z "$REGION" ]]; then
  echo "AWS region is required (set --region or AWS_REGION)." >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required." >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"
IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"

echo "Ensuring ECR repository exists: ${ECR_REPO}"
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$ECR_REPO" --region "$REGION" >/dev/null

echo "Logging in to ECR"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_URI"

echo "Building image: ${IMAGE_URI}"
docker build -t "$IMAGE_URI" .

echo "Pushing image: ${IMAGE_URI}"
docker push "$IMAGE_URI"

echo "Deploying CloudFormation stack: ${STACK_NAME}"
aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file infra/aws/ecs-fargate/stack.yaml \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --parameter-overrides \
    ProjectName="$PROJECT_NAME" \
    VpcId="$VPC_ID" \
    PublicSubnetIds="$PUBLIC_SUBNETS" \
    PrivateSubnetIds="$PRIVATE_SUBNETS" \
    ContainerImage="$IMAGE_URI" \
    CertificateArn="$CERTIFICATE_ARN" \
    HostedZoneId="$HOSTED_ZONE_ID" \
    ApiDomainName="$API_DOMAIN_NAME" \
    OpenRouterApiKeySecretArn="$OPENROUTER_SECRET_ARN" \
    DesiredCount="$DESIRED_COUNT" \
    MinTaskCount="$MIN_COUNT" \
    MaxTaskCount="$MAX_COUNT" \
    TaskCpu="$TASK_CPU" \
    TaskMemory="$TASK_MEMORY" \
    Workers="$WORKERS" \
    LogLevel="$LOG_LEVEL"

echo
echo "Deployment complete. Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table