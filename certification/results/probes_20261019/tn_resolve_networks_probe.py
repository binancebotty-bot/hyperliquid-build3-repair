import json, sys
sys.path.insert(0, '.')
import exchange_truth as X
cases = {
 'TN-A1': {'HL_INFO_URL': 'https://api.hyperliquid-testnet.xyz.evil.example/info'},
 'TN-A2': {'HL_INFO_URL': 'https://evil.example/?next=api.hyperliquid-testnet.xyz'},
 'TN-A3': {'HL_INFO_URL': 'https://user:pw@api.hyperliquid-testnet.xyz@evil.example/info'},
 'TN-A4': {'HL_INFO_URL': 'https://api.hyperliquid%2Dtestnet.xyz/info'},
 'TN-A5_ip': {'HL_INFO_URL': 'https://127.0.0.1/info'},
 'TN-A5_v6': {'HL_INFO_URL': 'https://[::1]/info'},
 'TN-A6_unicode': {'HL_INFO_URL': 'https://api.hyperliquid-testnet.xy\u017a/info'},
 'TN-T17_devnet': {'HL_FOLLOWER_NETWORK': 'devnet'},
 'TN-T17_blank_leader': {'HL_LEADER_NETWORK': ''},
 'TN-A7_redirect_note': {'HL_INFO_URL': 'https://api.hyperliquid-testnet.xyz/info'},
}
out = {}
for k, env in cases.items():
    base = {'HL_FOLLOWER_NETWORK': 'testnet'}
    base.update(env)
    try:
        nets = X.resolve_networks(base)
        out[k] = {'refused': False, 'nets': {kk: vv['base'] for kk, vv in nets.items()}}
    except X.NetworkConfigError as e:
        out[k] = {'refused': True, 'error': str(e)[:200]}
print(json.dumps(out, indent=1))
