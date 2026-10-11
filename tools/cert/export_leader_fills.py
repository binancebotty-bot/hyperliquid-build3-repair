#!/usr/bin/env python3
"""Capture the leader fills of an outage window to JSON, so cert_outage_classify.py
can run OFFLINE (GAP-1).

This is the ONE network-touching step of the offline set. It is read-only: it POSTs
the public Hyperliquid `userFillsByTime` info request for the wallets named in a
COPY of live_config.json and writes what comes back. No keys are read, printed or
stored; no order is placed; nothing is subscribed; mainnet leader reads are the
read-only pattern the E1 report uses (paced at <= 1 request/second).

Usage:
  python tools/cert/export_leader_fills.py --config <copy of live_config.json> \
      --start-ms 1791705404255 --end-ms 1791705704441 --out fills_window.json

Output: {"window": [start_ms, end_ms], "fills": [{"coin","dir","wallet","hash","time"}]}
Only wallets whose config mode is LIVE/CLO are read.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

INFO = 'https://api.hyperliquid.xyz/info'
TESTNET_INFO = 'https://api.hyperliquid-testnet.xyz/info'
MODES = ('LIVE', 'CLO')


def post(url, payload, timeout=15):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def wallets(cfg):
    w = cfg.get('wallets') or {}
    if isinstance(w, dict):
        return [k for k, v in w.items() if (v or {}).get('mode') in MODES]
    return [str((x or {}).get('address') or (x or {}).get('wallet') or '')
            for x in w if (x or {}).get('mode') in MODES]


def main(argv=None):
    ap = argparse.ArgumentParser(description='Read-only leader-fill export for the offline GAP-1 classifier.')
    ap.add_argument('--config', required=True, help='copy of live_config.json (wallets + modes only are read)')
    ap.add_argument('--start-ms', type=int, required=True)
    ap.add_argument('--end-ms', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--testnet-leaders', action='store_true', help='read the testnet info endpoint instead')
    args = ap.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    url = TESTNET_INFO if args.testnet_leaders else INFO
    fills = []
    for w in wallets(cfg):
        if not w:
            continue
        fs = post(url, {'type': 'userFillsByTime', 'user': w, 'startTime': args.start_ms, 'endTime': args.end_ms})
        for f in fs if isinstance(fs, list) else []:
            if args.start_ms <= int(f.get('time') or 0) <= args.end_ms:
                fills.append({'coin': f.get('coin'), 'dir': f.get('dir'), 'wallet': w,
                              'hash': f.get('hash'), 'time': int(f.get('time') or 0)})
        time.sleep(1.0)  # <= 1 req/s, the E1 read pattern
    out = {'window': [args.start_ms, args.end_ms], 'fills': fills}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding='utf-8')
    print('wrote %d leader fills from %d wallets -> %s' % (len(fills), len(wallets(cfg)), args.out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
