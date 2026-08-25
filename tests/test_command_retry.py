import sys, types, importlib, asyncio, logging, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stub
sys.path.insert(0, str(ROOT / "custom_components"))
logging.basicConfig(level=logging.CRITICAL)
import homeassistant.const as hconst
hconst.ATTR_DEVICE_ID = "device_id"
pkg = types.ModuleType("stellantis_vehicles")
pkg.__path__ = [str(ROOT / "custom_components" / "stellantis_vehicles")]
sys.modules["stellantis_vehicles"] = pkg

base = importlib.import_module("stellantis_vehicles.base")

class FakeStellantis:
    def __init__(self):
        self.action = 0
        self.sent = []
        self.scheduled = []
    async def send_mqtt_message(self, service, message, vehicle):
        self.action += 1
        self.sent.append((service, message))
        return f"action{self.action}"
    def do_async(self, coro, delay=0, wait=True):
        # run the retry now instead of after the delay
        self.scheduled.append(delay)
        asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.ensure_future(coro)

class C(base.StellantisVehicleCoordinator):
    def __init__(self):
        self._data = {"preconditionning": {"airConditioning": {"status": "Disabled", "programs": []}}}
        self._vehicle = {"vin": "VIN1", "type": "Electric"}
        self._sensors = {}
        self._dropped_programs = set()
        self._commands_history = {}
        self._disabled_commands = []
        self._programs_override = None
        self._programs_override_at = None
        self._stellantis = FakeStellantis()
    def async_update_listeners(self):
        pass

async def main():
    c = C()
    await c.send_preconditioning_programs("write", [(1, [1, 0, 0, 0, 0, 0, 0], 7, 30, True)])
    assert len(c._stellantis.sent) == 1
    assert "retry" in c._commands_history["action1"], "a program write must be retryable"

    # the vehicle was asleep
    await c.update_command_history("action1", "300")
    await asyncio.sleep(0)
    assert len(c._stellantis.sent) == 2, "timeout should resend the command"
    assert c._stellantis.sent[1] == c._stellantis.sent[0], "the resend must carry the same payload"
    assert c._stellantis.scheduled == [30], "the resend should be delayed"
    print("timeout          -> resent once, same payload, after", c._stellantis.scheduled[0], "s")

    # and the resend does not retry again
    assert "retry" not in c._commands_history["action2"]
    await c.update_command_history("action2", "300")
    await asyncio.sleep(0)
    assert len(c._stellantis.sent) == 2, "a resend that times out must not loop"
    print("second timeout   -> no further resend")

    # other outcomes do not resend
    c2 = C()
    await c2.send_preconditioning_programs("write", [(1, [1, 0, 0, 0, 0, 0, 0], 7, 30, True)])
    await c2.update_command_history("action1", "0")
    await asyncio.sleep(0)
    assert len(c2._stellantis.sent) == 1
    print("complete         -> nothing resent")

    # commands that are not opted in are not retried
    c3 = C()
    await c3.send_command("horn", "/Horn", {"nb_horn": "2"})
    assert "retry" not in c3._commands_history["action1"]
    await c3.update_command_history("action1", "300")
    await asyncio.sleep(0)
    assert len(c3._stellantis.sent) == 1, "only opted in commands resend"
    print("other command    -> not resent")
    print("ALL OK")

asyncio.run(main())
