def measure_voltage(dmm):
    dmm.write("*RST")
    dmm.write(":SENS:FUNC 'VOLT:DC'")
    dmm.write(":SENS:VOLT:DC:RANG:AUTO ON")

    value = dmm.query(":READ?")
    return float(value)
	
def measure_current(dmm):
    dmm.write("*RST")
    dmm.write(":SENS:FUNC 'CURR:DC'")
    dmm.write(":SENS:CURR:DC:RANG:AUTO ON")

    value = dmm.query(":READ?")
    return float(value)
	
def measure_capacitance(dmm):
    dmm.write("*RST")
    dmm.write(":SENS:FUNC 'CAP'")
    dmm.write(":SENS:CAP:RANG:AUTO ON")

    value = dmm.query(":READ?")
    return float(value)
    
def dmm_read_avg(dmm, n=5):
    values = [float(dmm.query(":READ?")) for _ in range(n)]
    return sum(values)/len(values)

def dmm_setup_voltage(dmm):
    """Setup DMM for DC voltage measurement and return measurement.
    
    Args:
        dmm: PyVISA DMM resource handle
        dmm: what do you mean wowoowowowo
    Returns:
        float: Measured voltage in volts
    """
    dmm.write("*RST")
    dmm.write(":SENS:FUNC 'VOLT:DC'")
    dmm.write(":SENS:VOLT:DC:RANG:AUTO ON")
    value = dmm.query(":READ?")
    return float(value)

def dmm_setup_current(dmm):
    """Setup DMM for DC current measurement and return measurement.
    
    Args:
        dmm: PyVISA DMM resource handle
        
    Returns:
        float: Measured current in amps
    """
    dmm.write("*RST")
    dmm.write(":SENS:FUNC 'CURR:DC'")
    dmm.write(":SENS:CURR:DC:RANG:AUTO ON")
    value = dmm.query(":READ?")
    return float(value)

def dmm_setup_cap(dmm):
    """Setup DMM for capacitance measurement and return measurement.
    
    Args:
        dmm: PyVISA DMM resource handle
        
    Returns:
        float: Measured capacitance in farads
    """
    dmm.write("*RST")
    dmm.write(":SENS:FUNC 'CAP'")
    dmm.write(":SENS:CAP:RANG:AUTO ON")
    value = dmm.query(":READ?")
    return float(value)

def dmm_read(dmm):
    """Read current DMM measurement without reconfiguration.
    
    Args:
        dmm: PyVISA DMM resource handle
        
    Returns:
        float: Current measurement value
    """
    value = dmm.query(":READ?")
    return float(value)