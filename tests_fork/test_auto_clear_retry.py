"""
Automatic clear and command failures, with the real send_command and a clock
under the test's control: backoff after a failed clear, no stacking of clears,
an override that follows its command, resends that must not stop a session,
and notifications that are only raised for failures nobody is handling.
"""
import sys, types, importlib, asyncio, logging
from datetime import datetime, timedelta
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

# Wednesday 18 Nov 2026, the four slots of the real run
tz = datetime.now().astimezone().tzinfo
NOW = [datetime(2026, 11, 18, 15, 31, 30, tzinfo=tz)]
base.get_datetime = lambda: NOW[0]
def advance(seconds):
    NOW[0] = NOW[0] + timedelta(seconds=seconds)

def slot(n, h, m):
    return {"slot": n, "enabled": True, "start": f"PT{h}H{m}M", "occurence": {"day": ["Wed"]}}
FOUR = [slot(1, 15, 30), slot(2, 15, 45), slot(3, 16, 0), slot(4, 16, 15)]

counter = [0]
def car(status="Disabled", programs=FOUR, moving=False):
    # every call is a fresh report, as after_async_update_data only runs on one
    counter[0] += 1
    return {"preconditionning": {"airConditioning": {"status": status, "programs": list(programs)}},
            "kinetic": {"moving": moving}, "ignition": {"type": "Stop"}, "n": counter[0]}

class FakeStellantis:
    def __init__(self):
        self.action = 0
        self.sent = []
        self.notified = []
        self.dismissed = []
        self.later = []
    async def send_mqtt_message(self, service, message, vehicle):
        self.action += 1
        self.sent.append(message)
        return f"a{self.action}"
    async def hass_notify(self, key, notification_id=None, details=None):
        self.notified.append((key, notification_id, details))
    def hass_dismiss_notification(self, notification_id):
        self.dismissed.append(notification_id)
    def do_async(self, coro, delay=0, wait=True):
        if delay:
            self.later.append(coro)   # run by the test when it wants to
        else:
            asyncio.ensure_future(coro)

class C(base.StellantisVehicleCoordinator):
    def __init__(self, sensors=None):
        self.data = car()
        self._vehicle = {"vin": "VIN1", "type": "Electric"}
        self._sensors = {"switch_clear_programs_automatically": True, "preconditioning": "Disabled", "moving": False, **(sensors or {})}
        self._dropped_programs = set()
        self._commands_history = {}
        self._pending_action_id = None
        self._disabled_commands = []
        self._programs_override = None; self._programs_override_at = None; self._programs_override_action_id = None
        self._auto_clear_action_id = None; self._auto_clear_failures = 0; self._auto_clear_next_at = None; self._auto_clear_last_status = None
        self._manage_charge_limit_sent = False; self._last_trip = None
        self._translations = {}
        self._hass = None
        self._stellantis = FakeStellantis()
    def async_update_listeners(self): pass
    async def async_refresh(self): pass
    async def get_vehicle_last_trip(self): pass
    def _vehicle_display_name(self): return "Blauwal"
    @property
    def vehicle_type(self): return "Electric"

async def update(c, d):
    """ One coordinator update with fresh data d. """
    await c.after_async_update_data(d)
    c.data = d
    c._sensors["preconditioning"] = c.get_preconditioning_data(d).get("status")
    c._sensors["moving"] = bool((d.get("kinetic") or {}).get("moving"))
    await asyncio.sleep(0)

async def status(c, action_id, code, result_code=None):
    await c.update_command_history(action_id, code, result_code if result_code is not None else code)
    await asyncio.sleep(0)

def shown_on(c):
    return [bool(c.get_programs()[f"program{n}"]["on"]) for n in (1, 2, 3, 4)]

async def main():
    # --- the real run's slot 1 clear, now with backoff -------------------
    c = C()
    st = c._stellantis
    await update(c, car())
    assert len(st.sent) == 1, "the spent slot is cleared"
    cmd = c._commands_history["a1"]
    assert "retry" not in cmd and cmd.get("internal"), "the automatic clear retries by itself, not with the 30 s resend"
    assert shown_on(c) == [False, True, True, True]
    assert c.auto_clear_state["state"] == "sending"

    await status(c, "a1", "900")
    advance(60)
    await update(c, car())
    assert len(st.sent) == 1, "no second clear while the first is still on its way (the Duplicates)"

    advance(64)
    await status(c, "a1", "300")
    assert st.later == [], "nothing resent 30 s later"
    assert st.notified == [], "a failed automatic clear is not notified on its own"
    assert shown_on(c) == [True, True, True, True], "the vehicle still holds slot 1, the switch must say so"
    assert c.auto_clear_state["state"] == "waiting" and c.auto_clear_state["failed_attempts"] == 1
    print("clear timed out      -> no resend, no notification, switch shows the truth, waiting")

    advance(60)
    await update(c, car())
    assert len(st.sent) == 1, "the next update is too early"
    advance(300)
    await update(c, car())
    assert len(st.sent) == 2, "after 5 minutes the next attempt goes out"
    print("backoff              -> next attempt after 5 min, not on the next update")

    # failures 2..4: the fourth one notifies, once, with a fixed id
    await status(c, "a2", "300")
    for wait, n in ((900, 3), (1800, 4)):
        advance(wait + 1)
        await update(c, car())
        assert len(st.sent) == n, (wait, len(st.sent))
        await status(c, f"a{n}", "300" if n < 4 else "502")
    assert c._auto_clear_failures == 4
    assert [k for k, *_ in st.notified] == ["auto_clear_failed"], st.notified
    key, nid, details = st.notified[0]
    assert nid == "stellantis_vehicles_vin1_auto_clear_failed" and "Blauwal" in details and "4x" in details, st.notified[0]
    advance(1801)
    await update(c, car())
    assert len(st.sent) == 5, "it keeps trying at the last step"
    await status(c, "a5", "300")
    assert len(st.notified) == 1, "notified once, not on every further failure"
    print("4 failures in a row  -> one notification,", nid)

    # a run that ends shows the car is awake: try now
    advance(60)
    await update(c, car(status="Enabled"))
    advance(60)
    await update(c, car(status="Disabled"))
    assert len(st.sent) == 6, "run ended, tried at once despite the backoff"
    await status(c, "a6", "903")
    await status(c, "a6", "0")
    assert "stellantis_vehicles_vin1_auto_clear_failed" in st.dismissed, "success dismisses the notification"
    assert shown_on(c) == [False, False, False, False], "complete: the clear stands in until the car reports it"
    advance(200)
    await update(c, car())
    assert len(st.sent) == 6, "no new clear while the car has not caught up with a completed one"
    await update(c, car(programs=[]))
    assert c.auto_clear_state["state"] == "idle" and c._auto_clear_failures == 0
    print("run ended            -> immediate attempt, Complete dismisses, reset once the car reports it")

    # --- a stale command counts as failed ---------------------------------
    c = C()
    await update(c, car())
    advance(301)
    await update(c, car())
    assert c._auto_clear_failures == 1 and len(c._stellantis.sent) == 1, "no status for 5 minutes: failed, backoff"
    print("no status at all     -> counted as failed after 5 min")

    # --- the override follows a user write --------------------------------
    c = C()
    c._sensors["switch_clear_programs_automatically"] = False
    st = c._stellantis
    await c.send_preconditioning_programs("Program 1", [(1, [0, 0, 1, 0, 0, 0, 0], 18, 0, True)])
    assert c.programs_unconfirmed
    await status(c, "a1", "900")
    advance(250)
    await status(c, "a1", "300")
    assert st.notified == [], "a timeout that will be resent is not notified"
    advance(200)  # past the old fixed 300 s TTL, the resend still pending
    assert c.get_programs()["program1"]["hour"] == 18, "held while the resend is pending"
    await st.later.pop()
    assert c._commands_history["a1"]["resent_as"] == "a2"
    advance(140)
    await status(c, "a2", "300")
    assert c.get_programs()["program1"]["hour"] == 15, "the resend failed too: back to what the car holds"
    assert len(st.notified) == 1 and st.notified[0][0] == "command_error"
    key, nid, details = st.notified[0]
    assert nid == "stellantis_vehicles_vin1_program_1" and details == "Blauwal: Program 1: 300", st.notified[0]
    print("user write           -> held through the resend, dropped and notified when it finally fails")

    await c.send_preconditioning_programs("Program 1", [(1, [0, 0, 1, 0, 0, 0, 0], 18, 0, True)])
    await status(c, "a3", "0")
    assert nid in st.dismissed, "the same command completing dismisses its notification"
    advance(299)
    assert c.get_programs()["program1"]["hour"] == 18
    advance(2)
    assert c.get_programs()["program1"]["hour"] == 15, "a Complete the car never reports expires"
    await c.send_preconditioning_programs("Program 1", [(1, [0, 0, 1, 0, 0, 0, 0], 18, 0, True)])
    await status(c, "a4", "500")
    await c.send_preconditioning_programs("Program 1", [(1, [0, 0, 1, 0, 0, 0, 0], 18, 0, True)])
    await status(c, "a5", "500")
    assert len({n for _, n, _ in st.notified}) == 1, "the same command replaces its notification, it does not stack"
    print("Complete             -> dismissed; repeated failures share one notification id")

    # --- a resend must not stop a session that has started since ---------
    c = C()
    c._sensors["switch_clear_programs_automatically"] = False
    st = c._stellantis
    await c.send_preconditioning_programs("Program 2", [(2, [0, 0, 1, 0, 0, 0, 0], 18, 0, True)])
    await status(c, "a1", "300")
    c.data = car(status="Enabled")
    await st.later.pop()
    await asyncio.sleep(0)
    assert len(st.sent) == 1, "not resent: it would have stopped the session"
    assert c.get_programs()["program2"]["hour"] == 15, "and the write counts as failed"
    assert len(st.notified) == 1, "a user command that was not resent is reported"
    print("resend during a run  -> skipped, reported")

    # the clear button pressed during a run is meant to stop it
    c = C()
    st = c._stellantis
    c.data = car(status="Enabled")
    await c.send_preconditioning_programs_clear("Clear preconditioning programs")
    await status(c, "a1", "300")
    await st.later.pop()
    assert len(st.sent) == 2, "a clear sent during a run is still resent during the run"
    print("clear button in run  -> still resent")

    # --- the charge stop is not internal: its failure is final -----------
    c = C()
    st = c._stellantis
    await c.send_command("Charge stop", "/VehCharge", {"type": "delayed"})
    await status(c, "a1", "300")
    assert len(st.notified) == 1, "a failed charge stop is reported"
    print("charge stop timeout  -> reported")
    print("ALL OK")

asyncio.run(main())
