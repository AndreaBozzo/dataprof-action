# Test Data and Fixtures

This directory holds datasets used by `.github/workflows/comprehensive-test.yml` and recorded fixtures used by `test/test_dataprof_action.py`.

## Layout

- `test/data/csv/`: clean, dirty, edge-case, and larger CSV datasets.
- `test/data/json/`: clean, incomplete, and edge-case JSON datasets.
- `test/data/batch/`: mixed CSV and JSON files for multi-source directory checks.
- `test/data/invalid/`: malformed JSON file for error-path checks.
- `test/data/policies/`: JSON policy files used in baseline and gate tests.
- `test/fixtures/`: recorded `python -m dataprof.check --json` documents and `--report` profiles used by unit tests without requiring a `dataprof` wheel.
- `test/test_dataprof_action.py`: pytest suite covering argument building, glob expansion, exit codes, absent scores, multi-source errors/skips, baseline runs, and Markdown summary rendering.

## Running Unit Tests

```bash
pytest -v
ruff check scripts test
ruff format --check scripts test
```
