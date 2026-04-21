# tests/ - Hermetic Test Rules

Use this guide when editing files under `tests/` or when adding new tests.

## Default Test Entry

- Prefer `scripts/run_tests.sh` over raw `pytest`.
- The wrapper keeps local runs closer to CI by controlling credential env vars, locale, timezone, worker count, and `HERMES_HOME` behavior.

## Rules

- Tests must not write to real `~/.hermes/` state.
- Respect the autouse isolation fixtures in `tests/conftest.py`.
- For profile-related tests, mock `Path.home()` **and** set `HERMES_HOME` so HOME-anchored and profile-anchored paths both resolve into the temp directory.
- If the wrapper truly cannot be used, keep raw pytest runs CI-like (for example `-n 4`).

## Validation

- Run the smallest focused test first, then the broader affected suite.
- If a change touches test isolation assumptions, inspect `tests/conftest.py` before changing individual tests.
