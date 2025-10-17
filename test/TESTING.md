# Testing Guide for DataProf Action

This guide explains how to test the DataProf GitHub Action locally and in CI/CD.

## Quick Test Commands

### Test Structure Overview

```
.github/workflows/
├── test.yml                      # Original basic tests (kept for backward compatibility)
└── comprehensive-test.yml        # New comprehensive test suite

test/
├── data/
│   ├── csv/                      # CSV test files
│   ├── json/                     # JSON test files
│   └── batch/                    # Batch processing test files
├── test_data.csv                 # Legacy test file
└── README.md                     # Test data documentation
```

## Running Tests

### Via GitHub Actions

#### Trigger All Tests

```bash
# Push to main branch
git push origin main

# Or create a PR
git checkout -b test-branch
git push origin test-branch
# Create PR on GitHub

# Or manually trigger
# Go to Actions tab → Select workflow → Run workflow
```

#### Test Specific Scenarios

The comprehensive test suite includes:

1. **test-csv-clean** - High quality CSV data
2. **test-csv-dirty** - Low quality CSV with issues
3. **test-csv-large** - Performance with larger datasets
4. **test-json-clean** - JSON format support
5. **test-json-incomplete** - JSON with missing data
6. **test-batch-csv** - Batch processing of CSV files
7. **test-batch-mixed-formats** - Mixed CSV and JSON batch
8. **test-quality-gate-pass** - Quality gate success
9. **test-quality-gate-warning** - Quality gate warning mode
10. **test-legacy-file** - Backward compatibility
11. **test-output-formats** - JSON, CSV, Text outputs

### Local Testing (Manual)

#### Prerequisites

1. Install dataprof CLI:
   ```bash
   cargo install dataprof
   ```

2. Verify installation:
   ```bash
   dataprof-cli --version
   ```

#### Test Single File Analysis

```bash
# CSV Analysis
dataprof-cli analyze test/data/csv/clean_data.csv --format json --detailed

# JSON Analysis
dataprof-cli analyze test/data/json/users.json --format json --detailed

# With output to file
dataprof-cli analyze test/data/csv/dirty_data.csv --format json --detailed > output.json
```

#### Test Batch Processing

```bash
# Batch analyze directory
dataprof-cli batch test/data/batch/ --format json --detailed

# With recursion
dataprof-cli batch test/data/batch/ --recursive --format json

# With parallel processing
dataprof-cli batch test/data/batch/ --parallel --format json
```

## Expected Test Results

### Clean Data (clean_data.csv)
- ✅ Quality Score: > 85%
- ✅ Quality Level: EXCELLENT or GOOD
- ✅ Issues Count: 0 or very low
- ✅ Completeness: > 95%
- ✅ Uniqueness: 100%

### Dirty Data (dirty_data.csv)
- ✅ Quality Score: 50-75%
- ✅ Quality Level: FAIR or POOR
- ✅ Issues Count: > 5
- ✅ Completeness: < 90%
- ✅ Uniqueness: < 100% (has duplicates)
- ✅ Validity: < 100% (invalid values)

### JSON Files
- ✅ users.json: Score > 85%
- ✅ transactions.json: Score ~80-90% (has 1 null)
- ✅ incomplete_records.json: Score < 60% (multiple issues)

### Batch Processing
- ✅ Files Analyzed: 3+ files
- ✅ Batch Summary: Non-empty
- ✅ Aggregated Metrics: Averaged scores
- ✅ JSON Export: Valid JSON file created

## Testing Checklist

Before submitting changes, ensure:

- [ ] All CSV format tests pass
- [ ] All JSON format tests pass
- [ ] Batch mode processes multiple files
- [ ] JSON export creates valid file
- [ ] Quality gates work (pass/fail/warn)
- [ ] High quality data scores > 85%
- [ ] Low quality data scores < 75%
- [ ] Issue detection works
- [ ] All output formats work (json, text)
- [ ] Backward compatibility with legacy files
- [ ] Error handling for invalid inputs

## Debugging Failed Tests

### Check Action Logs

1. Go to GitHub Actions tab
2. Click on failed workflow run
3. Expand failing job
4. Review step outputs

### Common Issues

#### Issue: "dataprof-cli not found"
**Solution**: Check dataprof installation step in action.yml

#### Issue: "Invalid JSON output"
**Solution**: Check parsing logic in action.yml, validate with `jq`

#### Issue: "Batch mode returns 0 files"
**Solution**: Verify file patterns and recursive flag

#### Issue: "Quality score is 0"
**Solution**: Check output parsing, may need to update JSON paths

### Local Debugging

```bash
# Run with debug output
set -x
dataprof-cli analyze test/data/csv/clean_data.csv --format json --detailed

# Validate JSON output
dataprof-cli analyze test/data/csv/clean_data.csv --format json --detailed | jq .

# Check specific metrics
dataprof-cli analyze test/data/csv/clean_data.csv --format json --detailed | \
  jq '.data_quality_metrics.completeness'
```

## Adding New Tests

### 1. Create Test Data

```bash
# Add new test file
echo "id,name,value" > test/data/csv/my_test.csv
echo "1,Test,100" >> test/data/csv/my_test.csv
```

### 2. Add Test Job to Workflow

```yaml
test-my-feature:
  runs-on: ubuntu-latest
  name: Test My Feature

  steps:
  - name: Checkout
    uses: actions/checkout@v4

  - name: Run Analysis
    id: test
    uses: ./
    with:
      file: 'test/data/csv/my_test.csv'
      quality-threshold: 80

  - name: Validate
    run: |
      score="${{ steps.test.outputs.quality-score }}"
      echo "Score: ${score}%"
```

### 3. Document Expected Results

Add to `test/README.md`:

```markdown
### my_test.csv
- Expected Quality Score: > 90%
- Key Features: [describe what it tests]
- Expected Issues: [list expected issues if any]
```

## Performance Benchmarks

Expected execution times on GitHub Actions (ubuntu-latest):

- Single CSV file (< 100 rows): ~30-60 seconds
- Single JSON file (< 100 records): ~30-60 seconds
- Large dataset (1000+ rows): ~60-120 seconds
- Batch mode (3-5 files): ~60-90 seconds
- With parallel processing: ~40-70 seconds

## CI/CD Integration Examples

### Pre-merge Quality Gate

```yaml
- name: Data Quality Check
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/production_data.csv'
    quality-threshold: 95
    fail-on-issues: true
```

### Nightly Quality Monitoring

```yaml
- name: Monitor Data Quality
  uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/'
    batch-mode: true
    recursive: true
    quality-threshold: 85
    fail-on-issues: false
    export-json-path: 'reports/quality_${{ github.run_number }}.json'
```

## Troubleshooting

### GitHub Actions Debugging

Enable debug logging:
```yaml
- name: Enable Debug
  run: echo "ACTIONS_STEP_DEBUG=true" >> $GITHUB_ENV
```

### Local Action Testing

Use [act](https://github.com/nektos/act) to run GitHub Actions locally:

```bash
# Install act
brew install act  # macOS
# or
choco install act  # Windows

# Run specific job
act -j test-csv-clean

# Run all jobs
act push
```

## Support

If tests fail unexpectedly:

1. Check [GitHub Actions logs](../../actions)
2. Review [test data documentation](README.md)
3. Verify dataprof version compatibility
4. Check [action.yml](../../action.yml) for recent changes
5. Open an issue with:
   - Failing test name
   - Error message
   - Expected vs actual results
