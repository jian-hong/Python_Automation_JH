# logic_tests.py
 
# User-defined test configurations
# Define test names, parameters to test, and details for each test run
# Only parameters actually logged by a running test will appear in the datalog.

def test_parameter():
    """Return the user-defined test configuration array.

    This function defines the available test names, parameter lists, and details.
    Parameters are only written to the datalog when their corresponding test is actually executed.
    """
    return [
        {
            "test_name": "LOGIC_RS29511_Test",
            "parameters": ["VCC", "IN_T_O_HL", "IN_T_O_LH", "TDIS", "TEN", "TIDLE_HL", "O_T_IN_HL", "O_T_IN_LH", "TEST"],
            "details": "Logic level shifter timing and voltage characterization tests"
        },
        # Add additional test configurations as needed
        # {
        #     "test_name": "Another_Test",
        #     "parameters": ["PARAM1", "PARAM2"],
        #     "details": "Description of another test"
        # }
    ]

TEST_CONFIGURATIONS = test_parameter()

#from procedures import *
from dmm_setup import *
from generator_setup import *
from psu_setup import *
from scope_setup import *
#from oscilloscope_setup import *
from configurations import *
import time
from datalog import DataLogger
from utils import initial_time, final_time
#from scope_screenshot import capture_scope_screenshot

def test_tp(instr, vcc, logger=None):
    """Test propagation delay (TP) through the logic level shifter.
    
    Measures both directions of signal propagation to characterize latency.
    - IN → OUT: Measures delay from input to output
    - OUT → IN: Measures delay in reverse direction (if device supports bidirectional)
    
    Results in nanoseconds represent the time for signal to traverse the device.
    """
    # Extract instrument objects from the instr parameter
    scope = instr.scope  # Oscilloscope object for measuring timing delays
    gen = instr.gen      # Signal generator object for creating input stimulus
    psu = instr.psu      # Power supply object for device power control

    # Record start timestamp
    start_time = time.time() * 1000  # in milliseconds

    # ========== SETUP PHASE ==========
    # 1. Power ON with current limiting protection
    # - Channel 1 on PSU supplies VCC voltage to device under test
    # - current_limit prevents excessive current draw if device shorts
    power_on_protected(psu, 1, vcc, current_limit)

    # 2. Configure signal generator on CH1 for input stimulus
    # - Generates 400 kHz square wave (typical logic signal)
    # - Voltage swings from 0V to VCC (full rail-to-rail)
    # - 50% duty cycle = VCC/2 mid-point for threshold detection
    setup_square(gen, 1, 400000, vcc, vcc/2)
    #time.sleep(5)  # Optional delay for signal stabilization

    # 3. Configure oscilloscope for timing measurement
    # - Set timebase to 1/400kHz ≈ 2.5µs for 1 period visibility
    # - Mid-threshold set to VCC/2 for consistent edge detection
    scope_setup(scope, HtoL * 1e-9, vcc/2)

    # 4. Set digital thresholds on oscilloscope channels
    # - Channel 1: Input signal threshold
    # - Channel 2: Output signal threshold
    # - Both required for accurate delay measurement between channels
    set_threshold(scope, 1)
    set_threshold(scope, 2)
    #time.sleep(5)  # Optional delay for threshold settling

    # 4.5. Capture screenshot before measurement
    # - Saves oscilloscope screen image for visual verification
    # - Captures setup state before delay measurements
    my_capture = screenshot()

    # ========== MEASUREMENT PHASE (IN → OUT) ==========
    # 5. Measure high-to-low transition delay (falling edge)
    # - "FFDelay": Fall-to-Fall delay from CH1 (input) to CH2 (output)
    # - Captures time from input falling edge to output falling edge
    # - Stored in nanoseconds for later analysis
    initial_time()
    t_fall = measure_delay(scope, "FFDelay", 1, 2)
    duration_hl = final_time()

    # 6. Measure low-to-high transition delay (rising edge)
    # - "RRDelay": Rise-to-Rise delay from CH1 (input) to CH2 (output)
    # - Captures time from input rising edge to output rising edge
    # - Propagation delay may differ between rising/falling transitions
    initial_time()
    t_rise = measure_delay(scope, "RRDelay", 1, 2)
    duration_lh = final_time()
    #time.sleep(5)  # Optional delay between measurements

    # 7. Stop input signal and wait for settling
    # - Disables signal generator output
    # - Settle time prevents signal overlap with reverse direction test
    stop_output(gen)
    time.sleep(1)  # 1 second settling time

    # ========== MEASUREMENT PHASE (OUT → IN) - BIDIRECTIONAL TEST ==========
    # 8. Configure signal generator on CH2 for reverse-direction stimulus
    # - Now CH2 is input, CH1 is output (tests bidirectional capability)
    # - Same 400 kHz frequency and voltage levels for consistency
    setup_square(gen, 2, 400000, vcc, vcc/2)
    #time.sleep(5)  # Optional delay for signal stabilization

    # 9. Measure reverse direction falling edge delay
    # - "FFDelay": Fall-to-Fall from CH2 (now input) to CH1 (now output)
    # - Validates device works in both directions
    # - May differ from forward direction due to internal asymmetry
    initial_time()
    t_fall_rev = measure_delay(scope, "FFDelay", 2, 1)
    duration_hl_rev = final_time()

    # 10. Measure reverse direction rising edge delay
    # - "RRDelay": Rise-to-Rise from CH2 to CH1 (reversed)
    # - Completes bidirectional characterization
    initial_time()
    t_rise_rev = measure_delay(scope, "RRDelay", 2, 1)
    duration_lh_rev = final_time()
    #time.sleep(5)  # Optional delay between measurements

    # 11. Capture screenshot after reverse measurement
    # - Saves oscilloscope screen image for visual verification
    # - Captures reverse direction setup state
    my_capture = screenshot()

    # ========== CLEANUP PHASE ==========
    # 12. Stop all signal outputs
    # - Disables both generator channels
    # - Prevents ringing or cross-coupling effects
    stop_output(gen)

    # 13. Power OFF device
    # - Reduces power consumption between tests
    # - Ensures clean state for next test
    power_off(psu)

    # 14. Return measurements in nanoseconds
    # - All delays converted from seconds (raw measurement) to ns (engineering units)
    # - "IN_T_O_HL": Input→Output high-to-low delay (ns)
    # - "IN_T_O_LH": Input→Output low-to-high delay (ns)
    # - "O_T_IN_HL": Output→Input high-to-low delay (ns) [bidirectional]
    # - "O_T_IN_LH": Output→Input low-to-high delay (ns) [bidirectional]

    # 15. Log results if logger provided
    # Record end timestamp and calculate overall duration
    end_time = time.time() * 1000  # in milliseconds
    overall_duration_ms = end_time - start_time

    results = {
        "VCC": vcc,
        "IN_T_O_HL": t_fall * 1e9,      # High-to-low propagation delay (ns)
        "IN_T_O_LH": t_rise * 1e9,      # Low-to-high propagation delay (ns)
        "O_T_IN_HL": t_fall_rev * 1e9,  # Reverse high-to-low delay (ns)
        "O_T_IN_LH": t_rise_rev * 1e9   # Reverse low-to-high delay (ns)
    }

    if logger:
        # Log VCC with overall duration
        logger.log_test("VCC", vcc, duration_ms=overall_duration_ms)
        # Log each parameter with its individual measurement duration
        logger.log_test("IN_T_O_HL", t_fall * 1e9, duration_ms=duration_hl)
        logger.log_test("IN_T_O_LH", t_rise * 1e9, duration_ms=duration_lh)
        logger.log_test("O_T_IN_HL", t_fall_rev * 1e9, duration_ms=duration_hl_rev)
        logger.log_test("O_T_IN_LH", t_rise_rev * 1e9, duration_ms=duration_lh_rev)

    return results
    
def test_tidle(instr, vcc, logger=None):
    """Test idle propagation delay (TIDLE) at low frequency.
    
    Measures propagation delay when input transitions slowly, simulating
    quasi-static or edge-case scenarios. Lower frequency (100 kHz vs 400 kHz)
    allows settling time and tests stability at device limits.
    """
    scope = instr.scope  # Oscilloscope for measuring timing delays
    gen = instr.gen      # Signal generator for slow input stimulus
    psu = instr.psu      # Power supply for device power

    # ========== SETUP PHASE ==========
    # 1. Enable power supply with current protection
    power_on_protected(psu, 1, vcc, current_limit)

    # 2. Configure signal generator for LOW FREQUENCY test
    # - 100 kHz frequency (slower than test_tp's 400 kHz)
    # - Tests behavior when device has more time to settle
    # - Useful for detecting frequency-dependent propagation delays
    # - VCC/2 threshold for consistent edge detection
    setup_square(gen, 1, 100000, vcc, vcc/2)

    # 3. Configure oscilloscope with LONGER timebase
    # - 500 ns timebase (5x longer than test_tp)
    # - Accommodates slower 100 kHz waveform (10 µs period)
    # - Allows full waveform capture for accurate edge detection
    # - VCC/2 threshold for logic-level triggering
    scope_setup(scope, 500e-9, vcc/2)

    # 4. Set detection thresholds on both channels
    # - Channel 1: Input signal threshold
    # - Channel 2: Output signal threshold
    set_threshold(scope, 1)
    set_threshold(scope, 2)

    # ========== MEASUREMENT PHASE ==========
    # 5. Measure falling edge delay (high-to-low transition)
    # - FFDelay: Fall-to-Fall from input (CH1) to output (CH2)
    # - At 100 kHz frequency (slower transitions)
    # - Propagation delay may differ vs. high-frequency test
    initial_time()
    t_fall = measure_delay(scope, "FFDelay", 1, 2)
    duration_hl = final_time()
    
    # 6. Measure rising edge delay (low-to-high transition)
    # - RRDelay: Rise-to-Rise from input (CH1) to output (CH2)
    # - At 100 kHz frequency (slower transitions)
    # - Asymmetric delays indicate frequency dependency
    initial_time()
    t_rise = measure_delay(scope, "RRDelay", 1, 2)
    duration_lh = final_time()

    # ========== CLEANUP PHASE ==========
    # 7. Stop signal generation
    # - Disables square wave output
    stop_output(gen)
    
    # 8. Power down device
    # - Reduces power consumption
    power_off(psu)

    # 9. Return idle-mode propagation delays
    # - TIDLE_HL: High-to-low delay at low frequency (ns)
    # - TIDLE_LH: Low-to-high delay at low frequency (ns)
    # - Compare vs test_tp results to identify frequency dependency
    results = {
        "VCC": vcc,
        "TIDLE_HL": t_fall * 1e9,  # Falling edge delay at 100 kHz (ns)
        "TIDLE_LH": t_rise * 1e9   # Rising edge delay at 100 kHz (ns)
    }
    
    if logger:
        logger.log_test("VCC", vcc)
        logger.log_test("TIDLE_HL", t_fall * 1e9, duration_ms=duration_hl)
        logger.log_test("TIDLE_LH", t_rise * 1e9, duration_ms=duration_lh)
    
    return results
   
def test_tdis(instr, vcc, logger=None):
    """Test output disable time (TDIS) - time from Output Enable to output Hi-Z.
    
    Validates the device's ability to quickly disable its output drivers when
    the Output Enable (OE) signal goes inactive. Critical for tri-state bus
    systems to prevent conflicts and bus contention.
    """
    scope = instr.scope  # Oscilloscope for measuring OE-to-Hi-Z delay
    gen = instr.gen      # Signal generator for OE control and data stimulus
    psu = instr.psu      # Power supply for device power

    # ========== SETUP PHASE ==========
    # 1. Enable power supply with current protection
    power_on_protected(psu, 1, vcc, current_limit)

    # 2. Configure CH1 as DATA signal
    # - 100 kHz frequency: normal data pattern
    # - Toggles between 0V and VCC (full swing)
    # - VCC/2 threshold for edge detection
    # - DATA is typically held constant during OE transition test
    setup_square(gen, 1, 100000, vcc, vcc/2)

    # 3. Configure CH2 as OUTPUT ENABLE (OE) control signal
    # - 10 kHz frequency (10x slower than data)
    # - Low frequency allows easy observation of OE transitions
    # - OE pulse width = 100 µs per cycle
    # - Tests device's response when OE becomes inactive (transition HIGH→LOW)
    setup_square(gen, 2, 10000, vcc, vcc/2)

    # 4. Configure oscilloscope for disable timing measurement
    # - 1 µs (1000 ns) timebase captures full cycle of OE at 10 kHz
    # - Sufficient resolution to observe output Hi-Z transition
    # - VCC/2 threshold for digital edge triggering
    scope_setup(scope, 1e-6, vcc/2)

    # 5. Set detection thresholds
    # - Channel 2: OE control signal threshold (input to device)
    # - Channel 1: Output signal threshold (device output being disabled)
    set_threshold(scope, 2)  # OE threshold
    set_threshold(scope, 1)  # Output threshold

    # ========== MEASUREMENT PHASE ==========
    # 6. Measure disable delay (OE falling edge to output Hi-Z)
    # - FFDelay: Measures from OE falling edge (CH2) to output falling edge (CH1)
    # - When OE goes LOW, output drivers should disable within TDIS time
    # - Measures control-to-output response time
    # - Hi-Z state occurs when output can no longer pull the bus low
    initial_time()
    t_dis = measure_delay(scope, "FFDelay", 2, 1)
    duration_tdis = final_time()

    # ========== CLEANUP PHASE ==========
    # 7. Stop signal generation
    # - Disables both CH1 (data) and CH2 (OE) outputs
    stop_output(gen)
    
    # 8. Power down device
    # - Reduces power consumption
    power_off(psu)

    # 9. Return disable time in nanoseconds
    # - TDIS: Time from OE going inactive to output entering Hi-Z state (ns)
    # - Typical range: 5-20 ns for modern logic shifters
    # - Longer delay = slower bus release = potential contention risk
    
    results = {
        "VCC": vcc,
        "TDIS": t_dis * 1e9  # Output disable time (ns)
    }
    
    if logger:
        logger.log_test("VCC", vcc)
        logger.log_test("TDIS", t_dis * 1e9, duration_ms=duration_tdis)
    
    return results
    
def test_ten(instr, vcc, logger=None):
    """Test output enable time (TEN) - time from Output Enable to active drive.
    
    Validates the device's ability to quickly enable its output drivers when
    the Output Enable (OE) signal becomes active. Critical for tri-state bus
    systems to minimize response time and ensure timely data presentation.
    """
    scope = instr.scope  # Oscilloscope for measuring OE-to-active delay
    gen = instr.gen      # Signal generator for OE control and data stimulus
    psu = instr.psu      # Power supply for device power

    # ========== SETUP PHASE ==========
    # 1. Enable power supply with current protection
    power_on_protected(psu, 1, vcc, current_limit)

    # 2. Configure CH1 as DATA signal
    # - 100 kHz frequency: normal data pattern
    # - Toggles between 0V and VCC (full swing)
    # - VCC/2 threshold for edge detection
    # - DATA pattern during OE transition tests stability
    setup_square(gen, 1, 100000, vcc, vcc/2)

    # 3. Configure CH2 as OUTPUT ENABLE (OE) control signal
    # - 10 kHz frequency (10x slower than data)
    # - Low frequency allows easy observation of OE transitions
    # - OE pulse width = 100 µs per cycle
    # - Tests device's response when OE becomes active (transition LOW→HIGH)
    setup_square(gen, 2, 10000, vcc, vcc/2)

    # 4. Configure oscilloscope for enable timing measurement
    # - 1 µs (1000 ns) timebase captures full cycle of OE at 10 kHz
    # - Sufficient resolution to observe output activation from Hi-Z
    # - VCC/2 threshold for digital edge triggering
    scope_setup(scope, 1e-6, vcc/2)

    # 5. Set detection thresholds
    # - Channel 2: OE control signal threshold (input to device)
    # - Channel 1: Output signal threshold (device output being enabled)
    set_threshold(scope, 2)  # OE threshold
    set_threshold(scope, 1)  # Output threshold

    # ========== MEASUREMENT PHASE ==========
    # 6. Measure enable delay (OE rising edge to output active)
    # - RRDelay: Measures from OE rising edge (CH2) to output rising edge (CH1)
    # - When OE goes HIGH, output drivers should activate within TEN time
    # - Measures control-to-output response time for enabling
    # - Active state: output transitions from Hi-Z to driven bus state
    initial_time()
    t_en = measure_delay(scope, "RRDelay", 2, 1)
    duration_ten = final_time()

    # ========== CLEANUP PHASE ==========
    # 7. Stop signal generation
    # - Disables both CH1 (data) and CH2 (OE) outputs
    stop_output(gen)
    
    # 8. Power down device
    # - Reduces power consumption
    power_off(psu)

    # 9. Return enable time in nanoseconds
    # - TEN: Time from OE going active to output driving the bus (ns)
    # - Typical range: 5-20 ns for modern logic shifters
    # - Longer delay = slower bus acquisition = potential timing violations
    
    results = {
        "VCC": vcc,
        "TEN": t_en * 1e9  # Output enable time (ns)
    }
    
    if logger:
        logger.log_test("VCC", vcc)
        logger.log_test("TEN", t_en * 1e9, duration_ms=duration_ten)
    
    return results
    
def test_supply_current(instr, vcc, logger=None):
    """Test supply current (IDD) - quiescent device power consumption.
    
    Measures DC current draw from the power supply when device is powered
    but outputs may or may not be switching. Important for power budget
    calculations and battery/thermal management.
    """
    psu = instr.psu  # Power supply for device power
    dmm = instr.dmm  # Digital multimeter for current measurement

    # ========== SETUP PHASE ==========
    # 1. Enable power supply with current protection
    # - Channel 1 supplies VCC voltage to device
    # - current_limit prevents excessive current draw if device shorts
    power_on_protected(psu, 1, vcc, current_limit)

    # ========== MEASUREMENT PHASE ==========
    # 2. Configure DMM for DC current measurement
    # - Sets DMM to current measurement mode
    # - Configures appropriate range (auto-range typical)
    # - Prepares ammeter measurement
    dmm_setup_current(dmm)
    
    # 3. Read current from DMM
    # - Captures steady-state current draw
    # - Returns value in Amperes (SI units)
    current = dmm_read(dmm)

    # ========== CLEANUP PHASE ==========
    # 4. Power down device
    # - Stops power supply
    # - Reduces consumption between tests
    power_off(psu)

    # 5. Return supply current in milliamps
    # - IDD_mA: Quiescent current draw in mA (typical datasheet spec)
    # - Multiplied by 1000 to convert from Amps to milliamps
    # - Typical range: 1-100 mA depending on device activity state
    return {
        "VCC": vcc,
        "IDD_mA": current * 1000  # Supply current in milliamps
    }
    
def test_output_voltage(instr, vcc, logger=None):
    """Test output voltage - verify device output voltage matches specification.
    
    Measures output DC voltage under quiescent conditions to validate
    voltage level shifting accuracy and output driver strength/quality.
    Important for digital logic interface compatibility.
    """
    psu = instr.psu  # Power supply for device power
    dmm = instr.dmm  # Digital multimeter for voltage measurement

    # ========== SETUP PHASE ==========
    # 1. Enable power supply with current protection
    # - Channel 1 supplies VCC voltage to device
    # - current_limit prevents excessive current draw if device shorts
    power_on_protected(psu, 1, vcc, current_limit)

    # ========== MEASUREMENT PHASE ==========
    # 2. Configure DMM for DC voltage measurement
    # - Sets DMM to voltage measurement mode
    # - Configures range to measure 0V to VCC range
    # - Connects voltmeter across device output
    dmm_setup_voltage(dmm)
    
    # 3. Read voltage from DMM
    # - Captures output DC voltage
    # - Returns value in Volts (SI units)
    vout = dmm_read(dmm)

    # ========== CLEANUP PHASE ==========
    # 4. Power down device
    # - Stops power supply
    # - Reduces power consumption between tests
    power_off(psu)

    # 5. Return output voltage
    # - VOUT: Output DC voltage in Volts
    # - Should equal VCC (for high state) or ~0V (for low state)
    # - Voltage droops indicate excessive output impedance or device stress
    return {
        "VCC": vcc,
        "VOUT": vout  # Output voltage in Volts
    }
    
    
def test_cap_load(instr):
    """Test capacitive load - measure parasitic capacitance on device pins.
    
    Characterizes pin capacitance which affects:
    - Output rise/fall times under load
    - Power dissipation (CV²F losses)
    - High-frequency behavior
    
    Important for design margin validation and system performance modeling.
    """
    dmm = instr.dmm  # Digital multimeter for capacitance measurement

    # ========== MEASUREMENT PHASE ==========
    # 1. Configure DMM for capacitance measurement
    # - Sets DMM to capacitance measurement mode
    # - Configures range for pin capacitance (typically pF range)
    # - Applies small AC test signal to measure capacitance
    dmm_setup_cap(dmm)
    
    # 2. Read capacitance from DMM
    # - Measures parasitic capacitance of device pins
    # - Returns value in Farads (typically in pF range)
    cap = dmm_read(dmm)

    # 3. Return capacitance measurement
    # - CAP_pF: Pin capacitance in picofarads (pF)
    # - Multiplied by 1e12 to convert from Farads to picofarads
    # - Typical range: 5-50 pF for small signal devices
    return {
        "CAP_pF": cap * 1e12  # Pin capacitance in picofarads
    }