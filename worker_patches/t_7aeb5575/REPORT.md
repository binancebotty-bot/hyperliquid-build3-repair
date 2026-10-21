Fill-trace lock-scope repair report

Card: t_7aeb5575
Base: b44e78d2989a5707de34220f91a58bd48d446374
Branch: wt/t_7aeb5575
HEAD: 11fc8f6cd154791115afaf8ac27007cb2d1c3be6

Changed files
- _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- _archive/hl_stage2/test_fill_trace_lock_scope.py

Verification
- RED control: restored Core to b44e78d2 and ran test_fill_trace_lock_scope.py: T1=True, T2=4016.0 ms (FAIL; rotation held producer), T3=True.
- GREEN: ran test_fill_trace_lock_scope.py on HEAD: T1=True, T2=0.0 ms, T3=True.
- Existing rotation check: RESULT::trace_rotation_PASS.
- Core py_compile: PASS.
- git diff --check: PASS.

Lock-scope change
- JSON serialization is outside the producer lock.
- Producers append to one persistent handle; the producer lock covers only handle/state access and the short write/flush.
- Rotation takes a separate rotation lock, swaps the active handle under the producer lock, closes/rotates/opens outside it, then flushes records buffered during rotation in order.
- No new threads, pollers, or gates.

Measured T2 latency
0.0 ms in the green run (threshold: <200 ms).

Known boundary
The persistent handle is intentionally kept open for the Core lifetime, so ad-hoc Windows tests must close the handle before deleting its temporary directory. The new acceptance test does this explicitly.
