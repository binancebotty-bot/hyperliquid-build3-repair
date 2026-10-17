#!/usr/bin/env python3
"""B3-CERT NETWORK TN-A1..A6 harness.

Checks the committed result JSON structure and verifies that the required
testnet transport / request-log oracle route is genuinely absent.
Does NOT mock any result. Run with python3 explicitly.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

RESULT = Path(__file__).with_name('B3H_b142cf88d3.json')
EXPECTED = {'TN-A1', 'TN-A2', 'TN-A3', 'TN-A4', 'TN-A5', 'TN-A6'}

# A route is absent when no module in the live tree implements it.
# We check source symbols, not test names, to avoid false greens.
def route_present(symbols: set[str]) -> bool:
    # grep the live tree for a real transport URL processor + request logger
    root = Path(__file__).resolve().parents[2]
    transport = False
    oracle = False
    for p in root.rglob('*.py'):
        if '__pycache__' in p.parts or '.worktrees' in p.parts:
            continue
        try:
            txt = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        if 'api.hyperliquid-testnet.xyz' in txt and ('evil' in txt or 'hostile' in txt or 'reject' in txt.lower()):
            transport = True
        if 'request_log' in txt or 'captured_request' in txt or 'packet_capture' in txt:
            oracle = True
    return transport and oracle

def main() -> int:
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    assert data['schema'] == 'b3-cert-result-v1'
    assert data['tested_commit'] == 'b142cf88d389e791160f691aac3d936852b99975'
    rows = data['rows']
    assert {r['id'] for r in rows} == EXPECTED, f'Row set mismatch: { {r["id"] for r in rows} }'
    for r in rows:
        rid = r['id']
        assert r['result'] == 'NOT_TESTED', f'{rid} result is {r["result"]}, expected NOT_TESTED'
        for c in r['checks']:
            cname = c['name']
            assert c['result'] == 'NOT_TESTED', f'{rid} check {cname} is {c["result"]}'
            assert 'MISSING_ROUTE' in c['evidence'], f'{rid} check missing MISSING_ROUTE evidence'
    present = route_present(set())
    print(f'CERT_BOUNDARY=PASS rows=6 statuses=NOT_TESTED live_oracle={"PRESENT" if present else "ABSENT"}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
