Development Documentation
=========================

This section contains documentation for contributors and developers.

.. toctree::
   :maxdepth: 2

   contributing

Development Setup
-----------------

Clone and Install
~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Clone repository
    git clone --recursive https://github.com/your-username/cymongoose.git
    cd cymongoose

    # Install with uv (recommended)
    uv sync

    # Or with pip
    pip install -e ".[dev]"

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

    # Run all tests
    make test

    # Or with pytest directly
    PYTHONPATH=src pytest tests/ -v

    # Run specific test file
    PYTHONPATH=src pytest tests/test_http_server.py -v

    # Run with coverage
    PYTHONPATH=src pytest tests/ --cov=cymongoose --cov-report=html

Build System
------------

Setuptools Build
~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Standard install
    pip install -e .

    # With options
    USE_NOGIL=0 pip install -e .  # Disable nogil
    USE_TLS=0 pip install -e .    # Disable TLS

    # Force rebuild
    pip install -e . --force-reinstall

CMake Build
~~~~~~~~~~~

.. code-block:: bash

    # Configure and build
    make build

    # Build variants
    UNIVERSAL=1 make build  # macOS universal binary
    CONFIG=Debug make build  # Debug build

    # Clean
    make clean

Code Structure
--------------

.. code-block:: text

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
    ├── docs/                      # Sphinx documentation
    ├── setup.py                   # Build configuration
    └── pyproject.toml             # Package metadata

Code Style
----------

Python
~~~~~~

.. code-block:: bash

    # Format with ruff
    ruff format .

    # Lint
    ruff check .

    # Type check
    mypy src/

Cython
~~~~~~

- 4-space indentation
- 100-character line limit
- Document all public functions
- Use type hints in .pyi files

Documentation
~~~~~~~~~~~~~

.. code-block:: bash

    # Build docs
    cd docs
    make html

    # View docs
    open _build/html/index.html

Releases
--------

Version Numbering
~~~~~~~~~~~~~~~~~

Follows semantic versioning: ``MAJOR.MINOR.PATCH``

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

Release Checklist
~~~~~~~~~~~~~~~~~

1. Update version in ``pyproject.toml``
2. Update ``CHANGELOG.md``
3. Run full test suite
4. Build and test distribution
5. Tag release
6. Push to PyPI

Contributing
------------

See :doc:`contributing` for contribution guidelines.

Useful Commands
---------------

.. code-block:: bash

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
    cd docs && make html

    # Run examples
    python tests/examples/http/http_server.py

See Also
--------

- :doc:`contributing` - Contribution guidelines
- `Mongoose Documentation <https://mongoose.ws/documentation/>`_
- `Cython Documentation <https://cython.readthedocs.io/>`_
