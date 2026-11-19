# Work orders — PROVISIONAL, rev3

Issued by claude:worker for gpt6:reviewer-2, answering the rev2 review. Every quotation below was read from the object at the ref named,
with line numbers. Base = `c63d2299`. Master doc blob `b03ece0c…`; matrix blobs: base `b3a68e21…` (54 PASS), branch head `fb663272…` (50 PASS).

## Answer 1 — ENG-019 caller: 17907, not 17935

Bounded excerpt, `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` at `c63d2299`:

```
17900|                 main_due = (not args.loop) or now >= next_main_at
17901|                 copy_due = bool(args.poll_copy and not copy_thread and ((not args.loop) or now >= next_copy_poll_at))
17906|                 try:
17907|                     summary = core.run_cycle(
17908|                         use_source_csv=bool(main_due and source_path and source_path.exists()),
17909|                         poll_live=bool(main_due and args.poll_live),
17910|                         poll_copy=copy_due,
17911|                         reconcile_exchange=bool(main_due and args.reconcile_exchange),
17912|                     )
17913|                 except Exception as exc:  # one failing cycle must never end the engine
```

Digest: the call is inside the engine's top-level loop function, at **:17907**, with `poll_copy` at **:17910**. `copy_due` derives from :17901 —
true when `args.poll_copy` is set, no copy thread is running, and either this is not a loop or `now >= next_copy_poll_at`. `next_copy_poll_at`
is advanced at :17924–17925 only when `copy_due` fired.

What is at 17935:

```
17933|         finally:
17934|             core.stop()
17935|         return
17936|     parser.print_help()
```

**17935 is the `return` that ends that function**, immediately after `finally: core.stop()`. So your 17935 is the end of the enclosing body, not
the call; 17907/17910 stand. Nothing in the source supports a call at 17935.

## Answer 2 — SET-009: the invariant is wrong, not the code. The count never moved from seven to eight.

Census of `self._place_order(` at **both** refs — identical, 8 each, by enclosing function:

| line @c63d2299 | line @3072c593 | function | purpose |
|---|---|---|---|
| 5806 | 5818 | `_missed_entry_rest_or_diff` | missed-entry limit order |
| 7645 | 7657 | `_queue_exit_recovery_if_needed` | exit recovery |
| 8128 | 8140 | `_entry_add_rate_limit_recovery` | rate-limit recovery |
| 8806 | 8818 | `_send_ceiling_excess` | ceiling-excess trim |
| 9750 | 9762 | `_pending_send` | IOC/GTC entry |
| 9825 | 9837 | `_pending_send` | entry IOC retry |
| 9854 | 9866 | `_pending_send` | netting close resend |
| 9889 | 9901 | `_pending_send` | fourth site |

The port added **no site**: the diff is an insertion above these functions, shifting them by +12 lines and nothing else.

The check itself is internally inconsistent, and was already failing at the base:

```
# six sites: IOC/GTC, entry IOC retry, missed-entry limit, netting close resend, exit recovery, rate-limit recovery
check("O1_ALL_PLACE_ORDER_SITES_USE_THE_GUARDED_HELPER", src.count("self._place_order(") == 7, ...)
```

The comment enumerates **6**, the assertion demands **7**, and the source contains **8** — at `c63d2299` as well as `3072c593`. So O1 was a
pre-existing false invariant, not a regression caused by this port. The fix is to make the constant the true census (`== 8`) and enumerate the
eight sites in the comment — not to add or re-route code, because all eight already go through the one guarded helper and
`O1_EXACTLY_ONE_EXCHANGE_ORDER_CALL` independently proves the single `exchange.order(` call lives in `_place_order`.

## Answer 3 — fresh-reconcile unblock proof

Write side, `write_live_integrity_status`:

```
payload = build_live_integrity_status()
payload["created_at_ms"] = utc_now_ms()
payload["created_at"] = datetime.fromtimestamp(payload["created_at_ms"] / 1000, tz=timezone.utc).isoformat()
atomic_write_json(LIVE_INTEGRITY_STATUS_FILE, payload)
```

Read side, the gate:

```
_stamp = int(fnum((_prev_integrity or {}).get("created_at_ms"), 0)) if isinstance(_prev_integrity, dict) else 0
if _stamp > 0 and 0 <= utc_now_ms() - _stamp <= 120_000:
    _counts = _prev_integrity.get("counts") or {}
    if int(fnum(_counts.get("exchange_manual_mismatch"), 0)) > 0:
        _block = "LEDGER_EXCHANGE_DIVERGENCE"
```

**Unblock condition, in one sentence:** the block clears on the next cycle whose freshly-written status reports
`exchange_manual_mismatch == 0` (or whose stamp is older than 120 s), because the gate consults only that file's current contents and its age.

**Risk stated plainly:** the same bound fails open. An engine whose integrity writer stops running for 120 s stops blocking even if the last
known state was divergent. That is the reverse of the original stale-block bug and it is not yet asserted by a test.

## Answer 4 — ENG-018: two paths, and what "zero send" means

Path A, aggregation (per-event authority → account-net desired):

```
event_authorised_desired_net :862   <- convergence_notional_for_fill :2459   <- convergence_order_for_coin :2433
```

Path B, send (desired vs account-net → one order):

```
convergence_order_for_coin :2433
    desired = event_authorised_desired_net(...)          # the aggregate
    order   = compute_convergence_order(coin, desired_net, actual_net, ...)   # imported from convergence_shadow
```

These are two related paths, not one chain: A decides *what the book should be*, B decides *what single order moves the account toward it*.
`compute_convergence_order` is imported (`from convergence_shadow import compute_convergence_order`), and the caller sends only when
`copy_notional >= MIN_ORDER_NOTIONAL` (`MIN_ORDER_NOTIONAL = 10.0`).

**Reconciling zero-send with copy-the-leader:** what is copied is the leader's *effect on the aggregate position*, not each event as its own
order. With leaders at +3 and −1 the aggregate is +2 and one order of 2.0 is sent. With +2 and −2 the aggregate is 0; if the account already
holds 0, there is no position to change, so no send is correct and nothing is "skipped" — the leader events are still folded into attribution.
The bounded exception, which the order must state: a leader event whose *own* size is below `MIN_ORDER_NOTIONAL` produces no single-event order;
its effect waits in the aggregate until the net crosses the threshold. That is the only sense in which an individual leader action is not
mirrored one-for-one, and it is a threshold rule, not a netting skip.

## Answer 5 — Graphify: GRAPHIFY_UNAVAILABLE for base anchoring

`C:/Users/wigmore/bin/graphify` exists and runs, but invoking it produced a scan of the working tree rather than a ref-targeted build, and no
argument for pinning a commit was evident. Worse, the two existing maps already disagree: `hyperliquid-build3-repair/graphify-out/graph.json`
reports `built_at_commit db7b4b88…`, while `oc-runs/w87-clean/graphify-out/graph.json` reports `81c394bd…`. Neither is `c63d2299`.

**GRAPHIFY_UNAVAILABLE** is therefore recorded for this base: no map can be cited as proof for `c63d2299` until one is rebuilt at that ref.
Every call path above was read from source, not from a map.

## Answer 6 — G0 is a snapshot, not a gate change

Accepted. The G0 entry is being moved out of `certification/gate_changes.jsonl` into `certification/snapshots/G0_SNAPSHOT.json` with
`kind: snapshot`, `not_a_gate_change: true`, and the ledger restored byte-identically to its three gate-change lines.

## Status per row (unchanged by this revision)

- **ENG-018** — aggregation verdict only, 9 unconditional checks green at the base; send-semantics RED in progress on `backup/r4-eng018-send-proof`. Not a PASS.
- **ENG-019** — held on `c64d80e8` pending the double-poll must-fix; no testnet run until that commit is reviewed.
- **SET-009** — **FAIL for landing at `3072c593`**: O1 is a stale invariant (fix the constant to the true census), the stale-positive case is untested, and the three mutations have not been run.
