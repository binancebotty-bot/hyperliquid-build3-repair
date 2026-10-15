PROCEDURE DRAFT JOB. SHELL NOTE: Windows PowerShell 5.1, no && (use ;), absolute paths, file tools, python -I script.py. Free model, <= 25 tool calls, 25 min cap, never print > 6 KB at once. No engine runs, no network, no keys/.env, never push, never write inside hl_stage2. For each row below (provable only on the Hyperliquid TESTNET with the running engine), write a numbered, minimal testnet procedure: preconditions, exact actions (UI control or API), what to observe (audit CSV column / UI cell / exchange query), PASS/FAIL criterion, and any risk. Testnet only, never mainnet. Write C:\Users\wigmore\trading_stack\_oc_jobs\proof_audit2\LIVE_PROC_0.md. Rows:
ENG-INV-01: Assert at runtime that exactly one engine process holds the run lease and that no second entry point starts a competing loop.
ENG-002: Assert sleeve = leader position x copy scale; order = desired - actual - in_flight converges on testnet for open, add, partial reduce, close
UI-WALLET-010: UI status display requires live viewing to validate; not provable via offline tests
UI-WALLET-011: Engine restart persistence requires live observation; not provable via offline tests
LIFE-001: Assert one start command creates exactly one engine process and second start does not create duplicate sender
NET-007: Assert certification follows real active mainnet leader wallets and sends only to testnet follower; no synthetic leader used
TN-CAMP-04: Assert ambiguous submission halts campaign until exchange truth resolves
TN-CAMP-05: Assert cleanup only touches campaign-created cloid/oid on testnet
