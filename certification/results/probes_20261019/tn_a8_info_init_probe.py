import json
from hyperliquid.api import API
from hyperliquid.info import Info

calls = []


def fake_post(self, url_path, payload=None):
    calls.append(payload)
    p = payload or {}
    if p.get('type') == 'spotMeta':
        return {'universe': [], 'tokens': []}
    if p.get('type') == 'meta':
        return {'universe': []}
    if p.get('type') == 'perpDexs':
        return []
    return {}


API.post = fake_post
Info('https://api.hyperliquid-testnet.xyz', True)
print(json.dumps({'requests_during_info_init': len(calls),
                  'types': [c.get('type') if isinstance(c, dict) else None for c in calls]}))
