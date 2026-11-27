# Lane results: core invariant test evidence

Branch: `lane-inv/core-invariant-evidence`

Base: `origin/main`

Checked-out commit during runs: `eff73dfac67c8557d7f7b8482e7872eddf43d1f3`

## Invariant evidence

`PASS`/`FAIL` below describes the named check as it ran. Fixture tests are unit-level evidence only; they do not establish a live/testnet certification result. The G2 and G3 fixtures import the archived `HL_Live_Copy_Service.py` path, so their passes must not be read as a certification of the Core runtime.

| Invariant | Test name and result | File path | Notes |
|---|---|---|---|
| ENG-INV-01 — One process | **MISSING** | — | No executable test for the one-process invariant found. |
| ENG-INV-02 — Exactly one physical production `.order()` call site | `test_only_core_has_the_exchange_order_callsite` — **PASS** (1 passed) | `_archive/hl_stage2/test_single_exchange_order_callsite.py` | AST census found one call site owned by `HL_Live_Copy_Service_Core.py`. |
| ENG-INV-03 — No new dependency without Architect approval | **MISSING** | — | Existing certification result files are not a runnable test in this checkout. |
| ENG-INV-04 — No new authoritative persistent trading-state store | **MISSING** | — | Existing certification result files are not a runnable test in this checkout. |
| ENG-INV-05 — No Build 4 control-plane/platform import | **MISSING** | — | Existing certification result files are not a runnable test in this checkout. |
| ENG-INV-06 — No new engine/runtime around Build 3 | **MISSING** | — | The order-site test does not test process/runtime count. |
| ENG-INV-07 — Leader mutable state isolated by `(wallet, coin)` | `t9: same-coin multi-wallet sleeves aggregate to one account-net target` — **PASS** (targeted assertion); containing G2 script **FAIL** overall (39 passed, 1 failed) | `_archive/hl_stage2/test_g2_copy_correctness.py` | Two-wallet aggregate assertion passed. The unrelated failing sender-payload check is recorded below. This is partial unit coverage, not a full isolation proof. |
| ENG-INV-08 — Startup/recovery truth includes all relevant perp DEX scopes; missing scope fails closed | G3 checks `HIP-3/builder DEX scope aggregates into account-net`, `unavailable required scope FAILS CLOSED`, `incomplete DEX enumeration FAILS CLOSED` — **PASS** (within 48 passed, 0 failed) | `_archive/hl_stage2/test_g3_exchange_truth.py` | Core-specific `test_core_dex_scope_and_ui_truth.py` could not start: `ModuleNotFoundError: No module named 'requests'`. |
| ENG-INV-09 — Exchange truth outranks local replay; manual follower-position file is not authoritative | G3 checks `MASTER exchange truth supplies ACTUAL` and `wallet-local provider never consulted when MASTER truth is configured` — **PASS** | `_archive/hl_stage2/test_g3_exchange_truth.py` | Offline fixture evidence only. |
| ENG-INV-10 — API acknowledgement is not settlement; sends need independent MASTER verification | G3 checks reservation before acknowledgement, MASTER fills/position settlement, partial/unknown evidence remains blocking — **PASS** | `_archive/hl_stage2/test_g3_exchange_truth.py` | Offline fixture evidence only. |
| ENG-INV-11 — MASTER and signer are distinct; account truth is read from MASTER | G3 checks signer-equals-MASTER rejection and distinct-identity acceptance — **PASS** | `_archive/hl_stage2/test_g3_exchange_truth.py` | Core-specific `test_core_sender_key.py` could not start: `ModuleNotFoundError: No module named 'requests'`. |
| ENG-INV-12 — Convergence moves actual toward desired and preserves unrelated inventory | G3 checks `copied sleeve converges while unrelated inventory is preserved` and `unattributed inventory is excluded from sleeve ACTUAL` — **PASS** | `_archive/hl_stage2/test_g3_exchange_truth.py` | Core-specific `test_core_run5_converge.py` could not start: `ModuleNotFoundError: No module named 'requests'`. |
| ENG-INV-13 — Restart/recovery snapshots establish truth for verification only and create zero trade authority | G3 checks `non-zero snapshot yields ZERO desired exposure` and `snapshot does not mutate event lineage` — **PASS** | `_archive/hl_stage2/test_g3_exchange_truth.py` | Offline fixture evidence only. |
| ENG-INV-14 — No mainnet/LIVE activation without explicit Richard approval | **MISSING** | — | No executable test for explicit activation approval found. |

Historical certification JSON files were not counted as current test runs: their `tested_commit` values do not match the checkout commit above. No test or invariant was altered.

## Commands and exact results

Python executable used: `C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe`.

| Command | Result |
|---|---|
| `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe' _archive/hl_stage2/test_g3_exchange_truth.py` | **48 passed, 0 failed**; all checks used offline injected fixtures. |
| `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe' _archive/hl_stage2/test_single_exchange_order_callsite.py` | **1 passed, 0 failed**. |
| `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe' _archive/hl_stage2/test_g2_copy_correctness.py` | **39 passed, 1 failed** per run; invoked 3 times while isolating the failing assertion (cumulative 117 passed, 3 failed). Failure: expected planner `FLATTEN SELL` at sender boundary; observed in-flight `BUY`, `reduce_only=False`. Assertion left unchanged. |
| `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe' _archive/hl_stage2/test_core_dex_scope_and_ui_truth.py` | **Blocked before checks**: `ModuleNotFoundError: No module named 'requests'`. |
| `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe' _archive/hl_stage2/test_core_sender_key.py` | **Blocked before checks**: `ModuleNotFoundError: No module named 'requests'`. |
| `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe' _archive/hl_stage2/test_core_run5_converge.py` | **Blocked before checks**: `ModuleNotFoundError: No module named 'requests'`. |

Distinct successful/failed assertions from one run of each runnable test: **88 passed, 1 failed**. Across all actual invocations including the two diagnostic G2 reruns: **166 passed, 3 failed**. Three Core-specific scripts were blocked before any checks. No live/testnet orders were sent.

## Tooling and blockers

- The `graphify` launcher (`graphify --help`) could not start because its wrapper invokes `python`, which is not installed on PATH. The checked-in `graphify-out/graph.json` was queried and explained with Node before opening raw source files.
- `uv` found Python 3.14.7, allowing the archived scripts to run, but the Core-specific scripts require the missing `requests` package. Network access was not used to install dependencies.
- No test was found for ENG-INV-01, 03, 04, 05, 06, or 14. These remain **MISSING**, rather than inferred from source or historical result artifacts.
- Commit/push blocker: `git add -- LANE_RESULTS.md` failed with `fatal: Unable to create '.git/index.lock': Permission denied`. The workspace grants read access to `.git`, so no commit can be created and the requested push cannot be attempted from this clone.
