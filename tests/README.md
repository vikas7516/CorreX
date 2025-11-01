# CorreX Test Suite

This directory contains unit tests for the CorreX project.

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_keystroke_buffer.py
pytest tests/test_config_manager.py
pytest tests/test_history_manager.py
```

### Run with Coverage
```bash
pytest --cov=correX --cov-report=html
```

### Run Specific Test Class or Function
```bash
pytest tests/test_keystroke_buffer.py::TestKeystrokeBuffer
pytest tests/test_keystroke_buffer.py::TestKeystrokeBuffer::test_buffer_overflow
```

### Run Tests by Marker
```bash
pytest -m unit          # Only unit tests
pytest -m "not slow"    # Exclude slow tests
```

## Test Coverage

After running tests with coverage, view the HTML report:
```bash
# Open htmlcov/index.html in browser
start htmlcov/index.html    # Windows
```

## Test Structure

```
tests/
├── __init__.py                    # Test package initialization
├── test_keystroke_buffer.py       # Tests for keystroke buffer
├── test_config_manager.py         # Tests for configuration
├── test_history_manager.py        # Tests for history tracking
└── README.md                      # This file
```

## Writing New Tests

### Test File Naming
- Prefix with `test_`
- Match the module being tested: `test_<module_name>.py`

### Test Class Naming
- Prefix with `Test`
- Example: `TestKeystrokeBuffer`

### Test Method Naming
- Prefix with `test_`
- Descriptive name: `test_buffer_overflow`

### Example Test
```python
import unittest
from correX.your_module import YourClass

class TestYourClass(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.instance = YourClass()
    
    def test_something(self):
        """Test specific functionality."""
        result = self.instance.do_something()
        self.assertEqual(result, expected_value)
```

## Test Markers

Use pytest markers to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_basic_functionality():
    pass

@pytest.mark.slow
def test_long_running():
    pass

@pytest.mark.integration
def test_component_interaction():
    pass
```

## Continuous Integration

Tests are designed to run in CI/CD environments:
- No GUI dependencies (GUI tests are mocked)
- Isolated test fixtures (temp files, databases)
- Fast execution (<5 seconds for unit tests)

## Test Data

Tests use temporary directories for:
- Config files
- Database files
- Log files

All test data is cleaned up automatically in `tearDown()` methods.

## Coverage Goals

- **Core Logic:** 80%+ coverage
- **Configuration:** 90%+ coverage
- **Buffer Management:** 90%+ coverage
- **History Tracking:** 85%+ coverage

## Known Limitations

- GUI tests are limited (requires Windows environment)
- Keyboard hook tests require elevated permissions
- API tests are mocked (no real Gemini calls)

## Debugging Tests

### Run Single Test with Verbose Output
```bash
pytest tests/test_keystroke_buffer.py::test_buffer_overflow -vv
```

### Drop into PDB Debugger on Failure
```bash
pytest --pdb
```

### Show Print Statements
```bash
pytest -s
```

### Disable Warnings
```bash
pytest --disable-warnings
```

## Dependencies

Test dependencies are specified in `pyproject.toml`:
```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.10.0",
]
```

Install with:
```bash
pip install -e ".[test]"
```
