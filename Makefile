.PHONY: all help install build clean test test-verbose test-coverage lint format \
		type-check docs docs-serve dev snap wheel-check full-check release publish

# Default target
# .DEFAULT_GOAL := help

# Variables
PROJECT = cymongoose
PYTHON = uv run python
PYTEST = uv run python -m pytest
SPHINX = uv run sphinx-build
RUFF = uv run ruff
MYPY = uv run mypy

all: build

help: ## Show this help message
	@echo "$(PROJECT) - Makefile commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation and Building
install: ## Install package in development mode
	@uv sync

build: clean ## Rebuild the package (forces reinstall)
	@uv sync --reinstall-package $(PROJECT)

clean: ## Remove build artifacts
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info
	@rm -rf .*_cache
	@rm -rf htmlcov/
	@rm -rf .coverage
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type f -name "*.so" -delete
	@rm -f src/$(PROJECT)/_mongoose.c
	@rm -rf docs/_build/

release:
	@rm -rf dist
	@uv build --sdist
	@uv build --wheel --python 3.11
	@uv build --wheel --python 3.12
	@uv build --wheel --python 3.13
	@uv build --wheel --python 3.14

wheel-check:
	@uv run twine check dist/*

publish:
	@uv run twine upload dist/*

# Testing
test: ## Run tests with pytest
	PYTHONPATH=src $(PYTEST) tests/ -v

test-verbose: ## Run tests with verbose output and print statements
	PYTHONPATH=src $(PYTEST) tests/ -v -s

test-coverage: ## Run tests with coverage report
	PYTHONPATH=src $(PYTEST) tests/ --cov=$(PROJECT) --cov-report=html --cov-report=term

test-fast: ## Run tests with minimal output
	PYTHONPATH=src $(PYTEST) tests/ -q --tb=line

test-examples: ## Run only example tests
	PYTHONPATH=src $(PYTEST) tests/examples/ -v

# Code Quality
lint: ## Run linter (ruff)
	@$(RUFF) check --fix src/

# lint-fix: ## Run linter with auto-fix
# 	$(RUFF) check --fix src/

format: ## Format code with ruff
	@$(RUFF) format src/

format-check: ## Check code formatting without modifying files
	@$(RUFF) format --check src/

type-check: ## Run type checker (mypy)
	@$(MYPY) src/

full-check: lint format-check type-check ## Run all code quality checks

# Documentation
docs: ## Build Sphinx documentation
	@cd docs && $(SPHINX) -b html . _build/html

docs-clean: ## Clean documentation build
	@rm -rf docs/_build/

docs-serve: docs ## Build and serve documentation locally
	@echo "Opening documentation in browser..."
	@open docs/_build/html/index.html 2>/dev/null || \
	 xdg-open docs/_build/html/index.html 2>/dev/null || \
	 echo "Please open docs/_build/html/index.html in your browser"

docs-rebuild: docs-clean docs ## Clean rebuild documentation

# Development
dev: install ## Set up development environment
	@echo "Development environment ready!"
	@echo "Run 'make test' to run tests"
	@echo "Run 'make docs' to build documentation"

watch-test: ## Watch for changes and run tests (requires pytest-watch)
	PYTHONPATH=src $(PYTEST) tests/ -f

# Version Management
version: ## Show current version
	@grep '^version = ' pyproject.toml | cut -d'"' -f2

bump-patch: ## Bump patch version (requires bump2version)
	@uv run bump2version patch

bump-minor: ## Bump minor version (requires bump2version)
	@uv run bump2version minor

bump-major: ## Bump major version (requires bump2version)
	@uv run bump2version major

# Git shortcuts
snap: ## Quick git commit and push (dev only)
	@git add --all . && git commit -m 'snap' && git push

commit: ## Interactive git commit
	@git add --all .
	@git status
	@read -p "Commit message: " msg; git commit -m "$$msg"

# Distribution
dist: clean ## Build distribution packages
	@uv build

# publish-test: dist ## Upload to TestPyPI
# 	@uv publish --publish-url https://test.pypi.org/legacy/

# publish: dist ## Upload to PyPI (production)
# 	@uv publish

# Benchmarks
bench: ## Run performance benchmarks
	@echo "Running benchmarks..."
	PYTHONPATH=src $(PYTHON) tests/benchmarks/quick_bench.py

# Examples
run-http-server: ## Run HTTP server example
	PYTHONPATH=src $(PYTHON) tests/examples/http/http_server.py

run-websocket: ## Run WebSocket server example
	PYTHONPATH=src $(PYTHON) tests/examples/websocket/websocket_server.py

run-mqtt-client: ## Run MQTT client example
	PYTHONPATH=src $(PYTHON) tests/examples/mqtt/mqtt_client.py

# Maintenance
update-deps: ## Update dependencies
	@uv sync --upgrade

lock: ## Update lock file
	@uv lock

info: ## Show project information
	@echo "Project: $(PROJECT)"
	@echo "Version: $$(grep '^version = ' pyproject.toml | cut -d'"' -f2)"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "UV: $$(uv --version)"
	@echo ""
	@echo "Test status:"
	@PYTHONPATH=src $(PYTEST) tests/ -q --tb=no --collect-only 2>&1 | grep -E "test session|collected" | head -1 || echo "Tests not collected"
