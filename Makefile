.PHONY: help install dev test test-unit test-integration test-behavioral test-property test-nightly lint format typecheck serve docker-build docker-up docker-down docker-smoke contract-test clean

PYTHON := python
UV := uv

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	$(UV) sync

dev: ## Install all dependencies (dev + test + docs + observability)
	$(UV) sync --all-extras
	$(UV) run pre-commit install

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run all tests except nightly
	$(UV) run --extra test pytest tests/ -m "not statistical and not slow" --tb=short -q

test-unit: ## Run unit tests only
	$(UV) run --extra test pytest tests/unit/ -m "unit" --tb=short -q

test-integration: ## Run integration tests
	$(UV) run --extra test pytest tests/integration/ -m "integration" --tb=short -q

test-behavioral: ## Run behavioral (CheckList) tests
	$(UV) run --extra test pytest tests/behavioral/ -m "behavioral" --tb=short -q

test-property: ## Run property-based (hypothesis) tests
	$(UV) run --extra test pytest tests/property/ -m "property" --tb=short -q

test-nightly: ## Run stochastic/statistical tests (nightly CI)
	$(UV) run --extra test pytest tests/statistical/ -m "statistical" --tb=short -q

test-cov: ## Run tests with coverage report
	$(UV) run --extra test pytest tests/ -m "not statistical and not slow" --cov=reinforce_spec --cov-report=html --cov-report=term-missing

# ── Code Quality ──────────────────────────────────────────────────────────────

lint: ## Run linter (ruff check)
	$(UV) run ruff check reinforce_spec/ tests/
	$(UV) run ruff format --check reinforce_spec/ tests/

format: ## Auto-format code
	$(UV) run ruff check --fix reinforce_spec/ tests/
	$(UV) run ruff format reinforce_spec/ tests/

typecheck: ## Run type checking (mypy + pyright)
	$(UV) run mypy reinforce_spec/
	$(UV) run --with pyright pyright reinforce_spec/

# ── Contract Testing ──────────────────────────────────────────────────────────

contract-test: ## Run OpenAPI contract tests via schemathesis
	$(UV) run st run openapi.yml --base-url http://localhost:8000 --checks all

# ── Server ────────────────────────────────────────────────────────────────────

serve: ## Start development server with auto-reload
	$(UV) run uvicorn reinforce_spec.server.app:create_app --factory --reload --host 0.0.0.0 --port 8000

serve-prod: ## Start production server
	$(UV) run reinforce-spec-server

# ── Docker ────────────────────────────────────────────────────────────────────

docker-build: ## Build Docker image
	DOCKER_BUILDKIT=1 docker build --pull -t reinforce-spec:latest .

docker-up: ## Start all services (app + redis + prometheus)
	docker compose up -d --wait

docker-down: ## Stop all services
	docker compose down

docker-smoke: ## Verify Dockerized API health endpoint
	curl -sSf "http://localhost:$${RS_PORT:-8000}/v1/health" >/dev/null && echo "docker smoke check passed"

# ── Database ──────────────────────────────────────────────────────────────────

db-migrate: ## Run database migrations
	$(UV) run alembic upgrade head

db-revision: ## Create a new migration revision
	$(UV) run alembic revision --autogenerate -m "$(msg)"

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
