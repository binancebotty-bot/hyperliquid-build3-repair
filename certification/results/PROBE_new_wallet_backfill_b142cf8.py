import sys, os, json, tempfile, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / '_cert_run' / '_archive' / 'hl_stage2'))

FAKE = {
    'id': 'f-2026-10-19T09:00:00Z-abc', 'coin': 'BTC', 'side': 'B', 'px': '100.0', 'sz': '1.0',
    'time': 1760864400000, 'startPosition': '0', 'closedPnl': '0', 'dir': 'Open Long',
    'fee': '0.01', 'oid': 1, 'crossed': True, 'hash': '0x1',
}

def call(wallet, since_ms):
    import HL_Live_Copy_Service_Core as c
    ing = c.LeaderFillIngestor() if hasattr(c.LeaderFillIngestor, '__init__') else None
    return ing

import HL_Live_Copy_Service_Core as c
print('POLL_WINDOW_MS', c.POLL_WINDOW_MS, 'OVERLAP', c.POLL_OVERLAP_MS, 'CURSOR_BOOT_DAYS', c.POLL_WINDOW_MS/86400000.0)
seen = []
class R:
    @staticmethod
    def post(url, json=None, timeout=None):
        seen.append({'start': json.get('startTime'), 'end': json.get('endTime'), 'user': json.get('user')})
        class Resp:
            @staticmethod
            def json(): return [FAKE]
        return Resp()
c.requests = R

ing = c.LeaderFillIngestor()
now = c.utc_now_ms()
fills, st = ing.poll_hyperliquid_fills('0x' + 'a'*40, max(0, now - c.POLL_WINDOW_MS - c.POLL_OVERLAP_MS), now)
print('STATUS', st, 'FILLS_RETURNED', len(fills))
print('REQUEST', seen[0])
span_h = (seen[0]['end'] - seen[0]['start']) / 3600000.0
print('LOOKBACK_HOURS', round(span_h, 2))
for f in fills:
    print('FILL', f.fill_id, f.wallet[:10], f.coin, f.timestamp_ms)
# pre-cutover check as the core does
print('is_pre_cutover relative to a fresh live_start (now):', [f.timestamp_ms < now for f in fills])
