# What this fork changes

A fork of [andreadegiovine/homeassistant-stellantis-vehicles](https://github.com/andreadegiovine/homeassistant-stellantis-vehicles)
that makes the vehicle's four preconditioning programs writable. It is not
proposed upstream, it is maintained here.

Read [docs/preconditioning.md](./docs/preconditioning.md) for what the feature
does and what was measured on a real car.

## Additions

| commit | what |
|---|---|
| Add writable preconditioning programs | a time, text and switch entity per slot, the `set_preconditioning_program` service, `services.yaml` |
| Let HACS install this fork from the branch | drops `zip_release` from `hacs.json`, since a fork has no release assets |
| Add a button to clear all preconditioning programs | resets all four slots, doubles as cancel during a run |
| Clear the preconditioning programs automatically | a switch, on by default, clearing after a run ends or when the car starts moving |
| Write several program slots in one command | batch writes, and the override that stops two quick writes racing each other |
| Document what the vehicle actually does | the measured behaviour |

## Files this fork touches

Changed, so upstream edits to these can conflict:

- `README.md`
- `custom_components/stellantis_vehicles/__init__.py`
- `custom_components/stellantis_vehicles/base.py`
- `custom_components/stellantis_vehicles/button.py`
- `custom_components/stellantis_vehicles/const.py`
- `custom_components/stellantis_vehicles/switch.py`
- `custom_components/stellantis_vehicles/text.py`
- `custom_components/stellantis_vehicles/time.py`
- `custom_components/stellantis_vehicles/translations/en.json`
- `custom_components/stellantis_vehicles/utils.py`
- `hacs.json`

Added, so they never conflict:

- `FORK.md`
- `custom_components/stellantis_vehicles/services.py`
- `custom_components/stellantis_vehicles/services.yaml`
- `docs/preconditioning.md`
- `tests/run_all.sh`
- `tests/stub.py`
- `tests/test_auto_clear.py`
- `tests/test_batch_write.py`
- `tests/test_clear_programs.py`
- `tests/test_program_entities.py`
- `tests/test_programs_payload.py`
- `tests/test_service.py`
- `tools/sync-upstream.sh`

The heaviest conflict risk is `custom_components/stellantis_vehicles/base.py`,
where the fork adds coordinator methods and one block inside
`after_async_update_data`, and `translations/en.json`, where it adds keys inside
existing sections. `README.md` is kept to five lines on purpose, with the detail
in `docs/`, because upstream edits its README often. `info.md` is deliberately
left identical to upstream: `hacs.json` sets `render_readme`, so HACS shows
`README.md` and `info.md` is dead weight that would only double the conflicts.

## Syncing with upstream

```
./tools/sync-upstream.sh --dry-run   # what is coming, and whether it overlaps
./tools/sync-upstream.sh             # fetch, merge, run the checks
git push
```

Merge rather than rebase. The fork is several commits deep, and a merge resolves
each conflict once where a rebase asks again for every commit. `git rerere` is
enabled in this clone, so a conflict resolved once resolves itself next time.
If a merge goes badly, `git merge --abort` puts everything back.

After pushing, Redownload in HACS and restart Home Assistant.

## Checking it still works

`./tests/run_all.sh` runs six offline suites covering the payload, the entities,
the service, the clear button, the automatic clearing and the batch write. They
need no Home Assistant install: `tests/stub.py` fabricates the modules the code
imports. Run them after every merge.

They do not talk to a car. These need a vehicle and are worth repeating after a
merge that touches the command path. All but the last were confirmed on
24 August 2026:

1. the entities read back the programs the car holds, confirmed
2. writing a slot is accepted, `command_status` reaching Complete, confirmed
3. the written program appears in the entities within a poll or two, confirmed
4. a two slot batch write leaves both slots set, confirmed. Two separate commands
   a second apart do not, which is why the batch exists
5. the clear button empties all four, confirmed
6. driving off clears the slots by itself, not yet seen

## Known unknowns

- how long the vehicle refuses a manual start after a session ends. Seven
  minutes was not enough once
- whether the vehicle limits how many programs run between drives. Six ran, the
  seventh did nothing, and after a short drive the next two ran
- everything measured comes from one vehicle, an electric Opel

Answered since: `asap: "deactivate"` does stop a running session, so the refusal
on program writes during a session is doing real work.
