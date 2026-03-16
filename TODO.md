# TODO

## CI

- [ ] **Validate ASAN CI job** -- the `asan` job in `ci.yml` uses a hardcoded `libasan.so.8` path via `LD_PRELOAD`. Push to a branch and verify the Ubuntu runner finds the correct library. May need `gcc -print-file-name=libasan.so` for dynamic discovery.

## Documentation

- [ ] **Enable GitHub Pages** -- toggle the Pages source to "GitHub Actions" in repo settings so the docs workflow actually publishes. The `Documentation` URL in `pyproject.toml` already points to `https://shakfu.github.io/cymongoose/`.

- [ ] **Deduplicate README.md and MkDocs docs** -- README duplicates much of the MkDocs content. Consider having the README link to hosted docs for details.
