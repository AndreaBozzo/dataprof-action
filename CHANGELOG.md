# Changelog

All notable changes to the DataProf GitHub Action are documented in this file.

## [2.0.0] - Unreleased

Breaking rewrite targeting `dataprof >= 0.14.1` and `python -m dataprof.check`.

### Breaking Changes

- Replaced the `cargo install dataprof` / `dataprof-cli` runtime with `pip install dataprof==<version>` inside an isolated Python virtual environment under `$RUNNER_TEMP`. Requires Python 3.11 or newer and `dataprof >= 0.14.1`.
- Removed inputs: `batch-mode`, `parallel`, `output-format`. Passing a directory, a glob pattern matching more than one file, or multiple paths runs `dataprof.check` in multi-source mode directly; a glob matching a single regular file runs in single-source mode with score outputs and `report-path`.
- Changed `quality-threshold` default from `80` to `''` (empty). Set `quality-threshold` or `policy` explicitly.
- Changed `dataprof-version` default from `latest` to `0.14.1`.
- Removed outputs: `quality-level`, `issues-count`, `batch-summary`. Replaced `issues-count` with `violations-count`.
- Removed all in-action scoring, weighting, quality-level bucketing, and threshold comparisons. The step result follows dataprof's exit code directly (`0` pass, `1` fail controlled by `fail-on-issues`, `2` inconclusive controlled by `fail-on-inconclusive`, `3` error always fails).
- `quality-score`, dimension `*-score` outputs, and `report-path` are now populated only in single-source runs from dataprof's `--report` profile JSON. Absent metrics and multi-source runs output empty strings, never `"0"`.
- `export-json-path` now writes the raw `--json` document emitted by `python -m dataprof.check`.

### Added

- `policy` takes a path to a JSON policy file or the policy as inline JSON, so a workflow can state its rules without a separate file.
- New inputs: `policy`, `scope`, `max-rows`, `source-version`, `baseline`, `allow-missing-baseline`, `promote`, `fail-on-inconclusive`, `python-version`.
- New outputs: `verdict`, `violations-count`, `unevaluated-count`, `errors-count`, `skipped-count`, `report-path`, `precision-score`.
- Python runner script (`scripts/dataprof_action.py`) with stdlib-only unit tests over recorded `--json` and `--report` fixtures under `test/fixtures/`.
- Cross-platform CI matrix (`ubuntu-latest`, `macos-latest`, `windows-latest`) covering pass, fail, inconclusive, error, multi-source directory, and first-run baseline promotion flows.

### Removed

- Deleted obsolete v1 documentation (`docs/CLAUDE.md`, `test/TESTING.md`, `.github/workflows/README.md`).

## [1.0.50] - 2025-10-17

### Added
- Multi-format support for CSV, JSON, and Parquet via `dataprof-cli`.
- Batch processing (`batch-mode`, `parallel`, `recursive`) and JSON export (`export-json-path`).
- Comprehensive workflow test suite and test datasets under `test/data/`.

## [1.0.0] - Previous Release

### Added
- Initial CSV data quality analysis action built on `dataprof-cli`.
