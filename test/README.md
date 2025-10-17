# Test Data Files

This directory contains test data files for validating the DataProf GitHub Action.

## Directory Structure

```
test/
├── data/
│   ├── csv/          # CSV test files
│   │   ├── clean_data.csv           # High quality data with no issues
│   │   ├── dirty_data.csv           # Data with quality issues (duplicates, missing values, invalid data)
│   │   └── large_dataset.csv        # Larger dataset for performance testing
│   ├── json/         # JSON test files
│   │   ├── users.json               # Clean user records
│   │   ├── transactions.json        # Transaction data with some nulls
│   │   └── incomplete_records.json  # Records with missing fields
│   └── batch/        # Files for batch processing tests
│       ├── customers_q1.csv         # Q1 customer data
│       ├── customers_q2.csv         # Q2 customer data (with issues)
│       ├── customers_q3.csv         # Q3 customer data (with issues)
│       ├── products_electronics.json # Electronics products
│       └── products_furniture.json   # Furniture products (with nulls)
└── legacy/           # Legacy test files (preserved for reference)
    ├── test_data.csv         # Original customer data test
    ├── test_data_2.csv       # Product data test
    ├── test_data_3.csv       # Employee data test
    └── test_output.json      # Sample dataprof output format

## Test File Descriptions

### CSV Files

**clean_data.csv**
- 15 employee records
- All fields complete and valid
- Expected quality score: > 90%
- Tests: Basic functionality, high quality data

**dirty_data.csv**
- 15+ employee records with various quality issues:
  - Missing emails (rows 2, 8, 10)
  - Missing names (rows 5, 10)
  - Invalid age values (row 3: 999)
  - Negative salary (row 4: -5000)
  - Invalid performance scores (row 4: 150, out of range)
  - Missing departments (row 6)
  - Missing status (row 7)
  - Duplicate IDs (rows 11, 12)
  - Invalid date formats (row 3)
- Expected quality score: < 70%
- Tests: Quality issue detection, completeness, uniqueness, validity

**large_dataset.csv**
- 30 product records
- Clean data with realistic values
- Expected quality score: > 95%
- Tests: Performance with larger datasets

### JSON Files

**users.json**
- 5 user records with nested preferences object
- All fields complete
- Expected quality score: > 90%
- Tests: JSON format support, nested structures

**transactions.json**
- 6 transaction records
- Contains null values (row 4: null amount)
- Expected quality score: ~85%
- Tests: JSON with missing values, completeness metric

**incomplete_records.json**
- 6 contact records with progressive data quality issues
- Multiple missing/null fields
- Empty strings (row 6)
- Expected quality score: < 60%
- Tests: Severe data quality issues in JSON format

### Batch Files

**customers_q1.csv, customers_q2.csv, customers_q3.csv**
- Quarterly customer data (5 records each)
- Q2 and Q3 contain missing email addresses
- Tests: Batch processing, aggregation of metrics across files

**products_electronics.json, products_furniture.json**
- Product catalog data
- Furniture file contains null stock value
- Tests: Batch processing of JSON files, mixed quality data

### Legacy Files

**test_data.csv, test_data_2.csv, test_data_3.csv**
- Original test files from earlier versions
- Preserved for reference and backward compatibility testing
- Located in `test/data/legacy/`

**test_output.json**
- Sample output structure from dataprof CLI
- Useful for understanding expected JSON format
- Located in `test/data/legacy/`

## Usage in Tests

These files are used by `.github/workflows/comprehensive-test.yml` to test:

1. **Single file analysis** (CSV and JSON)
2. **High quality vs low quality detection**
3. **Batch processing mode**
4. **JSON export functionality**
5. **Multi-format support**
6. **Edge cases and error handling**

## Expected Outcomes

| File | Expected Quality Score | Key Issues |
|------|----------------------|------------|
| clean_data.csv | > 90% | None |
| dirty_data.csv | < 70% | Duplicates, missing values, invalid data |
| large_dataset.csv | > 95% | None |
| users.json | > 90% | None |
| transactions.json | ~85% | 1 null value |
| incomplete_records.json | < 60% | Multiple nulls, empty strings |
| Batch CSV (combined) | ~80% | Some missing emails |
| Batch JSON (combined) | ~90% | 1 null value |
