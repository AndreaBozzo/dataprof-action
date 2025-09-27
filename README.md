# DataProf Action

A GitHub Action that analyzes CSV files for machine learning readiness using [dataprof](https://github.com/AndreaBozzo/dataprof).

## Usage

```yaml
- name: Analyze Data Quality
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/training_data.csv'
    ml-threshold: 80
    fail-on-issues: true
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `file` | Path to the CSV file to analyze | Yes | - |
| `ml-threshold` | ML readiness score threshold (0-100) | No | `80` |
| `fail-on-issues` | Fail job if score below threshold | No | `true` |
| `output-format` | Output format: json, csv, text | No | `json` |
| `generate-code` | Generate preprocessing code snippets | No | `true` |

## Outputs

| Output | Description |
|--------|-------------|
| `ml-score` | Overall ML readiness score (0-100) |
| `readiness-level` | Classification: Ready, Needs Work, Not Ready |
| `completeness-score` | Data completeness percentage |
| `consistency-score` | Data consistency percentage |
| `recommendations-count` | Number of improvement recommendations |
| `recommendations` | JSON array of detailed recommendations |
| `code-snippets` | Generated preprocessing code |

## License

MIT License - see [LICENSE](LICENSE) file for details.