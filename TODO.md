# TODO

Tasks derived from [REVIEW.md](REVIEW.md) (v0.1.14 review), ordered by priority.
Validated and pruned -- dropped tasks that are already covered, impractical,
or fix theoretical paths that can't be reached in practice.

## Security

- [x] **#16 -- Validate `ws_upgrade` headers for CR/LF/NUL** (Medium)
  Extracted CR/LF/NUL validation into shared `_validate_header()` helper,
  called from both `reply()` and `ws_upgrade()`. 3 tests added.

## Correctness

- [x] **#18 -- Guard `poll()` against concurrent calls** (Medium)
  Added `_poll_count > 0` check at the top of `poll()`. Fixed one existing
  test that was calling `poll()` from the main thread while a background
  thread was polling. 1 test added.

## Test Coverage

- [x] **Add `serve_dir()` / `serve_file()` tests** (High)
  11 tests in `tests/test_serve_static.py`: text/binary/nested files,
  404 handling, HTML content-type, extra headers, custom 404 page,
  serve_file ignoring URI, and nonexistent file handling.

- [x] **Add MQTT pub/sub round-trip tests** (Medium)
  6 tests in `tests/test_mqtt_pubsub.py`: publish-and-receive with
  MqttMessage property verification (topic, data, text), binary payload,
  multiple messages, topic filtering, broker cmd property, and
  MG_EV_MQTT_OPEN event.

- [x] **Add `ws_upgrade` header injection tests** (Medium)
  Done as part of #16.

## Documentation

- [x] **Document `error_handler` expected signature** (Low)
  Added docstring to `Manager.__cinit__` showing the expected signature:
  `(exc: Exception) -> None`.

- [x] **Document `shutdown_timeout` in shutdown guide** (Low)
  Added "AsyncManager Shutdown" section to `docs/advanced/shutdown.md`
  with the 5-step shutdown sequence and a code example.

## CI

- [x] **Run network tests as a separate CI job** (Low)
  Added `network-tests` job to `.github/workflows/ci.yml` with
  `continue-on-error: true` so it doesn't block the pipeline.
