import json
from pathlib import Path

raw = Path('raw')

def load_text(p):
    return (raw / p).read_text(encoding='utf-8', errors='replace')

ev = {
 'batch': 'CERT 23/53',
 'task_id': 't_e3846ecf',
 'rows': 'CTRL-I22 CTRL-I23 CTRL-GATE0 CTRL-BIND CTRL-HWM CTRL-EVID CTRL-ESC B4-I01 B4-I02 B4-I03 B4-I04 B4-I05 B4-I06 B4-I07 B4-I08'.split(),
 'tested_commit': 'b142cf88d389e791160f691aac3d936852b99975',
 'engine_blob': '_archive/hl_stage2/HL_Live_Copy_Service.py',
 'engine_blob_sha256': 'e2f04fa826958c73169bae2490a6ebb3ebfd09d9aecda513ef0d7bd8a10ec2c6',
 'engine_blob_identical_at': ['fa9d9f55fffa74cb6888c471d97d1655267999b6', 'b142cf88d389e791160f691aac3d936852b99975'],
 'control_mailbox_head': '97d8e350b0593ffb649d5ab7bfef5aea72edf0f2',
 'envelope_count': 102,
 'python': '3.11.9 C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe',
 'prior_evidence_rejected': {
   'control_file': 'certification/results/CONTROL_fa9d9f55ff.json',
   'regression_file': 'certification/results/REGRESSION_fa9d9f55ff.json',
   'reason': 'Control rows carry a 24-check shared sweep of which 14 checks are byte-identical boilerplate across every row; 3 of the row-named checks (KEY_ENVELOPES_HAVE_TASK_ID, EVERY_HANDOFF_HAS_COMMIT_SHA, EVERY_HANDOFF_HAS_FILES_CHANGED) would pass for any row and are contradicted by direct measurement. Regression rows carry exactly 1 auto-named check per row with an EMPTY detail string - no assertion, cannot fail. CTRL-BIND has no row in the control file at all.',
   'regression_sweep_shape': '138 rows, 138 single-check rows, 32 checks with empty detail',
   'named_build4_tests_present_at_tested_commit': 0,
   'named_build4_tests_checked': ['test_new_events_only_authority.py', 'test_ws_first_acceptance.py', 'test_ws_first_execution.py', 'test_feed_manager.py', 'test_live_event_lifecycle_exactly_once.py', 'test_handover_lease_directory_contract.py', 'test_idle_no_post_baseline_event.py', 'test_unified_account_truth.py', 'test_live_fill_truth_429_fail_closed.py'],
 },
 'probes': {
   'engine_behaviour': json.loads(load_text('probe_engine.json')),
   'b4_static_and_sleeve': json.loads(load_text('probe_b4b.json')),
   'authority_and_i05': json.loads(load_text('probe_final.json')),
   'control_mailbox': load_text('probe_ctrl.txt'),
 },
 'reproduce': {
   'engine': 'python3.11 probe_engine.py',
   'b4b': 'python3.11 probe_b4b.py',
   'final': 'python3.11 probe_final.py',
   'ctrl': 'python3.11 probe_ctrl.py',
   'note': 'Probes read ./engine.py and ./env/control_mailbox/inbox/*.json. Reproduce from this repo: (1) git show b142cf88:_archive/hl_stage2/HL_Live_Copy_Service.py > engine.py (sha256 must equal engine_blob_sha256); (2) git archive origin/control-mailbox control_mailbox/inbox CONTROL_STATE.json | tar -x -C env; (3) git show b142cf88:CONTROL_STATE.json > CONTROL_STATE.json and copy the project CONTROL_CONTRACT.json in; (4) run each probe. Raw outputs of this run are committed as CERT23_t_e3846ecf_raw_*',
 },
}
Path('CERT23_t_e3846ecf_evidence.json').write_text(json.dumps(ev, indent=1), encoding='utf-8')
print('written bytes', len(json.dumps(ev)))
