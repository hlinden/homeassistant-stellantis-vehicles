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
utils = importlib.import_module("stellantis_vehicles.utils")
from stellantis_vehicles.const import PRECONDITIONING_PROGRAM_ASAP

# --- utils
assert utils.preconditioning_days_from_string("Mon,Fri") == [1,0,0,0,1,0,0]
assert utils.preconditioning_days_from_string(" mon , SUN ") == [1,0,0,0,0,0,1]
assert utils.preconditioning_days_from_string("") == [0]*7
try:
    utils.preconditioning_days_from_string("Mon,Funday")
    raise SystemExit("expected error")
except stub.ServiceValidationError as e:
    print("invalid day ->", e.translation_key, e.translation_placeholders)
assert utils.preconditioning_days_to_string([1,0,0,0,1,0,0]) == "Mon,Fri"
assert utils.preconditioning_program_time({"hour":34,"minute":7}) is None
assert str(utils.preconditioning_program_time({"hour":8,"minute":5})) == "08:05:00"

# --- coordinator
class FakeCoordinator(base.StellantisVehicleCoordinator):
    def __init__(self, data):
        self._data = data
        self._vehicle = {"vin": "VF1TESTVIN0000001", "type": "Electric"}
        self._sensors = {}
        self._dropped_programs = set(); self._programs_override = None; self._programs_override_at = None
        self.sent = []
    async def send_command(self, name, service, message, retry=False):
        self.sent.append((name, service, message))

data = {
  "preconditionning": {"airConditioning": {"status": "Disabled", "programs": [
     {"slot": 1, "enabled": True, "start": "PT7H30M", "occurence": {"day": ["Mon","Tue"]}},
     {"slot": 2, "enabled": False, "start": "PT18H0M"},
     {"slot": 3, "enabled": True, "start": "PT6H0M", "occurence": {"day": ["Sat","Sun"]}},
  ]}}
}
c = FakeCoordinator(data)
programs = c.get_programs()
print("programs:", programs)
assert programs["program1"] == {"day":[1,1,0,0,0,0,0],"hour":7,"minute":30,"on":1}
assert programs["program2"]["hour"] == 34 and programs["program2"]["minute"] == 7
assert c._dropped_programs == {2}
c.get_programs()  # second call must not warn again
assert c._dropped_programs == {2}

import asyncio
asyncio.run(c.send_preconditioning_program("test", 4, [0,0,0,0,0,1,0], 9, 15, True))
name, service, message = c.sent[-1]
print("payload:", message)
assert service == "/ThermalPrecond"
assert message["asap"] == PRECONDITIONING_PROGRAM_ASAP
assert message["programs"]["program4"] == {"day":[0,0,0,0,0,1,0],"hour":9,"minute":15,"on":1}
assert message["programs"]["program1"]["on"] == 1
assert message["programs"]["program2"] == {"day":[0]*7,"hour":34,"minute":7,"on":0}

# guard: enabling without a time
try:
    asyncio.run(c.send_preconditioning_program("test", 4, [1,0,0,0,0,0,0], 34, 7, True))
    raise SystemExit("expected error")
except stub.ServiceValidationError as e:
    print("enable without time ->", e.translation_key)
# guard: enabling without days
try:
    asyncio.run(c.send_preconditioning_program("test", 4, [0]*7, 9, 0, True))
    raise SystemExit("expected error")
except stub.ServiceValidationError as e:
    print("enable without days ->", e.translation_key)
# disabling an empty slot is allowed
asyncio.run(c.send_preconditioning_program("test", 4, [0]*7, 34, 7, False))
print("disable ok:", c.sent[-1][2]["programs"]["program4"])

# guard: preconditioning running
data["preconditionning"]["airConditioning"]["status"] = "Enabled"
assert c.preconditioning_is_running
try:
    asyncio.run(c.send_preconditioning_program("test", 1, [1,0,0,0,0,0,0], 7, 0, True))
    raise SystemExit("expected error")
except stub.ServiceValidationError as e:
    print("running ->", e.translation_key)

# empty vehicle data must not raise
empty = FakeCoordinator({})
assert empty.get_programs()["program1"]["hour"] == 34
assert not empty.preconditioning_data
print("ALL OK")
