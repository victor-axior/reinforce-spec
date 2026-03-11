#!/usr/bin/env bash
# =============================================================================
# SDK Publishing Script
# =============================================================================
# Builds and publishes all SDKs to AWS CodeArtifact / Go module proxy
# Usage: ./scripts/aws/publish_sdk.sh [--version VERSION] [--python] [--typescript] [--go]
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION=""
PUBLISH_PYTHON=false
PUBLISH_TYPESCRIPT=false
PUBLISH_GO=false
PUBLISH_ALL=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --version|-v)
            VERSION="$2"
            shift 2
            ;;
        --python)
            PUBLISH_PYTHON=true
            PUBLISH_ALL=false
            shift
            ;;
        --typescript|--ts)
            PUBLISH_TYPESCRIPT=true
            PUBLISH_ALL=false
            shift
            ;;
        --go)
            PUBLISH_GO=true
            PUBLISH_ALL=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--version VERSION] [--python] [--typescript] [--go]"
            echo ""
            echo "Build and publish SDKs to AWS CodeArtifact."
            echo ""
            echo "Options:"
            echo "  --version VERSION  Version to publish (required)"
            echo "  --python           Publish only Python SDK"
            echo "  --typescript       Publish only TypeScript SDK"
            echo "  --go               Publish only Go SDK"
            echo ""
            echo "If no SDK flags are provided, all SDKs are published."
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Validate version
if [[ -z "$VERSION" ]]; then
    echo -e "${RED}Error: --version is required${NC}"
    echo "Usage: $0 --version 1.0.0"
    exit 1
fi

# Set flags if publishing all
if $PUBLISH_ALL; then
    PUBLISH_PYTHON=true
    PUBLISH_TYPESCRIPT=true
    PUBLISH_GO=true
fi

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  ReinforceSpec SDK Publisher${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""
echo -e "Version: ${GREEN}$VERSION${NC}"
echo -e "Python SDK: $([ "$PUBLISH_PYTHON" = true ] && echo "${GREEN}yes${NC}" || echo "${YELLOW}no${NC}")"
echo -e "TypeScript SDK: $([ "$PUBLISH_TYPESCRIPT" = true ] && echo "${GREEN}yes${NC}" || echo "${YELLOW}no${NC}")"
echo -e "Go SDK: $([ "$PUBLISH_GO" = true ] && echo "${GREEN}yes${NC}" || echo "${YELLOW}no${NC}")"
echo ""

# Confirm
read -p "Continue with publishing? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# =============================================================================
# Publish Python SDK
# =============================================================================
publish_python() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Publishing Python SDK${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    cd "$PROJECT_ROOT/sdks/python"
    
    # Login to CodeArtifact
    echo -e "${YELLOW}Logging into CodeArtifact...${NC}"
    "$SCRIPT_DIR/codeartifact_login_pip.sh"
    
    # Update version in pyproject.toml
    echo -e "${YELLOW}Updating version to $VERSION...${NC}"
    sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml
    
    # Update version in __init__.py
    if [[ -f "src/reinforce_spec_sdk/__init__.py" ]]; then
        sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/reinforce_spec_sdk/__init__.py
    fi
    
    # Clean previous builds
    rm -rf dist/ build/ *.egg-info/
    
    # Build
    echo -e "${YELLOW}Building package...${NC}"
    python -m build
    
    # Publish
    echo -e "${YELLOW}Publishing to CodeArtifact...${NC}"
    twine upload dist/*
    
    echo -e "${GREEN}✓ Python SDK v$VERSION published${NC}"
}

# =============================================================================
# Publish TypeScript SDK
# =============================================================================
publish_typescript() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Publishing TypeScript SDK${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    cd "$PROJECT_ROOT/sdks/typescript"
    
    # Login to CodeArtifact
    echo -e "${YELLOW}Logging into CodeArtifact...${NC}"
    "$SCRIPT_DIR/codeartifact_login_npm.sh"
    
    # Update version
    echo -e "${YELLOW}Updating version to $VERSION...${NC}"
    npm version "$VERSION" --no-git-tag-version --allow-same-version
    
    # Clean and install
    rm -rf dist/ node_modules/
    npm ci
    
    # Build
    echo -e "${YELLOW}Building package...${NC}"
    npm run build
    
    # Publish
    echo -e "${YELLOW}Publishing to CodeArtifact...${NC}"
    npm publish
    
    echo -e "${GREEN}✓ TypeScript SDK v$VERSION published${NC}"
}

# =============================================================================
# Publish Go SDK
# =============================================================================
publish_go() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Publishing Go SDK${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    cd "$PROJECT_ROOT"
    
    # Go modules are published via git tags
    echo -e "${YELLOW}Creating git tag for Go module...${NC}"
    
    # Ensure we're on a clean working tree
    if [[ -n "$(git status --porcelain sdks/go/)" ]]; then
        echo -e "${YELLOW}Warning: Go SDK has uncommitted changes${NC}"
        read -p "Commit changes before tagging? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git add sdks/go/
            git commit -m "chore: prepare Go SDK v$VERSION"
        fi
    fi
    
    # Create tag
    TAG="sdks/go/v$VERSION"
    if git rev-parse "$TAG" >/dev/null 2>&1; then
        echo -e "${YELLOW}Tag $TAG already exists. Skipping.${NC}"
    else
        git tag -a "$TAG" -m "Go SDK v$VERSION"
        echo -e "${YELLOW}Pushing tag to origin...${NC}"
        git push origin "$TAG"
        echo -e "${GREEN}✓ Go SDK v$VERSION tagged and pushed${NC}"
    fi
    
    echo ""
    echo "Developers can install with:"
    echo "  go get github.com/your-org/reinforce-spec/sdks/go@v$VERSION"
}

# =============================================================================
# Main
# =============================================================================
FAILED=()

if $PUBLISH_PYTHON; then
    if publish_python; then
        :
    else
        FAILED+=("Python")
    fi
fi

if $PUBLISH_TYPESCRIPT; then
    if publish_typescript; then
        :
    else
        FAILED+=("TypeScript")
    fi
fi

if $PUBLISH_GO; then
    if publish_go; then
        :
    else
        FAILED+=("Go")
    fi
fi

echo ""
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Summary${NC}"
echo -e "${BLUE}==========================================${NC}"

if [[ ${#FAILED[@]} -eq 0 ]]; then
    echo -e "${GREEN}✓ All SDKs published successfully!${NC}"
else
    echo -e "${RED}✗ Failed to publish: ${FAILED[*]}${NC}"
    exit 1
fi

echo ""
echo "Version $VERSION is now available for:"
$PUBLISH_PYTHON && echo "  - pip install reinforce-spec-sdk==$VERSION"
$PUBLISH_TYPESCRIPT && echo "  - npm install @reinforce-spec/sdk@$VERSION"
$PUBLISH_GO && echo "  - go get github.com/your-org/reinforce-spec/sdks/go@v$VERSION"
