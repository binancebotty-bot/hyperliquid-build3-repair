import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exchange_truth as X
out = {}
A='0x34f322d8eb97461da8f1bd2f1b95dcf4ca52a76d'
B='0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'
out['identity_distinct_ok']=X.identity_ok(A,B)
out['identity_same_rejected']=X.identity_ok(A,A)
out['identity_garbage_rejected']=X.identity_ok('',B)
out['runtime_ident_no_env_ok']=X.runtime_master_identity({}).get('ok')
out['runtime_ident_distinct_ok']=X.runtime_master_identity({'HL_LIVE_HL_ACCOUNT_ADDRESS':B,'HL_LIVE_HL_SIGNER_ADDRESS':A}).get('ok')
r=X.runtime_master_identity({'HL_LIVE_HL_ACCOUNT_ADDRESS':A,'HL_LIVE_HL_SIGNER_ADDRESS':A})
out['runtime_ident_same_ok']=r.get('ok')
out['runtime_ident_same_status']=r.get('status')
d=X.resolve_networks({})
out['default_leader']=d['leader']['network']
out['default_follower']=d['follower']['network']
m=X.resolve_networks({'HL_FOLLOWER_NETWORK':'mainnet'})
out['mainnet_follower_by_env_only']=m['follower']['network']
try:
    X.resolve_networks({'HL_FOLLOWER_NETWORK':'testnet','HL_INFO_URL':'https://api.hyperliquid.xyz/info'})
    out['mismatch_guard']='NOT_RAISED'
except X.NetworkConfigError as e:
    out['mismatch_guard']='RAISED'
src=open('exchange_truth.py',encoding='utf-8',errors='replace').read().lower()
out['truth_module_mentions_approval']=('approval' in src or 'richard' in src)
print(json.dumps(out,indent=1))
