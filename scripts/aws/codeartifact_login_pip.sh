#!/usr/bin/env bash
# =============================================================================
# CodeArtifact Login Script for pip/Python
# =============================================================================
# Usage: ./scripts/aws/codeartifact_login_pip.sh [--domain DOMAIN] [--repo REPO]
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default configuration
DOMAIN="${CODEARTIFACT_DOMAIN:-reinforce-spec}"
REPO="${CODEARTIFACT_PYTHON_REPO:-python-packages}"
REGION="${AWS_REGION:-us-east-1}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --repo)
            REPO="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--domain DOMAIN] [--repo REPO] [--region REGION]"
            echo ""
            echo "Configure pip to use AWS CodeArtifact."
            echo ""
            echo "Options:"
            echo "  --domain DOMAIN  CodeArtifact domain (default: reinforce-spec)"
            echo "  --repo REPO      Repository name (default: python-packages)"
            echo "  --region REGION  AWS region (default: us-east-1)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}Configuring pip for CodeArtifact...${NC}"
echo "  Domain: $DOMAIN"
echo "  Repository: $REPO"
echo "  Region: $REGION"
echo ""

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Install it: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
    exit 1
fi

# Check pip is installed
if ! command -v pip &> /dev/null; then
    echo -e "${RED}Error: pip is not installed${NC}"
    exit 1
fi

# Verify AWS credentials
echo -e "${YELLOW}Verifying AWS credentials...${NC}"
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured or expired${NC}"
    echo "Run: aws configure"
    exit 1
fi

CALLER_ID=$(aws sts get-caller-identity --query "Arn" --output text)
echo -e "  Authenticated as: ${GREEN}$CALLER_ID${NC}"
echo ""

# Login to CodeArtifact for pip
echo -e "${YELLOW}Logging into CodeArtifact for pip...${NC}"
aws codeartifact login \
    --tool pip \
    --domain "$DOMAIN" \
    --repository "$REPO" \
    --region "$REGION"

# Also configure twine for publishing
echo -e "${YELLOW}Configuring twine for publishing...${NC}"
aws codeartifact login \
    --tool twine \
    --domain "$DOMAIN" \
    --repository "$REPO" \
    --region "$REGION"

echo ""
echo -e "${GREEN}✓ Successfully configured pip and twine for CodeArtifact${NC}"
echo ""
echo "You can now install packages:"
echo "  pip install reinforce-spec-sdk"
echo ""
echo "Or publish packages:"
echo "  python -m build"
echo "  twine upload dist/*"
echo ""
echo -e "${YELLOW}Note: This authentication expires in 12 hours${NC}"
