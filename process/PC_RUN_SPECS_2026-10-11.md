# PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)

**Task:** round J, job J4 (spec: `PARALLEL_JOBS.md` §J4). For the five gaps named in the engine-thread
handover comment `#issuecomment-6106236565` — outage recovery, memory live, liquidation parity vs the
exchange `liquidationPx`, realistic-load latency (Phase R), disk-full — write one PC run script spec each:
exact command, expected pass line, what to attach. **Doc only**: no engine code is edited by this job, no
run happens here.

**Repo / commit:** `binancebotty-bot/hyperliquid-build3-repair`, fresh clone of `main` @
`5e88e89c8dd8c2248475b89b177d1bc50e195e1f` (>= the `5e88e89` the envelope named; `core.autocrlf=false`).
**Branch:** `hermes/j4-matrix`. **Produced by:** hermes:implementation-owner, offline, 2026-10-11.

**Relation to the sibling doc on this branch.** `process/PC_RUN_SCRIPTS_2026-10-11.md` (commit `60017c1`, a
second hermes:implementation-owner worker) is the *script-reuse map* for the same five gaps; this file is the
*self-contained spec*: every gap carries the full paste-able command, a deterministic `GAP<n>_RESULT::` verdict
line with its pass criterion, and the attach list, plus `_archive/hl_stage2/test_j4_pc_run_specs.py` which fails
if any of the five is incomplete. Use both: the sibling for which existing `run5/run7/run8/test9-11` script to
reuse, this one for what to run and what a PASS is. (New evidence can go to `run9/` per the sibling; the paths
below use the existing `run5/` logs and helpers.)

**Source of the "five gaps" (the 2026-10-11 matrix was NOT in the repo).** The handover comment names
`/mnt/project-files/process/CERTIFICATION_MATRIX_2026-10-11.md` (20 rows) — a Claude-side path, not
committed. `git log --all --name-only` over every remote branch finds only
`process/CERTIFICATION_MATRIX_2026-10-10.md` (14 rows, F2) and `certification/*`. Per the envelope
("if absent, use certification/ files in the repo") this spec is built from:
`process/CERTIFICATION_MATRIX_2026-10-10.md` (rows 1–14 + "Top 5 gaps"), `certification/MATRIX_WALK_2026-10-10.md`,
`certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md`, `certification/RUN_STATUS.md`,
`certification/run_results.json`, and the run evidence in
`C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/` (RUN1/run3/run4/run5, delegation/*).

**Graphify usage (one line).** `graphify-out` was stale and did **not** contain the engine file at all
(`grep -c HL_Live_Copy_Service_Core.py graphify-out/graph.json` → 0), so I ran
`<PY311> -m graphify update .` (rebuilt: 1,842 nodes / 5,229 edges, Core now 2,682 mentions) and then used
it to jump straight to the symbols the five gaps touch — `.liq_parity_block()` L3758 and
`._follower_projected_liq_px()` L3729, `AuditLogWriter` L3100 / `.append_reconciliation()` L3167,
`append_csv()`/`read_csv_rows()` L1078, `test_core_liq_parity.py`, `test_core_outage_replay.py` — instead of
grepping a 659 KB module cold.

**Model per part.** Every part (spec read, graphify navigation, all five scripts, this doc) was done
in-session by **deepseek-flash** (the deepseek route). A worker split was attempted and is **not available on
this host**: `python C:/Users/wigmore/.codex/local_offload_router.py --json "<tiny probe>"` returns
`{"engine":"primary","model":"none","blocked":true,"reason":"no preferred local Ollama model is installed
or reachable"}` — no local/free backend reachable, and the config delegation model is excluded by this
round's rules and must not be changed. Flagged as an environment gap, not an ACK.

**Safety (this job).** Offline only. Nothing in
`C:/Users/wigmore/trading_stack/hl-build3-testnet-cert` was touched, the running engine was not signalled,
ports 8012/8014/8031 were not used, the Wallet Finder was not read or run, no keys/.env were opened or
printed, no orders, no WebSocket subscriptions. Every command below is written for **the PC operator** to
run later in one batch against the testnet follower.

---

## Common preamble (applies to every gap)

```bash
# ON THE PC. Testnet follower only. Never print/copy the key.
CERT=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert          # the RUNNING cert checkout (PC-owned)
AUD=$CERT/_archive/hl_stage2/hl_live_copy_audit_testnet            # engine audit dir
CFG=$AUD/live_config.json                                          # auto_send_enabled lives here
EV=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run5   # logs + helpers
PY311=/c/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe
LOG=$EV/engine_5e88e89.log                                         # one log name per commit
```

- **Start the engine** (after `git pull`, the PC is on `main`): from `$CERT/_archive/hl_stage2`
  `source ../run_env.sh && export HL_LIVE_HOT_SEND_WORKERS=12 && python HL_Live_Copy_Service_Core.py --ws --loop --interval 10 --poll-live --poll-copy > $LOG 2>&1 &`
  (background task; the UI on :8031 is read-only). Start with `auto_send_enabled=false` and arm later —
  never start armed. A fresh state folder is required per run, or backlog fills since the last start get traded.
- **Arm / disarm** (atomic, the pattern already used in `run5/test10a.sh`): rewrite `$CFG` `auto_send_enabled`
  to `true`/`false` via a temp file + `os.replace`, and append one line to `$EV/armed.txt` with the UTC time,
  the commit and the run name.
- **Independent check before arming** (never trust the engine's own summary):
  `cd $EV && python -I verify.py <armed_ms>` must print `RESULT:: MATCH at HH:MM:SSZ`. `MISMATCH` = do not arm.
- **Disarm before you stop or kill anything**, in every gap script (`auto_send_enabled=false`, then stop).
- **Latency/one-shot helpers already on the PC** (reuse, do not re-author):
  `$EV/lat_stamps.py <armed_ms_file>` (per-stage stamps vs leader fill time), `$EV/metrics.py <armed_ms>`
  (one JSON line: hourly latency, caps, resting entry orders, dust, copy-poll lag),
  `$EV/outage_analysis.py` (reads `outage_stop_ms.txt`/`outage_restart_ms.txt`),
  `$EV/../verify.py`, `$EV/../acct_snapshot.py <testnet|mainnet> <dex...>`.
- **Batch order on the PC** (one sitting, ~5 h wall): GAP-2 (memory, 60 min) → GAP-4 (Phase R, 60–120 min,
  can be the *same* run: same 3 leaders, the memory sampler runs alongside) → GAP-1 (outage, ~25 min) →
  GAP-3 (liq parity, read-only, 5 min, needs a position open) → GAP-5 (disk-full, offline suite + VHDX
  cycle, ~20 min, **needs elevation**).
- **Every run must carry `PYTHON*` scrubbed or the run is an instrument failure, not a product failure.**
  Under an inherited `PYTHONPATH`, 13 of 43 repo tests abort with
  `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'` (the F2 two-run control). Use
  `env -u PYTHONPATH -u PYTHONHOME` for every offline suite below.
- **Offline suite convention** (so the PC can batch the "already proven" parts too), from
  `$CERT/_archive/hl_stage2`: `env -u PYTHONPATH HL_LIVE_ENV_FILE=/nonexistent <PY311> -u <test>.py`;
  expect `RESULT::<NAME>_PASS` lines and a final `TOTAL=<n> FAILED=0`.

| gap | already proven offline (repo test, green) | PC proof needed | wall | elevation |
|---|---|---|---|---|
| 1 outage recovery | `test_core_outage_replay.py` 17/17 | controlled 2-min outage + coverage count | ~25 min | no |
| 2 memory live | `tools_memory_profile.py` (tool); `test_core_memory_bounds.py` 16/16 | 60-min live RSS + rotation/real-file sizes | ~60 min | no |
| 3 liquidation parity vs exchange | `test_core_liq_parity.py` 10, `test_core_liq_projection.py` 6, `test_core_liquidation.py` 9, `test_core_liq_isolated.py` | exchange `liquidationPx` vs follower position | ~5 min | no |
| 4 realistic-load latency (Phase R) | none (this is the headline live number) | 60–120 min with the E1 3-leader cohort | ~60–120 min | no |
| 5 disk-full | J1 (branch `hermes/j1-diskfull`), pending | real ENOSPC on a bounded volume | ~20 min | **yes (diskpart)** |

---

## GAP-1 · outage recovery

**Why it is a gap.** Row 4 (WS+poll catch-up) and row 6 (idempotent replay) of the 10-10 matrix are
mock-only on current main. The one *live* outage test (run5, `fc7efd7`, comment-documented in
`run5/OUTAGE_RESULT_fc7efd7.txt`) showed real loss: of 1,013 leader fills in the 120 s outage, **720 had no
engine row at all**, and replay sends after restart ran from 38 s to a median 215 s / last 606 s. The R1
cursor fix (PR #30) is mock-only; the offline outage replay (`test_core_outage_replay.py`, 17/17, 300 fills
over 20 coins) proves the mechanism, not the coverage on a live leader burst.

- **offline proof (already green, PC can re-run it):**
  `env -u PYTHONPATH HL_LIVE_ENV_FILE=/nonexistent <PY311> -u test_core_outage_replay.py` →
  `RESULT::EVERY_FILL_ENDS_IN_EXACTLY_ONE_TERMINAL_ROW_PASS` … `TOTAL=17 FAILED=0`

- **exact command:** paste as `$EV/gap1_outage.sh` and run `bash $EV/gap1_outage.sh`
```bash
set -u
CERT=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert
AUD=$CERT/_archive/hl_stage2/hl_live_copy_audit_testnet; CFG=$AUD/live_config.json
EV=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run5; L=$EV/engine_5e88e89.log
setarm() { python -I -c "
import json,os,sys;p=sys.argv[1];d=json.load(open(p,encoding='utf-8'));d['auto_send_enabled']=(sys.argv[2]=='1')
t=p+'.tmp';open(t,'w',encoding='utf-8').write(json.dumps(d,indent=2));os.replace(t,p)" "$CFG" "$1"
  echo "$(date -u +%FT%TZ) auto_send=$1 gap1 $2" >> $EV/armed.txt; }
cd $EV
for i in $(seq 1 240); do b=$(grep -o '"send_backlog": [0-9]*' $L | tail -1 | grep -o '[0-9]*$'); [ -n "${b:-}" ] && [ "$b" -lt 50 ] && break; sleep 15; done
ok=0; for k in 1 2 3 4 5 6 7 8; do r=$(timeout 150 python -I verify.py 1791603649258 | grep RESULT); case "$r" in *"RESULT:: MATCH"*) ok=1; break;; esac; sleep 20; done
[ $ok = 1 ] || { echo "GAP1_RESULT:: FAIL not_armed_verify"; exit 1; }
setarm 1 "gap1 armed, normal traffic first"; sleep 300
setarm 0 "gap1 disarm before stop"; sleep 30
PID=$(python -c "
import psutil
print(' '.join(str(p.pid) for p in psutil.process_iter(['name','cmdline'])
      if (p.info['name'] or '').startswith('python') and 'HL_Live_Copy_Service_Core.py' in ' '.join(p.info['cmdline'] or [])))")
echo "engine pid(s)=$PID"; date -u +%s%3N > outage_stop_ms.txt
for p in $PID; do python -c "import psutil,sys;psutil.Process(int(sys.argv[1])).kill()" $p; done   # explicit PIDs only
sleep 120; date -u +%s%3N > outage_restart_ms.txt
setarm 1 "gap1 armed restart"
cd $CERT/_archive/hl_stage2 && source ../run_env.sh && export HL_LIVE_HOT_SEND_WORKERS=12 \
  && exec python HL_Live_Copy_Service_Core.py --ws --loop --interval 10 --poll-live --poll-copy >> $L 2>&1
```
then, 15 min after the restart:
```bash
cd $EV && python -I outage_analysis.py | tee gap1_outage_analysis.txt
python -I outage_missed_detail.py | tee gap1_missed_detail.txt
python -I verify.py 1791603649258 | grep -E "MISMATCH|oids|RESULT"
# one deterministic verdict line:
miss=$(grep -o 'no engine row (missed): [0-9]*' gap1_outage_analysis.txt | grep -o '[0-9]*$')
dup=$(grep -o 'replayed twice.*: [0-9]*' gap1_outage_analysis.txt | grep -o '[0-9]*$'); dup=${dup:-0}
last=$(grep -o 'last [0-9]*s' gap1_outage_analysis.txt | grep -o '[0-9]*'); last=${last:-0}
if [ "${miss:-1}" -eq 0 ] && [ "$dup" -eq 0 ]; then echo "GAP1_RESULT:: PASS missed=0 duplicates=0 replay_last_s=$last"
else echo "GAP1_RESULT:: FAIL missed=$miss duplicates=$dup replay_last_s=$last"; fi
```

- **expected pass line:** `GAP1_RESULT:: PASS missed=0 duplicates=0 replay_last_s=<n>`
  Pass = **every** leader fill in the outage window ends in an engine row (sent / skipped-with-reason /
  resting diff) **and** no leader order is sent twice. `replay_last_s` is recorded, not gated — run5's 606 s
  says coverage is the defect; the R1 cursor's job is that nothing is *lost*. Also required:
  `RESULT:: MATCH at …` from `verify.py` after the restart.
- **attach:** `gap1_outage_analysis.txt` (the counter table + missed examples), `gap1_missed_detail.txt`,
  the `RESULT:: MATCH` line, the post-restart engine log tail (`grep -E "REBUILD|cursor|catchup" $L | tail -50`),
  `outage_stop_ms.txt`/`outage_restart_ms.txt`, `armed.txt`.
- **notes/risks:** disarm *before* the kill (a queued-but-unsent order after a sudden stop is a separate
  invariant). Kill by the explicit PID the cmdline match printed — never by name/wildcard. Fills for coins
  in `symbol_blocklist` are "blocked by design" and are not misses.

## GAP-2 · memory live (flat RSS on current main)

**Why it is a gap.** The M1 profile found and *fixed* `send_attempt_rows` (1,172 → 102 MB retained) and
`_owned_fill_size` (2,087 MB / 3.9 s → 0 MB / 26 ms) on the then-main, and named the **remaining** driver:
`ExchangeReconciler.audit_orphan_attribution` still reads and parses all of `reconciliation.csv` every
cycle — peak 3,253 MB and 18.2 s at a 200 MB file (≈16× the file), un-fixed on current main. The only live
datapoint (`run5/PHASE_R.txt`) is RSS 0.59 → 0.91 GB over 2 h, but that run produced 2 copies and its
`reconciliation.csv` was small — so "flat" is not yet proven at the file sizes a busy day produces.

- **offline proof (already green):** `env -u PYTHONPATH HL_LIVE_ENV_FILE=/nonexistent <PY311> -u test_core_memory_bounds.py`
  (16 checks: rotation at the limit, newest kept, no middle loss, `send_attempts` not rotated) →
  `TOTAL=16 FAILED=0`; plus `<PY311> -u tools_memory_profile.py` re-measured at the run's real file sizes.

- **exact command:** paste as `$EV/gap2_memory.sh` and run `bash $EV/gap2_memory.sh` (60 min; can run
  alongside GAP-4 on the same armed run)
```bash
set -u
CERT=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert
AUD=$CERT/_archive/hl_stage2/hl_live_copy_audit_testnet; CFG=$AUD/live_config.json
EV=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run5; L=$EV/engine_5e88e89.log; O=$EV/GAP2_MEMORY.txt
rss() { python -c "
import psutil,time
for p in psutil.process_iter(['cmdline','memory_info']):
    c=p.info['cmdline'] or []
    if len(c)>1 and c[1].endswith('HL_Live_Copy_Service_Core.py'):
        print(time.strftime('%H:%M:%S'),'engine RSS',round(p.info['memory_info'].rss/1e9,3),'GB')"; }
: > $O
[ -f $EV/gap4_armed_ms.txt ] || { echo "start+arm the engine first (see GAP-4 / preamble)" >&2; exit 1; }
for m in $(seq 1 12); do sleep 300; rss | tee -a $O; done      # 12 x 5 min = 60 min
echo "== audit file sizes / rotation" >> $O
ls -l $AUD/append_only/*.csv | awk '{print $5, $9}' | sort -rn | head -20 >> $O
echo "== copy-poll + caps + dust" >> $O
python -I $EV/metrics.py "$(cat $EV/gap4_armed_ms.txt)" >> $O
first=$(awk '/engine RSS/{print $4; exit}' $O); last=$(awk '/engine RSS/{print $4}' $O | tail -1)
max=$(awk '/engine RSS/{print $4}' $O | sort -rn | head -1)
recon=$(ls -l $AUD/append_only/reconciliation.csv 2>/dev/null | awk '{print $5}'); recon=${recon:-0}
delta=$(python -c "print(round($last-$first,3))")
verdict=$(python -c "print('PASS' if ($delta<=0.5 and $max<2.0 and $recon<104857600) else 'FAIL')")
echo "GAP2_RESULT:: $verdict rss_first_gb=$first rss_last_gb=$last rss_max_gb=$max delta_gb=$delta recon_bytes=$recon"
```

- **expected pass line:** `GAP2_RESULT:: PASS …` with **`delta_gb <= 0.5`** over 60 min, **`rss_max_gb < 2.0`**
  **and `recon_bytes < 100 MB`**. The third term is the real gate: if `reconciliation.csv` reaches 100 MB the
  unfixed `audit_orphan_attribution` transient (~16× the file ≈ 1.6 GB peak, per cycle) is still armed on
  main and GAP-2 is FAIL regardless of a flat RSS — the peak is a per-cycle high-water mark that Windows
  keeps in RSS (it is the one remaining unfixed driver from M1). The `metrics.py` JSON must also show
  `send_lock_hold_ms_max` and `copy_poll.lag_max_ms` for the same run.
- **attach:** `GAP2_MEMORY.txt` (12 timestamped RSS samples + file sizes + the metrics JSON), the
  `tools_memory_profile.py` table recomputed at the real `reconciliation.csv` size, the `test_core_memory_bounds.py`
  tail, and any `*.20261*.csv` rotated files (proof rotation fired).
- **notes/risks:** sample RSS with `psutil` (never spawn `tasklist`/console tools per tick — that is the
  focus-stealing pattern this project bans). `metrics.py` prints `dust_positions_below_min` and
  `resting_entry_orders` too, which GAP-4 needs.

## GAP-3 · liquidation parity vs the exchange `liquidationPx`

**Why it is a gap (with the exact defect).** Row 8 is the head commit's own feature and has never touched a
live account. Worse, graphify + a read of the Core show the "exchange-reported" half is **unwired**:
`._follower_projected_liq_px()` (L3729) prefers `EXCHANGE_ACCOUNT_SNAPSHOT_FILE`'s
`snapshot["liquidation_px_by_coin"][coin]` with reason `"exchange-reported"`, but the only writer of that
file — `ExchangeReconciler.fetch_snapshot()` (L7806–7819) — writes just
`{"created_at", "created_at_ms", "raw", "positions_by_coin"}`. So the gate always falls through to the
internal projection (`crossMarginSummary` + `crossMaintenanceMarginUsed` + a `maxLeverage or 10` default)
and is never checked against what the exchange actually reports. Second sub-gap: an **ADD** to an open
isolated-only position `LIQ_PARITY_BLOCKED`s by design ("not provable yet", L3764–3769).

- **offline proof (already green):** from `$CERT/_archive/hl_stage2`,
  `for f in test_core_liq_parity.py test_core_liq_projection.py test_core_liquidation.py test_core_liq_isolated.py test_core_adl.py; do env -u PYTHONPATH HL_LIVE_ENV_FILE=/nonexistent <PY311> -u $f; done` →
  each ends `TOTAL=<n> FAILED=0` (10, 6, 9, …, 11 checks).

- **exact command:** paste as `$EV/gap3_liqparity.py` and run `python -I $EV/gap3_liqparity.py` (read-only)
```python
import csv, json, sys
from pathlib import Path
import requests
A = "0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205"                       # follower (testnet), the registered user
T = "https://api.hyperliquid-testnet.xyz/info"; M = "https://api.hyperliquid.xyz/info"
AUD = Path(r"C:\Users\wigmore\trading_stack\hl-build3-testnet-cert\_archive\hl_stage2\hl_live_copy_audit_testnet")

def post(u, p):
    return requests.post(u, json=p, timeout=10).json()

mids = post(T, {"type": "allMids"})
cfg = json.loads((AUD / "live_config.json").read_text(encoding="utf-8")); W = cfg["wallets"]
leaders = list(W.keys()) if isinstance(W, dict) else [w.get("address") or w.get("wallet") for w in W]
ldist = {}
for w in leaders:                                                      # read-only, leader side is mainnet
    st = post(M, {"type": "clearinghouseState", "user": w})
    for ap in st.get("assetPositions", []):
        p = ap["position"]; c = p["coin"]; l = float(p.get("liquidationPx") or 0); m = float(mids.get(c) or 0)
        if m > 0:
            d = abs(m - l) / m if l > 0 else 0.25                      # no liq price = fully collateralised = floor
            ldist[c] = max(ldist.get(c, 0.0), d)                       # the SAFEST leader is the bar
cs = post(T, {"type": "clearinghouseState", "user": A})
n = miss = 0; worst = 1.0; violated = []
for ap in cs.get("assetPositions", []):
    pos = ap["position"]; c = pos["coin"]; szi = float(pos["szi"]); l = float(pos.get("liquidationPx") or 0)
    m = float(mids.get(c) or 0)
    if m <= 0 or l <= 0 or c not in ldist:
        miss += 1; print("%-10s szi=%+.6f exchange_liq_px=%g <- UNCHECKED" % (c, szi, l)); continue
    f = abs(m - l) / m; n += 1; ratio = f / ldist[c] if ldist[c] else 1.0
    worst = min(worst, ratio)
    if ratio < 1.0 - 1e-9:
        violated.append(c)
    print("%-10s szi=%+.6f exchange_liq_px=%g mark=%g follower=%6.2f%% safest_leader=%6.2f%% %s"
          % (c, szi, l, m, f * 100, ldist[c] * 100, "OK" if ratio >= 1 else "PARITY_VIOLATED"))
snap = json.loads((AUD / "exchange_account_snapshot.json").read_text(encoding="utf-8"))
wired = bool(snap.get("liquidation_px_by_coin"))
blocked = sum(1 for r in csv.DictReader(open(AUD / "append_only" / "reconciliation.csv", encoding="utf-8"))
              if "LIQ_PARITY" in (r.get("reject_category") or "") or "LIQ_PARITY" in (r.get("status") or ""))
ok = (not violated) and n > 0
print("GAP3_RESULT:: %s positions_checked=%d unchecked=%d worst_margin_ratio=%.3f"
      % ("PASS" if ok else "FAIL", n, miss, worst))
print("GAP3_GAP:: WIRING exchange_reported_liquidation_px_used=%s snapshot_keys=%s "
      "liq_parity_blocked_rows=%d -> propose populating liquidation_px_by_coin in ExchangeReconciler.fetch_snapshot"
      % (wired, sorted(snap), blocked))
sys.exit(0 if ok else 1)
```

- **expected pass line:** `GAP3_RESULT:: PASS positions_checked=<n> unchecked=<m> worst_margin_ratio=<r>`
  Pass = for **every** open follower position, `follower_dist >= safest_leader_dist` measured on the
  **exchange's own** `clearinghouseState … position.liquidationPx` (not a projection). `unchecked` must be 0
  for a verdict to count (a position with no exchange liq price or no leader counterpart is reported, not
  silently passed). The `GAP3_GAP:: WIRING …` line is a **finding to attach**, not a gate — it is expected
  to read `exchange_reported_liquidation_px_used=False` until the snapshot writer is fixed.
- **attach:** the per-position table, the `GAP3_GAP::` line, `exchange_account_snapshot.json`'s key list,
  the `LIQ_PARITY_BLOCKED` row count since arm, the engine log lines for parity (`grep -i liq_parity $LOG | tail -20`),
  and a proposed one-hunk patch diff for `fetch_snapshot` (engine thread applies it; J4 does not).
- **notes/risks:** runs only when a position is actually open; else it reports `positions_checked=0` and
  `INCONCLUSIVE_NO_POSITION`. Mainnet reads are leader-side only and read-only (the E1 pattern, ≤1 req/s).

## GAP-4 · realistic-load latency (Phase R)

**Why it is a gap.** The headline number (Boss's real cohort ≈100–200 trades/day) has never been measured on
current main. `LATENCY_AB_PLAN.md` §6 is the spec; the only Phase R attempt (`run5/PHASE_R.txt`) produced
**2 copies in 2 h** and therefore no p50/p90 — the earlier numbers (exchange call p50 1.0 s / p90 3.3 s on
testnet) come from the 10-busiest-leader stress run, not the realistic cohort. Judge against: detection
< 1 s with the feed (< 8 s with the poll for 3 leaders); everything **after** detection < 2 s on testnet.

- **offline proof:** none by design — this gap *is* the missing live measurement. (The hot-path bench
  `test_hotpath_replay_bench.py` is currently FAILED=3/7 for unrelated structural reasons, recorded in the
  10-10 matrix as a separate top gap; do not cite it as a latency proof.)

- **exact command:** the cohort is the 3 E1 picks (165 orders/24 h together, human-paced, ≥5 orders in the
  last 6 h each — `delegation/E1_PHASE_R_LEADERS.md`):
  `0x7bc5239180bea2255f4dd243d79481d39adee41e`, `0x1f4ab7e9acebb8b591e74b81e34bebe8be9bc934`,
  `0xcbe834386b8ec9d8c50eaad48dacb83e8b42ddfc`.
```bash
set -u
CERT=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert
AUD=$CERT/_archive/hl_stage2/hl_live_copy_audit_testnet; CFG=$AUD/live_config.json
EV=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run5; L=$EV/engine_5e88e89_phaser.log; O=$EV/GAP4_PHASE_R.txt
cp -n $CFG $CFG.gap4bak                                     # back up ONCE; restored at the end
# 1) narrow the cohort to the 3 human-paced leaders in the live config (same caps, stays disarmed)
python -I - "$CFG" <<'PY'
import json,os,sys
p=sys.argv[1]; d=json.load(open(p,encoding='utf-8')); d['auto_send_enabled']=False
picks={'0x7bc5239180bea2255f4dd243d79481d39adee41e','0x1f4ab7e9acebb8b591e74b81e34bebe8be9bc934',
       '0xcbe834386b8ec9d8c50eaad48dacb83e8b42ddfc'}
W=d.get('wallets')
if isinstance(W,dict): d['wallets']={k:v for k,v in W.items() if k.lower() in picks} or W
else: d['wallets']=[w for w in W if (w.get('address') or w.get('wallet') or '').lower() in picks] or W
t=p+'.tmp'; open(t,'w',encoding='utf-8').write(json.dumps(d,indent=2)); os.replace(t,p)
print('GAP4 cohort wallets:', [w if isinstance(w,str) else w.get('address') or w.get('wallet') for w in d['wallets']])
PY
# 2) start main with that config (fresh state folder), wait for drain, verify, arm, run 60 min
cd $CERT/_archive/hl_stage2 && source ../run_env.sh && export HL_LIVE_HOT_SEND_WORKERS=12 \
  && python HL_Live_Copy_Service_Core.py --ws --loop --interval 10 --poll-live --poll-copy > $L 2>&1 &
sleep 200
python -I -c "
import json;s=json.load(open(r'$AUD/live_ws_health.json'))['ws_summary']
print('WS',{k:s.get(k) for k in ('ws_status','subscribe_acked','wallets_without_feed','last_refusal')})" | tee $O
for i in $(seq 1 240); do b=$(grep -o '"send_backlog": [0-9]*' $L | tail -1 | grep -o '[0-9]*$'); [ -n "${b:-}" ] && [ "$b" -lt 50 ] && break; sleep 15; done
cd $EV; r=$(timeout 150 python -I verify.py 1791603649258 | grep RESULT); echo "verify $r" | tee -a $O
python -I -c "
import json,os,sys;p=sys.argv[1];d=json.load(open(p,encoding='utf-8'));d['auto_send_enabled']=True
t=p+'.tmp';open(t,'w',encoding='utf-8').write(json.dumps(d,indent=2));os.replace(t,p)" "$CFG"
date -u +%s%3N > $EV/gap4_armed_ms.txt; echo "$(date -u +%FT%TZ) gap4 PhaseR armed 5e88e89 3 leaders" >> $EV/armed.txt
sleep 3600                                                   # 1 h (extend to 7200 if copies < 5)
python -I $EV/lat_stamps.py $EV/gap4_armed_ms.txt | tee -a $O
python -I $EV/metrics.py "$(cat $EV/gap4_armed_ms.txt)" | tee -a $O
python -I $EV/lat_stamps.py $EV/gap4_armed_ms.txt | python -c "
import sys,re
t=sys.stdin.read(); m=re.search(r'copies (\d+)',t); n=int(m.group(1)) if m else 0
def p50(name):
    for ln in t.splitlines():
        s=ln.strip()
        if not s.startswith(name):              # names contain spaces: 'leader->exch done'
            continue
        nums=[x for x in s[len(name):].split() if re.fullmatch(r'-?\d+(?:\.\d+)?',x)]
        if len(nums)>=3:                        # n, p50[, p90], max  -> p50 = 2nd from the end
            return int(float(nums[-2] if len(nums)==3 else nums[-3]))
    return None
det=p50('leader->enqueued'); done=p50('leader->exch done')   # detection vs the whole tail
if n<5 or det is None:
    print('GAP4_RESULT:: INCONCLUSIVE_LOW_N copies=%d (need >=5 for a p50; extend the run)' % n)
else:
    tail=(done-det) if done is not None else None
    ok = det<8000 and (tail is not None and tail<2000)
    print('GAP4_RESULT:: %s copies=%d detect_p50_ms=%s post_detect_p50_ms=%s' % ('PASS' if ok else 'FAIL', n, det, tail))"
python -I $EV/../verify.py 1791603649258 | grep -E "MISMATCH|oids|RESULT" | tee -a $O
[ -f $CFG.gap4bak ] && cp $CFG.gap4bak $CFG && echo "restored $CFG" >> $O
```

- **expected pass line:** `GAP4_RESULT:: PASS copies=<n> detect_p50_ms=<d> post_detect_p50_ms=<t>` with
  `copies >= 5`, `detect_p50_ms < 8000` (poll fallback for 3 leaders; < 1000 if the feed is acked) and
  `post_detect_p50_ms < 2000` (everything after detection on testnet). If fewer than 5 copies arrive, the
  honest line is `INCONCLUSIVE_LOW_N` — **not** a pass: extend the run to 2 h rather than quoting a p50 from
  two samples (exactly what run5's PHASE_R.txt could not do).
- **attach:** `GAP4_PHASE_R.txt` (WS health line, verify line, the full `lat_stamps.py` stage table, the
  `metrics.py` JSON with `latency_by_hour`), the 3 wallets actually configured,
  `armed.txt`, and the raw `send_attempts.csv` rows for the run (`created_at_ms >= armed_ms`).
- **notes/risks:** there is no `HL_LIVE_CONFIG` — this script edits the live `live_config.json` (after backing
  it up) and restores the `.gap4bak` copy at the end; check it restored. Never arm before `verify.py` says
  `MATCH`. Expect the feed to ack all 3 leaders (`wallets_without_feed: 0`); if `WS_DEGRADED`, the poll path
  is what is being measured (the 8 s bar applies).

## GAP-5 · disk-full robustness

**Why it is a gap.** Row 11 (audit rotation) is mock-only and the "audit write fails" class is not covered
live at all: a failed append must never (a) lose a fill silently, (b) let a send go out whose record could
not be written, or (c) kill the loop. J1 (`PARALLEL_JOBS.md` §J1, branch `hermes/j1-diskfull`) writes the
offline injection tests; the PC half is the **real** ENOSPC test on a bounded volume, which no run has done.

- **offline proof (J1, when merged):** from `$CERT/_archive/hl_stage2`,
  `env -u PYTHONPATH HL_LIVE_ENV_FILE=/nonexistent <PY311> -u test_disk_full_robustness.py` →
  `TOTAL=<n> FAILED=0` (adjust the filename to J1's merged one; cases: `order_intents` append fails before a
  send → no order, loud log; `send_attempts` final-status write fails → no exchange call; `reconciliation`
  append fails after a send → counted in the integrity status, no second order for the same intent on retry;
  state/runtime json write fails → next cycle still runs).

- **exact command:** paste as `$EV/gap5_diskfull.sh` and run **in an elevated shell** `bash $EV/gap5_diskfull.sh`
```bash
set -u
CERT=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert
AUD=$CERT/_archive/hl_stage2/hl_live_copy_audit_testnet; CFG=$AUD/live_config.json
EV=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run5; L=$EV/engine_5e88e89_diskfull.log
PY311=/c/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe
S=/c/Users/wigmore/.hermes/cache/scratch/gap5; mkdir -p $S
# --- part A: offline injection suite (no elevation) ---
cd $CERT/_archive/hl_stage2 \
  && env -u PYTHONPATH HL_LIVE_ENV_FILE=/nonexistent $PY311 -u test_disk_full_robustness.py | tee $S/offline.txt
grep -q 'FAILED=0' $S/offline.txt || { echo "GAP5_RESULT:: FAIL offline_suite"; exit 1; }
# --- part B: real ENOSPC on a bounded 256 MB VHD mounted at X: (elevated; NEVER consumes C: free space) ---
VHD='C:\Users\wigmore\.hermes\cache\scratch\gap5\gap5.vhd'
printf 'create vdisk file="%s" maximum=256 type=fixed\nselect vdisk file="%s"\nattach vdisk\ncreate partition primary\nformat fs=ntfs quick label=GAP5\nassign letter=X\n' "$VHD" "$VHD" > $S/dp_attach.txt
diskpart /s "$(cygpath -w $S/dp_attach.txt)"
XAUD=/x/audit; mkdir -p $XAUD
# start a SHORT testnet run with its audit dir on X:, auto_send ON, one leader, then fill the volume mid-run
cd $CERT/_archive/hl_stage2 && source ../run_env.sh && export HL_LIVE_HOT_SEND_WORKERS=2 \
  && export HL_LIVE_AUDIT_DIR='X:\audit' \
  && python HL_Live_Copy_Service_Core.py --ws --loop --interval 10 --poll-live --poll-copy > $L 2>&1 &
sleep 180
python -I -c "
import json,os,sys;p=sys.argv[1];d=json.load(open(p,encoding='utf-8'));d['auto_send_enabled']=True
t=p+'.tmp';open(t,'w',encoding='utf-8').write(json.dumps(d,indent=2));os.replace(t,p)" "$CFG"
dd if=/dev/zero of=$XAUD/../filler.bin bs=1M count=400 2>/dev/null      # exhausts the 256 MB volume -> ENOSPC
sleep 600                                                              # >=10 min of cycling on a full disk
alive=no; logit=no
PID=$(python -c "
import psutil
print(' '.join(str(p.pid) for p in psutil.process_iter(['name','cmdline'])
      if (p.info['name'] or '').startswith('python') and 'HL_Live_Copy_Service_Core.py' in ' '.join(p.info['cmdline'] or [])))")
[ -n "$PID" ] && alive=yes
grep -qiE 'ENOSPC|no space left|disk full|OSError 28' $L && logit=yes
# no order may exist on the exchange without a matching send_attempts row on the full volume
orph=$(python -I - "$XAUD" <<'PY'
import csv,sys,requests
aud=sys.argv[1]; A="0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205"
rows=list(csv.DictReader(open(aud+"/append_only/send_attempts.csv",encoding="utf-8")))
oids={str(r.get("exchange_order_id") or "") for r in rows}-{""}
fl=requests.post("https://api.hyperliquid-testnet.xyz/info",
                 json={"type":"userFillsByTime","user":A,"startTime":0},timeout=20).json()
un=sorted({str(f["oid"]) for f in fl}-oids)
print("unrecorded_exchange_orders:",un[:5],file=sys.stderr); print(len(un))
PY
)
python -I -c "
import json,os,sys;p=sys.argv[1];d=json.load(open(p,encoding='utf-8'));d['auto_send_enabled']=False
t=p+'.tmp';open(t,'w',encoding='utf-8').write(json.dumps(d,indent=2));os.replace(t,p)" "$CFG"
for p in $PID; do python -c "import psutil,sys;psutil.Process(int(sys.argv[1])).terminate()" $p; done
ok=$( [ "$alive" = yes ] && [ "$logit" = yes ] && [ "${orph:-1}" -eq 0 ] && echo PASS || echo FAIL )
echo "GAP5_RESULT:: $ok engine_alive=$alive loud_log_line=$logit unrecorded_exchange_orders=${orph:-?} filler_mb=400"
# cleanup: never leave the volume mounted
printf 'select vdisk file="%s"\ndetach vdisk\n' "$VHD" > $S/dp_detach.txt
diskpart /s "$(cygpath -w $S/dp_detach.txt)" && rm -f $XAUD/../filler.bin
```

- **expected pass line:** `GAP5_RESULT:: PASS engine_alive=yes loud_log_line=yes unrecorded_exchange_orders=0
  filler_mb=400` **and** the offline part `TOTAL=<n> FAILED=0`. Pass = on a genuinely full audit volume the
  engine (a) sends **no** order the exchange holds without a matching `send_attempts.csv` row on the volume
  (`unrecorded_exchange_orders=0`), (b) emits a loud log line naming the failure, (c) is still alive and
  cycling. (b) and (c) alone are not a pass — the invariant is (a).
- **attach:** `$S/offline.txt` (the injection suite tail), the diskpart transcript, the engine log excerpt
  around the first ENOSPC (`grep -n -A3 -B3 -iE "ENOSPC|no space left|OSError 28" $L`), the `verify.py`
  line, the `send_attempts.csv`/`reconciliation.csv` rows written on `X:` before the freeze, and the
  confirmation the VHD was detached and deleted.
- **notes/risks:** **never** test ENOSPC by consuming C: free space (`fsutil file createnew`, a big filler in
  the cert dir, …) — the box runs 42–54 GiB free and that is exactly the kind of "test" that becomes an
  incident. The bounded VHD is the only sanctioned method, and it must be detached + deleted afterwards.
  Part B needs elevation (`diskpart`); if elevation is unavailable, run part A and record
  `GAP5_RESULT:: PARTIAL offline_suite=<TOTAL/FAILED> elev=no`. Adjust `append_only` in the inline check if
  the layout under `X:\audit` differs.

---

## What this job does NOT do

No engine/Core edit, no test of the running engine, no orders, no keys, no ports, no Wallet Finder, nothing
written under `hl-build3-testnet-cert`. The five scripts above are for the PC operator to paste and run;
this branch carries the doc plus one conformance test (`_archive/hl_stage2/test_j4_pc_run_specs.py`) that
fails if any of the five gaps is missing an exact command, a `GAPn_RESULT::` pass line, or an attach list, or
if a repo test the doc relies on does not exist.
