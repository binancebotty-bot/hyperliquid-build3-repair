# Lane engine fail-closed notes

## Change

`ConfigManager._send_mode_of` now resolves only `global_controls.send_mode`. `OFF`, `ON`, `CLOSE`, `CLOSE ONLY`, and `CLO` (case-insensitive, with `_` and `-` accepted) retain their existing meanings. Missing, blank, null, and invalid values return `OFF`; `auto_send_enabled` no longer arms sending. The UI resolver was left unchanged because it already fails closed.

Added `test_send_mode_resolver_parity.py` with 31 pytest parameter cases and a `main()` that runs those same cases as a script. Missing, blank, null, whitespace, and invalid modes each cover `auto_send_enabled` absent, `True`, `False`, and `"true"`; valid modes are also covered, including both `_` and `-` separators. The invalid `BANANA` case remains OFF regardless of the auto-send setting.

## RED/GREEN evidence

- **RED on original `0cc80b80` source (static expected result):** the original resolver falls through to `auto_send_enabled` for absent/blank modes. The parity test therefore has 10 expected failures: each of the five missing/blank forms combined with `True` and `"true"` resolves to engine `ON` while the UI resolves to `OFF`. `BANANA` already fails closed in the original code.
- **GREEN after the fix (static expected result):** the resolver now returns `OFF` for every unrecognized or empty normalized value and retains the valid-value branches, so all 31 cases are expected to pass.
- **Execution status:** neither RED nor GREEN was executable in this environment. The requested `C:\Users\wigmore\AppData\Local\Programs\Python\Python311\python.exe` path returned Access Denied when checked/launched. `py -3.11 -m pytest -q test_send_mode_resolver_parity.py` reported `No installed Python found!`; the `python` command resolves to an inaccessible Windows system shim. No test pass is claimed. `git diff --check` completed successfully.
- The original-source execution via `git show 0cc80b80:_archive/hl_stage2/HL_Live_Copy_Service_Core.py` copied to a temporary test directory was not attempted because no Python 3.11 interpreter was available.

## Follow-up failures and corrections

The supplied run and fixture audit identified these follow-up issues:

- `test_core_run4_fixes.py`: the `config(send=True)` helper enabled only the legacy `auto_send_enabled` flag. With the fail-closed resolver, its intended send scenarios were OFF, explaining the empty order calls and missing recovery-fill ledger update. The helper now also sets `global_controls.send_mode` to `ON` when sending is enabled, while an explicit mode such as `CLOSE` overrides that default.
- `test_core_scope_sweep_resilience.py`: its send-enabled config statement had been dedented outside `main()`. It is now back at the function's indentation level.
- `test_send_mode_resolver_parity.py`: the resolver belongs to `ConfigManager`; both the pytest test and script entry point now call `ConfigManager._send_mode_of`.
- `test_core_run5_converge.py`: its send-enabled config helper also relied on the legacy flag, so it now supplies `ON` by default while allowing explicit controls to override it.

No assertions were removed or weakened, and resolver semantics were not changed in this follow-up. The supplied test output predates these corrections; execution remains unavailable here, so no post-fix pass is claimed. `test_core_engine_gaps.py` remains the known environment failure identified in the task.

## Test files touched and why

- `test_send_mode_resolver_parity.py` — new engine/UI parity matrix and script entry point.
- `test_core_catchup_window_rows.py` — explicitly arms the send path with `send_mode=ON` in its auto-send fixture.
- `test_core_dex_scope_and_ui_truth.py` — explicitly arms its engine send fixture with `send_mode=ON`.
- `test_core_disk_full.py` — explicitly arms the engine in the disk-full send-path fixture.
- `test_core_dust_rules.py` — explicitly arms the order fixture.
- `test_core_engine_gaps.py` — keeps the auto-enabled daily-loss scenario armed with an explicit mode.
- `test_core_liq_isolated.py` — explicitly arms the gateway behavior fixture.
- `test_core_liq_parity.py` — explicitly arms the default auto-enabled fixture while allowing supplied controls to override it.
- `test_core_local_first.py` — explicitly arms its live-send fixture.
- `test_core_missed_entry_rule.py` — maps its on/off send fixture to explicit `ON`/`OFF` and arms the other send-path fixture explicitly.
- `test_core_network_and_global_controls.py` — explicitly configures send mode in auto-armed fixtures.
- `test_core_no_silent_fill.py` — explicitly arms its send fixture.
- `test_core_outage_defer.py` — explicitly arms its send fixture.
- `test_core_outage_replay.py` — explicitly arms its send fixture.
- `test_core_run4_fixes.py` — defaults enabled-send scenarios to `ON`, with explicit controls taking precedence so its close-only case remains `CLOSE`.
- `test_core_run3_fixes.py` — explicitly arms helper/direct send fixtures when enabled.
- `test_core_run5_converge.py` — explicitly arms its send helper when enabled.
- `test_core_scope_sweep_resilience.py` — explicitly arms its send fixture.
- `test_core_sender_key.py` — explicitly arms its sender fixture.
- `test_core_switch_states.py` — updates the former legacy-fallback case to preserve the OFF/ON switch assertion using explicit modes; no assertion was removed or weakened.
- `test_hotpath_replay_bench.py` — explicitly arms its send fixture.
- `test_j2_local_rejects.py` — explicitly arms its send fixture.
- `test_t1a_cloid_pending_row.py` — explicitly arms its send fixture.

No other engine behavior was changed. No commit was created.
