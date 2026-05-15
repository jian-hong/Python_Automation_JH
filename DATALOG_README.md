# LabAutomation Datalog System

This document describes the integrated datalog system for the LabAutomation workspace.

## Overview

The datalog system provides automated logging of test results to CSV format with built-in pass/fail analysis based on predefined specifications.

## Features

- **CSV Export**: Exports test results to CSV with columns: `parameters`, `min`, `max`, `T_ms`, `Value`, `pass_fail`, `soft_bin`
- **Automatic Pass/Fail**: Determines pass/fail status based on configurable tolerances
- **Duration Logging**: `T_ms` now stores measurement duration in milliseconds for each parameter
- **Selective Logging**: Only tests that are actually run are included in the datalog
- **Metadata Header**: Adds `Beginning Time`, `Ending Time`, `userID`, `runID`, `test_name`, `Pass/Fail`, and `Soft Bin` at the top of the CSV
- **Append Mode**: Appends new results to existing CSV files
- **Summary Reports**: Provides pass/fail statistics

## Usage

### Basic Usage

```python
from datalog import DataLogger

# Create logger
logger = DataLogger('test_results.csv')

# Log test results using measurement duration
logger.log_test('VCC', 5.4, duration_ms=250.0)
logger.log_test('IN_T_O_HL', 3.1, duration_ms=120.5)

# Save to CSV
logger.save_to_csv()

# Get summary
print(logger.get_summary())
```

### Integration with Tests

Modify test functions to accept a logger parameter and only log when the test actually runs:

```python
def my_test_function(instr, logger=None):
    # ... perform measurements ...
    result = measure_something()
    duration_ms = measure_duration()

    if logger:
        logger.log_test('PARAMETER_NAME', result, duration_ms=duration_ms)

    return result
```

The logger does not write parameters for tests that are skipped or not executed.

## CSV Format

The CSV file contains the following columns:

- `parameters`: Name of the parameter being tested
- `min`: Minimum acceptable value
- `max`: Maximum acceptable value
- `T_ms`: Measurement duration in milliseconds
- `Value`: Measured result value
- `pass_fail`: 'PASS' or 'FAIL'
- `soft_bin`: Failure classification (1 = PASS, 2 = Functional FAIL, 3 = AC FAIL)

### Metadata Header

At the top of the CSV file, the logger writes metadata rows before the column header:

- `Beginning Time`: Start of the datalog run (`yyyy-mm-dd hh:mm:ss`)
- `Ending Time`: End of the datalog run (`yyyy-mm-dd hh:mm:ss`)
- `userID`: User identifier
- `runID`: Automatic run identifier
- `test_name`: Test suite name
- `Pass/Fail`: Overall overall pass/fail result
- `Soft Bin`: Overall failure classification

## Example CSV Output

```
Beginning Time,2026-05-07 15:18:17
Ending Time,2026-05-07 15:20:05
userID,unknown
runID,20260507_151817
test_name,default
Pass/Fail,FAIL
Soft Bin,3
parameters,min,max,T_ms,Value,pass_fail,soft_bin
VCC,5.225,5.775,21239.45,5.5,PASS,1
IN_T_O_HL,0.9,1.1,1078.086,9.90E+46,FAIL,2
IN_T_O_LH,1.8,2.2,11050.17,9.90E+46,FAIL,2
```

## Configuration

Test specifications are defined in `limits.py`:

```python
TEST_SPECS = {
    'VCC': (5.5, 5.0),           # Supply voltage: 5.5V nominal, 5% tolerance
    'IN_T_O_HL': (1, 10.0),    # Input to Output propagation delay (High to Low): 3.2 ns, 10% tolerance
    'IN_T_O_LH': (2, 10.0),    # Input to Output propagation delay (Low to High): 3.5 ns, 10% tolerance
    'TDIS': (3, 10.0),         # Disable time: 6.8 ns, 10% tolerance
    'TEN': (4, 10.0),          # Enable time: 7.1 ns, 10% tolerance
    'TIDLE_HL': (5, 10.0),     # Idle propagation delay (High to Low): 3.0 ns, 10% tolerance
    'O_T_IN_HL': (6, 10.0),    # Output to Input propagation delay (High to Low): 3.2 ns, 10% tolerance
    'O_T_IN_LH': (7, 10.0),    # Output to Input propagation delay (Low to High): 3.5 ns, 10% tolerance
}
```

The system calculates min/max as:
- `min = nominal * (1 - tolerance/100)`
- `max = nominal * (1 + tolerance/100)`

## Adding New Parameters to the Datalog

To include new parameters in the datalog system:

### 1. Add Parameter Specifications

Edit `limits.py` and add your new parameter to `TEST_SPECS`:

```python
TEST_SPECS = {
    # ... existing parameters ...
    'NEW_PARAMETER': (nominal_value, tolerance_percent),
}
```

### 2. Add Parameter Category

Add your parameter to `TEST_CATEGORIES` in `limits.py`:

```python
TEST_CATEGORIES = {
    # ... existing parameters ...
    'NEW_PARAMETER': 'functional',  # or 'ac' for AC-related tests
}
```

### 3. Create Test Function

Create a test function that measures the parameter and logs it:

```python
def test_new_parameter(instr, vcc, logger=None):
    # ... perform measurements ...
    result = measure_new_parameter()
    duration_ms = final_time()  # if using timing
    
    if logger:
        logger.log_test('NEW_PARAMETER', result, duration_ms=duration_ms)
    
    return {'NEW_PARAMETER': result}
```

### 4. Add to Test Configuration

Update `logic_tests.py` to include the new parameter in `TEST_CONFIGURATIONS`:

```python
TEST_CONFIGURATIONS = [
    {
        "test_name": "LOGIC_RS29511_Test",
        "parameters": ["VCC", "IN_T_O_HL", "IN_T_O_LH", "TDIS", "TEN", "TIDLE_HL", "O_T_IN_HL", "O_T_IN_LH", "NEW_PARAMETER"],
        "details": "Logic level shifter timing and voltage characterization tests"
    }
]
```

### 5. Integrate into Main Test Loop

Add the test function call to `main.py`:

```python
for vcc in VCC_LIST:
    results = test_tp(instr, vcc, logger)
    results = test_tidle(instr, vcc, logger)
    results = test_tdis(instr, vcc, logger)
    results = test_ten(instr, vcc, logger)
    results = test_new_parameter(instr, vcc, logger)  # Add this line
```

The datalog will automatically include the new parameter when the test is run, with proper pass/fail analysis based on the specifications you defined.

## Running Tests

Use `main.py` to run integrated tests:

```bash
python main.py
```

This will:
1. Initialize instruments
2. Run selected test procedures with logging
3. Save results to the configured CSV file
4. Display summary statistics

## Selective Logging Behavior

The datalog only includes test parameters for tests that were actually executed. If a test function is commented out or skipped, its parameter rows are omitted from the CSV.

## Backward Compatibility

The legacy `save_results()` function is still available for Excel export, but the new `DataLogger` class is recommended for new implementations.