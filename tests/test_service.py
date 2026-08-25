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
        self._data = data
        self._vehicle = {"vin": "VIN1", "type": "Electric"}
        self._sensors = {}
        self._dropped_programs = set(); self._programs_override = None; self._programs_override_at = None
        self.sent = []
        self.refreshed = 0
    async def send_command(self, name, service, message, retry=False):
        self.sent.append((name, service, message))
    async def async_refresh(self):
        self.refreshed += 1
    def get_translation(self, path, default=None):
        return default

coordinator = FakeCoordinator({"preconditionning": {"airConditioning": {"status": "Disabled", "programs": [
    {"slot": 2, "enabled": True, "start": "PT7H0M", "occurence": {"day": ["Mon"]}}
]}}})

class FakeStellantis:
    def async_get_coordinator_by_vin(self, vin):
        return coordinator if vin == "VIN1" else None

class Device:
    identifiers = {("stellantis_vehicles", "VIN1", "Electric")}
    config_entries = ["entry1"]

class Registry:
    def async_get(self, device_id):
        return Device() if device_id == "dev1" else None

class Services:
    def __init__(self): self.registered = {}
    def has_service(self, domain, service): return service in self.registered
    def async_register(self, domain, service, func, schema=None): self.registered[service] = func

class Hass:
    def __init__(self):
        self.data = {"stellantis_vehicles": {"entry1": FakeStellantis()}}
        self.services = Services()

import homeassistant.helpers as helpers
helpers.device_registry.async_get = staticmethod(lambda hass: Registry())

services = importlib.import_module("stellantis_vehicles.services")
hass = Hass()
asyncio.run(services.async_setup_services(hass))
handler = hass.services.registered["set_preconditioning_program"]

class Call:
    def __init__(self, data): self.data = data

from datetime import time as dtime
asyncio.run(handler(Call({"device_id": ["dev1"], "slot": 2, "days": ["Tue", "Thu"], "time": dtime(6, 30), "enabled": True})))
print("full call:", coordinator.sent[-1][2]["programs"]["program2"], "| name:", coordinator.sent[-1][0], "| refresh:", coordinator.refreshed)
assert coordinator.sent[-1][2]["programs"]["program2"] == {"day":[0,1,0,1,0,0,0],"hour":6,"minute":30,"on":1}

# omitted fields keep the current value, which after a write is what was written,
# not the older one the vehicle is still reporting
asyncio.run(handler(Call({"device_id": ["dev1"], "slot": 2, "enabled": False})))
print("partial call:", coordinator.sent[-1][2]["programs"]["program2"])
assert coordinator.sent[-1][2]["programs"]["program2"] == {"day":[0,1,0,1,0,0,0],"hour":6,"minute":30,"on":0}

# unknown device
try:
    asyncio.run(handler(Call({"device_id": ["nope"], "slot": 1})))
    raise SystemExit("expected error")
except stub.ServiceValidationError as e:
    print("unknown device ->", e.translation_key, e.translation_placeholders)

# invalid day name from an automation
try:
    asyncio.run(handler(Call({"device_id": ["dev1"], "slot": 1, "days": ["Monday"]})))
    raise SystemExit("expected error")
except stub.ServiceValidationError as e:
    print("invalid day ->", e.translation_key)
# batch: several slots in a single command
coordinator.sent.clear()
asyncio.run(handler(Call({"device_id": ["dev1"], "programs": [
    {"slot": 1, "days": ["Mon"], "time": dtime(19, 55), "enabled": True},
    {"slot": 2, "days": ["Mon"], "time": dtime(20, 20), "enabled": True}]})))
assert len(coordinator.sent) == 1, "batch must be one command"
p = coordinator.sent[0][2]["programs"]
print("batch ->", {k: (v["hour"], v["minute"], v["on"]) for k, v in p.items()})
assert (p["program1"]["hour"], p["program2"]["hour"]) == (19, 20)

# neither slot nor programs
try:
    asyncio.run(handler(Call({"device_id": ["dev1"]})))
    raise SystemExit("expected error")
except stub.ServiceValidationError as e:
    print("no slot, no programs ->", e.translation_key)
print("ALL OK")
