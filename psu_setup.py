# procedures.py

import time

# def power_on(psu, voltage):
    # psu.write(":OUTP CH1,OFF")
    # psu.write(f":SOUR1:VOLT {voltage}")
    # time.sleep(0.5)
    # psu.write(":OUTP CH1,ON")


def power_on(psu, channel: int, voltage: float):
    """
    Power ON a DP832 channel safely.

    psu     : VISA handle to DP832
    channel : PSU channel number (1, 2, or 3)
    voltage : Output voltage in volts
    """

    psu.write(f":OUTP CH{channel},OFF")       # Ensure channel is OFF
    psu.write(f":SOUR{channel}:VOLT {voltage}")  # Set voltage
    time.sleep(0.5)                           # Allow voltage register to settle
    psu.write(f":OUTP CH{channel},ON")        # Enable 

def power_off(psu):
    psu.write(":OUTP CH1,OFF")
    psu.write(":OUTP CH2,OFF")
    psu.write(":OUTP CH3,OFF")

def power_on_protected(psu, channel, voltage, current_limit, ovp=None, ocp=None):
    """
    Safe power ON with OVP & OCP protection (flexible channel)

    psu           : VISA handle to DP832
    channel       : PSU channel number (1 / 2 / 3)
    voltage       : Output voltage (V)
    current_limit : Current limit (A)
    ovp           : Over-voltage protection (V), default = 110% of voltage
    ocp           : Over-current protection (A), default = current_limit
    """

    # 1️⃣ Ensure output OFF (safety)
    psu.write(f":OUTP CH{channel},OFF")

    # 2️⃣ Set voltage & current limit
    psu.write(f":SOUR{channel}:VOLT {voltage}")
    psu.write(f":SOUR{channel}:CURR {current_limit}")

    # 3️⃣ Set OVP (default = 10% above voltage)
    if ovp is None:
        ovp = voltage * 1.1

    psu.write(f":SOUR{channel}:VOLT:PROT {ovp}")
    psu.write(f":SOUR{channel}:VOLT:PROT:STAT ON")

    # 4️⃣ Set OCP (default = current limit)
    if ocp is None:
        ocp = current_limit

    psu.write(f":SOUR{channel}:CURR:PROT {ocp}")
    psu.write(f":SOUR{channel}:CURR:PROT:STAT ON")

    # 5️⃣ Small delay before ON
    time.sleep(0.5)

    # 6️⃣ Turn ON output
    psu.write(f":OUTP CH{channel},ON")

    # 7️⃣ Stabilization delay
    time.sleep(1)
