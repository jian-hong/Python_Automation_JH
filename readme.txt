LabAutomation/
├── configurations.py          # Global test configuration: VCC ranges, limits, filenames, sample count
├── instruments.py     # VISA abstraction layer: instrument discovery, connection, basic I/O
├── scope_setup.py     # Oscilloscope configuration: channels, timebase, triggers, measurements
├── dmm_setup.py   	   # DMM configuration and measurement functions (V, I, continuity)
├── psu_setup.py   	   # Power supply setup: channel config, voltage/current limits, sequencing
├── generator_setup.py # Signal generator setup: waveform type, frequency, amplitude, duty cycle
├── logic_tests.py     # Logic device test cases: threshold levels, propagation delay, disable timing
├── datalog.py         # Test data logging: results, pass/fail status, metadata, CSV/Excel output
└── main.py            # Main execution entry: test flow control and sequence orchestration
└── utils.py           # common utility functions and classes for logging setup, error handling decorators, safe module imports, progress indication, binary data parsing, and file size formatting used across the application.



# workflow test marker

To add on in future
├── limits.py        		# Datasheet limits only (no logic), add pass/fail criteria
├── ldo_tests.py	 		# LDO test cases: threshold levels, propagation delay, disable timing
├── level_shifter_tests.py  # Level Shifter test cases: threshold levels, propagation delay, disable timing
├── opamp_tests.py          # OPA test cases: threshold levels, propagation delay, disable timing


