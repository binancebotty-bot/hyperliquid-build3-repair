# J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)

**Doc only.** Nothing here was executed by me. Source of the gap list: the engine thread's handover (locator: issue #3)
(comment 6106236565) - "Top 5 gaps need the PC: outage recovery, memory flat on new main, liquidation parity vs
exchange liquidationPx, realistic-load latency (Phase R), disk-full robustness" - and
`process/CERTIFICATION_MATRIX_2026-10-10.md` (the 2026-10-11 matrix lives in the Claude project, not this repo).
Every command below is the pattern the already-proven run scripts use (`run5/run7_arm.sh`, `run5/phaseR.sh`,
`run5/outage_test.sh`, `run5/test9a.sh`, `run5/test10a.sh`, `run5/test11a.sh`, `run5/test11b.sh`) - reuse them.

## 0. Common preamble (every gap)

Engine dir (PC): `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert`; state folder
`.../_archive/hl_stage2/hl_live_copy_audit_testnet`. Evidence dir: `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence`.
Orchestration scripts run from the evidence dir; the engine runs from the cert clone.
New evidence for this batch goes in `.../hl-build3-testnet-cert-evidence/run9/` - `cd .../hl-build3-testnet-cert-evidence && mkdir -p run9`.

    # 0.1 fresh code (the engine thread asks for 9a651cd+; the PC should pull the current main)
    cd /c/Users/wigmore/trading_stack/hl-build3-testnet-cert && git fetch && git log --oneline -1

    # 0.2 FIRST start rewrites send_attempts.csv ONCE (the cloid column). Do it before any measured run:
    cd .../hl-build3-testnet-cert/_archive/hl_stage2 && source ../run_env.sh \
      && python HL_Live_Copy_Service_Core.py --once --poll-live --poll-copy   # no --ws, no arm

    # 0.3 the run start line every gap uses (testnet follower; mainnet MUST NOT be named):
    cd /c/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2 && source ../run_env.sh \
      && export HL_LIVE_HOT_SEND_WORKERS=12 \
      && exec python HL_Live_Copy_Service_Core.py --ws --loop --interval 10 --poll-live --poll-copy \
           > /c/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run9/engine_<sha>.log 2>&1

    # 0.4 arm / disarm (the ONLY switch the runs use; runtime config, not the repo copy):
    CFG=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet/live_config.json
    setarm() { python -I -c "
import json,os,sys;p=sys.argv[1];d=json.load(open(p,encoding='utf-8'));d['auto_send_enabled']=(sys.argv[2]=='1')
t=p+'.tmp';open(t,'w',encoding='utf-8').write(json.dumps(d,indent=2));os.replace(t,p)" "$CFG" "$1"
      echo "$(date -u +%FT%TZ) auto_send=$1 $2" >> run9/armed.txt; }

    # 0.5 drain + independent oracle (READ-ONLY exchange check; the arrow every gap ends on):
    #     drain: poll the log until '\\"send_backlog\\": N' < 50
    ok=0; for k in $(seq 1 8); do r=$(timeout 150 python -I verify.py "$(cat run9/run_armed_ms.txt)" | grep RESULT)
      echo "$r"; case "$r" in *"RESULT:: MATCH"*) ok=1; break;; esac; sleep 20; done
    [ $ok = 1 ] || { echo NOT_ARMED; exit 1; }
    # verify.py prints per-coin 'exchange_szi / engine_net' and 'RESULT:: MATCH|MISMATCH' from the exchange's own
    # clearinghouseState/userFillsByTime/openOrders (oracle, no engine code).

Safety for the whole batch: testnet only; never `--confirm-mainnet-follower`; never touch the Wallet Finder; stop the
engine with its own PID only (`psutil`, exact cmdline `HL_Live_Copy_Service_Core.py`) - never by name/wildcard.

## 1. Outage recovery (gap 1)

Script: reuse `run5/test11b.sh` (or `outage_test.sh`); the classifier is the tail of `run5/test11a.sh`.

    A. armed drain + arm:      sleep 60; drain to backlog<50; verify.py -> expect MATCH; setarm 1 "run9 outage A"
    B. disarm first:           setarm 0 "outage: disarm before stop"; sleep 30          # never stop while armed
    C. controlled stop:        kill the engine by its own PID; date -u +%s%3N > run9/outage_stop_ms.txt
    D. down 300 s (or 1200 s): sleep 300
    E. armed restart:          setarm 1 "outage: armed restart"; date -u +%s%3N > run9/outage_restart_ms.txt
                               start the engine again with the 0.3 line
    F. classifier:             run the counter block from test11a.sh over the outage window
                               (leader fills vs engine rows: missed / taken / blocked coin / resting limit / refused /
                                replayed twice / replay lag) -> run9/OUTAGE_RESULT_<sha>.txt

**Expected pass line** (`run9/OUTAGE_RESULT_<sha>.txt`):
    replayed twice (more than one filled send for one leader order): 0 []        # never a double copy
    replay sends after restart: median < 300 s and last < 900 s                  # the catch-up finished
and within 10 min of restart `RESULT:: MATCH`. `no engine row (missed)` may be non-zero ONLY for fills the rules
block (blocked coin / missed_entry terminal) - the classifier prints them, so name them. Baseline for comparison:
`run5/OUTAGE_RESULT_fc7efd7.txt` (720 missed, 0 replayed twice, median 215 s).

**Attach:** pre + post outage engine logs, `run9/armed.txt` lines, the stop/restart ms files, the classifier stdout,
`verify.py` output before and after, and `hl_live_copy_audit_testnet/live_integrity_status.json` (must not be RED at
the end). Also attach `_archive/hl_stage2/test_core_outage_replay.py` passing (`TOTAL=..  FAILED=0`).

## 2. Memory flat on new main (gap 2)

Offline baseline first (fast, no engine): `python bench_memory_profile.py --skip-large` then without `--skip-large`
(10/100/200 MB synthetic audit files; prints peak / retained / RSS delta / ms per call site).

Live: sample RSS every 5 min for 120 min on the armed run - reuse the `rss()` function in `run5/phaseR.sh`
(psutil, exact cmdline match) - and SHARE this run with gap 4 (same 120 min, same arm).

**Expected pass line:**
    offline: no row with retained_mb > 10 and no row with rss_delta_mb > 15   (bounded tail reads, no whole-file scan)
    live:    (last RSS - first RSS over the 120 min after 15 min warm-up) <= +50 MB, and no single step > 100 MB
             (a flat line, not a slope). Proposed gate - the coordinator may tighten it after the first run.

**Attach:** the offline table, the RSS table (`run9/PHASE_R.txt`), the 200 MB-file rows, `send_attempts.csv` size
growth over the window, and the integrity status at the end.

## 3. Liquidation parity vs exchange liquidationPx (gap 3)

Needs a coin where a leader's projected 3x liquidation is CLOSER than the follower's, so the gate must fire. Two
read-only reads + the engine:

    # 3.1 the follower must be on cross 3x: read it back from the exchange (per dex)
    python -I -c "import requests;A='0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205';
      print(requests.post('https://api.hyperliquid-testnet.xyz/info',json={'type':'clearinghouseState','user':A},timeout=10).json())"
    # 3.2 the leader's own liquidation for the same coin (mainnet read-only, no writes)
    POST https://api.hyperliquid.xyz/info {"type":"clearinghouseState","user":"<leader>"}   -> liquidationPx per coin
    # 3.3 arm with ONLY that leader enabled, then confirm from the engine's own rows + the exchange

**Expected pass line:** for every coin the engine entered,
`|mark - follower_liquidationPx| / mark  >=  max over the safest leader of |mark - leader_liquidationPx| / mark`
(the follower is never closer to liquidation than the safest leader), and where that cannot hold the entry is refused
with terminal `LIQ_PARITY_BLOCKED` / operator `NO_SEND_LIQ_PARITY` and the exchange shows NO order for that coin
(`openOrders` + `userFillsByTime` since arm). `updateLeverage` is called once per asset before its first order
(grep the log once).

**Attach:** the follower's `clearinghouseState` (each dex) at arm and after, the leader's `liquidationPx` for the
same coin, the `send_attempts.csv`/`reconciliation.csv` rows for that coin (terminal_state + notes), the log line
carrying the parity numbers, and `RESULT:: MATCH`.

## 4. Realistic-load latency, Phase R (gap 4)

Reuse `run5/phaseR.sh` as-is: 3 human-paced leaders, armed, 120 min, RSS sampling + a latency dump at 60 and 120 min.
`run5/test11a.sh` is the shorter variant (5 human + 2 low bots, 15 min) - run it too if time allows.

    python -I run5/lat_stamps.py run9/run_armed_ms.txt      # per-stage p50/max ms after the leader fill
    python -I verify.py "$(cat run9/run_armed_ms.txt)"      # the oracle

**Expected pass line:**
    lat_stamps.py: the p50 of leader_fill -> intent_written, -> send_attempt, -> exchange call each <= 2000 ms,
      and each max <= 5000 ms; copies counted > 0 with no status left at `pending_send`
    verify.py: RESULT:: MATCH at 60 min and at 120 min
    integrity status: no `filled_without_live_fill_beyond_grace` and no `latency_warnings` on the armed window

**Attach:** `run9/PHASE_R.txt`, the lat_stamps output, both verify.py outputs, the armed.txt line, the integrity
status JSON, and the leader cohort used (3 wallets + their orders/24 h from `E1_PHASE_R_LEADERS.md`).

## 5. Disk-full robustness (gap 5)

Two variants. **(i) is the primary - no admin, no disk filling, no risk to C:.**

    # (i) PermissionError: deny write+append on the audit append_only dir, run one cycle, then restore
    AUD=/c/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet/append_only
    icacls "$(cygpath -w "$AUD")" /deny "$USERNAME:(WD,AD)"     # if $USERNAME is empty in bash use `whoami`
    cd .../hl_stage2 && source ../run_env.sh && python HL_Live_Copy_Service_Core.py --once --poll-live --poll-copy \
       > /c/.../hl-build3-testnet-cert-evidence/run9/diskfull_once.log 2>&1
    icacls "$(cygpath -w "$AUD")" /remove:d "$USERNAME"          # RESTORE IMMEDIATELY, then confirm a clean --once
    # (never leave the deny ACE in place: the running engine's audit appends would keep failing)
    # (ii) true ENOSPC (admin, 512 MB only): create a 512 MB VHD, mount it as e.g. X:, put a FRESH state folder on it
    #      (HL_LIVE_AUDIT_DIR=X:\state), pre-fill it to ~5 MB free, disarm, run --once, then dismount. Never fill C:.

**Expected pass line:** on current main the known result is FAIL - the J1 test and findings: the order-intent append
raises out of the fill unit, the post-send terminal/reconciliation appends raise with the order already sent, and
nothing durable is logged. After the J1 patch (`hermes/j1-diskfull`, `DISK_FULL_PATCH_PROPOSAL.diff`) the pass line is:
    no NEW order after the audit write fails (or at most the single in-flight one), the cycle finishes with exit 0,
    `errors.csv` carries the AUDIT_WRITE_FAILED record, one terminal row/reconciliation per affected intent,
    `write_live_integrity_status` still writes after the disk is restored  -> next `--once` is clean and verify.py MATCH

**Attach:** `diskfull_once.log`, `errors.csv` tail, `live_integrity_status.json`, the before/after `--once` outputs,
`verify.py` MATCH, and `_archive/hl_stage2/test_core_disk_full.py` output (15 checks; 5 FAIL before the patch,
15/15 after).

## 6. Batch plan (one PC session)

| order | gap | wall time | notes |
|---|---|---|---|
| 1 | 3 liquidity parity | ~60-90 min | smallest change footprint; disarm after |
| 2 | 4 realistic-load + 2 memory flat | 120 min together | one armed run: Phase R leaders, RSS every 5 min, lat_stamps at 60/120 |
| 3 | 1 outage recovery | ~45 min | disarm -> stop -> 5-20 min down -> armed restart -> classifier |
| 4 | 5 disk-full | ~15 min | icacls variant; ends with a clean --once; no engine left armed |
| end | - | - | disarm, stop the engine, `git status` clean, attach `run9/RESULTS.md` (one line per gap) + all files |

Nothing in this document changes code. Rules kept: testnet only, no mainnet, no keys printed, ports 8012/8014/8031 and
the Wallet Finder untouched, no WebSocket subscriptions from anything other than the engine itself.
