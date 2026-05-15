#Testing VSC and GitHub integration with this line of code. Please ignore.

# opa_tests.py
# Operational Amplifier (OPA) test procedures
# Tests for GBW (Gain-Bandwidth Product) and SR (Slew Rate)

def test_parameter():
    """Return the user-defined test configuration array.

    This function defines the available test names, parameter lists, and details.
    Parameters are only written to the datalog when their corresponding test is actually executed.
    """
    
    return [
        {
            "test_name": "OPA_RS622_Test",
            "parameters": ["IN+"],
            "details": "OPA Parameter tests"
        },
        # Add additional test configurations as needed
        # {
        #     "test_name": "Another_Test",
        #     "parameters": ["PARAM1", "PARAM2"],
        #     "details": "Description of another test"
        # }
    ]

TEST_CONFIGURATIONS = test_parameter()


from dmm_setup import *
from generator_setup import *
from psu_setup import *
from scope_setup import *
from configurations import *
import time
from datalog import DataLogger
from utils import initial_time, final_time

# =========================
# Debug configuration
# =========================
# Option A: hardcode
DEBUG_MODE = True # Set to True to enable debug prints, False to disable

# Option B: override by environment variable:
#   Windows PowerShell:  $env:OPA_DEBUG="1"
#   cmd.exe:             set OPA_DEBUG=1
#   bash:                export OPA_DEBUG=1
DEBUG_MODE = os.getenv("OPA_DEBUG", "0").strip().lower() in ("1", "true", "yes", "y", "on")

def dbg(msg: str, *, enabled: bool = None): # type: ignore
    """Lightweight debug print with consistent prefix + timestamp."""
    use = DEBUG_MODE if enabled is None else enabled
    if use:
        ts = time.strftime("%H:%M:%S")
        print(f"[OPA-DEBUG {ts}] {msg}")

def safe_write(instr, cmd: str, label: str = "WRITE"):
    """Write SCPI and print it if debug is enabled."""
    dbg(f"{label}: {cmd}")
    return instr.write(cmd)

def safe_query(instr, cmd: str, label: str = "QUERY"):
    """Query SCPI and print cmd + raw response if debug is enabled."""
    dbg(f"{label}: {cmd}")
    resp = instr.query(cmd)
    dbg(f"{label}-RESP: {resp!r}")
    return resp

def safe_float(x, *, context: str = ""):
    """Convert to float with debug info on failure."""
    try:
        return float(x)
    except Exception as e:
        dbg(f"FLOAT-CONVERT FAIL {context}: value={x!r}, err={e}")
        raise

def measure_gbw(instr, vcc, amp, gain, logger=None, debug: bool = None): # type: ignore
    """Measure Gain-Bandwidth Product (GBW).
    
    Measures the frequency at which gain drops to 0.707 (-3dB) of initial gain.
    Uses binary search to find the -3dB frequency point.
    
    Args:
        instr: Instruments object containing psu, gen, scope
        vcc: Supply voltage in Volts
        amp: Input amplitude in Volts (typically 50mV)
        gain: Closed-loop gain setting
        logger: Optional DataLogger for recording results
        
    Returns:
        Dictionary with 'IN+' and 'GBW_MHz' keys
    """
    power_supply = instr.psu
    signal_generator = instr.gen
    oscilloscope = instr.scope
    
    start_time = time.time() * 1000  # in milliseconds
    dbg(f"GBW START vcc={vcc}, amp={amp}, gain={gain}", enabled=debug)

    try:
        # Setup phase
        # 1. Power supply configuration
        dbg("PSU: enabling rails", enabled=debug)

        power_on_protected(power_supply, 1, vcc / 2, current_limit)
        power_on_protected(power_supply, 2, vcc / 2, current_limit)
        time.sleep(1)
        
        # 2. Signal generator setup - initial sine wave at 1kHz
        dbg("GEN: setup sine 1kHz", enabled=debug)
        setup_sine(signal_generator, 1, 1000, amp, 0)  # Convert to mV
        time.sleep(1)
        enable_output(signal_generator, 1)
        time.sleep(1)
        
        # 3. Oscilloscope setup for AC measurement
        # Use a low trigger level for the small OPA signal instead of half the supply.
        dbg("SCOPE: setup + thresholds", enabled=debug)
        scope_setup(oscilloscope, 1e-6, 0)
        set_threshold(oscilloscope, 1)
        set_threshold(oscilloscope, 2)
        time.sleep(1)
        
        # Measurement phase
        # 4. Get initial amplitude at 1kHz baseline
        dbg("GBW: measuring baseline VAMP (CHAN2)", enabled=debug)
        initial_amps = []
        for _ in range(5):
            try:
                raw = safe_query(oscilloscope, ":MEAS:ITEM? VAMP,CHAN2")
                amp_value = float(oscilloscope.query(":MEAS:ITEM? VAMP,CHAN2"))
                # measure_single(oscilloscope, "VAMP", 2)  # Measure amplitude on output channel
                dbg(f"baseline sample={amp_value}", enabled=debug)
                if amp_value < 1e10:  # Filter invalid values
                    initial_amps.append(amp_value)
                else:
                    dbg(f"baseline rejected (too large): {amp_value}", enabled=debug)
            except Exception as e:
                dbg(f"baseline read fail sample: {e}", enabled=debug)
                pass
            time.sleep(0.1)
        
        if not initial_amps:
            raise ValueError("GBW: no valid baseline VAMP samples (CHAN2). Check scope measurement setup / channel scaling / trigger.")
        
        initial_amp_avg = sum(initial_amps) / len(initial_amps)
        
        # 5. Calculate target amplitude (0.707 of initial for -3dB point)
        target_amp = initial_amp_avg * 0.707
        dbg(f"baseline avg={initial_amp_avg}, target(-3dB)={target_amp}", enabled=debug)
        
        # 6. Binary search for -3dB frequency
        initial_time()
        low, high = 500, 1000000  # Frequency range: 500 Hz to 1.0 MHz
        
        while high - low > 100:
            mid = (low + high) / 2
            signal_generator.write(f":SOUR1:FREQ {mid}")
            
            time.sleep(0.5)
            
            # Measure current amplitude at this frequency
            current_amps = []
            for _ in range(3):
                try:
                    amp_value = float(oscilloscope.query(":MEAS:ITEM? VAMP,CHAN2"))
                    if amp_value < 1e10:  # Filter invalid values
                        current_amps.append(amp_value)
                except Exception as e:
                    pass
                time.sleep(0.1)
            
            if not current_amps:
                raise ValueError("Could not obtain valid amplitude measurement at frequency {mid}")
            
            current_amp_avg = sum(current_amps) / len(current_amps)
            
            # Adjust search range based on amplitude
            if current_amp_avg > target_amp:
                low = mid
            else:
                high = mid
        
        duration_gbw = final_time()
        gbw_freq = (low + high) / 2
        gbw_mhz = round(gbw_freq * gain * 1e-6, 4)  # Convert to MHz
        
        results = {
            "IN+": vcc,
            "GBW_MHz": gbw_mhz
        }
        
        if logger:
            logger.log_test("IN+", vcc, duration_ms=duration_gbw)
            logger.log_test("GBW_MHz", gbw_mhz, duration_ms=duration_gbw)
        
        return results
        
    except Exception as e:
        print(f"Error measuring GBW: {e}")
        return None
    finally:
        try:
            disable_output(signal_generator, 1)
        except:
            pass


def measure_sr(instr, vcc, amp, logger=None):
    """Measure Slew Rate (SR) - positive and negative.
    
    Measures the maximum rate of change of output voltage in response to
    a square wave input. Tests both positive and negative slew rates.
    
    Args:
        instr: Instruments object containing psu, gen, scope
        vcc: Supply voltage in Volts
        amp: Input amplitude in Volts (typically 1V)
        logger: Optional DataLogger for recording results
        
    Returns:
        Dictionary with 'IN+', 'SR_positive', and 'SR_negative' keys
    """
    power_supply = instr.psu
    signal_generator = instr.gen
    oscilloscope = instr.scope
    
    start_time = time.time() * 1000  # in milliseconds
    
    try:
        # Setup phase
        # 1. Power supply configuration
        power_on_protected(power_supply, 1, vcc / 2, current_limit)
        time.sleep(1)
        power_on_protected(power_supply, 2, vcc / 2, current_limit)
        time.sleep(1)
        
        # 2. Signal generator setup - square wave for slew rate measurement
        setup_square(signal_generator, 1, 1000, amp, 0)  # Convert to V
        time.sleep(1)
        enable_output(signal_generator, 1)
        time.sleep(1)
        
        # 3. Oscilloscope setup for transient measurement
        # Use wider timebase (100 µs) to capture full rising/falling edges for SR measurement
        scope_setup(oscilloscope, 500e-9, 0)
        time.sleep(1)
        
        input("Press Enter to continue...")

        # Measurement phase
        # 4. Collect slew rate measurements (multiple samples for averaging)
        initial_time()
        pslewrates = []
        nslewrates = []
        
        for measurement_idx in range(20):
            try:
                # Query positive and negative slew rates from oscilloscope
                pslew = float(oscilloscope.query(":MEAS:ITEM? PSLewrate,CHAN2")) * 1e-6  # Convert to V/µs
                nslew = float(oscilloscope.query(":MEAS:ITEM? NSLewrate,CHAN2")) * 1e-6

                print(f"Sample {measurement_idx+1}: PSlew={pslew:.4f} V/µs, NSlew={nslew:.4f} V/µs")

                pslewrates.append(pslew)
                nslewrates.append(nslew)
            except Exception as e:
                pass
            time.sleep(0.01)
        
        duration_sr = final_time()
        
        if not pslewrates or not nslewrates:
            raise ValueError("Could not obtain valid slew rate measurements")
        
        # Calculate averages
        sr_positive = round(sum(pslewrates) / len(pslewrates), 4)
        sr_negative = round(sum(nslewrates) / len(nslewrates), 4)
        
        results = {
            "IN+": vcc,
            "SR_positive": sr_positive,
            "SR_negative": sr_negative
        }
        
        if logger:
            logger.log_test("IN+", vcc, duration_ms=duration_sr)
            logger.log_test("SR_positive", sr_positive, duration_ms=duration_sr)
            logger.log_test("SR_negative", sr_negative, duration_ms=duration_sr)
        
        return results
        
    except Exception as e:
        print(f"Error measuring SR: {e}")
        return None
    finally:
        try:
            disable_output(signal_generator, 1)
        except:
            pass


def test_opa_gbw(instr, vcc, logger=None):
    """Test OPA GBW at specified VCC.
    
    Wrapper function for measuring GBW that follows the standard test pattern. 
    Measures gain-bandwidth product using a binary search
    to find the -3dB frequency point.
    
    Args:
        instr: Instruments object
        vcc: Supply voltage in Volts
        logger: Optional DataLogger for recording results
        
    Returns:
        Dictionary with test results
    """
    amp = 0.05  # 50 mV input amplitude
    gain = 11   # Typical closed-loop gain
    return measure_gbw(instr, vcc, amp, gain, logger)


def test_opa_sr(instr, vcc, logger=None):
    """Test OPA Slew Rate at specified VCC.
    
    Wrapper function for measuring slew rate that follows the standard test pattern.
    Measures both positive and negative slew rates.
    
    Args:
        instr: Instruments object
        vcc: Supply voltage in Volts
        logger: Optional DataLogger for recording results
        
    Returns:
        Dictionary with test results
    """
    amp = 1.0  # 1V input amplitude for SR measurement
    return measure_sr(instr, vcc, amp, logger)


def test_opa_bandwidth(instr, vcc, logger=None):
    """Test OPA bandwidth - combined GBW and SR measurement.
    
    Comprehensive bandwidth test combining GBW measurement and slew rate.
    Tests device performance at specified VCC level.
    
    Args:
        instr: Instruments object
        vcc: Supply voltage in Volts
        logger: Optional DataLogger for recording results
        
    Returns:
        Dictionary with combined GBW and SR results
    """
    gbw_result = test_opa_gbw(instr, vcc, logger)
    sr_result = test_opa_sr(instr, vcc, logger)
    
    # Combine results
    combined = {
        "IN+": vcc,
    }
    if gbw_result:
        combined.update(gbw_result)
    if sr_result:
        combined.update(sr_result)
    
    return combined

def test_settlingTime(instr, vcc, logger=None):
    scope = instr.scope  # Oscilloscope object for measuring timing delays
    gen = instr.gen      # Signal generator object for creating input stimulus
    psu = instr.psu      # Power supply object for device power control

    start_time = time.time() * 1000  # in milliseconds

    # ========== SETUP PHASE ==========

    initial_time()


    # 1. Enable power supply with current protection
    power_on_protected(psu, 1, vcc/2, current_limit)
    power_on_protected(psu, 2, vcc/2, current_limit)
    
    # 2. Configure signal generator for square wave input
    # - 1 kHz frequency: tests high-speed response

    setup_square(gen, 1, 1000, 2, 0)

    # 3. Configure oscilloscope for timing measurement
    # - 200 ns timebase: captures fast transitions and settling behavior
    scope_setup(scope, 200e-9, 0.5)

    # set_threshold(scope, 1)
    # set_threshold(scope, 2)

    # ========== MEASUREMENT PHASE ==========
    r_IN = measure_single(scope, "VPP", 1)  # Input amplitude
    r_settlingTime = measure_single(scope, "VPP", 2)  # Rising edge delay
    print(f"Measured IN+: {r_IN:.4f} V")

    duration_hl = final_time()
    end_time = time.time() * 1000  # in milliseconds
    overall_duration_ms = end_time - start_time
    
    print(f"Test duration: {overall_duration_ms:.2f} ms")

    my_capture = screenshot()

    input("Press Enter to continue...")

    results = {
        "IN+": r_IN,
        # "IN_T_O_LH": t_rise * 1e9,      # Low-to-high propagation delay (ns)
    }

    if logger:
        # Log VCC with overall duration
        logger.log_test("IN+", r_IN, duration_ms=overall_duration_ms)
        # # Log each parameter with its individual measurement duration
        # logger.log_test("IN_T_O_HL", t_fall * 1e9, duration_ms=duration_hl)

    stop_output(gen)

    power_off(psu)

    return results
    
def test_SSR(instr, vcc, logger=None):
    scope = instr.scope  # Oscilloscope object for measuring timing delays
    gen = instr.gen      # Signal generator object for creating input stimulus
    psu = instr.psu      # Power supply object for device power control

    start_time = time.time() * 1000  # in milliseconds

    # ========== SETUP PHASE ==========

    initial_time()


    # 1. Enable power supply with current protection
    power_on_protected(psu, 1, vcc/2, current_limit)
    power_on_protected(psu, 2, vcc/2, current_limit)
    
    # 2. Configure signal generator for square wave input
    # - 500 kHz frequency: tests high-speed response

    setup_square(gen, 1, 500000, 0.1, 0)

    # 3. Configure oscilloscope for timing measurement
    # - 200 ns timebase: captures fast transitions and settling behavior
    scope_setup(scope, 200e-9, 0.025)

    # set_threshold(scope, 1)
    # set_threshold(scope, 2)

    # ========== MEASUREMENT PHASE ==========
    t_rise = measure_delay(scope, "RRDelay", 2, 1)  # Rising edge delay

    duration_hl = final_time()
    end_time = time.time() * 1000  # in milliseconds
    overall_duration_ms = end_time - start_time

    print(f"Test duration: {overall_duration_ms:.2f} ms")

    time.sleep(10)  # Wait for any transient effects to settle

    # my_capture = screenshot()
    input("Press Enter to continue...")
    # my_capture = screenshot()
    # input("Press Enter to continue...")
    # my_capture = screenshot()
    # input("Press Enter to continue...")
    # my_capture = screenshot()
    # input("Press Enter to continue...")

    stop_output(gen)

    power_off(psu)

    results = {
        # "VCC": vcc,
        # "IN_T_O_HL": t_fall * 1e9,      # High-to-low propagation delay (ns)
        # "IN_T_O_LH": t_rise * 1e9,      # Low-to-high propagation delay (ns)
    }

    # if logger:
        # Log VCC with overall duration
        # logger.log_test("VCC", vcc, duration_ms=overall_duration_ms)
        # # Log each parameter with its individual measurement duration
        # logger.log_test("IN_T_O_HL", t_fall * 1e9, duration_ms=duration_hl)
        # logger.log_test("IN_T_O_LH", t_rise * 1e9, duration_ms=duration_lh)
        # logger.log_test("O_T_IN_HL", t_fall_rev * 1e9, duration_ms=duration_hl_rev)
        # logger.log_test("O_T_IN_LH", t_rise_rev * 1e9, duration_ms=duration_lh_rev)

    return results
    
def test_LSR(instr, vcc, logger=None):
    scope = instr.scope  # Oscilloscope object for measuring timing delays
    gen = instr.gen      # Signal generator object for creating input stimulus
    psu = instr.psu      # Power supply object for device power control
    
    start_time = time.time() * 1000  # in milliseconds

    # ========== SETUP PHASE ==========

    initial_time()


    # 1. Enable power supply with current protection
    power_on_protected(psu, 1, vcc/2, current_limit)
    power_on_protected(psu, 2, vcc/2, current_limit)
    
    # 2. Configure signal generator for square wave input
    # - 500 kHz frequency: tests high-speed response

    setup_square(gen, 1, 250000, 4, 0)

    # 3. Configure oscilloscope for timing measurement
    # - 200 ns timebase: captures fast transitions and settling behavior
    scope_setup(scope, 200e-9, 1)

    # set_threshold(scope, 1)
    # set_threshold(scope, 2)

    # ========== MEASUREMENT PHASE ==========
    # t_rise = measure_delay(scope, "RRDelay", 2, 1)  # Rising edge delay

    duration_hl = final_time()
    end_time = time.time() * 1000  # in milliseconds
    overall_duration_ms = end_time - start_time
    
    print(f"Test duration: {overall_duration_ms:.2f} ms")

    time.sleep(10)  # Wait for any transient effects to settle

    # my_capture = screenshot()
    input("Press Enter to continue...")
    # my_capture = screenshot()
    # input("Press Enter to continue...")
    # my_capture = screenshot()
    # input("Press Enter to continue...")
    # my_capture = screenshot()
    # input("Press Enter to continue...")

    results = {
        # "VCC": vcc,
        # "IN_T_O_HL": t_fall * 1e9,      # High-to-low propagation delay (ns)
        # "IN_T_O_LH": t_rise * 1e9,      # Low-to-high propagation delay (ns)
    }

    # if logger:
        # Log VCC with overall duration
        # logger.log_test("VCC", vcc, duration_ms=overall_duration_ms)
        # # Log each parameter with its individual measurement duration
        # logger.log_test("IN_T_O_HL", t_fall * 1e9, duration_ms=duration_hl)
        # logger.log_test("IN_T_O_LH", t_rise * 1e9, duration_ms=duration_lh)
        # logger.log_test("O_T_IN_HL", t_fall_rev * 1e9, duration_ms=duration_hl_rev)
        # logger.log_test("O_T_IN_LH", t_rise_rev * 1e9, duration_ms=duration_lh_rev)

    stop_output(gen)

    power_off(psu)

    return results

def test_ORT(instr, vcc, logger=None):
    scope = instr.scope  # Oscilloscope object for measuring timing delays
    gen = instr.gen      # Signal generator object for creating input stimulus
    psu = instr.psu      # Power supply object for device power control
    
    start_time = time.time() * 1000  # in milliseconds

    # ========== SETUP PHASE ==========

    initial_time()

    # 1. Enable power supply with current protection
    power_on_protected(psu, 1, vcc/2, current_limit)
    power_on_protected(psu, 2, vcc/2, current_limit)
    
    # 2. Configure signal generator for square wave input
    # - 500 kHz frequency: tests high-speed response

    setup_square(gen, 1, 1000, 0.2, 0.1)

    # 3. Configure oscilloscope for timing measurement
    # - 200 ns timebase: captures fast transitions and settling behavior
    scope_setup(scope, 1e-6, 0.1)

    # ========== MEASUREMENT PHASE ==========
    # t_rise = measure_delay(scope, "RRDelay", 2, 1)  # Rising edge delay

    duration_hl = final_time()
    end_time = time.time() * 1000  # in milliseconds
    overall_duration_ms = end_time - start_time

    print(f"Test duration: {overall_duration_ms:.2f} ms")

    # my_capture = screenshot()
    input("Press Enter to continue...")

    initial_time()

    stop_output(gen)
    time.sleep(1) 

    setup_square(gen, 1, 1000, 0.2, -0.1)

    scope_setup(scope, 1e-6, -0.1)

    time.sleep(10)  # Wait for any transient effects to settle

    my_capture = screenshot()
    input("Press Enter to continue...")

    results = {
        # "VCC": vcc,
        # "IN_T_O_HL": t_fall * 1e9,      # High-to-low propagation delay (ns)
        # "IN_T_O_LH": t_rise * 1e9,      # Low-to-high propagation delay (ns)
    }

    # if logger:
        # Log VCC with overall duration
        # logger.log_test("VCC", vcc, duration_ms=overall_duration_ms)
        # # Log each parameter with its individual measurement duration
        # logger.log_test("IN_T_O_HL", t_fall * 1e9, duration_ms=duration_hl)
        # logger.log_test("IN_T_O_LH", t_rise * 1e9, duration_ms=duration_lh)
        # logger.log_test("O_T_IN_HL", t_fall_rev * 1e9, duration_ms=duration_hl_rev)
        # logger.log_test("O_T_IN_LH", t_rise_rev * 1e9, duration_ms=duration_lh_rev)

    stop_output(gen)

    power_off(psu)

    return results

#STILL IN DEVELOPMENT - NOT CALLED IN MAIN YET
def test_powerONtime(instr, vcc, logger=None): 
    scope = instr.scope  # Oscilloscope object for measuring timing delays
    gen = instr.gen      # Signal generator object for creating input stimulus
    psu = instr.psu      # Power supply object for device power control
    
    start_time = time.time() * 1000  # in milliseconds

    # ========== SETUP PHASE ==========

    initial_time()


    # 1. Enable power supply with current protection
    power_on_protected(psu, 1, vcc/2, current_limit)
    power_on_protected(psu, 2, vcc/2, current_limit)
    
    # 2. Configure signal generator for square wave input
    # - 500 kHz frequency: tests high-speed response

    setup_square(gen, 1, 1000, 0.2, 0.1)

    # 3. Configure oscilloscope for timing measurement
    # - 200 ns timebase: captures fast transitions and settling behavior
    scope_setup(scope, 1e-6, vcc/2)

    # ========== MEASUREMENT PHASE ==========
    # t_rise = measure_delay(scope, "RRDelay", 2, 1)  # Rising edge delay

    # my_capture = screenshot()
    input("Press Enter to continue...")

    setup_square(gen, 1, 1000, 0.2, 0.1)

    duration_hl = final_time()
    end_time = time.time() * 1000  # in milliseconds
    overall_duration_ms = end_time - start_time

    print(f"Test duration: {overall_duration_ms:.2f} ms")

    time.sleep(10)  # Wait for any transient effects to settle

    # my_capture = screenshot()
    input("Press Enter to continue...")

    results = {
        # "VCC": vcc,
        # "IN_T_O_HL": t_fall * 1e9,      # High-to-low propagation delay (ns)
        # "IN_T_O_LH": t_rise * 1e9,      # Low-to-high propagation delay (ns)
    }

    # if logger:
        # Log VCC with overall duration
        # logger.log_test("VCC", vcc, duration_ms=overall_duration_ms)
        # # Log each parameter with its individual measurement duration
        # logger.log_test("IN_T_O_HL", t_fall * 1e9, duration_ms=duration_hl)
        # logger.log_test("IN_T_O_LH", t_rise * 1e9, duration_ms=duration_lh)
        # logger.log_test("O_T_IN_HL", t_fall_rev * 1e9, duration_ms=duration_hl_rev)
        # logger.log_test("O_T_IN_LH", t_rise_rev * 1e9, duration_ms=duration_lh_rev)

    stop_output(gen)

    power_off(psu)

    return results