# Engine memory profile - HL_Live_Copy_Service_Core.py

- **Baseline revision profiled: `f37b9c1`** - the revision named in task M1 ("4.5 GB private after ~10 min on f37b9c1") and the tip of `main` when the delegation was written (2026-10-10T21:17Z).
- **Comparison revision: `main` `06435bf`** (merge of PR #40). Commit `c39d9cc` *"Memory: bounded send-attempt cache with O(1) order-id index, streaming CSV reads, per-order owned totals, 100 MB rotation ..., intent retention"* landed **21:50Z, ~20 min AFTER the delegation**, so the task's suspects are the pre-fix `f37b9c1` code. Both revisions profiled with the same tool.
- **Tool:** `_archive/hl_stage2/tools_memory_profile.py` (tracemalloc + psutil RSS; `--toplines` mode). Row shapes copied verbatim from the module's own writers (`SEND_ATTEMPT_FIELDS`/`LIVE_FILL_FIELDS`/`RECONCILIATION_FIELDS`).
- **Safety:** the tool works only on files it creates in a private temp dir; no network, no exchange calls, no keys; the running engine (PID/port 8031) and its state folder were never touched.

| operation | file size | iters | peak MB | retained MB | ms/call | rss peak MB |
|---|---|---|---|---|---|---|
| a.read_csv_rows | 10 MB | 1 | 109.4 | 59.0 | 119.871 | 126 |
| b.send_attempt_rows | 10 MB | 1000 | 119.6 | 59.1 | 0.307 | 194 |
| c.fresh_sent_row_for_oid | 10 MB | 1000 | 0.1 | 0.0 | 3.782 | 125 |
| c2.choose_intent_scan | 10 MB | 1000 | 0.0 | 0.0 | 0.375 | 66 |
| d.owned_fill_size | 10 MB | 80 | 104.7 | 0.0 | 189.776 | 115 |
| e.audit_orphan_attribution | 10 MB | 10 | 164.0 | 0.0 | 1284.055 | 122 |
| a.read_csv_rows | 100 MB | 1 | 1096.4 | 589.9 | 1618.205 | 701 |
| b.send_attempt_rows | 100 MB | 1000 | 1198.6 | 590.8 | 1.932 | 1352 |
| c.fresh_sent_row_for_oid | 100 MB | 167 | 1.0 | 0.0 | 90.283 | 718 |
| c2.choose_intent_scan | 100 MB | 1000 | 0.0 | 0.0 | 0.350 | 224 |
| d.owned_fill_size | 100 MB | 7 | 1042.4 | 0.0 | 2239.463 | 231 |
| e.audit_orphan_attribution | 100 MB | 2 | 1638.2 | 0.0 | 13666.412 | 503 |
| a.read_csv_rows | 200 MB | 1 | 2176.5 | 1170.3 | 3822.369 | 2195 |
| b.send_attempt_rows | 200 MB | 1000 | 2379.6 | 1172.2 | 5.021 | 2614 |
| c.fresh_sent_row_for_oid | 200 MB | 69 | 1.9 | 0.0 | 218.091 | 1362 |
| c2.choose_intent_scan | 200 MB | 1000 | 0.0 | 0.0 | 0.333 | 419 |
| d.owned_fill_size | 200 MB | 4 | 2086.8 | 0.0 | 3928.335 | 523 |
| e.audit_orphan_attribution | 200 MB | 1 | 3260.5 | 0.0 | 22863.035 | 509 |
| f.intents_by_id_5000 | 0 MB | 1 | 4.0 | 4.0 | 18.867 | 87 |

## Where each suspect runs

- `a.read_csv_rows` -> once / per startup load, and per call wherever invoked
- `b.send_attempt_rows` -> per copy fill (matcher OID lookups) + once at startup
- `c.fresh_sent_row_for_oid` -> per copy fill (candidate scan)
- `c2.choose_intent_scan` -> per copy fill (fallback candidates)
- `d.owned_fill_size` -> per standing/recovery close decision
- `e.audit_orphan_attribution` -> per reconciliation cycle
- `f.intents_by_id_5000` -> retained for the whole run; scanned per copy fill

## Ranking (by measured contribution)

1. `b.send_attempt_rows` @ 200 MB - peak 2379.6 MB, retained 1172.2 MB, 5.021 ms/call
2. `a.read_csv_rows` @ 200 MB - peak 2176.5 MB, retained 1170.3 MB, 3822.369 ms/call
3. `e.audit_orphan_attribution` @ 200 MB - peak 3260.5 MB, retained 0.0 MB, 22863.035 ms/call
4. `d.owned_fill_size` @ 200 MB - peak 2086.8 MB, retained 0.0 MB, 3928.335 ms/call
5. `b.send_attempt_rows` @ 100 MB - peak 1198.6 MB, retained 590.8 MB, 1.932 ms/call
6. `a.read_csv_rows` @ 100 MB - peak 1096.4 MB, retained 589.9 MB, 1618.205 ms/call
7. `e.audit_orphan_attribution` @ 100 MB - peak 1638.2 MB, retained 0.0 MB, 13666.412 ms/call
8. `d.owned_fill_size` @ 100 MB - peak 1042.4 MB, retained 0.0 MB, 2239.463 ms/call

## 2. Top tracemalloc allocation lines (`f37b9c1`, 50 MB synthetic CSV)

```
== a.read_csv_rows (send_attempts) at peak, result held ==
    199.33 MB  n=3122977   ...\Python311\Lib\csv.py:111
     95.05 MB  n=120080    ...\Python311\Lib\csv.py:119
      0.50 MB  n=4         ...\_archive\hl_stage2\HL_Live_Copy_Service_Core.py:1078   <- list(csv.DictReader(...))

== b.send_attempt_rows (module row cache retained) ==
    199.33 MB  n=3122977   ...\Lib\csv.py:111
     95.04 MB  n=120002    ...\Lib\csv.py:119
      0.50 MB  n=2         HL_Live_Copy_Service_Core.py:1114   <- cache["rows"] = list(reader)
      0.48 MB  n=2         HL_Live_Copy_Service_Core.py:1122   <- return list(cache["rows"])   (full copy per call)

== d.owned_fill_size (whole live_fills.csv read) at peak, result held ==
    172.14 MB  n=2543743   ...\Lib\csv.py:111
     99.85 MB  n=240081    ...\Lib\csv.py:119
      1.01 MB  n=4         HL_Live_Copy_Service_Core.py:1078

== e.audit_orphan_attribution (whole reconciliation.csv read) at peak, result held ==
    165.70 MB  n=2412908   ...\Lib\csv.py:111
     68.68 MB  n=296081    ...\Lib\csv.py:119
      1.28 MB  n=4         HL_Live_Copy_Service_Core.py:1078
```

**Reading:** the peak allocation is `csv.py:111`/`csv.py:119` - `csv.DictReader` building one `dict` per row with a fresh `str` per field. For a 50 MB file that is ~3.1M strings + 120-296k dicts = ~265-295 MB live at peak (~5.3-5.9x the file); `read_csv_rows` line 1078 wraps it in `list(...)` so the whole structure is retained while the caller holds the result.

## 3. Verdict per suspect (prove / disprove)

1. **`send_attempt_rows` caches every row forever and returns a full copy each call - CONFIRMED.** Retained after the first read = **59.1 / 590.8 / 1172.2 MB** at 10/100/200 MB (~5.9x file size), held in the module-global `_SEND_ROWS_CACHE` for the process lifetime. Every call also returns `list(cache["rows"])` (line 1122) - an O(rows) pointer copy (0.3 ms warm @10 MB, 5.0 ms @200 MB). Runs once at startup then **per copy fill**.
2. **`read_csv_rows` parses the whole file into a list of dicts (multi-GB transient) - CONFIRMED.** One call: peak **109.4 / 1096.4 / 2176.5 MB** (peak ~10.9x file size), retained (list held) **59.0 / 589.9 / 1170.3 MB**. Called **per call** on the live path by `_owned_fill_size` (whole `live_fills.csv`: peak **104.7 / 1042.4 / 2086.8 MB**, **190 / 2239 / 3928 ms** per call) and by `audit_orphan_attribution` (whole `reconciliation.csv`: peak **164.0 / 1638.2 / 3260.5 MB**, **1284 / 13666 / 22863 ms** per call). Top lines above.
3. **`intents_by_id` keeps every Intent for the whole run; matcher scans `.values()` linearly - CONFIRMED.** 5000 intents = **4.0 MB retained** for the process lifetime; the fallback coin/side/time scan (`_choose_intent` / `_unmatched_reason`) is **0.33-0.38 ms per call** at 5000 intents and grows with dict size. The explicit-id and OID fast paths avoid the scan. Retained once (whole run); scanned per copy fill on the fallback path only.
4. **`dedupe.processed`, `_idem_accepted`, `_exchange_cache`, `_recovery_intent_ids` - CONFIRMED small.** All bounded: `processed` sets are capped (`sorted(...)[-250000:]`), `_recovery_intent_ids` holds one id per recovery, `_exchange_cache` one `Exchange` per key. Not a heap driver.

## 4. Interpretation - ranking by contribution to the observed 4.5 GB

1. **`read_csv_rows` multi-GB transient on the per-call live path** (`d`, `e`, and the retained `b` cache): a single `_owned_fill_size` / `audit_orphan_attribution` call allocates **1.0-3.3 GB transient** at 100-200 MB - this alone can explain the 4.5 GB private set.
2. **`send_attempt_rows` permanent row cache:** +1.17 GB at a 200 MB `send_attempts.csv`, retained for the run.
3. **`intents_by_id`:** +4 MB per 5000 intents (grows with run length) plus per-fill scan CPU.
4. **Small bounded sets/caches:** negligible.

Per fill / per cycle / once:
- per copy fill: `b.send_attempt_rows` (full copy), `c.fresh_sent_row_for_oid`, `c2.choose_intent_scan` (fallback)
- per close decision: `d.owned_fill_size` (whole `live_fills.csv`)
- per recon cycle: `e.audit_orphan_attribution` (whole `reconciliation.csv`)
- once / startup: `a.read_csv_rows` loaders, first `send_attempt` read, `intents_by_id` skeleton (retained thereafter)

## 5. Fix verification on current `main` (`06435bf`)

`main` now contains `c39d9cc`, which targets exactly these readers. Re-ran the identical tool on `06435bf`:

| operation | file size | peak MB | retained MB | ms/call |
|---|---|---|---|---|
| a.read_csv_rows | 200 MB | 2169.4 | 1167.9 | 2992.4 |
| b.send_attempt_rows | 200 MB | 1305.0 | **102.1** | 3.256 |
| c.fresh_sent_row_for_oid | 200 MB | 0.0 | 0.0 | **2.908** |
| d.owned_fill_size | 200 MB | **0.0** | 0.0 | **26.283** |
| e.audit_orphan_attribution | 200 MB | **3253.5** | 0.0 | **18209.5** |
| f.intents_by_id_5000 | 0 MB | 4.0 | 4.0 | 14.892 |

Deltas vs baseline (200 MB):
- `b` retention **1172.2 -> 102.1 MB (-91%)** - cache is now bounded (100 MB tier: 590.8 -> 95.5 MB).
- `c` **218.1 -> 2.9 ms** - O(1) order-id index replaces the linear scan.
- `d` **2086.8 -> 0.0 MB peak, 3928 -> 26.3 ms** - per-order owned totals replace the whole-`live_fills.csv` read. FIXED.
- `a` unchanged (same function; not a target of the fix).
- **`e.audit_orphan_attribution` UNCHANGED - still reads and parses the whole `reconciliation.csv` per call (3253.5 MB peak, 18.2 s at 200 MB).** The `c39d9cc` bounded-tail work covered the *integrity status* reader (which parsed all four CSVs every cycle), not `ExchangeReconciler.audit_orphan_attribution`. **This is the remaining unfixed memory driver.**

## Notes / method

- `peak` = tracemalloc peak above the pre-op baseline for the measured op; `retained` = still-allocated bytes at the end of the op window (i.e. what the caller/global cache keeps).
- `read_csv_rows` result is kept to reflect a caller that holds the parsed list; `_owned_fill_size` / `audit_orphan_attribution` discard per call, so their retained ~= 0 while their PEAK is the whole-file transient.
- Each measurement is capped by a wall budget; `iters` is the number actually completed (so `ms/call` is the meaningful figure at large sizes).
- No network, no exchange calls, no writes outside the private temp dir; the running engine was never touched.

