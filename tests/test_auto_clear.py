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

PROG = {"slot":1,"enabled":True,"start":"PT18H30M","occurence":{"day":["Mon"]}}
def data(status="Disabled", programs=(PROG,), moving=False):
    return {"preconditionning": {"airConditioning": {"status": status, "programs": list(programs)}},
            "kinetic": {"moving": moving}, "ignition": {"type": "Stop"}}

class C(base.StellantisVehicleCoordinator):
    def __init__(self, d, sensors):
        self._data = d; self._vehicle = {"vin":"VIN1","type":"Electric"}
        self._sensors = dict(sensors); self._dropped_programs = set(); self._programs_override = None; self._programs_override_at = None; self.sent = []
        self._manage_charge_limit_sent = False; self._last_trip = None
        self._update_interval_seconds = 60
    async def send_command(self, n, s, m): self.sent.append((n, s, m))
    async def async_refresh(self): pass
    async def get_vehicle_last_trip(self): pass
    def get_translation(self, path, default=None): return default or "Clear preconditioning programs"
    @property
    def vehicle_type(self): return "Electric"

on = {"switch_clear_programs_automatically": True}
def run(c):
    asyncio.run(c.after_async_update_data()); return len(c.sent)

# a run that ends clears only the slot it ran for, a later slot survives
import datetime as _dt
now = _dt.datetime.now()
past = "PT%dH%dM" % (max(now.hour - 1, 0), now.minute)
future = "PT%dH%dM" % (min(now.hour + 1, 23), now.minute)
today = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][now.weekday()]
chain = (
    {"slot": 1, "enabled": True, "start": past, "occurence": {"day": [today]}},
    {"slot": 2, "enabled": True, "start": future, "occurence": {"day": [today]}},
)
c = C(data("Disabled", programs=chain), {**on, "preconditioning": "Enabled"})
assert run(c) == 1, "expected a clear when the run ended"
sent = c.sent[0][2]["programs"]
assert sent["program1"]["hour"] == 34, "the slot that ran should be cleared"
assert sent["program2"]["hour"] != 34, "a later slot must survive, it is the rest of the chain"
print("run ended            -> cleared slot 1, kept slot 2 at", sent["program2"]["hour"])

# a run that ends with nothing spent sends no command
c = C(data("Disabled", programs=(chain[1],)), {**on, "preconditioning": "Enabled"})
assert run(c) == 0
print("nothing spent yet    -> no command")

# session still running -> nothing
c = C(data("Enabled"), {**on, "preconditioning": "Enabled"})
assert run(c) == 0
print("session still running -> no command")

# driving off clears everything, spent or not
c = C(data("Disabled", programs=chain, moving=True), {**on, "preconditioning": "Disabled", "moving": False})
assert run(c) == 1
sent = c.sent[0][2]["programs"]
assert all(sent[f"program{n}"]["hour"] == 34 for n in range(1, 5))
print("started moving       -> cleared all four")

# already moving, and nothing spent -> nothing
c = C(data("Disabled", programs=(chain[1],), moving=True), {**on, "preconditioning": "Disabled", "moving": True})
assert run(c) == 0
print("already moving       -> no command")

# nothing to clear -> no pointless command
c = C(data("Disabled", programs=()), {**on, "preconditioning": "Disabled", "moving": False})
c._data["kinetic"]["moving"] = True
assert run(c) == 0
print("no programs set      -> no command")

# a slot whose time passed without any run is still cleared
c = C(data("Disabled", programs=(chain[0],)), {**on, "preconditioning": "Disabled", "moving": False})
assert run(c) == 1
assert c.sent[0][2]["programs"]["program1"]["hour"] == 34
print("passed, never ran   -> cleared anyway")

# but not while a session is running
c = C(data("Enabled", programs=(chain[0],)), {**on, "preconditioning": "Enabled", "moving": False})
assert run(c) == 0
print("running             -> left alone")

# switch off -> nothing
c = C(data("Disabled", moving=True), {"switch_clear_programs_automatically": False, "preconditioning": "Enabled", "moving": False})
assert run(c) == 0
print("switch off           -> no command")
print("ALL OK")
