# Makefile frontend for scikit-build-core project
#
# This Makefile wraps common build commands for convenience.
# The actual build is handled by scikit-build-core via pyproject.toml

.PHONY: all sync build rebuild test lint format typecheck qa clean \
        distclean wheel sdist dist check publish-test publish upgrade \
        coverage coverage-html docs release build-asan test-asan help

# Default target
all: build

# Sync environment (initial setup, installs dependencies + package)
sync:
	@uv sync

# Build/rebuild the extension after code changes
build:
	@uv sync --reinstall-package cymongoose

# Alias for build
rebuild: build

# Run tests
test:
	@uv run python -m pytest tests/ -v

# Lint with ruff
lint:
	@uv run ruff check --fix src/ tests/

# Format with ruff
format:
	@uv run ruff format src/ tests/

# Type check with mypy
typecheck:
	@uv run mypy --strict src --exclude '.venv'

# Run a full quality assurance check
qa: test lint typecheck format

# Build wheel
wheel:
	@uv build --wheel

# Build source distribution
sdist:
	@uv build --sdist

# Check distributions with twine
check:
	@uv run twine check dist/*

# Build both wheel and sdist
dist: wheel sdist check

# Publish to TestPyPI
publish-test: check
	@uv run twine upload --repository testpypi dist/*

# Publish to PyPI
publish: check
	@uv run twine upload dist/*

# Upgrade all dependencies
upgrade:
	@uv lock --upgrade
	@uv sync

# Run tests with coverage
coverage:
	@uv run python -m pytest tests/ -v --cov=src/cymongoose --cov-report=term-missing

# Generate HTML coverage report
coverage-html:
	@uv run python -m pytest tests/ -v --cov=src/cymongoose --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# Build documentation (requires sphinx in dev dependencies)
docs:
	@uv run sphinx-build -b html docs/ docs/_build/html

# Build with AddressSanitizer enabled
# Also compiles a small helper (build/run_asan) that injects the ASAN runtime
# via DYLD_INSERT_LIBRARIES before exec'ing Python. This is needed on macOS
# because SIP strips DYLD_INSERT_LIBRARIES from processes spawned by
# SIP-protected binaries (/usr/bin/make, /bin/sh, /bin/zsh, etc.).
ASAN_LIB := $(shell find /Applications/Xcode.app -name "libclang_rt.asan_osx_dynamic.dylib" 2>/dev/null | head -1)
build-asan: clean
	SKBUILD_CMAKE_DEFINE="USE_ASAN=ON" uv sync --reinstall-package cymongoose
	@mkdir -p build
	@printf '#include <stdlib.h>\n#include <unistd.h>\nint main(int c,char**v){setenv("DYLD_INSERT_LIBRARIES",v[1],1);execvp(v[2],v+2);return 1;}\n' \
		| cc -o build/run_asan -x c -
	@echo "ASAN helper built: build/run_asan"

# Run tests with AddressSanitizer
test-asan: build-asan
	@echo "Running tests with AddressSanitizer..."
	ASAN_OPTIONS=detect_leaks=0:allocator_may_return_null=1:halt_on_error=1 \
		build/run_asan $(ASAN_LIB) .venv/bin/python -m pytest tests/ -v -x --tb=short
	@echo "ASAN tests completed successfully"

# Clean build artifacts
clean:
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info/
	@rm -rf src/*.egg-info/
	@rm -rf .pytest_cache/
	@find . -name "*.so" -delete
	@find . -name "*.pyd" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Clean everything including CMake cache
distclean: clean
	@rm -rf CMakeCache.txt CMakeFiles/

# Show help
help:
	@echo "Available targets:"
	@echo "  all          - Build/rebuild the extension (default)"
	@echo "  sync         - Sync environment (initial setup)"
	@echo "  build        - Rebuild extension after code changes"
	@echo "  rebuild      - Alias for build"
	@echo "  test         - Run tests"
	@echo "  lint         - Lint with ruff"
	@echo "  format       - Format with ruff"
	@echo "  typecheck    - Type check with mypy"
	@echo "  qa           - Run full quality assurance (test, lint, typecheck, format)"
	@echo "  wheel        - Build wheel distribution"
	@echo "  sdist        - Build source distribution"
	@echo "  dist         - Build both wheel and sdist"
	@echo "  check        - Check distributions with twine"
	@echo "  publish-test - Publish to TestPyPI"
	@echo "  publish      - Publish to PyPI"
	@echo "  upgrade      - Upgrade all dependencies"
	@echo "  coverage     - Run tests with coverage"
	@echo "  coverage-html- Generate HTML coverage report"
	@echo "  docs         - Build documentation with Sphinx"
	@echo "  build-asan   - Build with AddressSanitizer"
	@echo "  test-asan    - Run tests with AddressSanitizer"
	@echo "  clean        - Remove build artifacts"
	@echo "  distclean    - Remove all generated files"
	@echo "  help         - Show this help message"
