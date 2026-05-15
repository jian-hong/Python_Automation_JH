# instruments.py

import pyvisa
#from config import *



def find_instruments():
    import pyvisa

    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()

    instruments = {}

    for res in resources:
        try:
            inst = rm.open_resource(res)
            idn = inst.query("*IDN?").strip()
            print(f"🔍 Found: {res} → {idn}")

            # Identify based on IDN string
            if "MSO5" in idn:
                instruments["MSO"] = res

            elif "DP832" in idn:
                instruments["PSU"] = res

            elif "DG8" in idn or "DG811" in idn:
                instruments["AWG"] = res

            # elif "DMM6500" in idn:
            #     instruments["DMM"] = res

            inst.close()

        except Exception as e:
            print(f"⚠️ Skipping {res}: {e}")

    return instruments
    


class Instruments:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()

        # Auto detect
        self.inst_map = find_instruments()

        print("✅ Final Mapping:")
        print(self.inst_map)

        # Open instruments safely
        self.scope = self._open("MSO")
        self.psu   = self._open("PSU")
        self.gen   = self._open("AWG")
        # self.dmm   = self._open("DMM")

    def _open(self, key):
        url = self.inst_map.get(key)

        if not url:
            raise Exception(f"❌ {key} not found")

        inst = self.rm.open_resource(url)
        inst.timeout = 3000
        return inst

    def reset_all(self):
        for inst in [self.scope, self.gen, self.psu]:
            try:
                inst.write("*RST")
            except Exception as e:
                print(f"⚠️ Reset failed: {e}")

    def close_all(self):
        for inst in [self.scope, self.gen, self.psu]:
            try:
                inst.close()
            except:
                pass
    
# class Instruments:
   # inst = find_instruments()

# MSO50_URL = inst.get("MSO")
# DP832_URL = inst.get("PSU")
# DG811_URL = inst.get("AWG")
# DMM6500_URL = inst.get("DMM")

    # print("Final Mapping:")
    # print(inst)

    # def __init__(self):
        # self.rm = pyvisa.ResourceManager()
        # self.scope = self.rm.open_resource(MSO50_URL)
        # self.psu = self.rm.open_resource(DP832_URL)
        # self.gen = self.rm.open_resource(DG811_URL)
        # self.dmm = self.rm.open_resource(DMM6500_URL) 
    # def reset_all(self):
        # self.scope.write("*RST")
        # self.gen.write("*RST")
        # self.psu.write("*RST")
        # self.dmm.write("*RST")
    # def close_all(self):
        # self.scope.close()
        # self.gen.close()
        # self.psu.close()
        # self.dmm.close()    
        



