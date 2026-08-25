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
time_p = importlib.import_module("stellantis_vehicles.time")
switch_p = importlib.import_module("stellantis_vehicles.switch")
text_p = importlib.import_module("stellantis_vehicles.text")

class Description:
    def __init__(self, key):
        self.key = key
        self.translation_key = key
        self.name = key

class FakeCoordinator(base.StellantisVehicleCoordinator):
    def __init__(self, data):
        self._data = data
        self._hass = None
        self._config = {}
        self._vehicle = {"vin": "VF1TESTVIN0000001", "type": "Electric"}
        self._stellantis = None
        self._sensors = {}
        self._dropped_programs = set(); self._programs_override = None; self._programs_override_at = None
        self._commands_history = {}
        self._disabled_commands = []
        self.sent = []
        self.refreshed = 0
    async def send_command(self, name, service, message, retry=False):
        self.sent.append((name, service, message))
    async def async_refresh(self):
        self.refreshed += 1

data = {"preconditionning": {"airConditioning": {"status": "Disabled", "programs": [
    {"slot": 1, "enabled": True, "start": "PT7H30M", "occurence": {"day": ["Mon","Tue"]}}
]}}}
c = FakeCoordinator(data)

def make(cls, key, slot):
    e = cls.__new__(cls)
    base.StellantisBaseEntity.__init__(e, c, Description(key))
    e._sensor_key = key.split("_")[0] + "_" if False else None
    return e

# use the real constructors instead
t = time_p.StellantisPreconditioningProgramTime(c, Description("program1_time"), 1)
sw = switch_p.StellantisPreconditioningProgramSwitch(c, Description("program1_enabled"), 1)
tx = text_p.StellantisPreconditioningProgramDays(c, Description("program1_days"), 1)
for e in (t, sw, tx):
    e.name = e._key   # Entity.name is provided by HA at runtime

print("mro ok:", t._sensor_key, sw._sensor_key, tx._sensor_key)
t.coordinator_update(); sw.coordinator_update(); tx.coordinator_update()
print("time:", t.native_value, "| switch:", sw.is_on, "| days:", tx.native_value)
assert str(t.native_value) == "07:30:00"
assert sw.is_on is True
assert tx.native_value == "Mon,Tue"

from datetime import time as dtime
asyncio.run(t.async_set_value(dtime(6, 45)))
print("after time write:", c.sent[-1][2]["programs"]["program1"], "refresh:", c.refreshed)
assert c.sent[-1][2]["programs"]["program1"] == {"day":[1,1,0,0,0,0,0],"hour":6,"minute":45,"on":1}
assert c.sent[-1][0] == "program1_time"

asyncio.run(tx.async_set_value("wed, Thu"))
print("after days write:", c.sent[-1][2]["programs"]["program1"], "| entity:", tx.native_value)
assert c.sent[-1][2]["programs"]["program1"]["day"] == [0,0,1,1,0,0,0]

asyncio.run(sw.async_turn_off())
assert c.sent[-1][2]["programs"]["program1"]["on"] == 0
assert sw.is_on is False
print("after switch off:", c.sent[-1][2]["programs"]["program1"])

# empty slot: no time, no days
t4 = time_p.StellantisPreconditioningProgramTime(c, Description("program4_time"), 4)
sw4 = switch_p.StellantisPreconditioningProgramSwitch(c, Description("program4_enabled"), 4)
tx4 = text_p.StellantisPreconditioningProgramDays(c, Description("program4_days"), 4)
for e in (t4, sw4, tx4):
    e.name = e._key
    e.coordinator_update()
print("empty slot:", t4.native_value, sw4.is_on, repr(tx4.native_value))
assert t4.native_value is None and sw4.is_on is False and tx4.native_value == ""
try:
    asyncio.run(sw4.async_turn_on())
    raise SystemExit("expected error")
except stub.ServiceValidationError as e:
    print("enable empty slot ->", e.translation_key)

# no vehicle data yet: entities must keep their restored value
empty = FakeCoordinator({})
t_e = time_p.StellantisPreconditioningProgramTime(empty, Description("program1_time"), 1)
empty._sensors["time_program1_time"] = dtime(5, 0)
t_e.coordinator_update()
assert str(t_e.native_value) == "05:00:00"
print("days pattern:", text_p.DAYS_PATTERN)
import re
for value, expected in [("", True), ("Mon", True), ("Mon,Sun", True), ("mon", False), ("Mon,", False), ("Funday", False)]:
    assert bool(re.match(text_p.DAYS_PATTERN, value)) is expected, value
print("ALL OK")
