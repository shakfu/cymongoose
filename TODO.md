# TODO

## Code

## Testing

- [ ] **Add negative/adversarial tests** -- malformed HTTP requests, invalid WebSocket
  frames, oversized headers, connection flooding.

- [ ] **Add concurrent client tests** -- all HTTP tests currently use a single sequential
  `urllib` client.

- [x] **Add memory leak tests** -- Added AddressSanitizer (ASAN) support via `make build-asan` and `make test-asan`.

## Documentation

- [ ] **Deploy Sphinx docs** to ReadTheDocs or GitHub Pages so users can browse the API reference without building locally.

- [ ] **Update documentation URL** in `pyproject.toml` to point to hosted docs instead of the GitHub repo.

- [ ] **Clean up developer docs** -- some files (e.g., `ctrl_c_workaround.md`, `mg_http_delete_chunk.md`) are process artifacts rather than maintained reference material. Consider removing or consolidating.

- [ ] **Deduplicate README.md and Sphinx docs** -- README duplicates much of the Sphinx content. Consider having the README link to hosted docs for details.
