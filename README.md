# DataProf Action

A GitHub composite action that profiles CSV, JSON, JSONL, and Parquet files and evaluates data quality gates using `python -m dataprof.check` from [dataprof](https://github.com/AndreaBozzo/dataprof).

## Requirements

- **Minimum dataprof version**: `0.15.0` (installed as a Python wheel into an isolated virtual environment under `$RUNNER_TEMP`; no Rust toolchain is installed and nothing is built at job runtime).
- **Python**: CPython 3.11 or newer on the runner, or configured via the optional `python-version` input.
- **Runners**: `ubuntu-latest`, `macos-latest`, and `windows-latest`.

The action delegates all profiling, scoring, baseline comparison, and verdict decisions to `dataprof.check`. It sets GitHub outputs from the `--json` result (and from the saved `--report` profile for single-source runs), writes a Markdown job summary, and maps the exit code to the step status.

## Usage Examples

### Single File Gate

```yaml
- name: Check dataset quality
  id: gate
  uses: AndreaBozzo/dataprof-action@v2
  with:
    file: data/orders.csv
    quality-threshold: '85'
```

### Directory Check (Multi-Source)

```yaml
- name: Check data directory
  id: batch
  uses: AndreaBozzo/dataprof-action@v2
  with:
    file: data/drops/
    recursive: 'true'
    quality-threshold: '80'
    export-json-path: reports/gate.json
```

Passing a directory, a glob pattern matching multiple files, or multiple space- or newline-separated paths runs `dataprof.check` in multi-source mode and lets dataprof decide the combined verdict.

### Policy File

```yaml
- name: Enforce quality policy
  uses: AndreaBozzo/dataprof-action@v2
  with:
    file: data/orders.parquet
    policy: policies/orders.json
    scope: full_source
    source-version: ${{ github.sha }}
```

### First-Run Baseline with Promotion

```yaml
- name: Check against baseline and promote on pass
  uses: AndreaBozzo/dataprof-action@v2
  with:
    file: data/orders.csv
    policy: policies/orders_baseline.json
    baseline: baselines/orders.json
    allow-missing-baseline: 'true'
    promote: baselines/orders.json
```

On the first run, when `baselines/orders.json` does not exist yet, `allow-missing-baseline` marks change rules as not applicable so absolute rules decide the verdict; on a pass, `promote` saves the profile atomically to `baselines/orders.json` for subsequent runs.

## Inputs

| Input | Description | Required | Default |
| --- | --- | --- | --- |
| `file` | File, directory, or glob pattern to check; space- or newline-separated for several sources | Yes | - |
| `recursive` | Pass `-r` to recurse into subdirectories of directory sources. A `**` glob in `file` always matches across subdirectories, whatever this is set to | No | `false` |
| `quality-threshold` | Minimum overall quality score (`0-100`), passed to `--min-quality`. Empty means no threshold unless set in `policy` | No | `''` |
| `policy` | Path to a UTF-8 JSON policy file (`--policy`) | No | `''` |
| `scope` | Evidence scope: `full_source` or `observed` (`--scope`) | No | `''` |
| `max-rows` | Cap the number of profiled rows (`--max-rows`) | No | `''` |
| `source-version` | Source version identifier recorded in saved reports and gate output (`--source-version`) | No | `''` |
| `baseline` | Saved baseline report JSON path (`--baseline`; single source only) | No | `''` |
| `allow-missing-baseline` | Allow an absent `baseline` file on the first run (`--allow-missing-baseline`; single source only) | No | `false` |
| `promote` | Path to atomically save the profile on a pass (`--promote`; single source only) | No | `''` |
| `fail-on-issues` | Fail the step on exit code `1` (verdict `fail`) | No | `true` |
| `fail-on-inconclusive` | Fail the step on exit code `2` (verdict `inconclusive`). Exit code `3` always fails | No | `true` |
| `export-json-path` | Path to write the raw `--json` document from `dataprof.check` | No | `''` |
| `dataprof-version` | Version of `dataprof` to install from PyPI (`0.15.0`, `latest`, or an exact pre-release such as `0.15.0rc1`) | No | `0.15.0` |
| `python-version` | Optional Python version (3.11 or newer) to set up via `actions/setup-python` | No | `''` |

## Outputs

Absent values are empty strings, never `"0"`. Score outputs (`quality-score` and `*-score`) and `report-path` are populated for single-source runs only and are empty for multi-source runs or when not analyzed.

| Output | Description |
| --- | --- |
| `verdict` | Gate verdict decided by dataprof: `pass`, `fail`, `inconclusive`, or `error` |
| `quality-score` | Overall quality score (`0-100`) from the saved profile report (single source only) |
| `completeness-score` | Completeness score (`0-100`) (single source only) |
| `uniqueness-score` | Uniqueness score (`0-100`) (single source only) |
| `validity-score` | Validity score (`0-100`) (single source only) |
| `consistency-score` | Consistency score (`0-100`) (single source only) |
| `timeliness-score` | Timeliness score (`0-100`) (single source only) |
| `accuracy-score` | Accuracy score (`0-100`) (single source only) |
| `precision-score` | Precision score (`0-100`) (single source only) |
| `violations-count` | Number of checks with status `failed` across evaluated sources |
| `unevaluated-count` | Number of checks with status `not_evaluated` across evaluated sources |
| `errors-count` | Number of source or invocation errors |
| `skipped-count` | Number of skipped files in a multi-source run |
| `file-path` | The `file` input passed to the action |
| `files-analyzed` | Number of sources that produced a gate result |
| `json-export-path` | Path to the exported `--json` document when `export-json-path` was set |
| `report-path` | Path to the saved full profile JSON under `$RUNNER_TEMP` (single source only) |
| `analysis-summary` | Short plain-text summary of the check |

## Exit Code Behaviour

| `dataprof.check` exit code | Verdict | Step result |
| --- | --- | --- |
| `0` | `pass` | Passes |
| `1` | `fail` | Fails when `fail-on-issues` is `true`; passes with a warning when `false` |
| `2` | `inconclusive` | Fails when `fail-on-inconclusive` is `true`; passes with a warning when `false` |
| `3` | `error` | Always fails |

## Migrating from v1

`v2` is a breaking release built on `dataprof` 0.15.0 (`python -m dataprof.check`). `v1` remains available at its existing tag for workflows that pin it.

### Runtime and Installation

- `v2` installs the `dataprof` Python wheel into a virtual environment under `$RUNNER_TEMP` instead of installing Rust and running `cargo install dataprof`.
- Requires `dataprof >= 0.15.0` and Python `>= 3.11`.
- Default `dataprof-version` changed from `latest` to `0.15.0`.

### Input Changes

- **Removed inputs**: `batch-mode`, `parallel`, `output-format`. Multi-source mode is triggered automatically when `file` is a directory, a glob matching multiple files, or several paths. Output is always JSON.
- **Changed default**: `quality-threshold` now defaults to `''` (empty) instead of `80`. Because `dataprof.check` requires at least one policy rule, set `quality-threshold` or `policy` explicitly.
- **New inputs**: `policy`, `scope`, `max-rows`, `source-version`, `baseline`, `allow-missing-baseline`, `promote`, `fail-on-inconclusive`, `python-version`.

### Output Changes

- **Removed outputs**: `quality-level`, `issues-count`, `batch-summary`.
- **Renamed output**: `issues-count` is replaced by `violations-count`.
- **New outputs**: `verdict`, `unevaluated-count`, `errors-count`, `skipped-count`, `report-path`, `precision-score`.
- **Changed score semantics**:
  - `quality-score` and all `*-score` outputs are read from dataprof's saved profile report rather than weighted in shell.
  - Missing or unanalyzed scores are empty strings (`""`), never `"0"`.
  - In multi-source runs, `quality-score`, all `*-score` outputs, and `report-path` are always empty strings.
- **Changed JSON export shape**: `export-json-path` now writes the exact `--json` document from `python -m dataprof.check` (`QualityGateResult` for a single source, `{"verdict", "sources", "skipped"}` for multiple sources, or `{"error": ...}` on a top-level error).

## License

MIT License. See [LICENSE](LICENSE).
