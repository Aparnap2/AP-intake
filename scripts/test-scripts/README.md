# Test Scripts

This directory contains standalone test scripts and specialized test suites.

## 🧪 Test Categories

### Integration Tests
- `test_enhanced_extraction_validation.py` - Enhanced extraction and validation tests
- `test_ar_models_simple.py` - Simple AR models tests
- `test_ar_integration.py` - AR integration tests
- `test_n8n_simple.py` - N8n workflow tests
- `test_cfo_digest_integration.py` - CFO digest integration tests
- `test_rbac_system.py` - Role-based access control tests
- `test_ap_intake.py` - Core AP intake tests

### Security Tests
- `security_compliance_test.py` - Security compliance validation
- `acceptance_criteria_test_suite.py` - Acceptance criteria validation

### UX Tests
- `ux_test_comprehensive.py` - Comprehensive UX testing

## 🚀 Usage

```bash
# Navigate to test scripts directory
cd scripts/test-scripts/

# Run specific test
python test_enhanced_extraction_validation.py

# Run all integration tests
python -m pytest test_*_integration.py

# Run security tests
python security_compliance_test.py
```

## 📝 Test Results

Test results and reports are generated in:
- `/tmp/test_results/` - Temporary test outputs
- `reports/` - Formal test reports and analysis

---

*These scripts are supplementary to the main test suite in `/tests/`.*