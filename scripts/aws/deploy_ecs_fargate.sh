#!/usr/bin/env bash
set -euo pipefail

# Load repository .env defaults when present.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

emit_status() {
  local stage="$1"
  local status="$2"
  local message="$3"
  printf 'RS_STATUS:{"stage":"%s","status":"%s","message":"%s"}\n' "$stage" "$status" "$message"
}

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
  --database-secret-arn <secretsmanager-secret-arn>  (RDS connection string secret)
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

Notes:
  - If .env exists in repo root, script loads it automatically.
  - RS_AWS_* values in .env are used as defaults and can be overridden by CLI flags.

Example:
  scripts/aws/deploy_ecs_fargate.sh \
    --vpc-id vpc-123 \
    --public-subnets subnet-a,subnet-b \
    --private-subnets subnet-c,subnet-d \
    --certificate-arn arn:aws:acm:... \
    --openrouter-secret-arn arn:aws:secretsmanager:...
EOF
}

STACK_NAME="${RS_AWS_STACK_NAME:-reinforce-spec-api}"
PROJECT_NAME="${RS_AWS_PROJECT_NAME:-reinforce-spec}"
REGION="${AWS_REGION:-}"
ECR_REPO="${RS_AWS_ECR_REPO:-reinforce-spec}"
IMAGE_TAG="$(git rev-parse --short HEAD)"
DESIRED_COUNT="${RS_AWS_DESIRED_COUNT:-2}"
MIN_COUNT="${RS_AWS_MIN_COUNT:-2}"
MAX_COUNT="${RS_AWS_MAX_COUNT:-6}"
TASK_CPU="${RS_AWS_TASK_CPU:-1024}"
TASK_MEMORY="${RS_AWS_TASK_MEMORY:-2048}"
WORKERS="${RS_AWS_WORKERS:-2}"
LOG_LEVEL="${RS_AWS_LOG_LEVEL:-info}"

VPC_ID="${RS_AWS_VPC_ID:-}"
PUBLIC_SUBNETS="${RS_AWS_PUBLIC_SUBNETS:-}"
PRIVATE_SUBNETS="${RS_AWS_PRIVATE_SUBNETS:-}"
CERTIFICATE_ARN="${RS_AWS_CERTIFICATE_ARN:-}"
OPENROUTER_SECRET_ARN="${RS_AWS_OPENROUTER_SECRET_ARN:-}"
DATABASE_SECRET_ARN="${RS_AWS_DATABASE_SECRET_ARN:-}"
HOSTED_ZONE_ID="${RS_AWS_HOSTED_ZONE_ID:-}"
API_DOMAIN_NAME="${RS_AWS_API_DOMAIN_NAME:-}"

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
    --database-secret-arn)
      DATABASE_SECRET_ARN="$2"; shift 2 ;;
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
  emit_status "preflight" "failed" "aws CLI missing"
  echo "aws CLI is required." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  emit_status "preflight" "failed" "docker missing"
  echo "docker is required." >&2
  exit 1
fi

emit_status "preflight" "success" "validated prerequisites"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"
IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"
BUILD_CACHE_REF="${ECR_URI}:buildcache"

emit_status "build" "in_progress" "ensuring ECR repository exists"
echo "Ensuring ECR repository exists: ${ECR_REPO}"
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$ECR_REPO" --region "$REGION" >/dev/null

emit_status "build" "in_progress" "logging in to ECR"
echo "Logging in to ECR"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_URI"

emit_status "build" "in_progress" "building image"
echo "Building image: ${IMAGE_URI}"
if docker buildx version >/dev/null 2>&1; then
  emit_status "build" "in_progress" "building and pushing image with buildx cache"
  if docker buildx build \
    --platform linux/amd64 \
    --pull \
    --cache-from "type=registry,ref=${BUILD_CACHE_REF}" \
    --cache-to "type=registry,ref=${BUILD_CACHE_REF},mode=max" \
    -t "$IMAGE_URI" \
    --push \
    .; then
    :
  else
    emit_status "build" "in_progress" "buildx cache unavailable; retrying without cache export"
    if docker buildx build \
      --platform linux/amd64 \
      --pull \
      -t "$IMAGE_URI" \
      --push \
      .; then
      :
    else
      emit_status "build" "in_progress" "buildx failed; falling back to classic docker build"
      DOCKER_BUILDKIT=0 docker build --pull -t "$IMAGE_URI" .

      emit_status "build" "in_progress" "pushing image"
      echo "Pushing image: ${IMAGE_URI}"
      docker push "$IMAGE_URI"
    fi
  fi
else
  emit_status "build" "in_progress" "building image with classic docker build"
  DOCKER_BUILDKIT=0 docker build --pull -t "$IMAGE_URI" .

  emit_status "build" "in_progress" "pushing image"
  echo "Pushing image: ${IMAGE_URI}"
  docker push "$IMAGE_URI"
fi

emit_status "deploy" "in_progress" "deploying CloudFormation stack"
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
    DatabaseSecretArn="$DATABASE_SECRET_ARN" \
    DesiredCount="$DESIRED_COUNT" \
    MinTaskCount="$MIN_COUNT" \
    MaxTaskCount="$MAX_COUNT" \
    TaskCpu="$TASK_CPU" \
    TaskMemory="$TASK_MEMORY" \
    Workers="$WORKERS" \
    LogLevel="$LOG_LEVEL"

emit_status "deploy" "success" "CloudFormation deploy completed"

echo
echo "Deployment complete. Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

ALB_URL="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='HttpsUrl'].OutputValue | [0]" \
  --output text)"

if [[ -n "$ALB_URL" && "$ALB_URL" != "None" ]] && command -v curl >/dev/null 2>&1; then
  emit_status "smoke" "in_progress" "running health smoke check"
  if curl -fsS "${ALB_URL}/v1/health" >/dev/null; then
    emit_status "smoke" "success" "health endpoint reachable"
    echo "Smoke check passed: ${ALB_URL}/v1/health"
  else
    emit_status "smoke" "failed" "health endpoint check failed"
    echo "Smoke check failed: ${ALB_URL}/v1/health" >&2
  fi
fi