import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .utils import preconditioning_days_from_string

from .const import (
    DOMAIN,
    PRECONDITIONING_PROGRAM_SLOTS,
    SERVICE_SET_PRECONDITIONING_PROGRAM
)

_LOGGER = logging.getLogger(__name__)

ATTR_SLOT = "slot"
ATTR_DAYS = "days"
ATTR_TIME = "time"
ATTR_ENABLED = "enabled"
ATTR_PROGRAMS = "programs"

PROGRAM_SCHEMA = vol.Schema({
    vol.Required(ATTR_SLOT): vol.All(vol.Coerce(int), vol.In(PRECONDITIONING_PROGRAM_SLOTS)),
    vol.Optional(ATTR_DAYS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_TIME): cv.time,
    vol.Optional(ATTR_ENABLED): cv.boolean
})

SET_PRECONDITIONING_PROGRAM_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_SLOT): vol.All(vol.Coerce(int), vol.In(PRECONDITIONING_PROGRAM_SLOTS)),
    vol.Optional(ATTR_DAYS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_TIME): cv.time,
    vol.Optional(ATTR_ENABLED): cv.boolean,
    vol.Optional(ATTR_PROGRAMS): vol.All(cv.ensure_list, [PROGRAM_SCHEMA])
})


def get_coordinators(hass: HomeAssistant, device_ids):
    """ Get the coordinators of the vehicles targeted by a service call. """
    registry = dr.async_get(hass)
    coordinators = []
    for device_id in device_ids:
        device = registry.async_get(device_id)
        coordinator = None
        if device:
            for identifier in device.identifiers:
                if identifier[0] != DOMAIN:
                    continue
                for entry_id in device.config_entries:
                    stellantis = hass.data.get(DOMAIN, {}).get(entry_id)
                    if stellantis:
                        coordinator = stellantis.async_get_coordinator_by_vin(identifier[1])
                        if coordinator:
                            break
                if coordinator:
                    break
        if not coordinator:
            raise ServiceValidationError(
                translation_domain = DOMAIN,
                translation_key = "device_not_found",
                translation_placeholders = {"device_id": device_id}
            )
        coordinators.append(coordinator)
    return coordinators


async def async_setup_services(hass: HomeAssistant) -> None:
    """ Register the integration services. """

    async def async_set_preconditioning_program(call: ServiceCall) -> None:
        """ Write preconditioning program slots of one or more vehicles.

        Slots given under "programs" are written in a single command, so a set of
        slots that belong together cannot be half applied.
        """
        wanted = call.data.get(ATTR_PROGRAMS)
        if not wanted:
            if ATTR_SLOT not in call.data:
                raise ServiceValidationError(
                    translation_domain = DOMAIN,
                    translation_key = "preconditioning_program_slot_missing"
                )
            wanted = [call.data]
        for coordinator in get_coordinators(hass, call.data[ATTR_DEVICE_ID]):
            programs = coordinator.get_programs()
            updates = []
            for item in wanted:
                slot = item[ATTR_SLOT]
                program = programs[f"program{slot}"]
                day = program["day"]
                hour = program["hour"]
                minute = program["minute"]
                on = program["on"]
                if ATTR_DAYS in item:
                    day = preconditioning_days_from_string(",".join(item[ATTR_DAYS]))
                if ATTR_TIME in item:
                    hour = item[ATTR_TIME].hour
                    minute = item[ATTR_TIME].minute
                if ATTR_ENABLED in item:
                    on = item[ATTR_ENABLED]
                updates.append((slot, day, hour, minute, on))
            slots = ", ".join([str(update[0]) for update in updates])
            name = coordinator.get_translation(f"component.{DOMAIN}.entity.switch.program{updates[0][0]}_enabled.name", f"program{updates[0][0]}_enabled")
            if len(updates) > 1:
                name = f"{name} (+{len(updates) - 1})"
            _LOGGER.debug("Writing preconditioning program slots %s of vehicle '%s'", slots, coordinator._vehicle["vin"])
            await coordinator.send_preconditioning_programs(name, updates)
            await coordinator.async_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_SET_PRECONDITIONING_PROGRAM):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_PRECONDITIONING_PROGRAM,
            async_set_preconditioning_program,
            schema = SET_PRECONDITIONING_PROGRAM_SCHEMA
        )
