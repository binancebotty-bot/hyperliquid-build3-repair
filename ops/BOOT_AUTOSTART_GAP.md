# Core+UI pair auto-start: what is covered, and the one known gap

Status: **LOGON-ONLY** (ruling C7-DIR-183, 2026-10-29). Accepted knowingly, not an oversight.

## What runs today

| Path | Covers | Mechanism |
|---|---|---|
| `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Hermes_Build3_Pair_Autostart.vbs` | **Logon** | waits 90 s, then `pythonw.exe ops\boot_start_pair.py` window style 0 - console-less, focus-free |
| Task Scheduler `Hermes_Build3_Pair_Autostart` | *nothing - not registered* | see gap below |

The VBS and any future scheduled task both call the same pinned launcher, `ops/boot_start_pair.py`, which:

- refuses unless the checkout is at `PINNED_SHA a1acc28c0cd9d3a6710783ed08a7b9401475c644`
- refuses if the state dir is unseeded (no `live_config.json`, no `clean_core_runtime_state.json`)
- refuses if an engine already holds the machine-wide global lock or the per-state `instance.lock`
- appends every decision to `%LOCALAPPDATA%\HL_Live_Copy_Service_Core\boot_start_pair.log`
- supports `--check` / `--dry-run`, which starts nothing and prints what it would do and why it would refuse

The VBS is **not** removed (C7-DIR-181 item 3 withdrawn). It is the live logon coverage.

## The gap: boot without an interactive logon

`Hermes_Build3_Pair_Autostart.vbs` lives in the Startup folder, so it fires on **interactive logon only**.
A reboot that never reaches an interactive logon leaves the pair down - the exact shape of the
2026-10-29T23:26Z outage (C7-DIR-154).

Registration of the boot-capable task is blocked, not broken:

- `schtasks /Create` -> `ERROR: Access is denied.`
- cause: this shell is at Medium Mandatory Level (`net session` returns 2, i.e. not elevated); a task in the
  root folder carrying a `BootTrigger` requires administrator rights
- a logon-only XML variant was also refused, by the local focus-guard, on the *invocation* rather than the
  task action (the action is already `pythonw.exe`, console-less)

## The one line that closes the gap

Run **once**, from an **Administrator** prompt (raises UAC - operator-only on this host):

```
schtasks /Create /TN "Hermes_Build3_Pair_Autostart" /XML "C:\tmp\v33_a1acc28\ops\Hermes_Build3_Pair_Autostart.xml" /F
```

The XML declares: `BootTrigger` delay PT2M, `LogonTrigger` delay PT1M for `wigmore`,
action `pythonw.exe "C:\tmp\v33_a1acc28\ops\boot_start_pair.py"`, working dir the checkout,
`Hidden=true`, `RunLevel=LeastPrivilege`, `MultipleInstancesPolicy=IgnoreNew`.

**Verification after running it** - do not accept the registration on the strength of the /Create message:

```
schtasks /Query /TN "Hermes_Build3_Pair_Autostart" /FO LIST /V
schtasks /Query /TN "Hermes_Build3_Pair_Autostart" /XML
```

The `/XML` readback must match `ops\Hermes_Build3_Pair_Autostart.xml`; confirm the stored action is
`pythonw.exe` (never `cmd`/`powershell`/`python.exe`) or every fire opens a console window.

## Reboot test

The Startup-VBS path is exercised as part of the next swap-window reboot test. If the scheduled task has
been registered by then, verify **both** paths, and confirm `boot_start_pair.log` shows exactly one
`boot_start_invoked` event per boot - two would mean both paths fired and the `IgnoreNew` policy did not
apply across the VBS.

## Removing the duplication once the task exists

Only after the task is verified working: disable the Startup VBS, do not delete it. Never leave both live
without checking the log for double starts.
