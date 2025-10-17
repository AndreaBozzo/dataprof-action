# GitHub Actions Workflows

This directory contains CI/CD workflows for testing the DataProf Action.

## Workflows

### test.yml
**Purpose**: Quick smoke tests for basic functionality
**Trigger**: Push to main, Pull requests, Manual dispatch
**Duration**: ~2-3 minutes
**Tests**:
- Basic CSV single file analysis
- Low quality data detection
- JSON format support
- JSON export feature
- Basic batch processing

**Use case**: Fast feedback during development, pre-merge checks

### comprehensive-test.yml
**Purpose**: Comprehensive test suite covering all features
**Trigger**: Push to main, Pull requests, Manual dispatch
**Duration**: ~5-10 minutes (tests run in parallel)
**Tests** (11 scenarios):
1. Clean CSV data analysis
2. Dirty CSV data detection
3. Large CSV dataset performance
4. JSON format - clean data
5. JSON format - incomplete data
6. Batch mode - CSV files
7. Batch mode - mixed formats
8. Quality gate - pass scenario
9. Quality gate - warning mode
10. Legacy file compatibility
11. Multiple output formats

**Use case**: Full validation before release, comprehensive feature testing

## Running Workflows

### Automatic Triggers
Both workflows run automatically on:
- Push to `main` branch
- Pull requests to `main` branch

### Manual Trigger
1. Go to **Actions** tab in GitHub
2. Select the workflow (test.yml or comprehensive-test.yml)
3. Click **Run workflow**
4. Select branch
5. Click **Run workflow** button

## Workflow Strategy

```
┌─────────────────────────────────────┐
│  Pull Request / Push to main        │
└──────────────┬──────────────────────┘
               │
               ├─────────────────────────────────┐
               │                                 │
               ▼                                 ▼
    ┌──────────────────┐              ┌──────────────────────┐
    │   test.yml       │              │ comprehensive-       │
    │   (Quick Tests)  │              │   test.yml           │
    │                  │              │   (Full Suite)       │
    │   ~2-3 min       │              │   ~5-10 min          │
    │   2 jobs         │              │   11 jobs (parallel) │
    └──────────────────┘              └──────────────────────┘
               │                                 │
               └─────────────┬───────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  All Tests Pass  │
                    │   ✅ Ready to    │
                    │     Merge/Deploy │
                    └──────────────────┘
```

## Test Results Interpretation

### Success Criteria
- ✅ All jobs complete with status "success"
- ✅ Quality scores match expected ranges
- ✅ No unexpected errors in logs
- ✅ All assertions pass

### Common Warnings (Expected)
- ⚠️  "Quality score lower than expected" on dirty data tests (this is correct!)
- ⚠️  "Expected some quality issues" on incomplete data tests (this is correct!)

### Failure Investigation
If tests fail:

1. **Check the logs**:
   - Click on the failed workflow run
   - Expand the failed job
   - Review step outputs

2. **Common issues**:
   - **dataprof installation failure**: Check if crates.io is accessible
   - **Parsing errors**: dataprof output format may have changed
   - **Timeout**: Large files or slow runners
   - **File not found**: Path issues (Windows vs Unix)

3. **Local reproduction**:
   ```bash
   # Test locally with same file
   dataprof-cli analyze test/data/csv/clean_data.csv --format json --detailed

   # Compare with expected output
   cat test/data/legacy/test_output.json
   ```

## Adding New Tests

### To test.yml (Quick Tests)
Add inline test data for rapid testing:
```yaml
- name: Create test data
  run: |
    mkdir -p test_data
    cat > test_data/my_test.csv << 'EOF'
    id,value
    1,100
    EOF
```

### To comprehensive-test.yml (Full Suite)
Use files from `test/data/`:
```yaml
test-my-feature:
  runs-on: ubuntu-latest
  name: Test My Feature

  steps:
  - uses: actions/checkout@v4

  - name: Run Test
    id: test
    uses: ./
    with:
      file: 'test/data/csv/my_test_file.csv'
      quality-threshold: 80
```

## Performance Optimization

Both workflows run jobs in parallel to minimize total execution time:

```
Sequential (old):        Parallel (current):
Job 1  ████ (2min)       Job 1  ████ (2min)
Job 2  ████ (2min)       Job 2  ████ (2min)  ← Same time
Job 3  ████ (2min)       Job 3  ████ (2min)  ← Same time
Total: 6 minutes         Total: 2 minutes
```

## Maintenance

### When to Update Workflows

- ✏️  New feature added to action.yml
- 📝 Input parameters changed
- 🐛 Bug fix requires new test case
- 📊 New output format supported
- 🔄 Breaking changes to dataprof CLI

### Checklist for Workflow Changes

- [ ] Update both workflows if feature is core functionality
- [ ] Update only comprehensive-test.yml if feature is advanced
- [ ] Add corresponding test data to `test/data/`
- [ ] Document expected results in `test/README.md`
- [ ] Update this README if workflow structure changes
- [ ] Test manually before committing

## See Also

- [Test Data Documentation](../../test/README.md)
- [Testing Guide](../../test/TESTING.md)
- [Action Documentation](../../README.md)
- [Changelog](../../CHANGELOG.md)
