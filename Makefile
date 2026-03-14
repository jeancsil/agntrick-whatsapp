.PHONY: help install test clean format check build release
.DEFAULT_GOAL := help

# Use `uv` for python environment management
UV ?= uv
PYTHON ?= $(UV) run python
PYTEST ?= $(UV) run pytest
RUFF ?= $(UV) run ruff

## -- Help System --

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

## -- Commands --

install: ## Install all dependencies using uv
	@$(UV) sync

install-local: ## Install local dependencies using uv
	@$(UV) pip install -e .

test: ## Run tests with coverage
	@$(UV) run pytest tests/ -v --cov=src --cov-report=xml --cov-report=term

check: ## Run all checks (mypy, ruff lint, ruff format) - no modifications
	@$(UV) run mypy src/
	@$(UV) run ruff check src/ tests/
	@$(UV) run ruff format --check src/ tests/

format: ## Auto-fix lint and format issues (runs ruff check --fix and ruff format)
	@$(UV) run ruff check --fix src/ tests/
	@$(UV) run ruff format src/ tests/

clean: ## Deep clean temporary files and virtual environment
	rm -rf .venv
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

## -- Build Commands --

build: ## Build wheel and sdist packages
	@$(UV) build
	@echo ""
	@echo "✓ Build complete!"
	@ls -la dist/ 2>/dev/null || true

build-clean: ## Remove build artifacts
	rm -rf dist/
	rm -rf build/
	rm -rf src/*.egg-info
	@echo "✓ Build artifacts cleaned!"

## -- Release Commands --

release: ## Release package (usage: make release VERSION=0.4.0)
	@if [ -z "$(VERSION)" ]; then echo "Error: VERSION is required (e.g., VERSION=0.4.0)"; exit 1; fi
	@./scripts/release.sh $(VERSION)