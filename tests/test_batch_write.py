import sys, types, importlib, asyncio, logging, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stub
sys.path.insert(0, str(ROOT / "custom_components"))
logging.basicConfig(level=logging.WARNING)
import homeassistant.const as hconst
hconst.ATTR_DEVICE_ID = "device_id"
pkg = types.ModuleType("stellantis_vehicles")
pkg.__path__ = [str(ROOT / "custom_components" / "stellantis_vehicles")]
sys.modules["stellantis_vehicles"] = pkg

base = importlib.import_module("stellantis_vehicles.base")

class C(base.StellantisVehicleCoordinator):
    def __init__(self, d):
        self._data = d; self._vehicle = {"vin":"VIN1","type":"Electric"}
        self._sensors = {}; self._dropped_programs = set(); self.sent = []
        self._programs_override = None; self._programs_override_at = None
    async def send_command(self, n, s, m): self.sent.append((n, s, m))
    async def async_refresh(self): pass
    def get_translation(self, p, d=None): return d

data = {"preconditionning": {"airConditioning": {"status": "Disabled", "programs": []}}}
c = C(data)

# two slots, one command
asyncio.run(c.send_preconditioning_programs("chain", [(1,[1,0,0,0,0,0,0],19,55,True), (2,[1,0,0,0,0,0,0],20,20,True)]))
assert len(c.sent) == 1, "must be a single command"
p = c.sent[0][2]["programs"]
print("one command wrote:", {k: (v["hour"], v["minute"], v["on"]) for k, v in p.items()})
assert (p["program1"]["hour"], p["program1"]["minute"]) == (19, 55)
assert (p["program2"]["hour"], p["program2"]["minute"]) == (20, 20)

# the override survives a stale readback: the car has not reported anything yet
back = c.get_programs()
assert (back["program1"]["hour"], back["program2"]["hour"]) == (19, 20), back
print("stale readback answered from the override:", back["program1"]["hour"], back["program2"]["hour"])

# a second write now composes instead of reverting the first
asyncio.run(c.send_preconditioning_program("later", 3, [0,1,0,0,0,0,0], 7, 0, True))
p2 = c.sent[-1][2]["programs"]
assert (p2["program1"]["hour"], p2["program2"]["hour"], p2["program3"]["hour"]) == (19, 20, 7), p2
print("second write kept the earlier slots:", {k: v["hour"] for k, v in p2.items()})

# once the vehicle reports the same programs, the override lets go
data["preconditionning"]["airConditioning"]["programs"] = [
    {"slot":1,"enabled":True,"start":"PT19H55M","occurence":{"day":["Mon"]}},
    {"slot":2,"enabled":True,"start":"PT20H20M","occurence":{"day":["Mon"]}},
    {"slot":3,"enabled":True,"start":"PT7H0M","occurence":{"day":["Tue"]}}]
assert c.get_programs()["program1"]["hour"] == 19
assert c._programs_override is None, "override should clear once the vehicle agrees"
print("override released once the vehicle agreed")

# and it expires even if the vehicle never agrees
c2 = C({"preconditionning": {"airConditioning": {"status": "Disabled", "programs": []}}})
asyncio.run(c2.send_preconditioning_program("x", 1, [1,0,0,0,0,0,0], 9, 0, True))
c2._programs_override_at = c2._programs_override_at - datetime.timedelta(seconds=400)
assert c2.get_programs()["program1"]["hour"] == 34
print("override expired after the ttl, back to vehicle data")
print("ALL OK")
