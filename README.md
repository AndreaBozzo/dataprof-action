# DataProf Action

A GitHub Action that analyzes CSV, JSON, and Parquet files for data quality using [dataprof](https://github.com/AndreaBozzo/dataprof). Provides comprehensive ISO 8000/25012 compliant quality metrics and quality gates for CI/CD workflows with batch processing support.

## Features

- **Multi-Format Support**: Analyze CSV, JSON, and Parquet files
- **Batch Processing**: Process multiple files or entire directories in parallel
- **ISO 8000/25012 Compliant**: Industry-standard data quality metrics
- **5 Quality Dimensions**: Completeness, Uniqueness, Consistency, Accuracy, and Timeliness
- **Quality Gates**: Configurable thresholds to enforce data quality standards
- **JSON Export**: Export detailed results for downstream processing
- **Detailed Reporting**: Automatic workflow summaries with quality insights
- **Fast & Efficient**: Built on Rust, 20x more memory efficient than pandas

## Quick Start

### Single File Analysis

```yaml
- name: Analyze Data Quality
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/dataset.csv'
    quality-threshold: 80
    fail-on-issues: true
```

### Batch Processing

```yaml
- name: Analyze Multiple Files
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/'
    batch-mode: true
    recursive: true
    parallel: true
    quality-threshold: 85
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `file` | Path to file(s) to analyze. Single file, directory, or glob pattern (e.g., `data/**/*.csv`). Supports CSV, JSON, and Parquet formats. | Yes | - |
| `batch-mode` | Enable batch processing mode for analyzing multiple files | No | `false` |
| `recursive` | Recursively process directories when batch-mode is enabled | No | `false` |
| `parallel` | Enable parallel processing for batch mode (faster for multiple files) | No | `true` |
| `quality-threshold` | Overall quality score threshold (0-100). Job fails if score is below this value. | No | `80` |
| `fail-on-issues` | Fail job if score below threshold | No | `true` |
| `output-format` | Output format: `json`, `csv`, `text`. JSON recommended for detailed export. | No | `json` |
| `export-json-path` | Optional path to export detailed JSON results for downstream processing | No | `''` |
| `dataprof-version` | Version of dataprof to use (`latest` or specific version like `v0.4.77`) | No | `latest` |

## Outputs

| Output | Description |
|--------|-------------|
| `quality-score` | Overall data quality score (0-100) |
| `quality-level` | Quality level: EXCELLENT, GOOD, FAIR, POOR |
| `completeness-score` | Data completeness score (0-100) |
| `uniqueness-score` | Data uniqueness score (0-100) |
| `validity-score` | Data validity score (0-100) |
| `consistency-score` | Data consistency score (0-100) |
| `timeliness-score` | Data timeliness score (0-100) |
| `accuracy-score` | Data accuracy score (0-100) |
| `issues-count` | Total number of quality issues detected |
| `file-path` | Path of the analyzed file(s) |
| `files-analyzed` | Number of files analyzed (useful in batch mode) |
| `json-export-path` | Path to exported JSON file (if export-json-path was specified) |
| `batch-summary` | Summary of batch processing results (when batch-mode is enabled) |
| `analysis-summary` | Human-readable analysis summary |

## Example Workflows

### Basic CSV Analysis

```yaml
name: Data Quality Check

on:
  pull_request:
    paths:
      - 'data/**/*.csv'

jobs:
  quality-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check Data Quality
        id: dataprof
        uses: AndreaBozzo/dataprof-action@v1
        with:
          file: 'data/production_data.csv'
          quality-threshold: 85
          fail-on-issues: true

      - name: Comment on PR
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Data Quality Report\n\n**Score**: ${{ steps.dataprof.outputs.quality-score }}%\n**Level**: ${{ steps.dataprof.outputs.quality-level }}\n**Issues**: ${{ steps.dataprof.outputs.issues-count }}`
            })
```

### Multi-Format Support

```yaml
- name: Analyze JSON Data
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/api_responses.json'
    quality-threshold: 90
    output-format: json

- name: Analyze Parquet Data
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/warehouse_data.parquet'
    quality-threshold: 85
    output-format: json
```

### Batch Processing with JSON Export

```yaml
- name: Batch Analyze All Data Files
  id: batch-analysis
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/'
    batch-mode: true
    recursive: true
    parallel: true
    quality-threshold: 80
    export-json-path: 'reports/quality_analysis.json'

- name: Upload Quality Report
  uses: actions/upload-artifact@v4
  with:
    name: quality-report
    path: reports/quality_analysis.json

- name: Process Results
  run: |
    echo "Analyzed ${{ steps.batch-analysis.outputs.files-analyzed }} files"
    echo "Average Quality Score: ${{ steps.batch-analysis.outputs.quality-score }}%"
    echo "Total Issues: ${{ steps.batch-analysis.outputs.issues-count }}"
```

### Advanced: Quality Gates with Custom Thresholds

```yaml
- name: Strict Quality Check for Production Data
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/prod/*.csv'
    batch-mode: true
    recursive: false
    quality-threshold: 95
    fail-on-issues: true

- name: Lenient Check for Development Data
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/dev/*.json'
    batch-mode: true
    quality-threshold: 70
    fail-on-issues: false
```

### Using Exported JSON in Downstream Steps

```yaml
- name: Run Quality Analysis
  id: quality
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/dataset.csv'
    export-json-path: 'quality_report.json'

- name: Custom Processing of Results
  run: |
    # Read the exported JSON
    completeness=$(jq '.data_quality_metrics.completeness.complete_records_ratio' quality_report.json)

    if (( $(echo "$completeness < 90" | bc -l) )); then
      echo "::warning::Completeness below 90%: $completeness%"
    fi

- name: Send to Monitoring System
  run: |
    curl -X POST https://monitoring.example.com/metrics \
      -H "Content-Type: application/json" \
      -d @quality_report.json
```

## Supported File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| CSV | `.csv` | Standard comma-separated values |
| JSON | `.json` | Structured JSON data |
| Parquet | `.parquet` | Columnar storage format |

All formats support the full suite of data quality metrics.

## License

MIT License - see [LICENSE](LICENSE) file for details.