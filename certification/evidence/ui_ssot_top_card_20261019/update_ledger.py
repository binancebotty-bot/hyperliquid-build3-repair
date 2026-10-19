import datetime
import json
import pathlib

root = pathlib.Path(__file__).resolve().parents[3]
results_path = root / 'certification' / 'run_results.json'
data = json.loads(results_path.read_text(encoding='utf-8'))
run_id = 'ui_ssot_top_card_20261019'
rows = [f'UI-SSOT-TOP-{i:02d}' for i in range(1, 10)]
evidence = 'certification/evidence/ui_ssot_top_card_20261019/rendered_dom_capture.json and render_probe.py; DOM labels rendered, but source-state/API payload and independent oracle unavailable in this capture; therefore BLOCKED, not PASS. CARD-01..06 applicability=SUPERSEDED per OD-21 and remain untested/void.'
run = {
    'run': run_id,
    'date': datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
    'commit': '819050c6018ab3264cfe911f927e1f97ff0f979b',
    'network': 'read-only local UI observation; no trading actions',
    'follower_network': 'testnet',
    'report': 'certification/evidence/ui_ssot_top_card_20261019/rendered_dom_capture.json',
    'summary': 'Fresh browser-rendered DOM captures from :8023/live-copy and :8031/; source content hashes recorded. Nine applicable TOP criteria blocked because capture does not establish required live state-to-payload-to-cell chain or independent oracle. CARD-01..06 remain void per OD-21.',
    'results': [{'id': row, 'result': 'BLOCKED', 'evidence': evidence} for row in rows],
}
if any(item.get('run') == run_id for item in data['runs']):
    raise SystemExit('run already exists; refusing duplicate')
data['runs'].append(run)
results_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('appended', run_id, 'rows', len(run['results']))
