import json, sys, importlib, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

W = '0xabc0000000000000000000000000000000000001'
FIXTURE_STATE = {
    'portfolio_history': [{'ts': '2026-10-21T20:00:00Z', 'copy_pnl': 1.0, 'pnl': 1.0}],
    'wallet_rows': [{'wallet': W, 'curve': [
        {'open_notional_usd': 500.0}, {'open_notional_usd': 2183.56}, {'open_notional_usd': 900.0}]}],
}
FIXTURE_SNAP = {'ok': True, 'withdrawable': 0.0, 'available_to_trade': 1007.0}
FIXTURE_PERF = {W: {'wallet': W, 'current_exposure': 2183.56, 'open_exposure': 2183.56, 'max_exposure': None}}


def probe(modname):
    for m in list(sys.modules):
        if m.startswith(modname):
            del sys.modules[m]
    ui = importlib.import_module(modname)
    ui.get_model_state_cached = lambda *a, **k: json.loads(json.dumps(FIXTURE_STATE))
    ui._build_live_leader_performance = lambda *a, **k: json.loads(json.dumps(FIXTURE_PERF))
    ui._load_live_copy_config = lambda: {'wallets': {W: {'enabled': True, 'service_eligible': True, 'label': 'fixture'}}}
    real_load = ui.load_json
    ui.load_json = lambda p, d=None: (json.loads(json.dumps(FIXTURE_SNAP))
                                      if Path(str(p)).name == 'exchange_account_snapshot_app.json' else real_load(p, d))
    s = ui._live_audit_summary()
    ph = s.get('portfolio_history') or []
    perf = s.get('live_leader_performance') or {}
    mx = [ui.fnum(p.get('max_exposure')) for p in perf.values() if p.get('max_exposure') is not None]
    op = [ui.fnum(p.get('open_exposure')) for p in perf.values()]
    rows = s.get('live_wallet_rows') or []
    rmx = [ui.fnum(r.get('max_exposure')) for r in rows if r.get('max_exposure') is not None]
    rop = [ui.fnum(r.get('open_exposure')) for r in rows]
    html = ''.join(ui._account_card_lines())
    return {
        'rows': len(rows),
        'rows_max_exposure_present': len(rmx),
        'rows_sum_max_exposure': round(sum(rmx), 2),
        'rows_max_open_exposure': round(max(rop) if rop else 0.0, 2),
        'rows_gte_at_one_wallet': bool(rmx) and max(rmx) >= (max(rop) if rop else 0.0),
        'portfolio_history_len': len(ph),
        'max_exposure_present': len(mx),
        'sum_max_exposure': round(sum(mx), 2),
        'max_open_exposure': round(max(op) if op else 0.0, 2),
        'gte_at_one_wallet': bool(mx) and max(mx) >= (max(op) if op else 0.0),
        'label_free_margin': 'FREE MARGIN (default DEX)' in html,
        'label_spot': 'SPOT AVAILABLE' in html,
    }


for name in sys.argv[1:]:
    try:
        print(name, json.dumps(probe(name), sort_keys=True))
    except Exception:
        print(name, 'ERROR', traceback.format_exc()[-300:])
