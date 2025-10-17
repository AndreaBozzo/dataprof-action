# Changelog

All notable changes to the DataProf GitHub Action will be documented in this file.

## [Unreleased]

### Added
- **Multi-Format Support**: Full support for CSV, JSON, and Parquet file formats
- **Batch Processing**: New `batch-mode` input for analyzing multiple files in one run
- **Parallel Processing**: `parallel` flag for faster batch processing
- **Recursive Directory Scanning**: `recursive` flag for deep directory traversal
- **JSON Export**: `export-json-path` input to save detailed analysis results
- **New Outputs**:
  - `files-analyzed`: Number of files processed in batch mode
  - `json-export-path`: Path to exported JSON file
  - `batch-summary`: Human-readable summary of batch results
- **Comprehensive Test Suite**:
  - 13 test data files covering various scenarios
  - New `comprehensive-test.yml` workflow with 11 test jobs
  - Edge case tests for special characters, unicode, nested structures
  - Batch processing tests with mixed formats
- **Documentation**:
  - `test/README.md`: Complete test data documentation
  - `test/TESTING.md`: Testing guide with examples and troubleshooting
  - Extended README with multiple usage examples

### Changed
- **Input Validation**: Enhanced to support multiple file formats (CSV, JSON, Parquet)
- **File Detection**: Removed strict `.csv` extension requirement
- **Analysis Logic**: Supports both `analyze` (single file) and `batch` (multiple files) commands
- **Output Parsing**:
  - Intelligent detection of single vs batch output
  - Aggregation of metrics across multiple files
  - Improved error handling and fallbacks
- **Workflow Summary**: Enhanced with batch mode indicators and file counts
- **README**: Complete rewrite with examples for all formats and features

### Fixed
- File path handling in batch mode
- JSON export functionality with proper directory creation
- Output parsing for various dataprof output structures
- Quality level calculation consistency

### Technical Details
- Action size: 689 lines (comprehensive implementation)
- Documentation: 216 lines README + additional guides
- Test coverage: 11 automated test scenarios
- Test data: 13 files covering CSV, JSON, edge cases, and batch scenarios
- Supported formats: CSV, JSON, Parquet (via dataprof CLI)
- Version-agnostic: Works with any dataprof version without hardcoded dependencies

## [1.0.0] - Previous Release

### Features
- Basic CSV file analysis
- Single file quality assessment
- ISO 8000/25012 compliant metrics
- Quality gate enforcement
- GitHub Actions workflow integration

---

## Migration Guide

### From v1.0.0 to v2.0.0

#### Backward Compatibility
All existing workflows continue to work without changes. The action is 100% backward compatible.

#### New Features Usage

**Multi-format support:**
```yaml
# Before (CSV only)
- uses: AndreaBozzo/dataprof-action@v1
  with:
    file: 'data/file.csv'

# Now (CSV, JSON, Parquet)
- uses: AndreaBozzo/dataprof-action@v2
  with:
    file: 'data/file.json'  # or .parquet
```

**Batch processing:**
```yaml
# New feature
- uses: AndreaBozzo/dataprof-action@v2
  with:
    file: 'data/'
    batch-mode: true
    recursive: true
    parallel: true
```

**JSON export:**
```yaml
# New feature
- uses: AndreaBozzo/dataprof-action@v2
  with:
    file: 'data/file.csv'
    export-json-path: 'reports/quality.json'

# Use in next step
- run: |
    cat reports/quality.json | jq '.data_quality_metrics'
```

#### Breaking Changes
None. The action maintains full backward compatibility.

#### Deprecated Features
None.

## Testing

All changes have been validated with:
- ✅ 11 automated test scenarios
- ✅ Clean data validation (>85% quality expected)
- ✅ Dirty data detection (<75% quality expected)
- ✅ Large dataset performance
- ✅ JSON format analysis
- ✅ Batch processing (3-5 files)
- ✅ Quality gate enforcement
- ✅ JSON export functionality
- ✅ Multiple output formats
- ✅ Legacy file compatibility

## Links
- [Repository](https://github.com/AndreaBozzo/dataprof-action)
- [DataProf CLI](https://github.com/AndreaBozzo/dataprof)
- [Issues](https://github.com/AndreaBozzo/dataprof-action/issues)
