.PHONY: install dev lint typecheck test test-cov format clean build

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/

typecheck:
	mypy src/

test:
	pytest -v

test-cov:
	pytest -v --cov=reinforce_spec_sdk --cov-report=term-missing --cov-report=xml

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .coverage htmlcov coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +

build: clean
	python -m build
