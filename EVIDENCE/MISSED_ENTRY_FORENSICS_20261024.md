# Missed-entry recovery - production forensics (order 6390203540)

Read-only. Data (unmodified): `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run8/state_20261024/` - `append_only/reconciliation.csv`, `append_only/send_attempts.csv`, `append_only/order_intents.csv`, `resting_entry_orders.json`, `fill_trace.jsonl`, `leader_poll_trace.jsonl`.

Question: the recovery passes its fake-exchange test (M2 passive GTC at leader price, M3 retry-once-inside-cap then rest). In production 11 intents end at `MISSED_ENTRY_IOC_NO_MATCH` with no later GTC at all, while a different set of 21 produced `REAL_GTC_MISSED_ENTRY_LIMIT`. Which of the three preconditions - (1) `missed` set, (2) asset safe, (3) no existing resting entry for the same wallet+coin+side - failed?

## Answer in one line

Condition (3) failed for all 11: an unresolved `ORDER_RESTING` row already existed on the same wallet+coin+side, so `resting_entry_for` suppressed the GTC by design. Condition (2) failed for the halted set: the exchange refused the order. No production defect is evidenced.

## 1. The 11 MISSED_ENTRY_IOC_NO_MATCH intents

All `decision=ENTRY_ALLOWED`, `lifecycle=ENTRY`, ENTRY adds on FLAT books.

| # | intent_id | coin | wallet | side | ts UTC | blocker | blocker id | blocker ts | size | later GTC |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | d129965e6b209124df290f3f02f5b452 | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:25:31.968 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 2 | 6e4e74e52bbc73fe2a4052301689c091 | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:25:53.299 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 3 | f87e12f1276ca1bde2d051fd7af704f8 | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:26:13.940 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 4 | 03bf67c86827fd49074b2a83dc3bb939 | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:28:04.714 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 5 | 8ce3707ad4cb3ab76f25f5db38bcc01a | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:28:24.814 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 6 | 5846a9549e800ef63f693c3434185227 | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:28:45.828 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 7 | 5c723a99b9c315ac150d059443062f13 | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:29:06.412 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 8 | e44aa3a498847c0eabc98a19f8531615 | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:30:23.687 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 9 | 746617cc8224599f73f4c8e312ba1285 | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:30:54.121 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 10 | 370d163ad79ffce96a53d9048f9f6b92 | XYZ:PLATINUM | 0x7717a7a2 | BUY | 16:31:24.238 | YES | 2a21983f9f23f7b8 | 16:25:23.935 | 0.0077 | 0 |
| 11 | 3dac85f5df99f2726728601a280ff56f | USELESS | 0x7717a7a2 | BUY | 16:53:04.402 | YES | 516347930bc6f170 | 16:50:08.507 | 78.0 | 0 |

Counts: YES 11, NO 0, UNKNOWN 0.

Corroboration from `resting_entry_orders.json` - the PLATINUM blocker is real and still open:

```
oid 63579216285  XYZ:PLATINUM BUY  size 0.0077  open_size 0.0077
placed_ms 1792859123932 (16:25:23.932)  open_checked_ms 1792880281837 (23:38:01)
intent_id 2a21983f9f23f7b8e3015629ca66aeec
why: copy order found no match (Order could not immediately match against any resting orders. asset=750035)
```

That intent `2a21983f` is itself one of the 21 that produced a `REAL_GTC_MISSED_ENTRY_LIMIT` (`ORDER_RESTING`, `ENTRY_LIMIT_RESTING_PRICE_MOVED`, 0.0077, 16:25:23.935). The recovery did fire on this coin - once - and its own resting order then blocked the next ten missed entries on the same key. The blocker was still open at 23:38, over seven hours later.

## 2. Market-halted intents (MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN)

Discrepancy to flag: the order states 13; `reconciliation.csv` carries 25 distinct intent_ids with this terminal state, all `reject_category=MARKET_HALTED`, all `decision=ENTRY_ALLOWED`. All 25 reported.

| # | intent_id | coin | wallet | side | ts UTC | resting blocker | later GTC |
|---|---|---|---|---|---|---|---|
| 1 | 1cc56f23fbb1072eedf065baa49f63dd | ZEC | 0x7717a7a2 | BUY | 16:48:38 | NO | 0 |
| 2 | 505b150dfa542565610d12589d2b562c | XYZ:MRVL | 0x7717a7a2 | SELL | 17:03:53 | NO | 0 |
| 3 | 53cf169b6965c0e5bf43c282f1ab1211 | XYZ:LITE | 0x7717a7a2 | SELL | 17:04:03 | NO | 0 |
| 4 | 9f1231553b92ba190fad502deecc499d | XYZ:EWY | 0x7717a7a2 | SELL | 17:06:25 | NO | 0 |
| 5 | fb9825e149f4ffdbb86eb2a62499170c | ZEC | 0x7717a7a2 | BUY | 17:29:54 | NO | 0 |
| 6 | eb160ace513354f1251092a84884e89f | ZEC | 0x7717a7a2 | BUY | 18:03:17 | NO | 0 |
| 7 | c82ea7180b05665cb0140885961471e6 | ZEC | 0x7717a7a2 | BUY | 18:18:34 | NO | 0 |
| 8 | 7a35add077e9d30f8117a9174ed4885f | XYZ:HYUNDAI | 0x7717a7a2 | SELL | 18:53:17 | NO | 0 |
| 9 | 7ce63e990e3f72ca2419b02f58de14d5 | XYZ:MRVL | 0x7717a7a2 | SELL | 19:06:44 | NO | 0 |
| 10 | 33e386e1ec65be9595fe764d1370e92c | XYZ:EWY | 0x7717a7a2 | SELL | 19:06:47 | NO | 0 |
| 11 | 5dc88ef51162f27b51f1cbf64ccf9ce8 | XYZ:HYUNDAI | 0x7717a7a2 | SELL | 19:17:21 | NO | 0 |
| 12 | 5989d1fabf894e85ab44a1265ae9549d | ZEC | 0xd4c1f7e8 | SELL | 20:02:33 | NO | 0 |
| 13 | 02941501965f689a0a8edfed203317c2 | XYZ:KORU | 0x7717a7a2 | SELL | 20:04:30 | NO | 0 |
| 14 | f373a2a9d1f7bfcfb70306834fb0d567 | ZEC | 0xd4c1f7e8 | SELL | 20:15:18 | NO | 0 |
| 15 | 6152f6b48d1ebd66f5144d0574a47f17 | ZEC | 0xd4c1f7e8 | SELL | 20:25:21 | NO | 0 |
| 16 | 32aec791bf46a55a77963325b80939f8 | ZEC | 0xd4c1f7e8 | SELL | 20:35:33 | NO | 0 |
| 17 | e95c6116148b97d2d75219b4b1d86f80 | XYZ:NOW | 0x7717a7a2 | BUY | 20:37:37 | NO | 0 |
| 18 | e7f381eb538e0414d6810c1042a6d873 | ZEC | 0xd4c1f7e8 | SELL | 20:45:36 | NO | 0 |
| 19 | b367086e4a4faf1b13b06d41701467d0 | ZEC | 0xd4c1f7e8 | SELL | 20:55:55 | NO | 0 |
| 20 | 5a42a1b3b2178e6533382c936639348e | ZEC | 0xd4c1f7e8 | SELL | 21:05:59 | NO | 0 |
| 21 | b4bc0c8c967dd00af6d24a4774162f15 | ZEC | 0xd4c1f7e8 | SELL | 21:21:22 | NO | 0 |
| 22 | 60d0ddcf81f48c2abdf46e4e349c5046 | ZEC | 0x7717a7a2 | BUY | 21:32:35 | NO | 0 |
| 23 | 128fef4efcf307f6e367f20843f38c25 | ZEC | 0xd4c1f7e8 | SELL | 21:42:36 | NO | 0 |
| 24 | 271e7d01e88bc43ad1f881d16765b07e | ZEC | 0xd4c1f7e8 | SELL | 21:52:55 | NO | 0 |
| 25 | a09b6f18ff416e0a260b79bd9357b9e5 | ZEC | 0xd4c1f7e8 | SELL | 22:04:57 | NO | 0 |

Counts: YES 0, NO 25, UNKNOWN 0. ZEC repeats every ~10 minutes on the same wallet+side from 20:02 to 22:05 - a halted market retried by new leader fills, each refused with the same category.

## 3. Follower mid at the time

NOT RECORDED for all 36 intents. No follower mid (nor book/bbo/mark) field exists in retained state: `send_attempts.csv` carries only the engine's `limit_price` on GTC rows, `order_intents.csv` only `leader_price`. `fill_trace.jsonl` keys are timing/stage stamps; `leader_poll_trace.jsonl` keys are cursor/count/status. `_FOLLOWER_MIDS` is a live in-memory cache, never persisted historically. No price reconstructed or approximated. Under invariant G this is "the data to answer it was never recorded", not a negative finding about the engine.

## 4. Contrast - the 21 intents that produced REAL_GTC_MISSED_ENTRY_LIMIT

All 21: `order_type=REAL_GTC_MISSED_ENTRY_LIMIT`, `status=ORDER_RESTING`, `terminal_state=ENTRY_LIMIT_RESTING_PRICE_MOVED`.

| intent_id | coin | dex | side | ts UTC | prior resting entry on same key (self excluded) |
|---|---|---|---|---|---|
| 548ed973f3b85662 | HYPE | main | BUY | 16:24:59 | NO |
| 2a21983f9f23f7b8 | XYZ:PLATINUM | xyz/builder | BUY | 16:25:23 | NO |
| bb030b206f121b16 | CHIP | main | BUY | 16:28:27 | NO |
| a104d7801deaf94a | BIGTIME | main | BUY | 16:50:02 | NO |
| 516347930bc6f170 | USELESS | main | BUY | 16:50:08 | NO |
| 8890d8d9e852c973 | TIA | main | BUY | 16:50:21 | NO |
| 642bd5c3a9ef321a | CHIP | main | BUY | 16:55:33 | YES (bb030b20) |
| 40e0643382a679d2 | ANIME | main | BUY | 17:04:12 | NO |
| 2d232da9fdc0fc99 | NXPC | main | BUY | 17:06:57 | NO |
| 20f91a72e7d16f40 | USELESS | main | BUY | 18:11:34 | YES (51634793) |
| 42a990dd2083e6ac | ANIME | main | BUY | 18:20:52 | YES (40e06433) |
| 7aa94a71db6c8626 | XYZ:CRCL | xyz/builder | SELL | 19:06:38 | NO |
| 9123873a68b2381d | XYZ:INTC | xyz/builder | SELL | 19:07:06 | NO |
| 7d92de2394227206 | HYPE | main | BUY | 19:17:43 | YES (548ed973) |
| b53187b430d3dd2b | SPX | main | BUY | 19:28:30 | NO |
| ad6924608d4f9c92 | VVV | main | BUY | 19:29:36 | NO |
| 70b551603afa901b | XYZ:CL | xyz/builder | BUY | 19:56:06 | NO |
| 25941eb26067d9ae | ANIME | main | BUY | 20:33:36 | YES (42a990dd) |
| 21390262b916df6c | ANIME | main | BUY | 21:22:07 | YES (25941eb2) |
| 39c41fd33fa478a8 | HYPE | main | BUY | 21:33:36 | YES (7d92de23) |
| c9af7a5b8e19594b | ANIME | main | BUY | 22:02:01 | YES (21390262) |

Totals: main-dex 17, xyz/builder 4; first resting entry for its key 13, repeat while an earlier one was open 8. All 21 have `open_size` in `resting_entry_orders.json` - all were real resting orders.

## 5. Conclusion

- Condition (3) "no existing resting entry" is ELIMINATED as the unknown - it is the answer, and it failed by design for every one of the 11. Each IOC-no-match intent had an unresolved ORDER_RESTING row on the identical wallet+coin+side created before it; for the ten PLATINUM intents that row is the output of the recovery itself (intent 2a21983f, oid 63579216285, still open at 23:38). Skipping the GTC is the documented `resting_entry_for` behaviour, not a lost order.
- Condition (2) "asset safe" is ELIMINATED as the explanation for the 11 and confirmed as the cause for the halted set. All 11 were `decision=ENTRY_ALLOWED`, and 4 of the 21 successful GTC rows are xyz/builder coins (PLATINUM among them), so builder-dex per se does not block recovery. For the 25 halted intents the exchange returned MARKET_HALTED on the IOC; a passive GTC cannot rest on a halted book, so no GTC is correct there.
- Condition (1) "missed set" is ELIMINATED as a candidate - the MISSED_ENTRY_* terminal states are present on all 36 rows.
- Still UNKNOWN, stated plainly: (a) the follower mid at each timestamp was never recorded, so no price-relative check (was a passive GTC inside the cap) can be made from this data; (b) whether a resting entry open for seven-plus hours should still suppress new missed-entry recoveries cannot be determined from these files - that is a staleness policy question, and the data shows only that it did.

Verdict: the evidence does not support a production defect. It supports the opposite reading - the recovery fired on PLATINUM (oid 63579216285) and then correctly suppressed duplicates, while the halted intents were refused by the exchange. The test's three preconditions explain every observed case with nothing left over. The residual questions are a never-recorded mid (invariant G gap) and a resting-order staleness policy, neither of which this data can settle.

Sanitisation: no balances, no private keys, no secrets; wallet addresses in the 10-character control-plane form. Read-only throughout - no engine start/stop, no port binding, no exchange calls, no config/roster/cap changes.
