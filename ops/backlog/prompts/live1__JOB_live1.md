PROCEDURE DRAFT JOB. SHELL NOTE: Windows PowerShell 5.1, no && (use ;), absolute paths, file tools, python -I script.py. Free model, <= 25 tool calls, 25 min cap, never print > 6 KB at once. No engine runs, no network, no keys/.env, never push, never write inside hl_stage2. For each row below (provable only on the Hyperliquid TESTNET with the running engine), write a numbered, minimal testnet procedure: preconditions, exact actions (UI control or API), what to observe (audit CSV column / UI cell / exchange query), PASS/FAIL criterion, and any risk. Testnet only, never mainnet. Write C:\Users\wigmore\trading_stack\_oc_jobs\proof_audit2\LIVE_PROC_1.md. Rows:
TN-CAMP-06: Assert bound breach/unexpected order/identity mismatch/leak halts sending immediately
TN-CAMP-07: Assert interpreter/SDK version/commit/config hashes recorded with evidence
TN-CAMP-08: Assert each scenario class passes only with exchange-parity evidence; FAILs kept permanently
TN-CAMP-09: Assert HIP-3 markets listed and verified on mainnet before mainnet certification
TN-T3: Assert per-request origin validation immediately before network I/O on testnet
ENG-VAL-02: Verify that parse_api_leader_fill and parse_leader_fill_row explicitly check for NaN/infinity values and reject them at ingestion (return None) rather than treating them as 0.0 via fnum()
ENG-VAL-03: Test for a malformed margin tier or meta row in exchange data: validate that it's rejected (fail closed) and never silently skipped
ENG-VAL-04: Test that maintenance margin is calculated from exchange marginTables (not a leverage-derived approximation) by verifying the specific code path that accesses exchange margin data
