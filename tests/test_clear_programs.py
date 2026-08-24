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

class FakeCoordinator(base.StellantisVehicleCoordinator):
    def __init__(self, data):
        self._data = data; self._vehicle = {"vin":"VIN1","type":"Electric"}
        self._sensors = {}; self._dropped_programs = set(); self.sent = []
    async def send_command(self, name, service, message): self.sent.append((name, service, message))

data = {"preconditionning": {"airConditioning": {"status": "Disabled", "programs": [
    {"slot": 1, "enabled": True, "start": "PT18H30M", "occurence": {"day": ["Mon"]}},
    {"slot": 3, "enabled": True, "start": "PT6H0M", "occurence": {"day": ["Sat","Sun"]}}]}}}
c = FakeCoordinator(data)
asyncio.run(c.send_preconditioning_programs_clear("Clear preconditioning programs"))
name, service, msg = c.sent[-1]
print("service:", service, "| asap:", msg["asap"])
for k in sorted(msg["programs"]): print(" ", k, msg["programs"][k])
assert service == "/ThermalPrecond"
assert len(msg["programs"]) == 4
for k, p in msg["programs"].items():
    assert p == {"day":[0]*7,"hour":34,"minute":7,"on":0}, (k, p)
# during a run it is allowed, the payload doubles as the stop command
data["preconditionning"]["airConditioning"]["status"] = "Enabled"
asyncio.run(c.send_preconditioning_programs_clear("Clear preconditioning programs"))
assert len(c.sent) == 2
assert c.sent[-1][2]["asap"] == "deactivate"
assert all(p == {"day":[0]*7,"hour":34,"minute":7,"on":0} for p in c.sent[-1][2]["programs"].values())
print("during a run -> allowed, sends", c.sent[-1][2]["asap"], "plus four cleared slots")
print("ALL OK")
