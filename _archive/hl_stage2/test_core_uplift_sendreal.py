#!/usr/bin/env python3
"""Offline _send_real uplift probe; all exchange effects terminate at a spy."""
import os, sys, tempfile
from pathlib import Path
ROOT=Path(sys.argv[1]); COMMIT=sys.argv[2]
CORE=ROOT/'_archive/hl_stage2/HL_Live_Copy_Service_Core.py'
tmp=Path(tempfile.mkdtemp(prefix='uplift_'))
os.environ.update(HL_LIVE_AUDIT_DIR=str(tmp), HL_LIVE_ENV_FILE='/nonexistent', HL_LEADER_NETWORK='testnet', HL_FOLLOWER_NETWORK='testnet', HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS='0', HL_LIVE_MISSED_ENTRY_RULE='0', HL_LIVE_DUST_CLOSE_ATTEMPT='1')
sys.path.insert(0,str(CORE.parent))
import HL_Live_Copy_Service_Core as c
class Spy:
 def __init__(self): self.calls=[]
 def update_leverage(self,*a,**k): return {'status':'ok'}
 def order(self,coin,is_buy,size,px,tif,reduce_only=False):
  self.calls.append((coin,size,px)); return {'status':'ok','response':{'type':'order','data':{'statuses':[{'filled':{'totalSz':str(size),'avgPx':str(px),'oid':1}}]}}}
 def __getattr__(self,n): return lambda *a,**k: {'status':'ok'}
LEADER='0x'+'a'*40
c.atomic_write_json(c.LIVE_CONFIG_FILE, {'auto_send_enabled':True,'global_controls':{'min_notional':10,'max_order_notional':0,'marketable_bps':20},'wallets':{LEADER:{'enabled':True,'mode':'LIVE','copy_mode':'fixed','fixed_notional':10}}})
c.USER_WALLET='0x'+'c'*40
c.wait_intent_durable=lambda *a,**k:None
c.update_send_attempt_row=lambda *a,**k:True
c.HLAccount=c.HLExchange=object
os.environ['HL_LIVE_HL_PRIVATE_KEY']='0x'+'1'*64; os.environ['HL_LIVE_HL_ACCOUNT_ADDRESS']=c.USER_WALLET
cases=[('px500',500,0),('px61000',61000,0),('px61000_merged500',61000,500),('finite_control',100,0)]
active_px={'value':500}
c.MIDS_FETCHER=lambda payload: {'TEST': active_px['value']} if payload.get('type')=='allMids' else []

for name,px,merged in cases:
 active_px['value']=px
 c._FOLLOWER_MIDS.update(px={},ms=0,scope=[])
 spy=Spy(); ledger=c.ManualLedger(path=tmp/(name+'.json')); gw=c.SenderGateway(c.ConfigManager(),c.AuditLogWriter(),ledger)
 md={'ok':True,'sdk_coin':'TEST','raw_coin':'TEST','sz_decimals':0,'price_max_decimals':2,'perp_dexs':[''],'sdk_order_compatible':True,'min_order_value_usd':10.,'min_size':1.,'status':'OK'}
 gw._resolve_coin=lambda coin,md=md:dict(md)
 gw._get_exchange_client=lambda *a,**k:spy
 gw._exchange_client_has_symbol=lambda *a,**k:True
 gw._pre_exchange_asset_safety=lambda *a,**k:(True,{})
 gw._pre_send_ownership_gate=lambda *a,**k:(True,{})
 gw._begin_pending_send=lambda *a,**k:'aid'
 gw._ensure_margin_mode=lambda *a,**k:None
 fill=c.LeaderFill('f-'+name,LEADER,'TEST','BUY',px,0.02,c.utc_now_ms(),'TEST')
 intent=c.Intent('i-'+name,fill,'BUY',10/px,10.0,'LIVE','fixed','ENTRY_ALLOWED','ENTRY','s','','LONG',0,0,False,False,c.utc_now_ms(),'lifecycle=ENTRY;')
 intent.copy_notional=10.0
 if merged: intent.merged_fill_count=merged
 try:
  ok,status,result=gw._send_real(intent)
  notional=spy.calls[0][1]*spy.calls[0][2] if spy.calls else float(result.get('copy_notional',0) or 0)
  print(f'{COMMIT} {name}: wire_notional={notional:g} spy_calls={len(spy.calls)} outcome={"SEND" if spy.calls else status} err={str(result.get("error"))[:200]}')
 except Exception as e: print(f'{COMMIT} {name}: wire_notional=NA spy_calls={len(spy.calls)} outcome=HARNESS_ERROR:{type(e).__name__}:{e}')
