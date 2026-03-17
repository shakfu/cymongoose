# Development Documentation

This section contains documentation for contributors and developers.

## Development Setup

### Clone and Install

```bash
# Clone repository
git clone --recursive https://github.com/shakfu/cymongoose.git
cd cymongoose

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
make test

# Or with pytest directly
PYTHONPATH=src pytest tests/ -v

# Run specific test file
PYTHONPATH=src pytest tests/test_http_server.py -v

# Run with coverage
PYTHONPATH=src pytest tests/ --cov=cymongoose --cov-report=html
```

## Build System

The project uses **scikit-build-core** with **CMake** as the build backend.

```bash
# Build/rebuild extension
make build

# Build with AddressSanitizer
make build-asan

# Clean build artifacts
make clean
```

## Code Structure

```text
cymongoose/
├── src/
│   └── cymongoose/
│       ├── __init__.py
│       ├── _mongoose.pyx      # Cython implementation
│       ├── _mongoose.pyi      # Type stubs
│       └── mongoose.pxd       # C declarations
├── tests/
│   ├── test_*.py              # Unit tests
│   └── examples/              # Example programs
├── thirdparty/
│   └── mongoose/              # Mongoose library
├── docs/                      # MkDocs documentation
├── CMakeLists.txt             # Build configuration
└── pyproject.toml             # Package metadata
```

## Code Style

### Python

```bash
# Format with ruff
ruff format .

# Lint
ruff check .

# Type check
mypy src/
```

### Cython

- 4-space indentation
- 100-character line limit
- Document all public functions
- Use type hints in .pyi files

### Documentation

```bash
# Build docs
make docs

# Serve locally with live reload
make docs-serve

# Deploy to GitHub Pages
make docs-deploy
```

## Releases

### Version Numbering

Follows semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Release Checklist

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Build and test distribution
5. Tag release
6. Push to PyPI

## Contributing

See [Contributing](contributing.md) for contribution guidelines.

## Useful Commands

```bash
# Run tests
make test

# Build extension
make build

# Clean build artifacts
make clean

# Format code
ruff format .

# Type check
mypy src/

# Build docs
make docs

# Run examples
python tests/examples/http/http_server.py
```

## Vendored Mongoose Patches

The vendored copy of mongoose (`thirdparty/mongoose/`) includes the following
local patches on top of the upstream release.  These must be re-applied after
upgrading the vendored source.

| File | Description |
|------|-------------|
| `mongoose.c:12583` | Free PKCS8 key buffer before returning error in `mg_tls_init`. Upstream leaks the `mg_parse_pem` allocation when a PKCS8 key is rejected. |

## See Also

- [Contributing](contributing.md) - Contribution guidelines
- [Mongoose Documentation](https://mongoose.ws/documentation/)
- [Cython Documentation](https://cython.readthedocs.io/)
