# Preconditioning programs

This is a fork addition, see [FORK.md](../FORK.md).

The vehicle stores four preconditioning programs. Each one is exposed as three entities, for the first program:

- **time.#####VIN#####_preconditioning_program_1_time**
- **text.#####VIN#####_preconditioning_program_1_days**, a comma separated list built from `Mon,Tue,Wed,Thu,Fri,Sat,Sun`
- **switch.#####VIN#####_preconditioning_program_1**

The time is the time the vehicle should be ready, not the time preconditioning starts. The vehicle decides how long in advance to start. Measured on one car: a program written at 17:59 with a time of 18:30 started preconditioning at 18:00 and stopped it at 18:31. Enabling a program whose time is nearer than the vehicle's lead time therefore starts preconditioning immediately.

A program can only be enabled once it has a time and at least one day. Writing a program is refused while preconditioning is running, because the write reuses the preconditioning command and could stop the running session.

The same values can be set from an automation:

```yaml
actions:
  - action: stellantis_vehicles.set_preconditioning_program
    data:
      device_id: 0123456789abcdef0123456789abcdef
      slot: 1
      days:
        - Mon
        - Tue
        - Wed
        - Thu
        - Fri
      time: "07:30:00"
      enabled: true
```

Several slots at once go in one call, which is written as a single command:

```yaml
actions:
  - action: stellantis_vehicles.set_preconditioning_program
    data:
      device_id: 0123456789abcdef0123456789abcdef
      programs:
        - slot: 1
          days: [Mon]
          time: "18:00:00"
          enabled: true
        - slot: 2
          days: [Mon]
          time: "18:25:00"
          enabled: true
```

Fields left out of the call keep the current value. Slots that belong together, such as a pair covering an hour, should go in one call with the `programs` field.

Two more entities handle the cleanup. **button.#####VIN#####_clear_preconditioning_programs** resets all four slots at once, and pressing it during a run also stops the run, since the command carries the same stop action as the preconditioning stop button. **switch.#####VIN#####_clear_preconditioning_programs_automatically**, on by default, clears slots that have been used. When a run ends it clears only the slots whose time has passed today, so a later slot covering the rest of a longer period survives. When the vehicle starts moving it clears all four, since the departure has happened.

What was measured on one vehicle, an electric Opel, and may differ on yours:

- The vehicle starts preconditioning about 30 minutes before the programmed time. A program written for a time nearer than that starts it immediately, and it runs until the programmed time rather than for a fixed duration.
- The vehicle does not act on a second command sent moments after the first. Slots that belong together must go in one call.
- After a session ends, the vehicle refuses a manual start for a while. A session of 32 minutes was followed by a refusal 7 minutes later, reported as `Preconditioning start: Error`. How long that lasts is unknown, and it applies to the preconditioning buttons as much as to programs.
- A written program takes a minute or two to appear in the entities, because they follow what the vehicle reports. Until it does, the integration answers with what it last wrote, so a second write does not undo the first.
