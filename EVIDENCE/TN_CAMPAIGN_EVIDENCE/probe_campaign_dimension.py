#!/usr/bin/env python3
"""TN-CAMP evidence probe: does the testnet append-only audit carry a campaign dimension?

READ-ONLY. Opens every file under the append-only audit directory in 'rb' and reads
only the header line plus a streaming row count. Never writes to that directory.

Purpose: decide whether a per-campaign extraction of TN-CAMP-01..09 is possible from
the on-disk testnet audit, or whether the honest verdict is NOT_TESTED.

Run:  python probe_campaign_dimension.py > campaign_dimension_result.json
"""
import csv
import json
import os
import sys

AUDIT = (
    'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/'
    'hl_live_copy_audit_testnet/append_only'
)

CAMPAIGN_TOKENS = ('campaign', 'camp_id', 'campaign_id', 'run_id', 'batch_id',
                   'manifest_id', 'scenario', 'scenario_id', 'phase6t')

TARGETS = ('live_fills.csv', 'send_attempts.csv', 'order_intents.csv')


def header_of(path):
    with open(path, 'rb') as f:
        raw = f.readline()
    text = raw.decode('utf-8', errors='replace').rstrip('\r\n')
    return [c.strip().lstrip('\ufeff') for c in next(csv.reader([text]))]


def count_rows_streaming(path):
    n = 0
    with open(path, 'rb') as f:
        f.readline()
        for _ in f:
            n += 1
    return n


def main():
    if not os.path.isdir(AUDIT):
        print(json.dumps({'error': 'audit dir not found', 'path': AUDIT}, indent=1))
        return 2

    out = {'audit_dir': AUDIT,
           'campaign_tokens_searched': list(CAMPAIGN_TOKENS),
           'files': []}

    for name in TARGETS:
        path = os.path.join(AUDIT, name)
        entry = {'file': name, 'exists': os.path.isfile(path)}
        if entry['exists']:
            cols = header_of(path)
            hits = [c for c in cols
                    if any(tok in c.lower() for tok in CAMPAIGN_TOKENS)]
            entry['columns'] = cols
            entry['column_count'] = len(cols)
            entry['campaign_columns_found'] = hits
            entry['has_campaign_dimension'] = bool(hits)
            entry['row_count'] = count_rows_streaming(path)
            entry['size_bytes'] = os.path.getsize(path)
            entry['identity_columns_present'] = [
                c for c in cols
                if c in ('intent_id', 'exchange_order_id', 'cloid', 'copy_fill_id',
                         'leader_fill_id', 'position_id', 'sleeve_id')]
        out['files'].append(entry)

    present = [f for f in out['files'] if f.get('exists')]
    any_campaign = any(f.get('has_campaign_dimension') for f in present)
    out['summary'] = {
        'files_inspected': [f['file'] for f in present],
        'total_rows_inspected': sum(f.get('row_count', 0) for f in present),
        'any_file_carries_campaign_column': any_campaign,
        'per_campaign_extraction_possible': any_campaign,
        'conclusion': (
            'A campaign dimension exists in the audit; per-campaign extraction is possible.'
            if any_campaign else
            'No file in the testnet append-only audit carries any campaign identifier '
            'column. The audit records orders and fills keyed by intent_id / '
            'exchange_order_id / cloid / sleeve_id only. There is no way to attribute a '
            'fill or an order to TN-CAMP-01..09, and no way to reconstruct the campaign '
            'bounds, the pre-declared manifest, or the campaign window. Per-campaign '
            'extraction from this audit is NOT POSSIBLE.'
        ),
    }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
