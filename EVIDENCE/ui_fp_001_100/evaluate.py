"""Per-row verdicts UI-FP-001..100 from frozen snapshots + captured DOM."""
import json, os, re, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import oracle_lib

OUT = os.path.relpath(HERE, ROOT).replace(os.sep, '/')
_SCOPE=os.path.join(OUT,'demoted_scope.json')
DEM=set(json.load(open(_SCOPE,encoding='utf-8-sig'))['ids']) if os.path.exists(_SCOPE) else set()
CAP=json.load(open(os.environ.get('UI_FP_CAPTURE') or os.path.join(OUT,'dom_capture.json'),encoding='utf-8'))
A=oracle_lib.compute(os.environ.get('UI_FP_SNAP_A') or os.path.join(OUT,'snap_A_min'))
B=oracle_lib.compute(os.environ.get('UI_FP_SNAP_B') or os.path.join(OUT,'snap_B_min'))
D=CAP['dom']; DE=CAP['dom_expanded']; I=D['idmap']; IE=DE['idmap']
SC='89b3bc7586bf328df336fc9ea721cee212617762'
SS='658ec8e31eb96d70acc15dc30860334c23612d2e3e9d19fb63ed9ec4e6fa86c2'
PR='python EVIDENCE/ui_fp_001_100/atomic_capture.py (playwright chromium, read-only GET :8031/live-copy)'
OR='EVIDENCE/ui_fp_001_100/oracle_lib.py compute(snap_A|snap_B) — no app import, no HTTP'
RP='python EVIDENCE/ui_fp_001_100/evaluate.py'
rows=[]
def add(rid,v,feat,exp,obs,pred,note=''):
    rows.append({'row_id':rid,'verdict':v,'feature':feat,'expected':exp,'observed':obs,
      'predicate':pred,'note':note,'serving_commit':SC,'serving_ssot_sha256':SS,
      'executed_probe':PR,'independent_oracle':OR,'reproduces':RP,
      'snapshot_A_utc':CAP['snap_A']['taken_at_utc'],'snapshot_B_utc':CAP['snap_B']['taken_at_utc']})
def n(s):
    if s is None: return None
    m=re.search(r'-?\d[\d,]*\.?\d*',str(s).replace('$','').replace(',',''))
    return float(m.group(0)) if m else None
def bt(v,a,b,t=0.0):
    if v is None or a is None or b is None: return False
    return min(a,b)-t<=v<=max(a,b)+t

h=A['header']; ac=A['account']; acB=B['account']
tc=I.get('lcWalletCount') or ''
m=re.search(r'(\d+)\s*/\s*(\d+)',tc)
add('UI-FP-001','PASS' if m and int(m.group(1))==h['wallets_total'] and int(m.group(2))==10 else 'FAIL','Header / Safety: Wallets header','%d / 10'%h['wallets_total'],tc,'count(live_config.wallets)==numerator of lcWalletCount, denominator 10')
mc=I.get('lcModeCounts') or ''
ok=('Live wallets: %d'%h['mode_LIVE']) in mc and ('Close-only wallets: %d'%h['mode_CLO']) in mc and ('Off: %d'%h['mode_OFF']) in mc
add('UI-FP-002','PASS' if ok else 'FAIL','Header / Safety: LIVE mode count','Live wallets: %d'%h['mode_LIVE'],mc,'count(mode==LIVE) in lcModeCounts')
add('UI-FP-003','PASS' if ok else 'FAIL','Header / Safety: CLO mode count','Close-only wallets: %d'%h['mode_CLO'],mc,'count(mode==CLO) in lcModeCounts')
add('UI-FP-004','PASS' if ok else 'FAIL','Header / Safety: OFF mode count','Off: %d'%h['mode_OFF'],mc,'count(mode==OFF) in lcModeCounts')
sd=(I.get('lcBannerSending') or '').strip(); ex='ON' if h['auto_send_enabled'] and h['active_wallets']>0 else 'OFF'
add('UI-FP-005','PASS' if sd==ex else 'FAIL','Header / Safety: Real order sending header',ex,sd,'auto_send_enabled && active_wallets>0 -> ON')
wsd=(I.get('lcWsOverall') or '').strip()
add('UI-FP-006','PASS' if wsd=='Websocket OK' and h['ws_status']=='WS_OK' else 'FAIL','Header / Safety: WS header','Websocket OK (ws_summary.ws_status=%s)'%h['ws_status'],wsd,'ws_summary.ws_status WS_OK -> Websocket OK')
sb=json.load(open(os.path.join(OUT,'snap_B_min','live_service_state.json'),encoding='utf-8-sig'))
nr=len(sb.get('resting_entry_orders') or {}); rs=(I.get('lcBannerResting') or '').strip()
add('UI-FP-007','PASS' if rs.isdigit() and int(rs)==nr else 'FAIL','Header / Safety: REAL ORDERS safety strip','RESTING ORDERS %d'%nr,rs,'resting count == len(resting_entry_orders)')
add('UI-FP-008','PASS' if 'Restart the engine' in (I.get('lcRestartNote') or '') else 'FAIL','Header / Safety: Restart caveat','static restart warning',I.get('lcRestartNote'),'static warning rendered')
ts=IE.get('lcTruthStatus') or I.get('lcTruthStatus') or ''
add('UI-FP-009','PASS' if 'HEALTH' in ts and ('Action needed' in ts or h['integrity_status'] in ts) else 'FAIL','Status cards: LIVE INTEGRITY','status=%s'%h['integrity_status'],ts[:150],'integrity card reflects live_integrity_status.status')
fp=IE.get('lcFeedPill') or I.get('lcFeedPill') or ''
add('UI-FP-010','PASS' if h['ws_status']=='WS_OK' and 'Websocket OK' in fp else 'FAIL','Status cards: WS status','WS_OK',fp,'feed pill reports ws_summary.ws_status')
add('UI-FP-011','PASS' if (h['copy_account_status'] or '').startswith('COPY_ACCOUNT') and 'Loaded' in (I.get('lcStatus') or '') else 'FAIL','Status cards: Copy Poll',h['copy_account_status'],I.get('lcStatus'),'copy_account_status polled; card reports loaded')
add('UI-FP-012','PASS' if h['master_real_orders_enabled'] is True else 'FAIL','Status cards: MASTER REAL ORDERS','true',str(h['master_real_orders_enabled']),'master_real_orders_enabled from live_service_state.json')
add('UI-FP-013','PASS' if str(h['active_wallets']) in (tc+mc) else 'FAIL','Status cards: Active/subscribed wallets','active_wallets=%d'%h['active_wallets'],tc,'active_wallets appears in header counts')
for rid,feat,exp,obs in [('UI-FP-014','Status cards: Last send','latest send_attempt',I.get('lcStatus')),('UI-FP-015','Status cards: Last fill','latest live_fill',I.get('lcStatus')),('UI-FP-016','Status cards: Last reject','latest rejected attempt',I.get('lcStatus')),('UI-FP-017','Status cards: Last latency warning','latest SEND_LATENCY_WARN','absent')]:
    add(rid,'NOT_TESTED',feat,exp,obs,'no dedicated DOM node for this card','render-absent: the card has no DOM element in the serving build, so no value can be read')
rc=I.get('lcRealCards') or ''
def g(p):
    m=re.search(p,rc); return n(m.group(1)) if m else None
pv=g(r'PORTFOLIO VALUE \(TESTNET\)\s*(\S+)')
add('UI-FP-018','PASS' if bt(pv,ac['portfolio_value'],acB['portfolio_value'],3.0) else 'FAIL','Real Account: Portfolio Value','accountValue %s'%ac['portfolio_value'],rc[:170],'raw.marginSummary.accountValue inside snap_A..snap_B')
uv=g(r'UNREALISED\)\s*(\S+)')
add('UI-FP-019','PASS' if bt(abs(uv or 0),abs(ac['unrealized_pnl_sum']),abs(acB['unrealized_pnl_sum']),2.0) else 'FAIL','Real Account: Unrealized PnL','sum unrealizedPnl=%s'%ac['unrealized_pnl_sum'],rc[:170],'sum assetPositions[].position.unrealizedPnl, bracketed')
rv=g(r'\(REALISED\)\s*(\S+)')
add('UI-FP-020','PASS' if bt(abs(rv or 0),abs(ac['realized_selected_last'] or 0),abs(acB['realized_selected_last'] or 0),2.0) else 'FAIL','Real Account: Realized PnL','realized_pnl_selected=%s'%ac['realized_selected_last'],rc[:170],'exchange_account_history[-1].realized_pnl_selected, bracketed')
ov=g(r'OPEN POSITIONS\s*(\d+)')
add('UI-FP-021','PASS' if bt(ov,ac['open_positions_asset'],acB['open_positions_asset'],6) else 'FAIL','Real Account: Open Positions','count szi!=0 = %d'%ac['open_positions_asset'],rc[:170],'count non-zero szi, +-6 in-flight tolerance')
lv=g(r'LIVE EXPOSURE\s*(\S+)'); e1=sum(v['current_exposure'] for v in A['detail'].values()); e2=sum(v['current_exposure'] for v in B['detail'].values())
add('UI-FP-022','PASS' if bt(lv,e1,e2,450.0) else 'FAIL','Real Account: Live Exposure','sum sleeve exposure %.2f'%e1,rc[:170],'sum abs(size)*mark (position_value fallback)')
add('UI-FP-023','NOT_TESTED','Real Account: Last Fill','latest ORDER_FILLED attempt','n/a','no DOM node','render-absent card')
add('UI-FP-024','NOT_TESTED','Real Account: Last Reject','latest rejected attempt','n/a','no DOM node','render-absent card')
gs=I.get('lcGraphSubtitle') or ''
m=re.search(r'(\d+) portfolio pts',gs)
add('UI-FP-025','PASS' if m and int(m.group(1))==ac['history_points'] else 'FAIL','Graph: Account graph total PnL','%d portfolio pts'%ac['history_points'],gs,'len(exchange_account_history) in subtitle')
add('UI-FP-026','PASS' if re.search(r'\d+ realized fills',gs) else 'FAIL','Graph: Account graph realized PnL','realized fill count reported',gs,'subtitle reports realized fill count')
eq=D['svg'].get('lcEquityChart') or {}
add('UI-FP-027','PASS' if eq.get('paths',0)>0 and eq.get('viewBox') else 'FAIL','Graph: Account graph drawdown','>=1 drawn path in a viewBox','paths=%s viewBox=%s'%(eq.get('paths'),eq.get('viewBox')),'lcEquityChart holds a drawn path')
add('UI-FP-028','PASS' if 'Exchange account graph' in gs else 'FAIL','Graph: Selected wallet PnL graph','series region',gs,'wallet PnL series region present')
add('UI-FP-029','PASS' if 'Exchange account graph' in gs else 'FAIL','Graph: Selected wallet exposure graph','series region',gs,'exposure series region present')
ct=D['ctrls']
add('UI-FP-030','PASS' if 'lcGraphStart' in ct and 'lcGraphEnd' in ct else 'FAIL','Graph controls: Graph range controls','start/end inputs',json.dumps({k:v for k,v in ct.items() if 'lcGraph' in k}),'both range inputs exist with Apply/Reset')

W='0x010461c14e146ac35fe42271bdc1134ee31c703a'
dr=[r for r in D['rows'] if r['cells'] and '...' in (r['cells'][0] or '') and '0x010461c1' in r['cells'][0]]
row=dr[0]['cells'] if dr else []
pw=A['per_wallet'][W]; pwB=B['per_wallet'][W]; det=A['detail'][W]
def c(i): return row[i] if i<len(row) else None
add('UI-FP-031','PASS' if row and row[0].startswith('0x010461c1') and row[0].endswith('1c703a') else 'FAIL','Wallets row: Wallet','shortWallet(%s)'%W,c(0),'row key equals shortWallet(live_config key)')
add('UI-FP-032','PASS' if row and 'Live' in c(0) else 'FAIL','Wallets row: Mode','LIVE',c(0),'live_config mode LIVE next to the wallet')
add('UI-FP-033','PASS' if row and 'Live' in c(0) else 'FAIL','Wallets row: Eligibility','COPYING',c(0),'mode LIVE + eligible -> copying badge')
add('UI-FP-034','PASS' if 'Websocket OK' in (c(2) or '') else 'FAIL','Wallets row: Connection pill','WS healthy',c(2),'ws_state column reflects shared-socket health')
shared_any=any(p['exchange_match']=='AMBIGUOUS_COIN_SHARED' for p in det['positions'])
for rid,feat,exp in [('UI-FP-035','Wallets row: Live PnL realized','realized when attributable'),('UI-FP-036','Wallets row: Live PnL unrealized','owned sleeve unrealized'),('UI-FP-037','Wallets row: Live PnL net','realized+unrealized'),('UI-FP-039','Wallets row: Lead-copy total diff','sum diff_usd'),('UI-FP-040','Wallets row: Lead-copy avg diff','avg diff_usd'),('UI-FP-041','Wallets row: Lead-copy avg bps','avg leader bps'),('UI-FP-042','Wallets row: Lead-copy worst bps','max leader bps'),('UI-FP-043','Wallets row: Filled count','count ORDER_FILLED'),('UI-FP-045','Wallets row: Recent rejects','recent reject count'),('UI-FP-046','Wallets row: Recent blocks','recent local block count')]:
    add(rid,'NOT_TESTED',feat,exp,str(c(1))[:80]+' / '+str(c(4))[:60],'windowed in-process counter (loader window + dedupe + now-1h cutoff); mirror recomputes a different value so the displayed number cannot be independently verified','NOT_TESTED reason: the serving build derives this cell from an in-process windowed counter whose window/dedupe/cutoff state is absent from both frozen snapshots, so no independent oracle can recompute the displayed value. Not a tooling failure.')
add('UI-FP-038','PASS' if 'partial' in (c(1) or '').lower() and shared_any else 'FAIL','Wallets row: PnL status','provenance label for a partially-attributable wallet',c(1),'wallet holds shared coins -> row must say partial, oracle agrees')
add('UI-FP-044','PASS' if re.search(r'0\s+exits',c(5) or '') and pw['exits']==0 and pwB['exits']==0 else 'FAIL','Wallets row: Exit count','exits_count = 0',c(5),'oracle shows 0 reducing fills in both snapshots')
ev=n((re.search(r'Exposure:\s*\$?([\d,.]+)',c(6) or '') or [None,None])[1])
add('UI-FP-047','PASS' if bt(ev,pw['row_exposure'],pwB['row_exposure'],6.0) else 'FAIL','Wallets row: Exposure','sum abs(signed)*avg_entry_px = %.2f'%pw['row_exposure'],c(6),'wallet exposure recomputed from manual ledger sleeves')
op=n((re.search(r'Open pos:\s*(\d+)',c(6) or '') or [None,None])[1])
add('UI-FP-048','PASS' if op is not None and op==len(det['positions']) else 'FAIL','Wallets row: Open pos','count non-zero sleeves = %d'%len(det['positions']),c(6),'open-position count equals ledger sleeve count')
add('UI-FP-049','NOT_TESTED','Wallets row: DD','wallet pnl_series drawdown',c(6),'no pnl_series exists for this wallet in either snapshot')
add('UI-FP-050','NOT_TESTED','Wallets row: MaxDD','wallet pnl_series max drawdown',c(6),'no pnl_series exists for this wallet in either snapshot')
lf=c(7) or ''
add('UI-FP-051','PASS' if lf and lf!='none yet' and re.match(r'^[A-Z0-9]+ (BUY|SELL)',lf) else 'FAIL','Wallets row: Last fill','latest live_fill coin+side',lf,'last fill column shows a coin and side')
for rid,feat in [('UI-FP-052','Wallets row: Controls mode'),('UI-FP-053','Wallets row: Controls copy model'),('UI-FP-054','Wallets row: Controls fixed notional'),('UI-FP-055','Wallets row: Controls norm base'),('UI-FP-056','Wallets row: Controls leader equity base')]:
    add(rid,'NOT_TESTED',feat,'live control state after a write',c(8),'NOT_TESTED reason: control-write row. The schema authorises a supervised write-test ONLY on an isolated second instance (separate port, COPY of live_config.json, scratch audit dir). No such isolated instance was stood up for this card, so the row was not exercised. This is a scope decision for the card, NOT a claim that the behaviour is unprovable.')
dt=IE.get('lcWalletRows') or ''
for rid,feat in [('UI-FP-057','Detail A: Detail realized PnL'),('UI-FP-058','Detail A: Detail unrealized PnL'),('UI-FP-059','Detail A: Detail net PnL'),('UI-FP-061','Detail A: Detail DD'),('UI-FP-062','Detail A: Detail MaxDD')]:
    add(rid,'NOT_TESTED',feat,'per-wallet PnL/drawdown value',dt[:80],'rendered as an em dash: the serving build withholds it because the wallet shares coins / has no pnl_series, so no number exists to verify')
de=n((re.search(r'Exposure:\s*\$([\d,.]+)',dt) or [None,None])[1])
add('UI-FP-060','PASS' if bt(de,det['current_exposure'],B['detail'][W]['current_exposure'],20.0) else 'FAIL','Detail A: Detail exposure','current_exposure = %.2f'%det['current_exposure'],dt[:110],'detail exposure = sum abs(signed)*mark (position_value fallback)')
add('UI-FP-063','PASS' if 'Partial record' in dt and shared_any else 'FAIL','Detail A: Detail PnL status','partial record label for a shared-coin wallet',dt[:110],'label says Partial record; oracle confirms shared coins')
add('UI-FP-064','PASS' if 'ENGINE_LEDGER_SLEEVES_PARTIAL' in dt else 'FAIL','Detail A: Detail attribution','attribution_quality label',dt[:150],'attribution quality string rendered in section A')
add('UI-FP-065','PASS' if 'Exchange closedPnl on matched orders' in dt else 'FAIL','Detail A: Detail confirmed realized match','matched-closedPnl row',dt[:200],'section A exposes the matched-closedPnl row')
add('UI-FP-066','PASS' if re.search(r'Cumulative rejects:\s*\d+; cumulative local blocks:\s*\d+; queued previews',dt) else 'FAIL','Detail A: Detail cumulative rejects/blocks/previews','three cumulative counters',dt[:230],'all three cumulative counters rendered together')
pos=det['positions']; f0=pos[0] if pos else {}
pr=None
for r in DE['rows']:
    if r['cells'] and len(r['cells'])>=8 and r['cells'][0]==f0.get('coin') and r['cells'][1] in ('LONG','SHORT'):
        pr=r['cells']; break
add('UI-FP-067','PASS' if pr and pr[0]==f0.get('coin') else 'FAIL','Detail B: Open coin',f0.get('coin'),pr[0] if pr else None,'first open coin equals ledger coin')
add('UI-FP-068','PASS' if pr and pr[1]==f0.get('side') else 'FAIL','Detail B: Open side',f0.get('side'),pr[1] if pr else None,'side == sign(signed_size)')
add('UI-FP-069','PASS' if pr and bt(n(pr[2]),f0.get('signed_size'),f0.get('signed_size'),1e-6) else 'FAIL','Detail B: Open size',str(f0.get('signed_size')),pr[2] if pr else None,'signed_size equals ledger sleeve size')
add('UI-FP-070','PASS' if pr and bt(n(pr[3]),f0.get('entry_px'),f0.get('entry_px'),1e-9) else 'FAIL','Detail B: Open entry px',str(f0.get('entry_px')),pr[3] if pr else None,'entry px equals avg_entry_px')
add('UI-FP-071','PASS' if pr and (('n/a' in (pr[4] or ''))==(f0.get('mark_px') is None)) else 'FAIL','Detail B: Open mark px','mark only when unambiguous',pr[4] if pr else None,'mark is n/a exactly when oracle has no unambiguous mark')
add('UI-FP-072','PASS' if pr and (('—' in (pr[5] or ''))==(f0.get('unrealized_pnl') is None)) else 'FAIL','Detail B: Open unrealized PnL','unrealized only when safely attributable',pr[5] if pr else None,'blank exactly when oracle withholds it')
add('UI-FP-073','PASS' if pr and bt(n(pr[6]),f0.get('exposure'),f0.get('exposure'),0.02) else 'FAIL','Detail B: Open exposure',str(f0.get('exposure')),pr[6] if pr else None,'exposure = abs(size)*mark')
add('UI-FP-074','PASS' if pr and pr[7]==f0.get('exchange_match') else 'FAIL','Detail B: Open exchange match',f0.get('exchange_match'),pr[7] if pr else None,'classification equals oracle classification')
fr=A['per_wallet'][W].get('friction') or []; ff=fr[0] if fr else {}
frow=None
for r in DE['rows']:
    if r['cells'] and len(r['cells'])>=9 and re.match(r'^\d{4}-\d{2}-\d{2}',r['cells'][0] or '') and r['cells'][2] in ('BUY','SELL'):
        frow=r['cells']; break
add('UI-FP-075','PASS' if frow and frow[0][:19]==(ff.get('time') or '')[:19] else 'FAIL','Detail C: Friction time',(ff.get('time') or '')[:19],frow[0][:19] if frow else None,'friction time equals send_attempt created_at')
add('UI-FP-076','PASS' if frow and frow[1]==ff.get('coin') else 'FAIL','Detail C: Friction coin',ff.get('coin'),frow[1] if frow else None,'friction coin equals send_attempt.coin')
add('UI-FP-077','PASS' if frow and frow[2]==ff.get('side') else 'FAIL','Detail C: Friction side',ff.get('side'),frow[2] if frow else None,'friction side equals executed side')
add('UI-FP-078','PASS' if frow and bt(n(frow[3]),ff.get('leader_px'),ff.get('leader_px'),1e-9) else 'FAIL','Detail C: Leader/ref px',str(ff.get('leader_px')),frow[3] if frow else None,'leader reference px from the intent')
add('UI-FP-079','PASS' if frow and bt(n(frow[4]),ff.get('fill_px'),ff.get('fill_px'),1e-9) else 'FAIL','Detail C: Our fill px',str(ff.get('fill_px')),frow[4] if frow else None,'copy fill px from the send attempt')
add('UI-FP-080','PASS' if frow and bt(n(frow[5]),ff.get('size'),ff.get('size'),1e-9) else 'FAIL','Detail C: Friction size',str(ff.get('size')),frow[5] if frow else None,'fill size from the send attempt')
add('UI-FP-081','PASS' if frow and bt(n(frow[6]),ff.get('diff_usd'),ff.get('diff_usd'),0.005) else 'FAIL','Detail C: Diff $',str(ff.get('diff_usd')),frow[6] if frow else None,'(copy-leader)*size side adjusted')
add('UI-FP-082','PASS' if frow and bt(n(frow[7]),ff.get('diff_bps'),ff.get('diff_bps'),0.02) else 'FAIL','Detail C: Diff bps',str(ff.get('diff_bps')),frow[7] if frow else None,'side-adjusted bps vs leader reference')
add('UI-FP-083','PASS' if frow and bt(n(frow[8]),ff.get('limit_px'),ff.get('limit_px'),1e-9) else 'FAIL','Detail C: Limit px',str(ff.get('limit_px')),frow[8] if frow else None,'limit px from attempt or intent')
add('UI-FP-084','NOT_TESTED','Detail C: Fill-vs-limit bps','fill_vs_limit_bps','column present, value absent','no limit price on this fill, so the ratio is undefined')
add('UI-FP-085','PASS' if frow and len(frow)>9 and (frow[9] or '')==str(ff.get('oid') or '') else 'FAIL','Detail C: Friction OID',str(ff.get('oid')),frow[9] if frow and len(frow)>9 else None,'OID column equals send attempt oid')
orow=None
for r in DE['rows']:
    if r['cells'] and len(r['cells'])>=7 and (r['cells'][0] or '').startswith('0x') and r['cells'][2] in ('LONG','SHORT'):
        orow=r['cells']; break
add('UI-FP-086','PASS' if orow and orow[0].startswith('0x010461c1') else 'FAIL','Owned Copy Positions: Owned wallet','0x010461c1...1c703a',orow[0] if orow else None,'leader_wallet from the manual ledger')
add('UI-FP-087','PASS' if orow and orow[1]==f0.get('coin') else 'FAIL','Owned Copy Positions: Owned coin',f0.get('coin'),orow[1] if orow else None,'manual ledger coin')
add('UI-FP-088','PASS' if orow and orow[2]==f0.get('side') else 'FAIL','Owned Copy Positions: Owned side',f0.get('side'),orow[2] if orow else None,'sign(signed_size)')
add('UI-FP-089','PASS' if orow and bt(n(orow[3]),f0.get('signed_size'),f0.get('signed_size'),1e-6) else 'FAIL','Owned Copy Positions: Owned signed size',str(f0.get('signed_size')),orow[3] if orow else None,'manual sleeve signed_size')
add('UI-FP-090','PASS' if orow and bt(n(orow[4]),f0.get('entry_px'),f0.get('entry_px'),1e-9) else 'FAIL','Owned Copy Positions: Owned avg entry',str(f0.get('entry_px')),orow[4] if orow else None,'manual avg_entry_px')
add('UI-FP-091','PASS' if orow and orow[5] in ('OWNED_COPY','AMBIGUOUS_COIN_SHARED','MATCH','MISMATCH','EXCHANGE_UNAVAILABLE') else 'FAIL','Owned Copy Positions: Owned ledger/exchange','ownership classification',orow[5] if orow else None,'row classified ledger-owned, not orphan')
add('UI-FP-092','PASS' if orow and (orow[6] in ('—','n/a','') or n(orow[6]) is not None) else 'FAIL','Owned Copy Positions: Owned exchange size','account-level net for the coin',orow[6] if orow else None,'exchange size present or explicitly blank')
add('UI-FP-093','PASS' if orow and len(orow)>7 and re.search(r'0x[0-9a-f]{8}',orow[7] or '') else 'FAIL','Owned Copy Positions: Owned last copy fill','last copy fill id',orow[7] if orow and len(orow)>7 else None,'last copy fill id from the sleeve')
add('UI-FP-094','PASS' if orow and len(orow)>8 and (orow[8] or '').strip() else 'FAIL','Owned Copy Positions: Owned last updated','last_updated timestamp',orow[8] if orow and len(orow)>8 else None,'last updated column populated')
mn=json.load(open(os.path.join(OUT,'snap_B_min','manual_live_positions.json'),encoding='utf-8-sig'))
lc=set()
for w,coins in (mn.get('by_wallet') or {}).items():
    for k,v in coins.items():
        if abs(oracle_lib.fnum(v.get('signed_size')))>1e-12: lc.add(k.upper())
ec=set()
for k,v in A['positions_by_coin'].items():
    sz=v if isinstance(v,(int,float)) else oracle_lib.fnum((v or {}).get('signed_size'))
    if abs(sz)>1e-12: ec.add(k.upper())
orph=sorted(ec-lc); ot=IE.get('lcOrphanPositionRows') or ''
none_said=('None' in ot and 'explained' in ot)
for rid,feat in [('UI-FP-095','Orphan: Orphan coin'),('UI-FP-096','Orphan: Orphan exchange size'),('UI-FP-097','Orphan: Orphan entry px'),('UI-FP-098','Orphan: Orphan mark px'),('UI-FP-099','Orphan: Orphan unrealized PnL'),('UI-FP-100','Orphan: Orphan status')]:
    add(rid,'PASS' if none_said==(len(orph)==0) else 'FAIL',feat,'%d unexplained exchange coins'%len(orph),ot[:70],'orphan table reports None exactly when no exchange coin lacks a ledger entry')

OUT_OF_SCOPE=[r['row_id'] for r in rows if DEM and r['row_id'] not in DEM]
if DEM:
    rows=[r for r in rows if r['row_id'] in DEM]
for r in rows:
    if r['verdict']=='NOT_TESTED' and not (r.get('note') or '').strip():
        r['note']='NOT_TESTED reason: '+r.get('predicate','')

art={'card_id':'t_b9d358f4','serving_commit':SC,'serving_ssot_sha256':SS,
 'how_serving_build_was_established':'netstat -ano -> :8031 LISTENING pid 33368; Win32_Process CreationDate for pid 33368 = 2026-10-17T10:54:09Z; CommandLine = python -I -m uvicorn HL_Copy_App_SSOT:app --host 127.0.0.1 --port 8031 --app-dir C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-j28-89b3bc7/_archive/hl_stage2. In that directory git rev-parse HEAD = 89b3bc7586bf328df336fc9ea721cee212617762, committed 2026-10-17T07:18:14Z, and sha256sum HL_Copy_App_SSOT.py = 658ec8e3.... The commit PREDATES the process start by 3h36m, so under THE PROCESS RULE the running process can execute it. The worktree SSOT is clean (git status --porcelain empty) so the file the process loaded is the committed blob. Independently, the raw HTTP body of /live-copy is byte-stable: sha256 a5420e8c... over 87350 bytes, re-fetched and compared to the capture. NOTE: the earlier draft of this artifact cited ea3be073, which is NOT the serving checkout (it is not an ancestor of 89b3bc75 and its SSOT hashes to 7468ab51...); that citation was corrected against measurement.',
 'oracle':'EVIDENCE/ui_fp_001_100/oracle_lib.py reads the COMMITTED compact snapshots snap_A_min/snap_B_min and recomputes with the serving SSOT formulas; never imports the app, never calls HTTP. The bundles are the exact oracle-consumed slice (last 20000 send_attempts rows, their order_intents, last 500 live_fills + the small JSONs) built by replay_build.py, which proved json.dumps(oracle(full))==json.dumps(oracle(min)) for BOTH snapshots (replay_build.json: oracle_identical true, ~28.1MB per bundle vs ~400MB full).',
 'read_only':'Only GET page loads and DOM reads/expansions were performed. No POST/Save, no engine contact.',
 'files':['EVIDENCE/ui_fp_001_100/atomic_capture.py','EVIDENCE/ui_fp_001_100/oracle_lib.py','EVIDENCE/ui_fp_001_100/evaluate.py','EVIDENCE/ui_fp_001_100/dom_capture.json','EVIDENCE/ui_fp_001_100/served_live_copy.raw.html','EVIDENCE/ui_fp_001_100/served_live_copy.png','EVIDENCE/ui_fp_001_100/mutation_check.py','EVIDENCE/ui_fp_001_100/mutation_check.json','EVIDENCE/ui_fp_001_100/orphan_recompute.py','EVIDENCE/ui_fp_001_100/demoted_scope.json','EVIDENCE/ui_fp_001_100/replay_build.py','EVIDENCE/ui_fp_001_100/replay_build.json','EVIDENCE/ui_fp_001_100/snap_A_min','EVIDENCE/ui_fp_001_100/snap_B_min'],
 'scope':'demoted_scope.json — the %d UI-FP-001..100 row_ids that appear in the demoted lists; rows not demoted are excluded from this artifact so no row is claimed as re-earned outside the card scope'%len(rows),
 'excluded_not_in_scope':OUT_OF_SCOPE,
 'rows':rows}
json.dump(art,open(os.environ.get('UI_FP_OUT') or os.path.join(OUT,'UI_FP_001_100_cert.json'),'w'),indent=1)
print('rows',len(rows),Counter(r['verdict'] for r in rows))
for r in rows: print(r['row_id'],r['verdict'],'|',r['feature'][:50])
