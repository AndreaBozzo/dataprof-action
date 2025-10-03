# DataProf Action

A GitHub Action that analyzes CSV files for data quality using [dataprof](https://github.com/AndreaBozzo/dataprof). Provides comprehensive ISO 8000/25012 compliant quality metrics and quality gates for CI/CD workflows.

## Features

- **ISO 8000/25012 Compliant**: Industry-standard data quality metrics
- **5 Quality Dimensions**: Completeness, Uniqueness, Consistency, Accuracy, and Timeliness
- **Quality Gates**: Configurable thresholds to enforce data quality standards
- **Multiple Output Formats**: JSON, CSV, or text output
- **Detailed Reporting**: Automatic workflow summaries with quality insights
- **Fast & Efficient**: Built on Rust, 20x more memory efficient than pandas

## Usage

```yaml
- name: Analyze Data Quality
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/dataset.csv'
    quality-threshold: 80
    fail-on-issues: true
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `file` | Path to the CSV file to analyze | Yes | - |
| `quality-threshold` | Overall quality score threshold (0-100) | No | `80` |
| `fail-on-issues` | Fail job if score below threshold | No | `true` |
| `output-format` | Output format: `json`, `csv`, `text` | No | `json` |
| `dataprof-version` | Version of dataprof to use (`latest` or specific version) | No | `latest` |

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
| `file-path` | Path of the analyzed file |
| `analysis-summary` | Human-readable analysis summary |

## Example Workflow

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

## License

MIT License - see [LICENSE](LICENSE) file for details.