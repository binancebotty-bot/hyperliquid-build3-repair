#!/usr/bin/env python3
'''Emit the row-specific evidence JSONs for t_7fc73e22 from the raw probe output.'''
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
RAW = os.path.join(ROOT, 'raw')
REG = 'b142cf88d389e791160f691aac3d936852b99975'
TESTED = '2026-10-17T00:12:39Z'
SSOT_SHA = '7468ab5188750617b090b56c3e719d73e91f5b4241f4782382ccac1a22989276'


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def load(name):
    with open(os.path.join(RAW, name), encoding='utf-8') as f:
        return json.load(f)


w = load('ui_wallet_probe.json')
c = load('ui_lcc_card02_probe.json')
w_raw_sha = sha(os.path.join(RAW, 'ui_wallet_probe.json'))
c_raw_sha = sha(os.path.join(RAW, 'ui_lcc_card02_probe.json'))

TOK = w['src_census']['token_counts']
COMMON = {
    'register_ref': 'main:certification/certification_matrix.json',
    'register_commit': REG,
    'tested_commit': REG,
    'tested_at_utc': TESTED,
    'ui_source_blob': '_archive/hl_stage2/HL_Copy_App_SSOT.py',
    'ui_source_sha256_at_register': SSOT_SHA,
    'independence_rule': 'HL_Copy_App_SSOT.py was never imported; oracle = urllib reads of the served JSON API + on-disk engine artefacts',
    'read_only': True,
    'probe': 'EVIDENCE/ui_wallet/scripts/ui_wallet_probe.py',
    'raw': 'EVIDENCE/ui_wallet/raw/ui_wallet_probe.json (sha256 %s)' % w_raw_sha,
}

rows = []

rows.append(dict(COMMON, **{
    'id': 'UI-WALLET-002', 'area': 'WALLET', 'applicability': 'OPEN_DECISION', 'open_decisions': ['OD-13'],
    'result': 'NOT_TESTED',
    'why': 'Requirement itself depends on unruled OD-13 (wallet archival/tombstone semantics); the register states an OPEN_DECISION record cannot be certified until ruled.',
    'executed_checks': [
        {'check': 'UI surface exposes a remove/archive control per wallet',
         'observed': "rendered #liveCopyPanel wallet rows: 15; per-row buttons LIVE=0 CLO=15 OFF=15 ARCHIVE=15 PURGE=0",
         'note': 'Archive control present in the rendered UI.'},
        {'check': 'source implements archive-then-hide + restore',
         'observed': 'remove-wallet handler pops the wallet, forces mode=OFF/enabled=false, writes archived_at and stores it under archived_wallets; set-mode/set-wallet pop it back out of archived_wallets',
         'note': 'archive/restore mechanism exists in source @register commit.'},
        {'check': 'source implements a tombstone for existing owned exposure',
         'observed': 'token "tombstone" occurrences in source = %d' % TOK['tombstone_token'],
         'note': 'No tombstone concept exists; the archival write path never inspects exposure.'},
    ],
    'missing_route': 'A ruling on OD-13 plus a documented, testable expectation for what happens to an archived wallet that still owns exposure.',
}))

rows.append(dict(COMMON, **{
    'id': 'UI-WALLET-006', 'area': 'WALLET', 'applicability': 'OPEN_DECISION', 'open_decisions': ['OD-02'],
    'result': 'NOT_TESTED',
    'why': 'Copy-model semantics (in particular the fixed-mode HOLD) depend on unruled OD-02.',
    'executed_checks': [
        {'check': 'source accepts and persists a per-wallet copy_mode',
         'observed': '_normalise_live_wallet_payload accepts copy_mode in {proportional, fixed} and raises BAD_COPY_MODE otherwise; persisted through /api/wallet-config and /api/live-config/set-wallet',
         'note': 'Persistence path exists.'},
        {'check': 'rendered UI exposes a prop/fixed selector per wallet',
         'observed': 'rendered wallet rows carry a copy_mode select (prop/fixed) + Set control',
         'note': 'UI control present.'},
        {'check': 'fixed is HOLD fail-closed until OD-02 is ruled and the UI says so',
         'observed': 'token "FIXED-MODE HOLD" occurrences in source = %d; token "OD-02" occurrences = %d' % (TOK['fixed_hold_token'], TOK['od02_token']),
         'note': 'No HOLD gate and no in-UI OD-02 disclosure exists; the fixed mode is accepted and acted on immediately.'},
    ],
    'missing_route': 'Ruling on OD-02; then a test of mode persistence -> engine sizing with the HOLD behaviour in force.',
}))

rows.append(dict(COMMON, **{
    'id': 'UI-WALLET-008', 'area': 'WALLET', 'applicability': 'OPEN_DECISION', 'open_decisions': ['OD-02'],
    'result': 'NOT_TESTED',
    'why': 'fixed_notional is only meaningful under the unruled fixed semantics of OD-02.',
    'executed_checks': [
        {'check': 'source enforces fixed_notional >= 0.01',
         'observed': "_normalise_live_wallet_payload: fixed_notional = max(0.01, fnum(payload.get('fixed_notional', base.get('fixed_notional', 10)), 10))",
         'note': 'Lower bound is enforced at the normalisation boundary (source read @register commit).'},
        {'check': 'live served config carries a fixed_notional',
         'observed': '/api/live-config wallets each carry copy_mode=fixed and fixed_notional=12',
         'note': 'Field is live in the served config.'},
        {'check': 'rendered UI exposes a fixed-$ input per wallet',
         'observed': 'rendered wallet rows carry an F input bound to fixed_notional',
         'note': 'Control present.'},
    ],
    'missing_route': 'Ruling on OD-02; then a persistence test proving the clamped value reaches engine sizing.',
}))

rows.append(dict(COMMON, **{
    'id': 'UI-WALLET-014', 'area': 'WALLET', 'applicability': 'OPEN_DECISION', 'open_decisions': ['OD-05'],
    'result': 'NOT_TESTED',
    'why': 'The coexistence rule between the two mode writers is exactly what unruled OD-05 covers.',
    'executed_checks': [
        {'check': 'two independent mode writers exist',
         'observed': 'legacy POST /api/set-wallet-mode and /api/set-all-modes write wallet_gate.json with modes {ON, OFF, CLOSE_ONLY}; POST /api/live-config/set-mode writes live_config.json with modes {LIVE, CLO, OFF}',
         'note': 'Both writers are present and reachable in the same process (source read @register commit).'},
        {'check': 'the two writers are reconciled / cannot contradict',
         'observed': 'token "contradict" occurrences = %d; no cross-file reconciliation call appears in either handler (the only consistency helper invoked is repair_live_config_consistency, which operates inside live_config.json alone)' % TOK['two_writer_guard_token'],
         'note': 'No reconciliation guard exists; the two files can hold independent, contradictory authority.'},
        {'check': 'the UI shows the effective mode',
         'observed': 'token "effective_mode" occurrences in source = %d; rendered DOM search for /effective|current mode/i returned []' % TOK['effective_mode_token'],
         'note': 'No effective-mode display exists.'},
        {'check': 'live served state shows the divergence',
         'observed': "/api/state send_mode=OFF while wallet_gate_on=['not-an-address'] (wallet_gate_on_count=1); /api/live-config wallets all carry mode=LIVE",
         'note': 'The two authority files disagree in the live system right now.'},
    ],
    'missing_route': 'Ruling on OD-05, then a bounded test that drives both writers and asserts a single effective authority.',
}))

rows.append(dict(COMMON, **{
    'id': 'UI-WALLET-015', 'area': 'WALLET', 'applicability': 'OPEN_DECISION', 'open_decisions': ['OD-13'],
    'result': 'NOT_TESTED',
    'why': 'Purge semantics for a wallet that owns exposure is what unruled OD-13 covers.',
    'executed_checks': [
        {'check': 'purge is exposed in the UI',
         'observed': 'rendered #liveCopyPanel PURGE buttons = 0; the legacy page source still emits a PURGE form on action=/api/admin/purge-wallet',
         'note': 'The admin purge form is not rendered on the live-copy surface captured here.'},
        {'check': 'source refuses or makes safe a purge when the wallet owns exposure',
         'observed': 'purge_wallet_everywhere() guards only wallet == USER_WALLET (CANNOT_PURGE_USER_WALLET) and then unconditionally removes the wallet from ui_state.json, wallet_gate.json, live_config.json, engine_truth, baselines, CSVs and derived files; no exposure/position lookup appears in the function body',
         'note': 'No exposure-ownership guard exists; purge proceeds regardless of open exposure.'},
        {'check': 'purge token census',
         'observed': 'endpoint /api/admin/purge-wallet occurrences = %d; purge_wallet_everywhere def = %d; archived_wallets key = %d' % (TOK['endpoint_purge_wallet'], TOK['purge_everywhere_def'], TOK['archived_wallets_key']),
         'note': 'Mechanism present, safety condition absent.'},
    ],
    'missing_route': 'Ruling on OD-13; then a safe-execution test that purges a wallet holding open exposure and asserts the documented outcome.',
}))

rows.append({
    'register_ref': 'main:certification/certification_matrix.json',
    'register_commit': REG,
    'tested_commit': REG,
    'tested_at_utc': TESTED,
    'id': 'UI-LCC-CARD-02',
    'area': 'UI',
    'applicability': 'APPLIES',
    'open_decisions': [],
    'result': 'PARTIAL',
    'why': 'The Unrealized PnL value leg and the source-unavailable leg are verified by executed probes, but two further legs named in the row are not satisfied: Live Exposure is still the manual estimate and is not labelled as such or replaced by exchange truth, and the card does not flag a stale source.',
    'executed_checks': [
        {'check': 'certified card renderer produces an Unrealized PnL cell in a real browser',
         'observed': "rendered DOM (renderCards + helpers extracted verbatim from the register blob, executed in a fresh headless Chromium on the live audit payload): label 'Unrealized PnL' value '$0.66' class 'value lc-pos'; all 7 card labels rendered",
         'verdict': 'PASS'},
        {'check': 'that value equals the exchange truth at snapshot time (independent oracle)',
         'observed': "urllib /api/live-audit-summary exchange_account_snapshot: account_address=0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205 (= MASTER), available=true, unrealized_pnl=0.659395, unrealized_pnl_source='sum(assetPositions.position.unrealizedPnl)', updated_at=2026-10-16T23:12:20Z; rendered value $0.66 == round(0.659395, 2); capture age 9,665 ms",
         'verdict': 'PASS'},
        {'check': 'source unavailable shows n/a / Unavailable rather than 0',
         'observed': "same certified renderer with available=false and unrealized_pnl=null: 'Unrealized PnL' = 'n/a', 'Portfolio Value' = 'Unavailable'",
         'verdict': 'PASS'},
        {'check': 'stale source is flagged',
         'observed': "rendered card shows no age/as-of/stale marker (source-renderCards has no age logic); the fresh master snapshot is ~10 s old and a STALE on-disk app snapshot (account 0xcccc..., fetched 1792154922440, unrealized_pnl 0.0) would render identically",
         'verdict': 'FAIL'},
        {'check': 'Live Exposure is exchange truth or is explicitly labelled as the manual estimate',
         'observed': "rendered label is plain 'Live Exposure' with value $9,390.04 (class lc-amber); the value comes from manual_live_summary.manual_live_exposure_estimate = 9390.043448; no 'estimated'/'manual' text appears in any card label or value",
         'verdict': 'FAIL'},
        {'check': 'API error surfaced',
         'observed': 'not executed against an induced API error; no non-destructive route to force a served-API error was available at capture',
         'verdict': 'NOT_TESTED'},
    ],
    'ui_source_sha256_at_register': SSOT_SHA,
    'probe': 'EVIDENCE/ui_wallet/scripts/ui_lcc_card02_probe.py',
    'raw': 'EVIDENCE/ui_wallet/raw/ui_lcc_card02_probe.json (sha256 %s)' % c_raw_sha,
    'harness_note': 'The :8031 service is NOT running the register-commit build (its Real Account strip renders the labels OPEN POSITIONS P&L (UNREALISED) / LIVE EXPOSURE / PORTFOLIO VALUE (TESTNET), which occur 0 times in the register blob). Rendering the live page would therefore certify the wrong artifact; the probe renders the certified renderer instead.',
    'independence_rule': 'HL_Copy_App_SSOT.py was never imported; oracle = urllib read of the served JSON API + on-disk engine artefacts.',
    'read_only': True,
})

with open(os.path.join(ROOT, 'UI_WALLET_002_006_008_014_015_t_7fc73e22.json'), 'w', encoding='utf-8') as f:
    json.dump({'register_commit': REG, 'tested_at_utc': TESTED, 'rows': rows[:5]}, f, indent=2, ensure_ascii=False)
with open(os.path.join(ROOT, 'UI_LCC_CARD_02_t_7fc73e22.json'), 'w', encoding='utf-8') as f:
    json.dump({'register_commit': REG, 'tested_at_utc': TESTED, 'rows': [rows[5]]}, f, indent=2, ensure_ascii=False)
print('rows emitted: %d' % len(rows))
print('wallet probe sha256 %s' % w_raw_sha)
print('lcc probe sha256 %s' % c_raw_sha)
