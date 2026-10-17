# RTT + XYZ arming RCA — CLAUDE RULING 6234527189

Task: t_2c6ce2fa. Branch `hermes/order-rtt-2c6ce2fa` off `89b3bc7`. OFFLINE analysis only:
no arm/disarm, no restart, no order, no credential, no live_config edit, no engine contact.

All figures below were produced by running the probes in this directory against
`api.hyperliquid-testnet.xyz` (read-only, no key, no order) on 2026-10-17.

## Headline correction to the premise

The premise "order costs two round trips (571 ms RTT vs 1121 ms order)" does not survive measurement.
571 ms is **not** a network round trip — it is the answer time of the `/info` endpoint, which is
itself a full server-side computation. Real transport cost on this host is ~46 ms:

    TCP connect 16 ms, TLS 1.3 handshake 15 ms, cold first POST 266 ms
    warm keep-alive /info POST  p50 570.5  min 250  p90 703  max 734  (n=12)
    new-connection total        734 ms
    /exchange POST (invalid sig) p50 250   min 234  max 250  (n=8)
    /info POST                   p50 679   min 234  max 719  (n=8)   ratio exch/info 0.37

So a 1121 ms "order" is ~ 571 (one /info read) + 250 (the order POST) + 250 (engine pacing)
+ ~0 (signing) — i.e. **one** exchange round trip plus engine-side time, not two exchange
round trips. The second term is engine work that sits *outside* the stamped interval.

## Part A — where the second 571 ms goes

### 1. Persistent connection? YES — the exchange POST reuses one pooled session.

- SDK client object: `Exchange`, constructed once per key/URL/address/dex-scope and cached —
  `HL_Live_Copy_Service_Core.py:6655` (`self._exchange_cache[cache_key] = Exchange(...)`),
  cache key at `:6639-6645`, accessor `_get_exchange_client` `:6626`.
- The SDK's HTTP layer is a single `requests.Session` created in the constructor:
  installed `hyperliquid/api.py:12-14` (`self.session = requests.Session()`), used by every
  `API.post` (`api.py:20-22`). Keep-alive is therefore on by default for `/exchange`.
- Proof by measurement (`rtt_probe_sdk_connections.py`, localhost HTTP/1.1 server counting
  client source ports = connections):
  construct → 2 `/info` posts on conn 60727; order → **1** request on conn 60728;
  second order → same conn 60728; `SESSION_REUSED_ACROSS_ORDERS: True`.
  A new connection per order is therefore **ruled out**.
- The read path has its own shared keep-alive session for `/info`
  (`exchange_truth.py:198-232`, `HTTPAdapter(pool_connections=4, pool_maxsize=8, pool_block=True)`),
  warmed every 20 s by `start_keepalive` (`exchange_truth.py:238-255`, started at
  `HL_Live_Copy_Service_Core.py:10866-10867`).

### 2. A preceding request inside the stamped interval? NO.

`_place_order` is the one physical order call (`HL_Live_Copy_Service_Core.py:4327`). Its body is:

- `:4337-4338` take `_exchange_order_lock` and call `_wait_exchange_order_slot()`
- `:4339-4340` **then** stamp `timing[started_key] = utc_now_ms()`
- `:4341-4344` build local `order_kwargs` + cloid, `_exchange_accepts_cloid` (signature-inspection,
  cached per type at `:2800-2815`)
- `:4346` `response = exchange.order(...)` — the single network call

Inside the SDK, `order()` → `bulk_orders()` (`exchange.py:140-181`) does
`order_request_to_order_wire(order, self.info.name_to_asset(coin))`, which is a **dict lookup**
(`info.py:789-790` over `coin_to_asset` built at construction, `info.py:38-56`), then
`get_timestamp_ms()` (`utils/signing.py:501-502`, local clock), then `sign_l1_action` (local
ECDSA), then `_post_action` → `API.post('/exchange')` (`exchange.py:101-110`).
**No meta, nonce, ticker or allMids request is issued per order.** There is nothing to cache
and no TTL to state: the metadata is resolved at client construction, not per order.

Anything network-shaped in the send path happens *before* the stamp, and is stamped separately:
`symbol_resolve_ms` / `sdk_client_ms` (`:6364-6365`), `margin_mode_started_ms` (`:6427`,
`_ensure_margin_mode` → `update_leverage`, once per asset per run, `:6427-6429`),
`_withdraw_standing_close` (`:6424`, a `cancel` — only on a close whose sleeve still has a
standing recovery close). Those inflate wall-clock send latency, not `exchange_call_ms`.

### 3. Signing cost — inside the stamp, and negligible.

Measured over 30 signatures of a real order action (`rtt_probe_sdk_connections.py`):
`SIGN_MS p50=0.00 min=0.00 max=16.00`. It is inside the stamped interval
(`:4346` returns only after signing) but is not a contributor at this scale.

### 4. `_wait_exchange_order_slot` — engine time, OUTSIDE the stamp.

`:5098-5104`: default gap `HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS` = **250 ms** (`:5099`), and the wait
is the max of that gap and `_exchange_rate_limit_cooldown_until_ms`, which is **8000 ms** after a
rate-limit reply (`:5106-5113`). The wait is at `:4337-4338`, before the stamp at `:4339`.

Pinned by test `test_order_rtt_and_xyz_arming.py` (15/15 PASS): A1 the stamped interval stays
below 250 ms while A2 the wall clock is >= 240 ms and A3 the two differ by >= 200 ms.
So part of the "exchange call" the operator sees in a send-latency row is engine pacing that the
`exchange_call_ms` column correctly excludes but the wall clock includes. A rate-limit cooldown
would add up to 8 s there and look like exchange slowness if only wall clock is read.

### 5. Smallest change, and the risk of each option

Given 1-4, there is **no second round trip to collapse inside the order call**. Options, smallest first:

- **(a) Do nothing to the transport.** Correct and free. Risk: none. The 571 ms figure should stop
  being read as RTT — it is `/info` answer time, and `/exchange` answers in 250 ms.
- **(b) If the goal is lower wall-clock order latency, shorten the pacing gap** —
  `HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS` (default 250, `:5099`). This is a one-line env change, not a
  code change. Risk: the gap exists to keep distinct signing nonces and to stay off the exchange
  rate limiter; lowering it on many simultaneous orders can earn `RATE_LIMIT_OR_TIMEOUT`, which
  installs the 8 s cooldown at `:5106-5113` and costs far more than it saves.
- **(c) Stop paying a warm `/info` read on the order path.** If a send is waiting on a 571 ms
  `/info` read before the POST, the smallest change is to make that read non-blocking
  (stale-while-revalidate) rather than to touch the order call — note `6cf5dcf` already did exactly
  this for allMids. Risk: serving a stale mid/price into a limit price; bounded by the existing
  max-age, but it is a correctness-adjacent change and must be measured, not assumed.

Recommendation: (a) as the report of record, (b) only as a measured experiment under Codex's
ownership of steps 1-3, (c) as a separate card after the send-path component breakdown is read
from real `send_attempts.csv` rows (`exchange_call_ms` vs `symbol_resolve_ms` vs `sdk_client_ms`).

## Part B — does the XYZ scope ledger update depend on arming?

**Answer: no, it is not armed-gated in code.** Searched: `update_xyz_position_state_from_fills`
and every `xyz`/`XYZ` reference in `HL_Live_Copy_Service_Core.py`, `HL_Live_Copy_Service.py`,
`HL_Copy_App_SSOT.py` (zero matches there), plus all call sites of `copy_poll_once`.

- The writer is `update_xyz_position_state_from_fills(fills, source)` at `:1844-1910`. It takes
  **no config object** and reads no send-mode: its inputs are the fills list and a source label
  (test `C2` pins that `cfg` is not in `co_varnames`). It writes `XYZ_POSITION_STATE_FILE`
  (`:137`) whenever it sees a preferred observation.
- Its one production call site is the copy poll: `:10732`, inside `_copy_poll_once`, guarded only by
  `copy_status == "COPY_ACCOUNT_POLLED"` and a non-empty fill list (`:10730-10733`). The status comes
  from the follower fills read at `:10715`.
- The copy poll is started by `start_copy_poll_thread` (`:10845-10864`), whose condition is
  `args.loop and args.poll_copy and HL_LIVE_COPY_POLL_THREAD` (`:13206-13208`). **Arming is not in
  that condition.** The in-cycle path (`run_cycle(..., poll_copy=copy_due)`, `:11239`, arg built at
  `:13217-13226`) is likewise not armed-gated.
- What *is* armed-gated is the DEX **scope sweep**, not the ledger: `_scope_sweep_block`
  (`:10663-10668`) returns `""` unless `cfg.auto_send_enabled`, and its thread is created only under
  that condition (`:10670-10672`). Pinned by tests E1-E4.
- The ledger is also **advance-only**: a prior observation that is not preferred is skipped
  (`:1882-1883`), so a restart cannot rewind it. Pinned by tests D1-D3 (no-new-fill is byte-identical;
an older fill never overwrites a newer one; the state reloads identically).

### So what produces "identical values reappearing"?

Not arming. The state file is a durable, advance-only file: once the four XYZ rows are written,
they are read back verbatim by any later process that reads **that same file**. The thing that
changes between runs is *which file is read*:

- `AUDIT_DIR` is derived from the follower network and can be overridden by env:
  `HL_Live_Copy_Service_Core.py:116-120` — `hl_live_copy_audit` for a mainnet follower,
  `hl_live_copy_audit_<network>` for testnet, or `HL_LIVE_AUDIT_DIR` if set; and
  `XYZ_POSITION_STATE_FILE = AUDIT_DIR / "xyz_position_state.json"` (`:137`).
- Consistently, the XYZ rows are merged into the position view from this file
  (`xyz_state_positions`, `:1921-1931`, merged at `:2543`), so a run pointed at a different audit dir
  shows the account without them.

That is a testable hypothesis, not a proven cause: the honest statement is that **no armed gate on
this writer exists in the code**, and the observation is fully explained by (i) the file persisting
identical values across restarts and (ii) the two observations reading different `AUDIT_DIR`s (network
or env derived). The discriminating probe is one line in each observation:
`HL_LIVE_AUDIT_DIR` / `_NETWORK_AUDIT_DIR` resolved path plus `mtime` of `xyz_position_state.json`.
If the 12:38Z armed run shows a different path or a missing file, the hypothesis is confirmed; if it
shows the same path and mtime, the arming-dependency is real and my search missed it.

## Evidence: probes and tests in this branch

| artifact | what it proves |
|---|---|
| `rtt_probe_handshake.py` | TCP/TLS cost, warm keep-alive p50, new-connection penalty |
| `rtt_probe_exchange_endpoint.py` | `/exchange` p50 250 ms vs `/info` p50 679 ms, invalid signature (cannot create an order) |
| `rtt_probe_sdk_connections.py` | one `requests.Session`, one connection for the order POST, reused across orders; signing p50 0.00 ms |
| `rtt_probe_idle_timeout.py` | idle-connection survival probe — **not completed** (runs > 4 min of sleeps); no claim is made from it |
| `test_order_rtt_and_xyz_arming.py` | A1-A3 pacing outside the stamp, B1-B2 250 ms default, C0-C2 writer not armed-gated, D1-D3 ledger advance-only and restart-stable, E1-E4 sweep gate is armed-gated |

Test run: `HL_LIVE_ENV_FILE=/nonexistent python3.11 test_order_rtt_and_xyz_arming.py`
→ `SUMMARY: 15 checks, 0 failed`.

SDK file references (`hyperliquid/api.py`, `exchange.py`, `info.py`, `utils/signing.py`) are the
installed package under Python 3.11 (`.../Python311/Lib/site-packages/hyperliquid`), not vendored
in this repo.
