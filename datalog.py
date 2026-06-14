# datalog.py
# Integrated datalog system for LabAutomation
# Unified log format: parameters, min, max, T_ms, Value, pass_fail, soft_bin

import pandas as pd
import os
import time
import datetime
from limits import TEST_SPECS, get_test_category

class DataLogger:
    
    def __init__(self, filename=None, test_name="default", user_id="unknown"):
        if filename is None:
            self.runID = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.filename = f"{self.runID}_datalog.xlsx"
        else:
            self.filename = filename
            # Extract runID from filename if possible
            parts = filename.split('_')
            self.runID = parts[0] if parts else "unknown"
        self.test_name = test_name
        self.user_id = user_id
        self.start_time = time.time()
        self.beginning_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.entries = ['lolollololo']
        self.columns = ['parameters', 'min', 'max', 'T_ms', 'Value', 'pass_fail', 'soft_bin']

    def log_test(self, parameter, result, t_ms=None, duration_ms=None):
        """
        Log a test result with unified format.
        - parameter: string, name of the parameter being tested
        - result: float, measured result (Value)
        - t_ms: float, deprecated - use duration_ms instead
        - duration_ms: float, test duration in milliseconds (optional)
        """
        if parameter not in TEST_SPECS:
            raise ValueError(f"Parameter '{parameter}' not found in TEST_SPECS")

        nominal, tolerance_percent = TEST_SPECS[parameter]
        tolerance = nominal * tolerance_percent / 100.0
        min_val = nominal - tolerance
        max_val = nominal + tolerance

        # Use duration_ms if provided, otherwise 0
        test_duration = duration_ms if duration_ms is not None else 0

        if min_val <= result <= max_val:
            pass_fail = 'PASS'
            soft_bin = 1
        else:
            category = get_test_category(parameter)
            pass_fail = 'FAIL'
            soft_bin = 3 if category == 'ac' else 2

        entry = {
            'parameters': parameter,
            'min': min_val,
            'max': max_val,
            'T_ms': test_duration,
            'Value': result,
            'pass_fail': pass_fail,
            'soft_bin': soft_bin # future implement
        }

        self.entries.append(entry)

    def save_to_csv(self):
        """Save all logged entries to Excel file with metadata in first sheet."""
        if not self.entries:
            return

        # Calculate summary statistics
        functional_fails = sum(1 for e in self.entries if e['soft_bin'] == 2)
        ac_fails = sum(1 for e in self.entries if e['soft_bin'] == 3)
        
        if functional_fails > 0:
            overall_pass_fail = 'FAIL'
            overall_soft_bin = 2  # Prioritize functional fail (closer to 1)
        elif ac_fails > 0:
            overall_pass_fail = 'FAIL'
            overall_soft_bin = 3
        else:
            overall_pass_fail = 'PASS'
            overall_soft_bin = 1

        # Generate ending time
        ending_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create metadata rows in the same order as the DataLogger attributes
        metadata_rows = [
            ['Beginning Time', self.beginning_time],
            ['Ending Time', ending_time],
            ['userID', self.user_id],
            ['runID', self.runID],
            ['test_name', self.test_name],
            ['Pass/Fail', overall_pass_fail],
            ['Soft Bin', overall_soft_bin],
            [],  # Empty row for spacing
        ]

        df_results = pd.DataFrame(self.entries, columns=self.columns)

        with pd.ExcelWriter(self.filename, engine='openpyxl') as writer:
            df_metadata = pd.DataFrame(metadata_rows)
            df_metadata.to_excel(writer, sheet_name='Summary', header=False, index=False)
            df_results.to_excel(writer, sheet_name='Summary', index=False, startrow=len(metadata_rows) + 1)

            # Optional: Add individual test result sheets grouped by parameter
            for parameter in set(e.get('parameters') for e in self.entries if 'parameters' in e):
                if parameter:
                    param_entries = [e for e in self.entries if e.get('parameters') == parameter]
                    if param_entries:
                        df_param = pd.DataFrame(param_entries, columns=self.columns)
                        sheet_name = str(parameter)[:31]
                        try:
                            df_param.to_excel(writer, sheet_name=sheet_name, index=False)
                        except Exception:
                            pass  # Skip if sheet name is invalid

        self.entries = []  # Clear after saving

    def get_summary(self):
        """Get a summary of pass/fail status."""
        if not self.entries:
            return "No entries logged yet."

        functional_fails = sum(1 for e in self.entries if e['soft_bin'] == 2)
        ac_fails = sum(1 for e in self.entries if e['soft_bin'] == 3)
        
        if functional_fails > 0:
            return "FAIL (Functional)"
        elif ac_fails > 0:
            return "FAIL (AC)"
        else:
            return "PASS"

    def get_average_test_time(self):
        """Get the average test duration in milliseconds."""
        if not self.entries:
            return 0
        durations = [e['T_ms'] for e in self.entries]
        return sum(durations) / len(durations)

    def get_run_duration(self):
        """Get the total run duration from start to now."""
        return time.time() - self.start_time

    def get_metadata(self):
        """Get metadata summary for the test run."""
        functional_fails = sum(1 for e in self.entries if e['soft_bin'] == 2)
        ac_fails = sum(1 for e in self.entries if e['soft_bin'] == 3)
        
        if functional_fails > 0:
            overall_pass_fail = 'FAIL'
            soft_bin = 2
        elif ac_fails > 0:
            overall_pass_fail = 'FAIL'
            soft_bin = 3
        else:
            overall_pass_fail = 'PASS'
            soft_bin = 1
            
        return {
            'user_id': self.user_id,
            'runID': self.runID,
            'test_name': self.test_name,
            'start_time': datetime.datetime.fromtimestamp(self.start_time).isoformat(),
            'run_duration_seconds': self.get_run_duration(),
            'average_test_time_ms': self.get_average_test_time(),
            'overall_pass_fail': overall_pass_fail,
            'soft_bin': soft_bin
        }

# Backward compatibility
def save_results(data_list, filename):
    """Legacy function for saving results to Excel."""
    df_new = pd.DataFrame(data_list)

    if os.path.exists(filename):
        df_old = pd.read_excel(filename)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new

    df.to_excel(filename, index=False)