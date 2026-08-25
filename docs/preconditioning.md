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

Two more entities handle the cleanup. **button.#####VIN#####_clear_preconditioning_programs** resets all four slots at once, and pressing it during a run also stops the run, since the command carries the same stop action as the preconditioning stop button. **switch.#####VIN#####_clear_preconditioning_programs_automatically**, on by default, clears slots whose time has passed today, whether or not the vehicle ran for them. A later slot is left alone, so a pair covering a longer period is not cut short. When the vehicle starts moving it clears all four, since the departure has happened.

What was measured on one vehicle, an electric Opel, and may differ on yours:

- The vehicle starts preconditioning about 30 minutes before the programmed time. A program written for a time nearer than that starts it immediately, and it runs until the programmed time rather than for a fixed duration.
- The vehicle does not act on a second command sent moments after the first. Slots that belong together must go in one call.
- After a session ends, the vehicle refuses a manual start for a while. A session of 32 minutes was followed by a refusal 7 minutes later, reported as `Preconditioning start: Error`. How long that lasts is unknown, and it applies to the preconditioning buttons as much as to programs.
- Programs do chain, but not always. Two slots ready at 06:03 and 06:28 both ran, the second starting 10 minutes after the first ended. The evening before, the same pairing at 21:09 and 21:34 produced nothing for the second slot: no session, no wallbox draw, no command. Six sessions had run since the vehicle was last driven, and after a very short drive the next two ran normally, so a limit on runs between drives is the likeliest explanation. Unconfirmed.
- How far ahead the vehicle starts varies. It began 15 minutes before the programmed time twice on a cold morning, and 24 to 31 minutes before on the previous evening. Chaining slots 25 minutes apart therefore left a 10 minute gap with nothing running.
- The clear button stops a running session. Pressing it at 19:48:35 ended a session 14 seconds later. Since every program write carries the same stop action, a write during a session would very likely stop it too, which is what the refusal on program writes protects against.
- A command sent while the vehicle is asleep can time out and is then lost. A write at 05:33 went Accepted, Wakeup Vehicle, Timeout, and nothing had changed. Program writes and clears are now sent once more 30 seconds after a timeout. Only those two, because they set state and can be sent twice without doing anything twice. The platform already attempts a wakeup as part of every command, so the retry does not send one of its own: wakeups are rate limited and drain the service battery.
- A written program takes a minute or two to appear in the entities, because they follow what the vehicle reports. Until it does, the integration answers with what it last wrote, so a second write does not undo the first.
