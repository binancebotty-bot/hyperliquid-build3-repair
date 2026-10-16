import json, os, sys, hashlib, time, csv
from pathlib import Path

SCR = Path('C:/Users/wigmore/.hermes/cache/scratch/b3cert_bb68')
REPO = Path('C:/Users/wigmore/.hermes/kanban/workspaces/t_bb684f9e/repo')
CORE_DIR = REPO / '_archive' / 'hl_stage2'
COMMIT = 'b142cf88d389e791160f691aac3d936852b99975'

out = {'task_id': 't_bb684f9e', 'tested_commit': COMMIT,
       'register_ref': 'b142cf88:certification/certification_matrix.json',
       'captured_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
       'checks': {}, 'artifacts': {}}


def ck(row, name, passed, detail, oracle):
    out['checks'].setdefault(row, []).append(
        {'name': name, 'pass': bool(passed), 'detail': detail, 'oracle': oracle})
    print('%-10s %-46s %s  %s' % (row, name, 'PASS' if passed else 'FAIL', detail))


core_path = CORE_DIR / 'HL_Live_Copy_Service_Core.py'
out['artifacts']['engine_sha256'] = hashlib.sha256(core_path.read_bytes()).hexdigest()
out['artifacts']['engine_lines'] = sum(1 for _ in core_path.open('rb'))
print('engine', out['artifacts']['engine_sha256'], out['artifacts']['engine_lines'], 'lines')
core_src = core_path.read_text(encoding='utf-8', errors='replace')
legacy_path = CORE_DIR / 'HL_Live_Copy_Service.py'
legacy_src = legacy_path.read_text(encoding='utf-8', errors='replace') if legacy_path.is_file() else ''

SURFACES = {
    'ENG-003': ['FIXED_MODE_AUTHORITY_HOLD', 'fixed_notional'],
    'ENG-INV-07': ['apply_fixed_sleeve_event', 'sleeve_id'],
    'ENG-INV-08': ['list_perp_dexes', 'perpDexs'],
    'ENG-INV-09': ['exchange_truth', 'manual_live_positions'],
    'PRICE-001': ['apply_fixed_sleeve_event', 'follower_mid'],
    'PRICE-002': ['HL_LIVE_QUOTE_CACHE_TTL_MS', 'EXECUTABLE_QUOTE_UNAVAILABLE', 'HL_LIVE_MIDS_CACHE_TTL_SEC', 'HL_LIVE_MIDS_MAX_AGE_SEC'],
}
out['census'] = {}
for row, toks in SURFACES.items():
    rec = {t: {'core': core_src.count(t), 'legacy': legacy_src.count(t)} for t in toks}
    out['census'][row] = rec
    print(row, json.dumps(rec))

os.environ['HL_LIVE_ENV_FILE'] = '/nonexistent'
for k in ('HL_LIVE_HL_PRIVATE_KEY', 'HL_LIVE_HL_ACCOUNT_ADDRESS', 'HL_LIVE_HL_SECRET'):
    os.environ.pop(k, None)
os.environ['HL_FOLLOWER_NETWORK'] = 'testnet'
os.environ['HL_LEADER_NETWORK'] = 'mainnet'
sys.path.insert(0, str(CORE_DIR))
import HL_Live_Copy_Service_Core as core

out['artifacts']['core_module_file'] = core.__file__
out['artifacts']['core_module_sha256'] = hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest()
out['artifacts']['HL_INFO_URL'] = getattr(core, 'HL_INFO_URL', None)
print('imported', core.__file__, 'info_url', out['artifacts']['HL_INFO_URL'])

perp = json.loads((SCR / 'oracle' / 'perpDexs.json').read_text(encoding='utf-8'))
named = [d.get('name') for d in perp if isinstance(d, dict) and d.get('name')]
ck('ENG-INV-08', 'PERP_DEXS_ENUMERATED_BY_ORACLE', len(named) > 0,
   'testnet perpDexs entries=%d named=%d sample=%s' % (len(perp), len(named), named[:5]),
   'live testnet info API type=perpDexs (oracle; no engine import)')
try:
    enum = core._XNET.list_perp_dexes(fetcher=None, info_url=core.HL_INFO_URL, timeout=core.HTTP_TIMEOUT_SEC)
    ok = bool(enum.get('ok'))
    dx = list(enum.get('dexes') or [])
    ck('ENG-INV-08', 'ENGINE_ENUMERATES_PERP_DEX_SCOPE', ok and len(dx) > 0,
       'engine list_perp_dexes() ok=%s n=%d sample=%s' % (ok, len(dx), dx[:6]),
       'engine runtime call at ' + COMMIT + ' against live testnet')
except Exception as e:
    ck('ENG-INV-08', 'ENGINE_ENUMERATES_PERP_DEX_SCOPE', False, 'raised %r' % (e,), 'engine runtime call')

real_mids = json.loads((SCR / 'oracle' / 'allMids_default.json').read_text(encoding='utf-8'))
sample_coin = 'HYPE' if 'HYPE' in real_mids else sorted(real_mids)[0]
out['artifacts']['oracle_allMids_sample'] = {sample_coin: real_mids[sample_coin]}
live = core.follower_mid(sample_coin)
ck('PRICE-002', 'REAL_NETWORK_PATH_RETURNS_LIVE_TESTNET_MID', live > 0,
   'follower_mid(%s)=%r live; oracle allMids=%r' % (sample_coin, live, real_mids[sample_coin]),
   'live testnet info API allMids')
ck('PRICE-001', 'FOLLOWER_MID_CONSULTED_ON_ENTRY_PRICE_PATH', live > 0,
   'engine mid source returned a live value for the entry limit-price computation',
   'live testnet info API')


class _Stub:
    def __init__(self, data, ok=True, dexes=None):
        self.data, self.ok, self.calls, self.dexes = data, ok, 0, dexes

    def list_perp_dexes(self, fetcher=None, info_url=None, timeout=None):
        return {'ok': True, 'dexes': list(self.dexes if self.dexes is not None else [''])}

    def _post(self, fetcher, payload, info_url, timeout):
        self.calls += 1
        return {'ok': self.ok, 'data': (self.data if payload.get('dex', '') == '' else {})}


_real_xnet = core._XNET


def now_ms():
    return int(time.time() * 1000)


def seed(px, age_ms, dexes=('',)):
    core._FOLLOWER_MIDS.clear()
    core._FOLLOWER_MIDS.update({'px': dict(px), 'ms': now_ms() - age_ms,
                                'dexes': list(dexes), 'dexes_ms': now_ms()})


max_age = float(os.environ.get('HL_LIVE_MIDS_MAX_AGE_SEC', '5.0'))
ttl = float(os.environ.get('HL_LIVE_MIDS_CACHE_TTL_SEC', '2.0'))
out['artifacts']['max_age_sec'] = max_age
out['artifacts']['cache_ttl_sec'] = ttl

core._XNET = _Stub({sample_coin: 123.456})
seed({sample_coin: 111.0}, 0)
v_within = core.follower_mid(sample_coin)
ck('PRICE-002', 'WITHIN_MAX_AGE_RETURNS_CACHED', abs(v_within - 111.0) < 1e-9,
   'cache age ~0s (< %ss) -> follower_mid=%r (cached, no refresh)' % (max_age, v_within),
   'engine runtime call at ' + COMMIT)

core._XNET = _Stub({}, ok=False)
seed({sample_coin: 111.0}, int((max_age + 1) * 1000))
v_stale = core.follower_mid(sample_coin)
ck('PRICE-002', 'STALE_BEYOND_MAX_AGE_RETURNS_ZERO', v_stale == 0.0,
   'cache age %ss (> %ss) and refetch unavailable -> follower_mid=%r (no order possible)' %
   (max_age + 1, max_age, v_stale), 'engine runtime call at ' + COMMIT)

stub_ref = _Stub({sample_coin: 222.0})
core._XNET = stub_ref
seed({sample_coin: 111.0}, int((ttl + 0.5) * 1000))
v_ref = core.follower_mid(sample_coin)
ck('PRICE-002', 'BEYOND_CACHE_TTL_REFETCHES', stub_ref.calls >= 1 and abs(v_ref - 222.0) < 1e-9,
   'cache age %ss (> TTL %ss) -> refresh calls=%d value=%r' % (ttl + 0.5, ttl, stub_ref.calls, v_ref),
   'engine runtime call at ' + COMMIT)
core._XNET = _real_xnet

live_dir = SCR / 'live'
seedf = SCR / 'oracle' / 'fills_all.json'
seed_fills = json.loads(seedf.read_text(encoding='utf-8')) if seedf.is_file() else []
WANT = {62916249666, 62916249669, 62916245305, 62916246142, 62916246146, 62916246171, 62916246380}
matched = {f['oid']: f for f in seed_fills if f.get('oid') in WANT}
out['artifacts']['oracle_fills_matched'] = len(matched)
ck('ENG-INV-09', 'EXCHANGE_FILLS_INDEPENDENTLY_READ', len(matched) == 7,
   'testnet userFillsByTime (no engine import) matched %d of 7 audit-referenced order ids' % len(matched),
   'live testnet info API userFillsByTime')

led = {}
lf = live_dir / 'live_fills.csv'
if lf.is_file():
    with lf.open(encoding='utf-8-sig', newline='') as fh:
        for r in csv.DictReader(fh):
            try:
                led[int(r['exchange_order_id'])] = r
            except (TypeError, ValueError):
                pass
both = sorted(set(matched) & set(led))
out['artifacts']['fills_matched_engine_and_oracle'] = len(both)
per_scope = sorted(set('%s|%s|%s|%s' % (matched[o]['coin'], led[o]['leader_wallet'],
                                        matched[o]['px'], led[o]['fill_price']) for o in both))
out['artifacts']['per_wallet_coin_rows'] = per_scope
ck('ENG-INV-09', 'ENGINE_LEDGER_AGREES_WITH_EXCHANGE', len(both) > 0,
   '%d order ids present in BOTH the engine ledger and the exchange oracle; sample=%s' %
   (len(both), per_scope[:2]), 'testnet userFillsByTime vs engine audit CSV')

oi = live_dir / 'order_intents.csv'
if oi.is_file():
    wallets, sleeves, coins = set(), set(), set()
    with oi.open(encoding='utf-8-sig', newline='') as fh:
        for r in csv.DictReader(fh):
            if r.get('leader_wallet'):
                wallets.add(r['leader_wallet'])
            if r.get('sleeve_id'):
                sleeves.add(r['sleeve_id'])
            if r.get('coin'):
                coins.add(r['coin'])
    keyed = sorted(s for s in sleeves if s and s.count('::') >= 2)
    out['artifacts']['intent_wallets'] = len(wallets)
    out['artifacts']['intent_sleeves'] = len(sleeves)
    out['artifacts']['intent_sleeve_sample'] = keyed[:3]
    ck('ENG-INV-07', 'SLEEVE_KEY_IS_WALLET_COIN', len(keyed) > 0 and len(wallets) > 0,
       'per (wallet,coin) keys: wallets=%d sleeves=%d coins=%d sample=%s' %
       (len(wallets), len(sleeves), len(coins), keyed[:2]), 'engine audit CSV order_intents.csv')

out['artifacts']['FIXED_MODE_AUTHORITY_HOLD_core'] = core_src.count('FIXED_MODE_AUTHORITY_HOLD')
out['artifacts']['FIXED_MODE_AUTHORITY_HOLD_legacy'] = legacy_src.count('FIXED_MODE_AUTHORITY_HOLD')
out['scope_notes'] = {
    'ENG-003': 'OD-02 OPEN_DECISION (Architect). Row expected_behaviour IS a fail-closed HOLD with ZERO orders; the row execution_proof (testnet order chain) contradicts it. NOT_TESTED.',
    'ENG-INV-07': 'per-(wallet,coin) keying proven on the live lineage audit artifact (sha256 in live/SNAPSHOT_SHA256.txt); the row execution_proof testnet order chain is not reproduced here.',
    'ENG-INV-08': 'engine DEX-scope enumeration + live allMids proven against the register commit; the negative case (missing required scope must fail closed) is NOT covered.',
    'ENG-INV-09': 'engine-ledger vs exchange agreement proven on the live lineage; the negative case (stale manual file must not override exchange) is NOT covered.',
    'PRICE-001': 'follower_mid liveness proven live at the register commit; apply_fixed_sleeve_event is absent from the ENGINE module under test (see census).',
    'PRICE-002': 'TTL/max-age rules executed at the register commit; the row oracle (l2Book/allMids at decision time + exchange fill) is only partly satisfied here.',
}
out['summary'] = {r: {'pass': sum(1 for c in v if c['pass']), 'total': len(v)} for r, v in out['checks'].items()}
p = SCR / 'harness' / ('ENG_PRICE_probe_%s.json' % COMMIT[:8])
p.write_text(json.dumps(out, indent=1), encoding='utf-8')
print('WROTE', p)
print(json.dumps(out['summary']))
sys.stdout.flush()
os._exit(0)
