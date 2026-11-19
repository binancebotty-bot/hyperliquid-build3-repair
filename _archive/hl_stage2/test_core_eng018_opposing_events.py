#!/usr/bin/env python3
"""ENG-018: opposing leader events enter Core independently; offline only."""
from __future__ import annotations
import os, re, sys, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
RESULTS=[]
def check(name, ok, detail=''):
    RESULTS.append((name,bool(ok)))
    print(f"RESULT::{name}_{'PASS' if ok else 'FAIL'}"+(f" | {detail}" if detail and not ok else ''),flush=True)
def main():
    tmp=Path(tempfile.mkdtemp(prefix='eng018_'))
    os.environ.update({'HL_LIVE_AUDIT_DIR':str(tmp),'HL_LEADER_NETWORK':'testnet','HL_FOLLOWER_NETWORK':'testnet','HL_LIVE_ENV_FILE':'/nonexistent','HL_LIVE_SCOPE_SWEEP_THREAD':'0','HL_LIVE_SNAPSHOT_REFRESH_INTERVAL_SEC':'100000','HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS':'0'})
    import requests
    import HL_Live_Copy_Service_Core as c
    def offline(*a,**k): raise RuntimeError('offline test: network forbidden')
    requests.post=offline; c.requests.post=offline
    A='0x'+'a'*40; B='0x'+'b'*40; c.USER_WALLET='0x'+'c'*40
    c.atomic_write_json(c.LIVE_CONFIG_FILE,{'auto_send_enabled':False,'global_controls':{},'wallets':{A:{'enabled':True,'mode':'ON','copy_mode':'fixed','fixed_notional':12},B:{'enabled':True,'mode':'ON','copy_mode':'fixed','fixed_notional':12}}})
    c.MIDS_FETCHER=lambda p: [] if p.get('type')=='perpDexs' else {'BTC':'100'}
    c.EXPOSURE_FETCHER=lambda p: {'assetPositions':[],'marginSummary':{'accountValue':'1000'}} if p.get('type')=='clearinghouseState' else []
    core=c.LiveCopyCore(source_csv=tmp/'none.csv')
    sent=[]
    core.sender._place_order=lambda *a,**k: sent.append((a,k)) or (None,None)
    def fill(fid,w,side,size): return c.LeaderFill(fid,w,'BTC',side,100.0,size,c.utc_now_ms(),'TEST',raw={})
    summary=c.CycleSummary()
    x=core._process_leader_fill(fill('opp-plus',A,'BUY',2),summary,'')
    y=core._process_leader_fill(fill('opp-minus',A,'SELL',2),summary,'')
    ledger=core.ledger
    rows=c.read_csv_rows(c.LIVE_FILLS_CSV) if c.LIVE_FILLS_CSV.exists() else []
    ids={str(r.get('leader_fill_id','')) for r in rows}
    check('OPPING_BOTH_EVENTS_CONSUMED',x[1]!='DEDUPED' and y[1]!='DEDUPED' and summary.leader_fills_deduped==0 and {'opp-plus','opp-minus'}<=ids,f'{x[1]} {y[1]} dedupe={summary.leader_fills_deduped} ids={ids}')
    target0=abs(float(ledger.sleeve(A,'BTC').get('signed_size',0)))<1e-9
    check('OPPING_NET_TARGET_ZERO',target0,str(ledger.sleeve(A,'BTC')))
    core._process_leader_fill(fill('opp-b',B,'BUY',1),summary,'')
    sl_a=ledger.sleeve(A,'BTC'); sl_b=ledger.sleeve(B,'BTC')
    check('OPPING_PER_LEADER_SLEEVES',sl_a is not sl_b and abs(float(sl_a.get('signed_size',0))-float(sl_b.get('signed_size',0)))>1e-9 and sl_a.get('pnl')!=sl_b.get('pnl'),f'{sl_a} {sl_b}')
    check('OPPING_ZERO_PHYSICAL_ORDER',not sent and {'opp-plus','opp-minus'}<=ids,f'calls={len(sent)} ids={ids}')
    src=(HERE/'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8-sig')
    check('OPPING_SINGLE_ORDER_SITE',len(re.findall(r'exchange\.order\(',src))==1,str(len(re.findall(r'exchange\.order\(',src))))
    real=core.ledger.sleeve
    outcomes=[]
    try:
        core.ledger.sleeve=lambda wallet,coin: real(B,coin) if wallet==A else real(wallet,coin)
        bad=core._process_leader_fill(fill('opp-falsify',A,'BUY',1),summary,'')
        outcomes.append(bad[2] is None or abs(float(real(A,'BTC').get('signed_size',0)))<1e-9)
    finally:
        core.ledger.sleeve=real
    check('OPPING_FALSIFICATION',any(outcomes),str(outcomes))
    core.stop()
    failed=[n for n,ok in RESULTS if not ok]
    print(f'TOTAL={len(RESULTS)} FAILED={len(failed)}')
    raise SystemExit(bool(failed))
if __name__=='__main__': main()
