# Installation

## Requirements

- Python 3.10 or higher
- C compiler (gcc, clang, or MSVC)
- CMake 3.15+

### Dependencies

cymongoose has **zero runtime dependencies**. Build dependencies are handled
automatically:

- **Cython** (>=3.0) - Compiles `.pyx` to C
- **scikit-build-core** - CMake-based build backend

Optional dependencies for development:

- **pytest** - Running tests
- **websocket-client** - WebSocket client tests
- **aiohttp, fastapi, uvicorn, flask** - Benchmark comparisons

## Install from PyPI

The easiest way to install cymongoose is from PyPI:

```bash
pip install cymongoose
```

This will download and install the latest stable release along with all
required dependencies.

## Install from Source

### Using pip

To install the latest development version from the repository:

```bash
git clone https://github.com/shakfu/cymongoose.git
cd cymongoose
pip install -e .
```

### Using uv (Recommended for Development)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer
and resolver:

```bash
git clone https://github.com/shakfu/cymongoose.git
cd cymongoose
uv sync
```

This will:

1. Create a virtual environment
2. Install all dependencies
3. Build the Cython extension
4. Install cymongoose in editable mode

### Using CMake (Alternative)

For advanced users who prefer CMake:

```bash
git clone https://github.com/shakfu/cymongoose.git
cd cymongoose
make build
```

### Build Options

```bash
# Build with AddressSanitizer (memory error detection)
make build-asan

# Run tests with AddressSanitizer
make test-asan
```

## Verifying Installation

After installation, verify it works:

```python
import cymongoose
print(cymongoose.__version__)

# Check available constants
from cymongoose import (
    Manager,
    Connection,
    MG_EV_HTTP_MSG,
    MG_EV_WS_MSG,
    WEBSOCKET_OP_TEXT,
)
print("Installation successful!")
```

## Running Tests

To run the test suite:

```bash
# Using make (recommended)
make test

# With coverage report
make coverage

# Using pytest directly
uv run pytest tests/ -v
```

All 366 tests should pass. If you encounter failures, please report them
on the [issue tracker](https://github.com/shakfu/cymongoose/issues).

### Common Makefile Commands

```bash
make help           # Show all available commands
make sync           # Install dependencies
make build          # Rebuild extension
make test           # Run tests
make lint           # Lint with ruff
make typecheck      # Type check with mypy
make qa             # Full quality assurance
make docs           # Build documentation
make docs-serve     # Serve docs locally with live reload
make docs-deploy    # Deploy docs to GitHub Pages
make clean          # Remove build artifacts
```

## Troubleshooting

### Build Errors

**Error: "Cython not found"**

Install Cython:

```bash
pip install cython
```

**Error: "C compiler not found"**

Install a C compiler:

- **Linux**: `sudo apt-get install build-essential`
- **macOS**: `xcode-select --install`
- **Windows**: Install Visual Studio with C++ tools

**Error: "mongoose.h not found"**

The Mongoose library is vendored in `thirdparty/mongoose/`. Ensure
you've cloned the repository completely:

```bash
git clone --recursive https://github.com/shakfu/cymongoose.git
```

### Import Errors

**Error: "ImportError: cannot import name 'Manager'"**

This usually means the extension wasn't built. Try:

```bash
pip install -e . --force-reinstall
```

**Error: "Symbol not found" or "DLL load failed" on macOS**

Rebuild with:

```bash
pip uninstall cymongoose
pip install -e . --no-cache-dir
```

### Performance Issues

If performance is lower than expected:

1. Ensure you're using `poll(100)` not `poll(5000)`

For more help, see the [Troubleshooting](advanced/troubleshooting.md) guide.

## Next Steps

- Follow the [Quickstart](quickstart.md) guide to build your first application
- Browse [Examples](examples.md) for common use cases
- Read the [User Guide](guide/index.md) for protocol-specific documentation
