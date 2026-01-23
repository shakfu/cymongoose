# Release Process Guide

This document explains how to build and publish cymongoose wheels using the automated GitHub Actions workflow.

## Overview

The `build-wheels.yml` workflow uses cibuildwheel to build cross-platform binary wheels for cymongoose. It supports:

- **Platforms**: Linux (x86_64, aarch64), macOS (x86_64, arm64), Windows (AMD64)
- **Python versions**: 3.9, 3.10, 3.11, 3.12, 3.13
- **Publishing targets**: TestPyPI (for testing), PyPI (for production), or both

## Prerequisites

### 1. Configure Trusted Publishing on TestPyPI (Recommended First Step)

Before publishing to TestPyPI, configure trusted publishing:

1. Go to <https://test.pypi.org/manage/account/publishing/>
2. Click "Add a new publisher"
3. Fill in the form:
   - **PyPI Project Name**: `cymongoose`
   - **Owner**: `shakfu` (or your GitHub username)
   - **Repository name**: `cymongoose`
   - **Workflow name**: `build-wheels.yml`
   - **Environment name**: `testpypi`
4. Save the publisher

### 2. Configure Trusted Publishing on PyPI (For Production Releases)

Once you've tested with TestPyPI, configure production publishing:

1. Go to <https://pypi.org/manage/account/publishing/>
2. Click "Add a new publisher"
3. Fill in the same information as above, but use environment name: `pypi`

**Note**: You must already have the `cymongoose` package registered on PyPI. If not, you'll need to do an initial upload manually using an API token.

## Usage

### Step 1: Trigger the Workflow

1. Go to your GitHub repository: <https://github.com/shakfu/cymongoose>
2. Click on the "Actions" tab
3. Select "Build Wheels" from the left sidebar
4. Click "Run workflow" button
5. Choose your publishing target from the dropdown:
   - **none** (default): Only build wheels, don't publish
   - **testpypi**: Build and publish to TestPyPI (recommended for testing)
   - **pypi**: Build and publish to production PyPI
   - **both**: Publish to both TestPyPI and PyPI simultaneously
6. Click "Run workflow"

### Step 2: Monitor the Build

The workflow will:

1. Build wheels for all platforms (30-60 minutes)
2. Run tests on each built wheel
3. Upload artifacts (wheels + source distribution)
4. Publish to selected target(s) if specified

### Step 3: Test Installation (TestPyPI)

After publishing to TestPyPI, test the installation:

```bash
# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ cymongoose

# Or with dependencies from PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ cymongoose
```

Verify it works:

```python
from cymongoose import Manager, MG_EV_HTTP_MSG

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"Hello from cymongoose!")

manager = Manager(handler)
print("cymongoose imported successfully!")
```

### Step 4: Publish to Production (PyPI)

Once you've verified the TestPyPI build works correctly:

1. Update version in `pyproject.toml` if needed
2. Run the workflow again with `publish_target: pypi`
3. Verify at <https://pypi.org/project/cymongoose/>

## Recommended Workflow

1. **Development**:
   - Make changes
   - Run `make test` locally
   - Update version in `pyproject.toml`
   - Commit and push

2. **Testing**:
   - Run workflow with `publish_target: testpypi`
   - Download and test the built wheels
   - Test installation from TestPyPI

3. **Production**:
   - Run workflow with `publish_target: pypi`
   - Create a GitHub release
   - Announce the new version

## Manual Download (Without Publishing)

If you want to test wheels without publishing:

1. Run workflow with `publish_target: none`
2. Go to the workflow run page
3. Download artifacts from the "Artifacts" section
4. Install locally: `pip install path/to/wheel.whl`

## Troubleshooting

### "Trusted publisher configuration mismatch"

This means the GitHub repository, workflow name, or environment name doesn't match what you configured on PyPI. Double-check:

- Repository owner and name
- Workflow filename: `build-wheels.yml`
- Environment name: `testpypi` or `pypi`

### "Project does not exist on PyPI"

For the first PyPI upload, you need to:

1. Register the project manually, OR
2. Use an API token for the first upload, OR
3. Configure trusted publishing with "Pending Publisher" status

### Build Failures

Check the workflow logs for:

- Cython compilation errors
- Test failures (consider disabling tests temporarily with `CIBW_TEST_COMMAND`)
- Platform-specific issues (check individual job logs)

### Wheels Not Found

Ensure your `setup.py` and `pyproject.toml` are correctly configured:

- `ext_modules` must be defined in `setup.py`
- Cython must be available during build
- Source files must be included in the source distribution

## Version Management

Before each release:

1. Update version in `pyproject.toml`:

   ```toml
   [project]
   version = "0.1.5"  # Increment as needed
   ```

2. Tag the release:

   ```bash
   git tag v0.1.5
   git push origin v0.1.5
   ```

3. Run the build workflow

## Additional Resources

- [cibuildwheel documentation](https://cibuildwheel.readthedocs.io/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [Python Packaging Guide](https://packaging.python.org/)
