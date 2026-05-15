# generator_setup.py

import time

# def power_on(psu, voltage):
    # psu.write(":OUTP CH1,OFF")
    # psu.write(f":SOUR1:VOLT {voltage}")
    # time.sleep(0.5)
    # psu.write(":OUTP CH1,ON")

def setup_square(gen, ch, freq, vpp, offset, duty=50):
    gen.write(f":SOUR{ch}:APPL:SQU {freq},{vpp},{offset},0")
    gen.write(f":SOUR{ch}:FUNC:SQU:DCYC {duty}")
    gen.write(f":OUTP{ch} ON")

def stop_output(gen):
    gen.write(":OUTP1 OFF")
    gen.write(":OUTP2 OFF")
    gen.write(":OUTP3 OFF")
    gen.write(":OUTP4 OFF")

# New procedures for different waveforms

def setup_sine(gen, ch, freq, vpp, offset, phase=0):
    """
    Setup sine wave on specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    freq: Frequency in Hz
    vpp: Peak-to-peak voltage
    offset: DC offset voltage
    phase: Phase in degrees (default 0)
    """
    gen.write(f":SOUR{ch}:APPL:SIN {freq},{vpp},{offset},{phase}")
    gen.write(f":OUTP{ch} ON")

def setup_triangle(gen, ch, freq, vpp, offset, phase=0):
    """
    Setup triangle wave on specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    freq: Frequency in Hz
    vpp: Peak-to-peak voltage
    offset: DC offset voltage
    phase: Phase in degrees (default 0)
    """
    gen.write(f":SOUR{ch}:APPL:RAMP {freq},{vpp},{offset},{phase}")
    gen.write(f":OUTP{ch} ON")

def setup_ramp(gen, ch, freq, vpp, offset, phase=0):
    """
    Setup ramp wave on specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    freq: Frequency in Hz
    vpp: Peak-to-peak voltage
    offset: DC offset voltage
    phase: Phase in degrees (default 0)
    """
    gen.write(f":SOUR{ch}:APPL:RAMP {freq},{vpp},{offset},{phase}")
    gen.write(f":OUTP{ch} ON")

def setup_pulse(gen, ch, freq, vpp, offset, phase=0, duty=50):
    """
    Setup pulse wave on specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    freq: Frequency in Hz
    vpp: Peak-to-peak voltage
    offset: DC offset voltage
    phase: Phase in degrees (default 0)
    duty: Duty cycle in percent (default 50)
    """
    gen.write(f":SOUR{ch}:APPL:PULS {freq},{vpp},{offset},{phase}")
    gen.write(f":SOUR{ch}:FUNC:PULS:DCYC {duty}")
    gen.write(f":OUTP{ch} ON")

def setup_noise(gen, ch, vpp, offset):
    """
    Setup noise on specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    vpp: Peak-to-peak voltage
    offset: DC offset voltage
    """
    gen.write(f":SOUR{ch}:APPL:NOIS {0},{vpp},{offset},0")  # Freq and phase not applicable for noise
    gen.write(f":OUTP{ch} ON")

def apply_waveform(gen, ch, waveform, freq, vpp, offset, phase=0, duty=50):
    """
    General function to apply any waveform.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    waveform: 'SIN', 'SQU', 'RAMP', 'PULS', 'NOIS'
    freq: Frequency in Hz (ignored for NOIS)
    vpp: Peak-to-peak voltage
    offset: DC offset voltage
    phase: Phase in degrees (default 0, ignored for NOIS)
    duty: Duty cycle in percent (default 50, for SQU and PULS)
    """
    if waveform.upper() == 'NOIS':
        gen.write(f":SOUR{ch}:APPL:NOIS 0,{vpp},{offset},0")
    else:
        gen.write(f":SOUR{ch}:APPL:{waveform.upper()} {freq},{vpp},{offset},{phase}")
        if waveform.upper() in ['SQU', 'PULS']:
            gen.write(f":SOUR{ch}:FUNC:{waveform.upper()}:DCYC {duty}")
    gen.write(f":OUTP{ch} ON")

# Parameter control functions

def set_frequency(gen, ch, freq):
    """
    Set frequency for specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    freq: Frequency in Hz
    """
    gen.write(f":SOUR{ch}:FREQ {freq}")

def set_amplitude(gen, ch, vpp):
    """
    Set amplitude (Vpp) for specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    vpp: Peak-to-peak voltage
    """
    gen.write(f":SOUR{ch}:VOLT {vpp}")

def set_offset(gen, ch, offset):
    """
    Set DC offset for specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    offset: DC offset voltage
    """
    gen.write(f":SOUR{ch}:VOLT:OFFS {offset}")

def set_phase(gen, ch, phase):
    """
    Set phase for specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    phase: Phase in degrees
    """
    gen.write(f":SOUR{ch}:PHAS {phase}")

def set_duty_cycle(gen, ch, duty):
    """
    Set duty cycle for square or pulse wave on specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    duty: Duty cycle in percent
    """
    # First check current waveform
    waveform = gen.query(f":SOUR{ch}:FUNC?").strip()
    if waveform in ['SQU', 'PULS']:
        gen.write(f":SOUR{ch}:FUNC:{waveform}:DCYC {duty}")

# Output control functions

def enable_output(gen, ch):
    """
    Enable output for specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    """
    gen.write(f":OUTP{ch} ON")

def disable_output(gen, ch):
    """
    Disable output for specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    """
    gen.write(f":OUTP{ch} OFF")

# Query functions

def query_output_state(gen, ch):
    """
    Query output state for specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    
    Returns: 1 if ON, 0 if OFF
    """
    return int(gen.query(f":OUTP{ch}?").strip())

def query_frequency(gen, ch):
    """
    Query frequency for specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    
    Returns: Frequency in Hz
    """
    return float(gen.query(f":SOUR{ch}:FREQ?").strip())

def query_amplitude(gen, ch):
    """
    Query amplitude for specified channel.
    
    gen: Generator instrument handle
    ch: Channel number (1-4)
    
    Returns: Amplitude in Vpp
    """
    return float(gen.query(f":SOUR{ch}:VOLT?").strip())

def reset_generator(gen):
    """
    Reset generator to default state.
    
    gen: Generator instrument handle
    """
    gen.write("*RST")
    time.sleep(0.5)

