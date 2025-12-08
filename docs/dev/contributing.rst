Contributing Guide
==================

We welcome contributions to cymongoose! This guide will help you get started.

Ways to Contribute
------------------

- **Bug Reports**: Report issues on GitHub
- **Feature Requests**: Suggest new features
- **Documentation**: Improve docs and examples
- **Code**: Fix bugs or add features
- **Testing**: Add test cases
- **Examples**: Add usage examples

Getting Started
---------------

1. Fork the Repository
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Fork on GitHub, then clone
    git clone https://github.com/YOUR-USERNAME/cymongoose.git
    cd cymongoose

2. Set Up Development Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Install development dependencies
    uv sync

    # Or with pip
    pip install -e ".[dev]"

3. Create a Branch
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    git checkout -b feature-name

Code Guidelines
---------------

Style
~~~~~

- Follow PEP 8 for Python code
- Use 4-space indentation
- 100-character line limit
- Use double quotes for strings

Testing
~~~~~~~

**All code must be tested!**

.. code-block:: bash

    # Run tests
    make test

    # Add tests in tests/ directory
    # tests/test_feature.py

Example test:

.. code-block:: python

    def test_my_feature():
        manager = Manager()
        # Test your feature
        assert something == expected

Documentation
~~~~~~~~~~~~~

- Add docstrings to all public functions
- Update relevant .rst files in docs/
- Include examples

Pull Request Process
--------------------

1. Write Tests
~~~~~~~~~~~~~~

Ensure your changes are covered by tests:

.. code-block:: bash

    PYTHONPATH=src pytest tests/ -v

All tests must pass!

2. Update Documentation
~~~~~~~~~~~~~~~~~~~~~~~~

- Add docstrings
- Update relevant documentation
- Add examples if needed

3. Format Code
~~~~~~~~~~~~~~

.. code-block:: bash

    ruff format .
    ruff check .

4. Commit Changes
~~~~~~~~~~~~~~~~~

.. code-block:: bash

    git add .
    git commit -m "Add feature: description"

Use clear commit messages:

- "Fix: description of bug fix"
- "Add: new feature description"
- "Update: what was updated"
- "Docs: documentation changes"

5. Push and Create PR
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    git push origin feature-name

Create pull request on GitHub.

PR Checklist
~~~~~~~~~~~~

- [ ] Tests pass
- [ ] Code formatted with ruff
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] No merge conflicts

Review Process
--------------

1. Maintainer reviews your PR
2. Address any feedback
3. Once approved, PR is merged

Common Tasks
------------

Adding a New Feature
~~~~~~~~~~~~~~~~~~~~

1. Write tests first (TDD)
2. Implement feature
3. Update documentation
4. Submit PR

Fixing a Bug
~~~~~~~~~~~~

1. Write test that reproduces bug
2. Fix bug
3. Verify test passes
4. Submit PR

Adding Examples
~~~~~~~~~~~~~~~

1. Add example in ``tests/examples/``
2. Make it runnable: ``python tests/examples/your_example.py``
3. Add test in ``tests/examples/test_*.py``
4. Document in ``docs/examples.rst``

Updating Documentation
~~~~~~~~~~~~~~~~~~~~~~

1. Edit .rst files in ``docs/``
2. Build locally: ``cd docs && make html``
3. Check output in ``docs/_build/html/``
4. Submit PR

Development Tips
----------------

Rebuilding After Changes
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Force rebuild after Cython changes
    rm src/cymongoose/_mongoose.c
    pip install -e . --force-reinstall

Debug Build
~~~~~~~~~~~

.. code-block:: bash

    # Build with debug symbols
    CONFIG=Debug make build

Verbose Tests
~~~~~~~~~~~~~

.. code-block:: bash

    # Show print statements
    PYTHONPATH=src pytest tests/ -v -s

Test Single File
~~~~~~~~~~~~~~~~

.. code-block:: bash

    PYTHONPATH=src pytest tests/test_http_server.py -v

Communication
-------------

- **GitHub Issues**: Bug reports and feature requests
- **Pull Requests**: Code contributions
- **Discussions**: Questions and ideas

Code of Conduct
---------------

Be respectful and professional in all interactions.

Questions?
----------

Feel free to open an issue or discussion on GitHub.

Thank You!
----------

Thank you for contributing to cymongoose!
