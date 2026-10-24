# LAG ARTEFACT SPLIT - run8 2026-10-24 (order 6389148772)

Read-only source: run8/state_20261024. Engine PID 5704, sole start 2026-10-24T16:24:19Z.
Rule: a leader fill timestamped before engine start cannot be copied live; its lag is start-up catch-up.

## Q1 split of rows carrying leader_to_intent_ms

| subset | definition | rows |
|---|---|---|
| (a) | fill BEFORE 16:24:19Z, start-up catch-up | 12 |
| (b) | fill AT/AFTER 16:24:19Z, live traffic | 269 |
| total | | 281 |

Controller's 273 = same population at an earlier read; append-only grew to 281 carry rows.

- ALL: p50 1.0s, p95 13.3s, max 5774.7s
- (a): p50 3746.5s, max 5774.7s, every lag exceeds intent_time - start
- (b): p50 1.0s, p95 2.7s, max 14.2s

The 1077s-class figure is entirely an artefact of (a).

### (b) per wallet, p95 desc

| wallet | n | p50 | p95 | max |
|---|---|---|---|---|
| 0x7717a7a245d9f950e586822b8c9b46863ed7bd7e | 196 | 1.0s | 3.5s | 14.2s |
| 0xd4c1f7e8d876c4749228d515473d36f919583d1d | 70 | 1.1s | 2.4s | 2.8s |
| 0x21ca98106c69bff036a194648ba30388ccbe811d | 1 | 1.7s | 1.7s | 1.7s |
| 0xbee0000c04ee2efe66234bec57f7eaf38818fbca | 2 | 0.9s | 1.0s | 1.0s |

### Ten slowest (b) rows - all 0x7717a7a2, queue_wait_ms ~97% of lag

| intent_id | coin | leader fill | intent | lag | status | terminal_state | queue_wait |
|---|---|---|---|---|---|---|---|
| 3dac85f5df99f2726728601a280ff56f | USELESS | 16:52:47.894Z | 16:53:04.401Z | 14.2s | ORDER_REJECTED | MISSED_ENTRY_IOC_NO_MATCH | 13779ms |
| 61c617c1cefbf2cbfbbe53a8cc550dec | TIA | 16:52:48.256Z | 16:53:04.240Z | 13.8s | ORDER_FILLED | FILLED_AWAITING_COPY_POLL | 13432ms |
| 27b4e6a22117684916b158f06ed0ce36 | JTO | 16:52:51.220Z | 16:53:05.725Z | 13.3s | ORDER_FILLED | FILLED_AWAITING_COPY_POLL | 12900ms |
| 3004144bbbab99e32919815a703ae88e | CHIP | 16:52:53.590Z | 16:53:07.614Z | 12.7s | ORDER_FILLED | FILLED_AWAITING_COPY_POLL | 12367ms |
| 34b97a01b65739c49ace00ec0eb13277 | CHIP | 16:52:51.220Z | 16:53:06.030Z | 10.9s | ORDER_FILLED | FILLED_AWAITING_COPY_POLL | 10522ms |
| ba2f47de15122ef285b696af1864de83 | TIA | 16:52:55.095Z | 16:53:05.464Z | 9.4s | ORDER_FILLED | FILLED_AWAITING_COPY_POLL | 9003ms |
| 53cf169b6965c0e5bf43c282f1ab1211 | XYZ:LITE | 17:03:56.529Z | 17:04:03.702Z | 6.0s | ORDER_REJECTED | MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN | 5493ms |
| 3fddbcbebd345fd541588499197704fe | S | 16:52:58.979Z | 16:53:04.907Z | 4.3s | ORDER_FILLED | FILLED_AWAITING_COPY_POLL | 3920ms |
| 4bada5e3381bba5bea0dbe507284a656 | CHIP | 18:20:34.569Z | 18:20:40.225Z | 3.9s | ORDER_FILLED | FILLED_AWAITING_COPY_POLL | 3503ms |
| bc7f5d289cf939d836cfdb8dec975b76 | XYZ:CRCL | 20:00:10.011Z | 20:00:15.959Z | 3.5s | ORDER_REJECTED | EXIT_RECOVERY_REQUIRED | 1731ms |

State in between: send queue (queue_wait_ms dominates, not leader-poll or SDK time).

### Verdict

0x7717 is NOT a real stall in (b): n=196, p50 1.0s, p95 3.5s, max 14.2s. The 1077s/5774s tail lives only in the 12 pre-start rows.

## Q2 six silent LIVE wallets

Roster live_config.json enabled+LIVE = 10. Four appear in send_attempts.csv. Source for fills seen:
leader_poll_trace.jsonl field `new` (post-start polls), cross-checked with fill_trace.jsonl `w` and
reconciliation FILL_MERGED.

| wallet | polls | fills seen | fill_trace | intents | attempts | LIQ_PARITY | top other block | class |
|---|---|---|---|---|---|---|---|---|
| 0xfe7ce058edc7cfcde9ef8262ba51f8d4796ab7ae | 123 | 4 | 5 | 835 | 0 | 5 | OWNERSHIP_CONTRACT_BLOCK 826 | BLOCKED |
| 0x8455193b0490ad091819000b01cd9bb833ac974b | 123 | 0 | 0 | 7 | 0 | 0 | FILL_MERGED 141, OWNERSHIP_CONTRACT_BLOCK 2 | BLOCKED (marginal) |
| 0x92bbd8110393350dda7e9c32089e95af071a9b6f | 123 | 0 | 0 | 108 | 0 | 0 | OWNERSHIP_CONTRACT_BLOCK 108, FILL_MERGED 91 | BLOCKED |
| 0x20ad988487d6a53fea7918657f45fe0bb8fd8183 | 123 | 0 | 0 | 0 | 0 | 0 | STALE_WS_SNAPSHOT_IGNORED 20 | QUIET |
| 0x46926d8fad4a36047a73ed7be1cec963c77fef87 | 123 | 0 | 0 | 0 | 0 | 0 | STALE_WS_SNAPSHOT_IGNORED 10 | QUIET |
| 0x77eeda199553e33b246e4b4666849b9ad0972902 | 123 | 0 | 0 | 0 | 0 | 0 | STALE_WS_SNAPSHOT_IGNORED 9 | QUIET |

None of the six is refused by LIQ_PARITY alone. Sanitised: no balances, no keys; data read-only; no config/roster/cap changes.
