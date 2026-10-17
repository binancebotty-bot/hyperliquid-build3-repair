import json

C = '43731b4f1f19a56e835032dabf608a550f925717'
P1 = 'certification/results/ENG_INV_rowbound_probe_batch1.py'
P2 = 'certification/results/ENG_INV_rowbound_probe2_batch1.py'
R1 = 'certification/results/ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json'
R3 = 'certification/results/ENG-INV-03-05_43731b4f.json'
R6 = 'certification/results/ENG-INV-06-09_43731b4.json'
R7 = 'certification/results/ENG-INV-07-09_runtime_43731b4f1f19.json'
R10 = 'certification/results/ENG-INV-10-14_43731b4f.json'

rows = [
 ('ENG-INV-01','PASS',P1,"Re-derived: 0 process-spawn constructs (subprocess/Popen/os.system/fork/multiprocessing) across the five product modules at the tested commit; hits exist only in test_*.py. Register control inv01_add_subprocess flips the predicate to FAIL, so non-vacuous. CAVEAT: static census only; the runtime process COUNT demanded by execution_proof is absent."),
 ('ENG-INV-02','FAIL',R1,"Product genuinely misses it. Invariant is exactly one physical production .order() call site, but the tested tree has TWO reachable production sites: Core.py:2703 and HL_Live_Copy_Service.py:1036 (send_hyperliquid_order builds a real Exchange client against LIVE_ORDER_ENDPOINT, reachable from main() via --send-one-intent --confirm-send). The census hard-scopes itself to the Core file ('not the UI/dry-run service') and prints 'Physical .order() calls: [2703] (total all: 2)' - it SAW the second site and excluded it by scope. A scope that excludes the counter-example cannot prove uniqueness."),
 ('ENG-INV-03','FAIL',R3,"Evidence cannot fail: census reports 0 unexpected third-party imports against a hardcoded allowlist (requests/websocket/eth_account/hyperliquid all found AND allowed). No Architect approval record is cited, and this artifact has no negative_tests key at all, so the predicate has no mutation control. 'Without Architect approval' is untested."),
 ('ENG-INV-04','FAIL',R3,"Predicate is blind to the mechanism in use: persistent_stores=0 was derived from sqlite3/shelve/dbm constructors only, while the engine persists trading state as JSON via atomic_write_json to MANUAL_LIVE_POSITIONS_FILE (written Core.py:6806/6812, read 1033/5718/5763). '0 persistent stores' is false as stated, and the row carries no negative test."),
 ('ENG-INV-05','PASS',P1,"Re-derived independently: grep for build4/build_4 across all five product modules returns 0 hits. The predicate is row-specific and capable of failing (any Build-4 import trips it). NOTE: the shipped artifact ran no mutation control for this row; the negative is supplied by my own committed re-derivation."),
 ('ENG-INV-06','FAIL',R6,"The row PASSes on a bundle that includes single_order_call_site: true - the same claim disproved for ENG-INV-02 (second production site at HL_Live_Copy_Service.py:1036). 'No new engine/runtime around Build 3' is asserted on a premise that is wrong on the committed bytes."),
 ('ENG-INV-07','PASS',R7,"Row-bound and non-vacuous: sleeve_id() takes exactly (wallet, coin) and returns normalise_wallet(wallet)::canonical_coin_key(coin); ManualLedger stores by_wallet[wallet][coin]; global leader dicts = []. Register mutation INV-07_remove_wallet_from_sleeve_id flips to FAIL; runtime wallet-A/wallet-B isolation self-test passes. Upgrade from register BLOCKED: the row asserts state isolation, not a physical fill."),
 ('ENG-INV-08','PASS',P2,"Direct runtime probe: list_perp_dexes(fixture) returns ['', 'XYZ'] (default + builder scope); fetcher failure -> DEX_ENUM_UNAVAILABLE; with the default scope readable and the HIP-3 scope raising, master_account_net(BTC, dexes=['','XYZ']) returns ok=False status=SCOPE_UNAVAILABLE - a missing required scope genuinely fails closed. Failing case constructed by me, so non-vacuous."),
 ('ENG-INV-09','PASS',R7,"Verified on committed bytes: account_net_actual() reads MASTER exchange truth and returns ACCOUNT_NET_TRUTH_UNAVAILABLE (fail closed) instead of falling back to local dry-run state; a mismatch never auto-corrects the ledger. Register mutation INV-09_manual_positions_authoritative flips to FAIL. CAVEAT: manual_live_positions.json IS read as a pre-emission guard (_fresh_persisted_coin_net) and written - bookkeeping, not order authority."),
 ('ENG-INV-10','PASS',P2,"Direct runtime probe: resolve_settlement(intent, fills=[], net unavailable, reject_evidence={ack:True}) returns SETTLEMENT_UNKNOWN, while the same intent with an independent MASTER fill returns SETTLED_FULL. A discriminating pair, so 'ack is not settlement' cannot pass by construction."),
 ('ENG-INV-11','PASS',P1,"Direct runtime probe against exchange_truth: identity_ok(distinct)=True, identity_ok(same)=False, identity_ok('')=False; runtime_master_identity({}) ok=False, same-address -> IDENTITY_INVALID, distinct -> ok=True. Engine enforces it at HL_Live_Copy_Service.py:2481 before master_account_net, failing closed. The register FAIL ('No MASTER_ADDRESS constant found') is a name-lookup miss: wiring is runtime_master_identity() keyed on HL_LIVE_HL_ACCOUNT_ADDRESS."),
 ('ENG-INV-12','PASS',P2,"Probe: compute_convergence_order exists; flatten-all/close-all pattern count = 0 across product modules; convergence_order_for_coin, convergence_notional_for_fill and apply_signed_delta_to_position present. Register control inv12_flatten_all flips to FAIL, so non-vacuous."),
 ('ENG-INV-13','FAIL',R10,"Evidence cannot fail: the artifact's own control inv13_order_in_restart expected FAIL, got PASS, non_vacuous=false, yet the row was still recorded passed=true while the artifact summary sets all_non_vacuous=false. The product does carry lineage gating (_lineage_checkpoint_valid -> LINEAGE_CHECKPOINT_INVALID), but ZERO NEW TRADE AUTHORITY is not established by a vacuous predicate. FAIL as unproven, not as a demonstrated code defect."),
 ('ENG-INV-14','FAIL',P1,"Product genuinely misses it: no approval mechanism exists. resolve_networks({'HL_FOLLOWER_NETWORK':'mainnet'}) switches the follower to mainnet with NO approval token or gate - approval is pure env configuration, and exchange_truth.py has zero occurrences of approval/richard. Default follower=testnet and the endpoint-mismatch guard both hold, but neither is the required Richard-approval gate."),
 ('ENG-SEM-B1','PASS',R1,"Row-bound with a real control: SEM-B1 asserts intent.fill.leader_fill_id=b1_fill_1 (authority derives from a concrete leader event) plus copy_size=0.0002 derived from that event; register mutation sem_b1_remove_fill_reference flips to FAIL. Lineage gating (_lineage_checkpoint_valid) further restricts authority to the frozen baseline plus post-baseline events."),
]

out = {
 'batch': 'CERT 1/53 ENG-INV-01..ENG-SEM-B1',
 'task_id': 't_e4d49ba2',
 'register_of_record': 'origin/cert/local-main-b142cf8:certification/certification_matrix.json',
 'tested_commit': C,
 'standard': 'row-bound; shared/vacuous predicates rejected as FAIL',
 'rows': [{'row_id': a, 'verdict': b, 'evidence_ref': c, 'tested_commit': C, 'why': d} for a, b, c, d in rows],
}

p = 'certification/results/ENG_INV_01_14_SEM_B1_verdicts_t_e4d49ba2.json'
with open(p, 'w', encoding='utf-8', newline='\n') as fh:
    json.dump(out, fh, indent=1)
print('wrote', p, len(out['rows']))
print('PASS', sum(1 for r in out['rows'] if r['verdict'] == 'PASS'), 'FAIL', sum(1 for r in out['rows'] if r['verdict'] == 'FAIL'))
