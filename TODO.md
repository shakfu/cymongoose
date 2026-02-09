# TODO

## Code

## Testing

- [x] **Add negative/adversarial tests** -- malformed HTTP requests, invalid WebSocket frames, oversized headers, connection flooding. (`tests/test_adversarial.py`, 12 tests)

- [x] **Add concurrent client tests** -- all HTTP tests currently use a single sequential `urllib` client. (`tests/test_concurrent_clients.py`, 6 tests)

## Documentation

- [ ] **Deploy Sphinx docs** to ReadTheDocs or GitHub Pages so users can browse the API reference without building locally.

- [ ] **Update documentation URL** in `pyproject.toml` to point to hosted docs instead of the GitHub repo.

- [ ] **Deduplicate README.md and Sphinx docs** -- README duplicates much of the Sphinx content. Consider having the README link to hosted docs for details.
