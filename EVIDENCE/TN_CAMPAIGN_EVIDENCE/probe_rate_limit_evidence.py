#!/usr/bin/env python3
"""TN-F24 support probe: is there any rate-limit / 429 evidence in the testnet audit?

READ-ONLY. Streams the audit CSVs and counts reject/429 categories. Used only to
state factually whether any 429-budget evidence exists; it cannot by itself certify
TN-F24, which requires a predeclared campaign scenario.

Run: python probe_rate_limit_evidence.py > rate_limit_result.json
"""
import csv
import json
import os
import sys
from collections import Counter

AUDIT = (
    'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/'
    'hl_live_copy_audit_testnet/append_only'
)

MAX_FIELD = sys.maxsize


def scan(name, cols_of_interest):
    path = os.path.join(AUDIT, name)
    if not os.path.isfile(path):
        return {'file': name, 'exists': False}
    counters = {c: Counter() for c in cols_of_interest}
    rate_hits = 0
    n = 0
    csv.field_size_limit(MAX_FIELD)
    with open(path, 'rb') as fb:
        text = (line.decode('utf-8', errors='replace') for line in fb)
        reader = csv.DictReader(text)
        for row in reader:
            n += 1
            blob = ' '.join(str(v) for v in row.values() if v)
            if '429' in blob or 'rate limit' in blob.lower() or 'ratelimit' in blob.lower():
                rate_hits += 1
            for c in cols_of_interest:
                v = (row.get(c) or '').strip()
                if v:
                    counters[c][v] += 1
    return {
        'file': name,
        'exists': True,
        'rows_scanned': n,
        'rows_mentioning_429_or_rate_limit': rate_hits,
        'value_counts': {col: dict(ct.most_common(8))
                         for col, ct in counters.items() if ct},
    }


def main():
    out = {
        'audit_dir': AUDIT,
        'purpose': 'factual inventory of rate-limit / 429 evidence in the testnet audit',
        'scans': [
            scan('send_attempts.csv',
                 ('status', 'reject_category', 'terminal_state',
                  'latency_classification', 'error')),
        ],
    }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
