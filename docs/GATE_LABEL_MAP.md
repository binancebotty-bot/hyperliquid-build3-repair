# GATE_LABEL_MAP — Build 3 trade-blocking labels and their CC-1 blocking category

Task: CC-1 / R21 T-B. Repo `hyperliquid-build3-repair`, commit `a1acc28`, engine Core
`_archive/hl_stage2/HL_Live_Copy_Service_Core.py` (16995 lines). Docs only; no Core or test change.

Purpose: every label the engine can use to refuse, skip or silently decline a trade must map to one of the ten
governance-approved blocking categories (CC-1 / GUT section E). A label that maps to none is `NO_CATEGORY` and is a
finding: the engine can refuse a trade for a reason governance does not recognise.

## How the labels were found (re-runnable)

Worktree: `git worktree add --detach C:/Users/wigmore/tmp/tb_labels a1acc28`

Greps, run in `_archive/hl_stage2`:

```
grep -nE 'return (False, )?"[A-Z][A-Z0-9_]{4,}"' HL_Live_Copy_Service_Core.py
grep -nE 'f"(ENTRY_BLOCKED|SEND_BLOCKED|NO_SEND|SKIP)' HL_Live_Copy_Service_Core.py
grep -nE '"(terminal_state|reject_category|action|operator_action)="' HL_Live_Copy_Service_Core.py
grep -nE 'startswith\("(OWNERSHIP_GATE_|SEND_NOT_ATTEMPTED_|LIQ_PARITY_|ENTRY_BLOCKED_)' HL_Live_Copy_Service_Core.py
sed -n '8095,8200p;5340,5390p;6940,7010p;8280,8540p;12900,13010p;1110,1200p' HL_Live_Copy_Service_Core.py
```

A Python pass over every upper-case string literal returned or written as `terminal_state=` / `reject_category=` /
`action=` / `operator_action=`, plus the three row-name frozensets at Core:1113-1196, produced **358 candidate
upper-case strings**. Those include non-blocking vocabulary (lifecycle words, health grades, terminal-class words,
allow decisions, direction words, and audit action names describing successful bookkeeping). Those are excluded below
and listed under WHAT I COULD NOT CLASSIFY.

Labels built by concatenation, which do not grep cleanly, are called out explicitly:

- `ENTRY_BLOCKED_{entry_block_reason}` — Core:8111. Only the suffix `RISK` is observed in this tree.
- `SEND_NOT_ATTEMPTED_{decision}` — Core:12977, terminal_state.
- `NO_SEND_{decision}` — Core:12984, audit action.
- `OWNERSHIP_GATE_*`, `LIQ_PARITY_*`, `SEND_NOT_ATTEMPTED_*` — matched as prefixes by
  `send_status_reaches_catchall` (Core:1186-1191).

## Category key

1 exchange/venue safety and reduce-only; 2 ownership and attribution uncertainty; 3 mode/configuration unreadable
or not applied; 4 liquidity, minimum notional and dust; 5 risk caps and exposure limits; 6 stale or missing market
data; 7 authentication, signer and account identity; 8 maintenance, outage and degraded venue state; 9 operator/CLI
explicit instruction; 10 invariant protection (the invariant is named); NO_CATEGORY = no approved category.

## Label table

| # | label | file:line | where returned | meaning | category |
|---|---|---|---|---|---|
| 1 | INTENT_NOT_SEND_ALLOWED | 8097 | `send_if_allowed` | intent was built with send_allowed=False | 10 (inv: nothing is sent without a send_allowed intent) |
| 2 | MASTER_REAL_ORDERS_OFF | 8102, 4074, 12878 | `send_if_allowed`, master gate, terminal row | global master real-orders switch off | 3 |
| 3 | SEND_BLOCKED_SENDER_KEY_NOT_VALID | 8104 | `send_if_allowed` | follower exchange does not know the signing key | 7 |
| 4 | ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY | 8109, 5679 | `send_if_allowed`, pre-send mode check | global send mode is CLOSE | 3 |
| 5 | ENTRY_BLOCKED_RISK | 8111 (`ENTRY_BLOCKED_{reason}`), 1137 | constructed prefix; terminal row name | risk/budget gate refused an entry | 5 |
| 6 | SEND_BLOCKED_LEADER_ALREADY_REDUCED | 8113 | `send_if_allowed` | leader reduced this coin after the fill | 2 |
| 7 | OWNERSHIP_GATE_MISSING_AUDIT_PROOF | 6946 | `_ownership_gate_block` | no audit proof for the ownership gate | 2 |
| 8 | OWNERSHIP_GATE_MISSING_EXCHANGE_PROOF | 6949 | `_ownership_gate_block` | persisted exchange positions unreadable | 2 |
| 9 | OWNERSHIP_GATE_UNEXPLAINED_EXCHANGE_POSITION | 6968, 6988 | `_ownership_gate_block` | exchange holds a position the sleeves do not explain | 2 |
| 10 | OWNERSHIP_GATE_SIGN_CONFLICT | 6979 | `_ownership_gate_block` | ledger and exchange net have opposite signs | 2 |
| 11 | OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE | 7006 | `_ownership_gate_block` | close intent has no matching wallet sleeve | 2 |
| 12 | OWNERSHIP_GATE_BLOCKED | 8139 | `_ownership_gate_block` | fallback status when the gate dict has none | 2 |
| 13 | OWNERSHIP_GATE_SHARED_SYMBOL_AMBIGUOUS | 1160 set / gate family | NON_TERMINAL row, gate | several sleeves hold the coin on a close | 2 |
| 14 | OWNERSHIP_GATE_UNRESOLVED_SYMBOL | gate family | gate | symbol unresolved for the ownership check | 2 |
| 15 | OWNERSHIP_GATE_ACCOUNT_RESIDUAL | gate family | gate | account-level residual not attributable | 2 |
| 16 | SKIPPED_MARKET_HALTED | 8145 | `send_if_allowed` | coin in post-halt cooldown | 8 |
| 17 | SKIPPED_IOC_NO_IMMEDIATE_MATCH | 8147 | `send_if_allowed` | coin in IOC-no-match cooldown | 1 |
| 18 | SKIPPED_INSUFFICIENT_MARGIN | 8149 | `send_if_allowed` | coin in margin-reject cooldown | 5 |
| 19 | EXIT_ATTEMPT_COOLDOWN | 8180 | `send_if_allowed` | second close attempt inside 60s | 10 (inv: one close attempt per coin in flight) |
| 20 | PENDING_EXIT_GUARD_ACTIVE | 8192, 1187 | `send_if_allowed`, retained set | a close for this coin is already reserved | 10 (inv: no duplicate full-sleeve close) |
| 21 | LIQ_PARITY_BLOCKED | 8171, 6098 | `send_if_allowed`, `liq_parity_block` | projected liquidation parity not provable | 1 (inv: follower liq not worse than leader) |
| 22 | BLOCKED_OFF | 8088, 5331 | send-time mode block, intent-time gate | wallet disabled | 3 |
| 23 | BLOCKED_CLO_ENTRY | 8092, 5336 | send-time mode block, intent gate | wallet in CLO, lifecycle is entry/add | 3 |
| 24 | MISSING_INTENT_CONTEXT | 5662 | pre-send ownership check | called with intent=None | 10 (inv: no send without an intent to check) |
| 25 | WALLET_DISABLED_AT_SEND | 5670 | pre-send mode check | wallet disabled between intent and send | 3 |
| 26 | WALLET_OFF | 4094, 5673 | mode readers | wallet mode OFF | 3 |
| 27 | CLO_BLOCKS_ENTRY | 5676 | pre-send mode check | wallet mode CLO blocks entry/add | 3 |
| 28 | SYMBOL_BLOCKED | 4239 | symbol policy | coin on the configured blocklist | 9 |
| 29 | SYMBOL_NOT_ALLOWED | 4241 | symbol policy | coin not on the configured allow-list | 9 |
| 30 | COPY_ACCOUNT_NOT_CONFIGURED | 5037 | exposure reader | USER_WALLET is not a valid address | 3 |
| 31 | SYMBOL_UNAVAILABLE | 5297, 5340 | intent gate | coin not resolvable to a tradable symbol | 6 |
| 32 | SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION | 5344 | intent gate | flat wallet got a leader close; would open a reverse position | 2 |
| 33 | BELOW_MIN_NOTIONAL | 5348 | intent gate | entry/add notional below configured minimum | 4 |
| 34 | SEND_BLOCKED_RISK (no fresh follower price) | 5355 | `_risk_block` | no fresh follower-network price to value the order | 6 |
| 35 | SEND_BLOCKED_RISK (max order notional) | 5362 | `_risk_block` | order notional over max_order_notional | 5 |
| 36 | SEND_BLOCKED_RISK (resting limits unreadable) | 5368 | `_risk_block` | open orders unreadable while a cap is set | 6 |
| 37 | SEND_BLOCKED_RISK (max wallet exposure) | 5374 | `_risk_block` | wallet exposure cap breached | 5 |
| 38 | SEND_BLOCKED_RISK (unowned inventory) | 5379 | `_risk_block` | would net into inventory the engine does not own | 2 |
| 39 | SEND_BLOCKED_RISK (exposure cap) | 5384 | `_risk_block` | total/per-asset exposure cap breached | 5 |
| 40 | SEND_NOT_ATTEMPTED_MISSED_ENTRY_ALREADY_RESTING | 6689 | missed-entry path | a resting limit already covers this fill | 10 (inv: one order per fill) |
| 41 | RESTING_ENTRY_CANCELLED_SENDING_OFF | 6739 | `_withdraw_rows` | sending switched off; resting entry withdrawn | 3 |
| 42 | SEND_NOT_ATTEMPTED_STANDING_CLOSE_IN_PLACE | 7135 | `_place_order` | a standing close order already exists | 10 (inv: one standing close per sleeve) |
| 43 | SEND_NOT_ATTEMPTED_STANDING_CLOSE_FILLED | 7165 | `_place_order` | standing close already filled | 10 (inv: one standing close per sleeve) |
| 44 | ORDER_CANCELLED | 7391 | `_place_order` | order cancelled instead of placed | 1 |
| 45 | EXCHANGE_ERROR | 7474 | `_place_order` | exchange call raised | 8 |
| 46 | ORDER_REJECTED | 8653 | `_place_order` | venue rejected the order | 1 |
| 47 | ORDER_UNKNOWN | 9930 | send reconciliation | order outcome undeterminable | 8 |
| 48 | EXCHANGE_CALL_ERROR_REVIEW_REQUIRED | 1024 | terminal classifier | exchange error needs human review | 8 |
| 49 | SEND_NOT_ATTEMPTED_UNSUPPORTED_SYMBOL | 8311 | `_send_real` | symbol not copyable from the asset cache | 6 |
| 50 | REAL_SENDER_NOT_CONFIGURED | 8343 | `_send_real` | sender/symbol resolution not configured | 7 |
| 51 | CREDENTIALS_MISSING | 8351 | `_send_real` result status | no HL private key | 7 |
| 52 | SDK_UNAVAILABLE | 8353, 12863 | `_send_real`, exit recovery | hyperliquid SDK not importable | 7 |
| 53 | SEND_NOT_ATTEMPTED_SYMBOL_REJECT_CIRCUIT | 8378 | `_send_real` | size/notional reject circuit breaker active | 1 |
| 54 | SEND_NOT_ATTEMPTED_FOLLOWER_PRICE_UNAVAILABLE | 8407 | `_send_real` | no fresh follower-network price | 6 |
| 55 | SEND_NOT_ATTEMPTED_LEADER_PRICE_UNAVAILABLE | 8424 | `_send_real` | no fresh leader price for the missed-entry comparison | 6 |
| 56 | SEND_NOT_ATTEMPTED_CLOSE_ADVERSE_DIFF | 8455 | `_send_real` | close limit too adverse vs follower price | 5 |
| 57 | SEND_NOT_ATTEMPTED_BELOW_SYMBOL_MIN_EXCEEDS_COPY_NOTIONAL | 8485 | `_send_real` | symbol minimum exceeds the copy notional | 4 |
| 58 | SEND_NOT_ATTEMPTED_BELOW_SYMBOL_MIN_EXCEEDS_MAX_ORDER | 8506 | `_send_real` | symbol minimum exceeds max_order_notional | 4 |
| 59 | SEND_NOT_ATTEMPTED_INVALID_SIZE | 8526 | `_send_real` | wire size rounds to <= 0 | 4 |
| 60 | SEND_NOT_ATTEMPTED_AUDIT_WRITE_FAILED | 8822 | `_send_real` | audit write failed before the order | 10 (inv: no send without an audit proof row) |
| 61 | SYMBOL_CACHE_MISS_NEEDS_REFRESH | 9796 | symbol resolver | asset cache miss, refresh required | 6 |
| 62 | SYMBOL_UNRESOLVED | 9811 | symbol resolver | indexed symbol unresolvable | 6 |
| 63 | SYMBOL_NOT_TRADABLE_BY_SENDER | 9861 | symbol resolver | coin exists but the sender cannot trade it | 6 |
| 64 | ASSET_META_SNAPSHOT_ONLY_SEND_BLOCKED | 1116 | terminal row, `LOCAL_BLOCK_NO_EXCHANGE` | only snapshot meta; sends fail closed | 6 |
| 65 | SYMBOL_SNAPSHOT_ONLY_NO_AUTHORITATIVE_META | 1213 | symbol status | snapshot-only metadata | 6 |
| 66 | SYMBOL_CACHE_MISS | 1215 | symbol status | cache miss | 6 |
| 67 | SYMBOL_NOT_LISTED | 1215 | symbol status | symbol not on the venue | 6 |
| 68 | META_UNAVAILABLE | 1211 | symbol status | metadata unavailable | 6 |
| 69 | SENDER_KEY_NOT_VALID | 923 | exchange error classifier | exchange does not know the signing key | 7 |
| 70 | MANUAL_REVIEW_FIX_SENDER_KEY_SENDING_STOPPED | 5773 | sending-stop path | sender key bad; sending stopped | 7 |
| 71 | MARKET_HALTED | 921 | exchange error classifier | venue halted the coin | 8 |
| 72 | INSUFFICIENT_MARGIN | 929 | exchange error classifier | not enough margin | 5 |
| 73 | REDUCE_ONLY_REJECTED | 931 | exchange error classifier | reduce-only order rejected | 1 |
| 74 | SYMBOL_OR_ASSET_REJECTED | 933 | exchange error classifier | venue rejected symbol/asset | 1 |
| 75 | PRICE_OR_TICK_REJECTED | 937 | exchange error classifier | price/tick invalid | 1 |
| 76 | SIZE_OR_NOTIONAL_REJECTED | 939 | exchange error classifier | size/notional invalid at the venue | 1 |
| 77 | RATE_LIMIT | 913 | exchange error classifier | venue rate limit | 8 |
| 78 | TIMEOUT | 914 | exchange error classifier | call timed out | 8 |
| 79 | RATE_LIMIT_OR_TIMEOUT | 935, 2426 | classifier, order retry | rate limit or timeout | 8 |
| 80 | IOC_NO_IMMEDIATE_MATCH | 925, 1120 | classifier, terminal row | IOC found no match | 1 |
| 81 | DUPLICATE_BLOCKED | 13208 | `process_leader_fill` | leader fill already handled | 10 (inv: one copy per leader fill) |
| 82 | DEDUPED | 13263 | `process_leader_fill` | fill de-duplicated | 10 (inv: one copy per leader fill) |
| 83 | PRE_CUTOVER_NOT_SENT | 13358 | pre-live-start block | engine has not passed live-start cutover | 3 |
| 84 | DAILY_LOSS_UNREADABLE | 13661 | daily loss gate | rolling daily P&L unreadable | 6 |
| 85 | DAILY_LOSS_LIMIT_REACHED | 13662 | daily loss gate | rolling daily loss limit hit | 5 |
| 86 | SCOPE_SWEEP_PENDING | 13827 | scope sweep gate | cross-DEX scope sweep not complete | 2 |
| 87 | SCOPE_SWEEP_FAILING | 1160, 13789 | terminal row, `ENTRIES_BLOCKED_UNTIL_SWEEP_CLEAN` | cross-DEX scope sweep failing | 2 |
| 88 | MANUAL_EXIT_RECOVERY_REQUIRED | 1120, 15652 | terminal row | close could not be placed; operator must exit | 2 |
| 89 | NO_MANUAL_POSITION_TO_CLOSE | 15637 | terminal row | nothing owned to close | 2 |
| 90 | SEND_NOT_ATTEMPTED_CLOSE_AT_TARGET | 12916, 12920 | terminal row | follower already at/past the close target | 10 (inv: no overshoot of a close target) |
| 91 | DUST_BELOW_MIN_NOTIONAL | 1117 | terminal row (mapped from SEND_NOT_ATTEMPTED_BELOW_MIN_NOTIONAL) | remainder is dust | 4 |
| 92 | CLOSE_ALREADY_AT_TARGET | 1117 | terminal row | close target already met | 10 (inv: no overshoot of a close target) |
| 93 | CLOSE_ADVERSE_DIFF_TOO_LARGE | 1117, 8455 | terminal row | close limit too adverse | 5 |
| 94 | BELOW_SYMBOL_MIN_EXCEEDS_COPY_NOTIONAL | 1160 set | NON_TERMINAL row | symbol min exceeds copy notional | 4 |
| 95 | BELOW_SYMBOL_MIN_EXCEEDS_MAX_ORDER | 1160 set | NON_TERMINAL row | symbol min exceeds max order | 4 |
| 96 | INVALID_WIRE_SIZE | 1160 set | NON_TERMINAL row | wire size invalid | 4 |
| 97 | BLOCKED_DUPLICATE_PRE_SEND | 1160 set | NON_TERMINAL row | duplicate detected pre-send | 10 (inv: one copy per leader fill) |
| 98 | BLOCKED_DUPLICATE_DEDUPE_STORE | 1160 set | NON_TERMINAL row | duplicate found in the dedupe store | 10 (inv: one copy per leader fill) |
| 99 | BLOCKED_NO_TERMINAL_RECORDED | 1160 set, 13394 | terminal row | send block with no terminal proof recorded | 10 (inv: every blocked send leaves a terminal proof) |
| 100 | BLOCKED_AT_PLACE_ORDER | 1115, 5691 | terminal row | blocked at place-order before the exchange call | 10 (inv: no exchange call without a recorded block reason) |
| 101 | BLOCKED_SEND_EXCEPTION | 1116 | terminal row | exception while sending | NO_CATEGORY |
| 102 | BLOCKED_SEND_UNCLASSIFIED | 1116, 12999 | terminal row, catch-all | send status the engine does not classify | NO_CATEGORY |
| 103 | BLOCKED_PROCESS_EXCEPTION | 1160 set | NON_TERMINAL row | exception in fill processing | NO_CATEGORY |
| 104 | PROCESS_EXCEPTION | 13056, 13158 | `process_leader_fill`, terminal row | unhandled exception processing a fill | NO_CATEGORY |
| 105 | SEND_EXCEPTION | 13375, 13370 | send path, terminal row | unhandled exception in the send path | NO_CATEGORY |
| 106 | EXCHANGE_REJECTED_UNKNOWN | 940 | exchange error classifier | venue rejection with no recognised class | NO_CATEGORY |
| 107 | MANUAL_REVIEW | 5346 | intent gate | copy notional is zero or sizing block text | NO_CATEGORY |
| 108 | NOT_APPLICABLE_SPOT | 5328 | intent gate | spot pair, no owned spot position | NO_CATEGORY |
| 109 | BLOCKED_SPOT_NOT_SUPPORTED | 5329 | intent gate | spot pair; only perps copyable | NO_CATEGORY |
| 110 | SEND_NOT_ATTEMPTED_SPOT_MARKET_SKIPPED | 8286 | `_send_real` | spot/index market not copyable by a perp sender | NO_CATEGORY |
| 111 | UNCLASSIFIED_SEND_BLOCK | 13005 | catch-all terminal row | unclassified send block | NO_CATEGORY |
| 112 | SEND_TERMINAL_UNCLASSIFIED | 13004 | catch-all | unclassified send terminal | NO_CATEGORY |
| 113 | UNRECORDED_SEND_BLOCK | 13394 | terminal row | send block that was never recorded | NO_CATEGORY |
| 114 | PERP_INDEX_MAPPING_UNVERIFIED | 1137 set, 8306 | terminal row | perp index mapping unverified | 6 |
| 115 | SYMBOL_REJECT_CIRCUIT_BREAKER_ACTIVE | 1162, 8380 | NON_TERMINAL row | reject circuit breaker active | 1 |
| 116 | MISSED_ENTRY_LEADER_ALREADY_CLOSED | 13090 | terminal row | leader already flat before the copy | 2 |
| 117 | MISSED_ENTRY_LEADER_ALREADY_REDUCED | 1137 set | terminal row | leader reduced before the copy | 2 |
| 118 | MISSED_ENTRY_LEADER_PRICE_UNAVAILABLE | 1120 set, 8424 | terminal row | no fresh leader price for the missed-entry check | 6 |
| 119 | MISSED_ENTRY_SKIP_META_UNAVAILABLE | 1137 set | terminal row | metadata unavailable at the missed-entry decision | 6 |
| 120 | MISSED_ENTRY_SKIP_SYMBOL_CACHE_MISS | 1137 set | terminal row | cache miss at the missed-entry decision | 6 |
| 121 | MISSED_ENTRY_SKIP_SYMBOL_SNAPSHOT_ONLY | 1137 set | terminal row | snapshot-only symbol | 6 |
| 122 | MISSED_ENTRY_SKIP_SYMBOL_NOT_TRADABLE_BY_SENDER | 1137 set | terminal row | symbol not tradable by this sender | 6 |
| 123 | MISSED_ENTRY_SKIP_SYMBOL_UNRESOLVED | 1137 set | terminal row | symbol unresolved | 6 |
| 124 | MISSED_ENTRY_SKIP_SPOT_MARKET_SKIPPED | 1137 set | terminal row | spot market skipped | NO_CATEGORY |
| 125 | MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED | 1137 set | terminal row | symbol not listed | 6 |
| 126 | EXCLUDED_NOT_LISTED_ON_FOLLOWER_NETWORK | 11798/11805 area | exclusion terminal row | coin not listed on the follower network | NO_CATEGORY |
| 127 | ILLIQUID_SKIP | 11798/11805 area | exclusion terminal row | market judged illiquid | 4 |
| 128 | SPOT_MARKET_SKIPPED | 8289 result status | `_send_real` result | spot market skipped | NO_CATEGORY |
| 129 | REDUCE_ONLY_REJECT_EXCHANGE_FLAT | 1137 set | terminal row | reduce-only rejected because the venue is flat | 1 |
| 130 | RESTING_ENTRY_FILLED_AFTER_LEADER_REDUCED | 1137 set | terminal row | resting entry filled after the leader reduced | 2 |
| 131 | RESTING_ENTRY_FILL_UNVERIFIED | 1137 set | terminal row | resting entry fill not verified | 2 |
| 132 | ENTRY_FILLED_AFTER_LEADER_REDUCED | 1119 | terminal row | entry filled after the leader reduced | 2 |
| 133 | SEND_NOT_ATTEMPTED_MAX_ORDER_NOTIONAL | 1137 set | terminal row | order over max_order_notional | 5 |
| 134 | SKIPPED_MARKET_HALTED | 1137 set | terminal row | market halted skip | 8 |
| 135 | SUPERSEDED_BY_RETRY | 1137 set | terminal row | attempt superseded by a retry | 10 (inv: one live attempt per fill) |
| 136 | SEND_OUTCOME_REVIEW_REQUIRED | 1137 set | terminal row | send outcome needs review | NO_CATEGORY |
| 137 | SEND_OUTCOME_UNKNOWN_MANUAL_ALERT | 1137 set | terminal row | send outcome unknown, manual alert | NO_CATEGORY |
| 138 | SEND_OUTCOME_CONFIRMED_CANCELLED_NO_RETRY | 1137 set | terminal row | confirmed cancelled, no retry | 10 (inv: no retry of a confirmed-cancelled order) |
| 139 | SEND_OUTCOME_DEFERRED_RESOLVED | 1137 set | terminal row | deferred outcome resolved | NO_CATEGORY |
| 140 | MARGIN_MODE_UNSET | 1137 set | terminal row | margin mode never set on the account | 3 |
| 141 | MARGIN_MODE_SETUP_PENDING | 1137 set | terminal row | margin mode setup in flight | 3 |
| 142 | MISSED_ENTRY_DIFF_MARGIN_SETUP_FAILED | 1137 set | terminal row | margin setup failed for a rest-or-diff order | 3 |
| 143 | MISSED_ENTRY_DIFF_MARGIN_SETUP_PENDING | 1137 set | terminal row | margin setup pending for a rest-or-diff order | 3 |
| 144 | MISSED_ENTRY_DIFF_LIMIT_REJECTED | 1137 set | terminal row | diff limit order rejected | 1 |
| 145 | MISSED_ENTRY_DIFF_NO_LIMIT_POSSIBLE | 1137 set | terminal row | no valid limit price can be derived | 6 |
| 146 | MISSED_ENTRY_DIFF_NO_FRESH_MID | 1137 set | terminal row | no fresh mid for the diff order | 6 |
| 147 | MISSED_ENTRY_LIMIT_OUTCOME_UNKNOWN | 1137 set | terminal row | resting missed-entry limit outcome unknown | NO_CATEGORY |
| 148 | MISSED_ENTRY_LIMIT_RESTED | 1137 set | terminal row | missed-entry limit rested | NO_CATEGORY |
| 149 | PRICE_SANITY_REJECTED | 1137 set, 9727 | terminal row | price failed sanity check | 6 |
| 150 | LIQUIDATION_NOT_APPLIED | 11063 | terminal row | liquidation detected, not applied to the ledger | 8 |
| 151 | OUTAGE_GAP | 14381 | terminal row | gap in fill coverage during an outage | 8 |
| 152 | REPLAY_DEFERRED_TRUTH_UNREADABLE | 13437 | terminal row | replay deferred, truth unreadable | 6 |
| 153 | REPLAY_DEFERRED_PAST_LIMIT_ALERT | 13424 | terminal row | replay deferred past the limit | NO_CATEGORY |
| 154 | REFUSED | 16093 | fill adoption | fills could not be read; adoption refused | 6 |
| 155 | PENDING_SEND | 6239 | startup review row | send row left pending on startup | NO_CATEGORY |
| 156 | USER_OWNED_ORDER_LEFT_UNTOUCHED | 6273 | terminal row | operator-owned order left alone | 9 |
| 157 | MOCK_ORDER_SUPPRESSED | 1187 | retained send_status | mock mode suppressed the order | 3 |
| 158 | HOLD_DUST_OR_AGGREGATE | 1094 | operator remedy text | hold dust or aggregate | 4 |
| 159 | COPY_NOTIONAL_TOO_SMALL_FOR_SYMBOL | 1098 | operator remedy text | copy notional too small for the symbol | 4 |
| 160 | ADJUST_RISK_CAP_OR_SKIP_SYMBOL | 1096 | operator remedy text | adjust the risk cap or skip the symbol | 5 |
| 161 | CONFIG_REVIEW_REQUIRED | 1088 | operator remedy text | configuration needs review | 3 |
| 162 | CREDENTIAL_REVIEW_REQUIRED | 1086 | operator remedy text | credentials need review | 7 |
| 163 | SYMBOL_REVIEW_REQUIRED | 1084 | operator remedy text | symbol needs review | 6 |
| 164 | RISK_REVIEW_REQUIRED | 1090 | operator remedy text | risk needs review | 5 |
| 165 | MANUAL_REVIEW_REQUIRED | 1082 | operator remedy text | manual review required | NO_CATEGORY |
| 166 | NO_SEND_INVALID_SIZE | 1104 | operator remedy text | invalid size, no send | 4 |
| 167 | NO_SEND_PRICE_SANITY | 1106, 9727 | operator remedy text | price sanity, no send | 6 |
| 168 | REVIEW_REQUIRED | 1107, 7782 | operator remedy text | review required | NO_CATEGORY |
| 169 | NO_SEND_UNSUPPORTED_SYMBOL | 1068, 9709 | operator remedy text | unsupported symbol, no send | 6 |
| 170 | NO_ACTION_SPOT_SKIP | 1066, 9736 | operator remedy text | spot skip, no action | NO_CATEGORY |
| 171 | WAIT_FOR_COPY_POLL | 1070, 7744 | operator remedy text | wait for the copy poll | NO_CATEGORY |
| 172 | MISSED_ENTRY | 1074 | operator remedy text | missed entry | 2 |
| 173 | MISSED_ADD | 1076 | operator remedy text | missed add | 2 |
| 174 | CLOSE_RECOVERY_NOT_IMPLEMENTED | 1080 | operator remedy text | close recovery not implemented | NO_CATEGORY |
| 175 | EXIT_RECOVERY_QUEUE_FAILED | 1119 | terminal row | exit recovery queue write failed | NO_CATEGORY |
| 176 | ENTRY_ADD_RATE_LIMIT_RECOVERY_FAILED | 1118 | terminal row | rate-limit recovery order failed | 8 |
| 177 | ENTRY_ADD_RATE_LIMIT_RECOVERY_EXPIRED | 1118 | terminal row | rate-limit recovery window expired | 8 |
| 178 | SERVICE_CREATED_UNLEDGERED | 1161, 11625 | NON_TERMINAL row | service created an order the ledger does not hold | 2 |
| 179 | SEND_OUTCOME_UNKNOWN_HOLD | 1161 | NON_TERMINAL row | send outcome unknown, held | NO_CATEGORY |
| 180 | SLOW_SEND_PATH | 1161 | NON_TERMINAL row | send path exceeded its time budget | 8 |
| 181 | STANDING_CLOSE_CANCELLED_BY_GUARD | 1161 | NON_TERMINAL row | standing close cancelled by the guard | 10 (inv: one standing close per sleeve) |
| 182 | STANDING_CLOSE_NOT_PLACED | 1162, 7251 | NON_TERMINAL row | standing close not placed | 2 |
| 183 | XYZ_UNMATCHED_COPY_FLAT_CLOSE_ADOPTED | 1163 | NON_TERMINAL row | unmatched copy flat-close adopted | 2 |
| 184 | ORPHAN_ORDER_ALREADY_GONE | 1164 | NON_TERMINAL row | orphan order no longer exists | 10 (inv: journal matches exchange truth) |
| 185 | RESTING_ENTRY_ALREADY_GONE | 1164 | NON_TERMINAL row | resting entry no longer exists | 10 (inv: journal matches exchange truth) |
| 186 | STANDING_CLOSE_WITHDRAWN | 1164 | NON_TERMINAL row | standing close withdrawn | 10 (inv: one standing close per sleeve) |
| 187 | ORPHAN_ATTEMPT_PARTIAL_FILL_UNRESOLVED | 1167 | NON_TERMINAL row | orphan attempt with an unresolved partial fill | 2 |
| 188 | ORPHAN_ORDER_CANCEL_FAILED | 1169 | NON_TERMINAL row | orphan order cancel failed | 8 |
| 189 | RESTING_ENTRY_CANCEL_FAILED | 1160 set | NON_TERMINAL row | resting entry cancel failed | 8 |
| 190 | SEND_ATTEMPT_SUPERSEDE_FAILED | 1160 set | NON_TERMINAL row | superseding a send attempt failed | NO_CATEGORY |
| 191 | REPLAY_DEFERRED_PROCESS_EXCEPTION | 1160 set | NON_TERMINAL row | replay deferred by a process exception | NO_CATEGORY |
| 192 | ENGINE_CLOSE_RETRY_REQUIRED | 1160 set | NON_TERMINAL row | engine must retry the close | NO_CATEGORY |
| 193 | EXIT_RECOVERY_REQUIRED | 1160 set | NON_TERMINAL row | exit recovery required | NO_CATEGORY |
| 194 | EXIT_CANCELLED_RECOMPUTE_PENDING | 1160 set | NON_TERMINAL row | exit cancelled, recompute pending | NO_CATEGORY |
| 195 | FILL_PENDING_QUEUED | 1160 set | NON_TERMINAL row | fill queued, pending | NO_CATEGORY |
| 196 | FILL_PENDING_STUCK | 1160 set | NON_TERMINAL row | fill stuck pending | NO_CATEGORY |
| 197 | AMBIGUOUS_SEND_EXIT_RESTING | 1160 set | NON_TERMINAL row | ambiguous send, exit resting | NO_CATEGORY |
| 198 | LEDGER_EXCHANGE_NET_MISMATCH | 1160 set | NON_TERMINAL row | ledger net differs from exchange net | 2 |
| 199 | CONVERGE_CLOSE_DROPPED_SLEEVE_CHANGED | 1160 set | NON_TERMINAL row | sleeve changed during converge-close | 2 |
| 200 | ENTRY_ADD_RATE_LIMIT_RECOVERY_BLOCKED_SAFETY | 1160 set | NON_TERMINAL row | rate-limit recovery blocked by the safety gate | 5 |
| 201 | EXCHANGE_MANUAL_NET_MATCH | 1160 set | NON_TERMINAL row | exchange net matches manual net | 2 |
| 202 | MANUAL_ONLY_EXCHANGE_FLAT_CLOSED | 1160 set | NON_TERMINAL row | manual-only position already flat on the exchange | 2 |
| 203 | AUDIT_WRITE_FAILED | 1160 set | NON_TERMINAL row | audit write failed | NO_CATEGORY |
| 204 | ASSET_META_REFRESH_FAILED_USING_LAST_GOOD | 1160 set | NON_TERMINAL row | meta refresh failed, last good used | 6 |
| 205 | COPY_FILL_UNMATCHED | 1160 set | NON_TERMINAL row | copy fill not matched to a leader fill | 2 |
| 206 | COPY_FILL_DUPLICATE | 1160 set | NON_TERMINAL row | duplicate copy fill | 10 (inv: one copy per leader fill) |
| 207 | LEADER_FILL_MERGED_INTO_ORDER | 1160 set | NON_TERMINAL row | leader fill merged into an existing order | NO_CATEGORY |
| 208 | LEDGER_REPAIR_PROVEN_EXCHANGE_FLAT | 1160 set | NON_TERMINAL row | ledger repair proven exchange-flat | 2 |
| 209 | POST_SEND_BOOKKEEPING_FAILED | 1160 set | NON_TERMINAL row | post-send bookkeeping failed | NO_CATEGORY |
| 210 | DEFERRED_ENTRY_RETAINED | 1196 | retained set (nothing writes it on this branch) | deferred entry retained | 3 |

Line numbers refer to `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` at commit `a1acc28`. "1137 set" / "1160 set"
mean the name is a member of `TERMINAL_ROW_NAMES` (Core:1113-1155) or `NON_TERMINAL_ROW_NAMES` (Core:1156-1170)
rather than a literal at a call site.

## Summary

- **Total distinct blocking labels: 210.**
- Source pool: **358** upper-case string candidates from the extraction; 210 survive after removing allow/decision/
  lifecycle/health vocabulary and folding repeated occurrences of one label into a single row.
- Counts below were produced mechanically from the table, so they can be re-checked against it:
  `awk -F'|' '/^\| [0-9]+ \|/{c=$7; gsub(/^ +| +$/,"",c); if(c ~ /^10/)k="10"; else if(c ~ /^NO_CATEGORY/)k="NC"; else{split(c,a," ");k=a[1]}; n[k]++; t++} END{for(i=1;i<=10;i++) printf "cat %s: %d\n", i, n[i]+0; printf "NC: %d\ntotal: %d\n", n["NC"]+0, t}' docs/GATE_LABEL_MAP.md`

| category | count |
|---|---|
| 1 exchange/venue safety, reduce-only | 13 |
| 2 ownership and attribution uncertainty | 33 |
| 3 mode/configuration unreadable or not applied | 17 |
| 4 liquidity, minimum notional and dust | 12 |
| 5 risk caps and exposure limits | 13 |
| 6 stale or missing market data | 32 |
| 7 authentication, signer and account identity | 7 |
| 8 maintenance, outage and degraded venue state | 16 |
| 9 operator/CLI explicit instruction | 3 |
| 10 invariant protection | 23 |
| **NO_CATEGORY** | **41** |
| **total** | **210** |

Category 9 is only 3 labels, and two of them (`SYMBOL_BLOCKED`, `SYMBOL_NOT_ALLOWED`) are config allow-lists rather
than a live operator instruction — so category 3 is doing most of the "operator said no" work by proxy. Category 6 being
the joint-largest is a finding in its own right: roughly one blocking label in six is a market-data problem.

## NO_CATEGORY labels (41), ranked by how dangerous it is to leave them unowned

Ranked most dangerous first. "Blocks" gives the trade effect; the note says whether the gap is acceptable.

1. **BLOCKED_SEND_UNCLASSIFIED** (1116, 12999), **UNCLASSIFIED_SEND_BLOCK** (13005), **SEND_TERMINAL_UNCLASSIFIED**
   (13004). Blocks: any send whose status the catch-all does not recognise. This is the engine's own admission that a veto
   exists which no category covers; a future code path reaches it with no governance review. Not acceptable as a
   permanent state — either it never fires (which should be proved by test) or every status that can reach it must be
   enumerated.
2. **UNRECORDED_SEND_BLOCK** (13394), **BLOCKED_NO_TERMINAL_RECORDED** (1160 set). Blocks: the state where a send block
   was applied but no terminal row was written. This is the *violation* of an invariant, not its protection, so it must
   not be filed as if it were a gate — but it silently changes what the ledger believes happened. Highest-value item to
   give an owner.
3. **EXCHANGE_REJECTED_UNKNOWN** (940). Blocks: an order the venue rejected with an error the classifier does not map.
   The engine treats an unparsed venue rejection as a terminal no-send without knowing whether it was reduce-only (1), a
   cap (5) or a signer problem (7). Defaulting it to category 1 would be a guess; the classifier should be exhaustive.
4. **PROCESS_EXCEPTION** (13056, 13158), **BLOCKED_PROCESS_EXCEPTION** (1160 set), **SEND_EXCEPTION** (13375),
   **BLOCKED_SEND_EXCEPTION** (1116). Blocks: any fill or send whose code raised. An exception is a defect, not a
   governance reason; mapping it to category 10 would launder bugs as invariant protection. Correctly unowned, but must
   be alertable and counted.
5. **MANUAL_REVIEW** (5346). Blocks: an entry whose copy notional is zero, or where `_sizing_block` text is set. One
   label doing two jobs; only the zero-notional half plausibly belongs to category 4.
6. **Spot family (6 labels):** **NOT_APPLICABLE_SPOT** (5328), **BLOCKED_SPOT_NOT_SUPPORTED** (5329),
   **SEND_NOT_ATTEMPTED_SPOT_MARKET_SKIPPED** (8286), **SPOT_MARKET_SKIPPED**, **MISSED_ENTRY_SKIP_SPOT_MARKET_SKIPPED**,
   **NO_ACTION_SPOT_SKIP** (1066). Blocks: every spot and spot-index market. A large deliberate product-scope exclusion
   with no governance category. Benign today — the engine is perp-only and the exclusion is loud and audited — but it is
   still an unowned blanket veto: any leader trading spot is silently not copied. Either add "asset class not supported by
   this engine" to the taxonomy or accept it explicitly.
7. **EXCLUDED_NOT_LISTED_ON_FOLLOWER_NETWORK** (11798/11805 area). Blocks: coins that exist on the leader network but not
   on the follower network. Close to category 6, but it is a static venue-scope exclusion rather than stale data; it
   deserves a named category rather than being folded in.
8. **Outcome-unknown family (7 labels):** **SEND_OUTCOME_REVIEW_REQUIRED**, **SEND_OUTCOME_UNKNOWN_MANUAL_ALERT**,
   **SEND_OUTCOME_DEFERRED_RESOLVED**, **SEND_OUTCOME_UNKNOWN_HOLD**, **AMBIGUOUS_SEND_EXIT_RESTING**,
   **MISSED_ENTRY_LIMIT_OUTCOME_UNKNOWN**, **MISSED_ENTRY_LIMIT_RESTED**. These are outcome states, not refusals — the
   trade may already exist. Forcing them into a blocking category would be wrong; they need an outcome taxonomy
   separate from the blocking taxonomy.
9. **Generic review text:** **REVIEW_REQUIRED** (1107), **MANUAL_REVIEW_REQUIRED** (1082),
   **REPLAY_DEFERRED_PAST_LIMIT_ALERT** (13424), **PENDING_SEND** (6239). What the operator actually sees, naming no
   cause, so governance cannot audit it.
10. **Recovery/bookkeeping family (13 labels):** **WAIT_FOR_COPY_POLL** (1070), **CLOSE_RECOVERY_NOT_IMPLEMENTED**
    (1080), **EXIT_RECOVERY_QUEUE_FAILED** (1119), **SEND_ATTEMPT_SUPERSEDE_FAILED**,
    **REPLAY_DEFERRED_PROCESS_EXCEPTION**, **ENGINE_CLOSE_RETRY_REQUIRED**, **EXIT_RECOVERY_REQUIRED**,
    **EXIT_CANCELLED_RECOMPUTE_PENDING**, **FILL_PENDING_QUEUED**, **FILL_PENDING_STUCK**, **AUDIT_WRITE_FAILED**,
    **POST_SEND_BOOKKEEPING_FAILED**, **LEADER_FILL_MERGED_INTO_ORDER**. Mostly affects recovery rather than the first
    send — but **CLOSE_RECOVERY_NOT_IMPLEMENTED** means a close was skipped for a structural reason and nobody owns it.

## WHAT I COULD NOT CLASSIFY

- **5346 `MANUAL_REVIEW`.** The return is a fixed label plus either `_sizing_block.get(wallet)` or the literal "copy
  notional is zero". The second element is free text set elsewhere; I did not trace every writer of `_sizing_block`, so I
  cannot say whether all producers are size/notional reasons.
- **`OWNERSHIP_GATE_UNRESOLVED_SYMBOL`, `OWNERSHIP_GATE_SHARED_SYMBOL_AMBIGUOUS`, `OWNERSHIP_GATE_ACCOUNT_RESIDUAL`.**
  These appear in the row-name frozensets and in comments, but I found no literal call site constructing each of them in
  the ranges read. Mapped to 2 on meaning; flagged because the call site is unconfirmed.
- **The `ENTRY_BLOCKED_{entry_block_reason}` family (8111).** Only `ENTRY_BLOCKED_RISK` is observed. Any other suffix
  would be constructed silently. Mapped the observed one to 5; the rest cannot be enumerated from this tree.
- **Audit action names that are not gates** — `NO_SEND`, `LOCAL_BLOCK_NO_EXCHANGE`, `AUDIT_ONLY`, `NO_ACTION`,
  `JOURNAL_SWEEP`, `LEDGER_CLOSED`, `APPLIED_TO_LEDGER`, `RECONCILED_ON_EXCHANGE`, `COPIED_WITH_MERGED_ORDER`,
  `QUEUED_NOT_LOST`, `HELD_WITH_MERGED_HEAD`, `NO_ACTION_CATCHUP_NET_ZERO`, `LEDGER_FILLS_ADOPTED`,
  `LEDGER_FILL_ADOPTED` — excluded: they describe successful or informational bookkeeping, not a refusal.
- **`ALERT_ONLY_ENTRIES_PROCEED`** (13643) is excluded from the table but deserves attention: it records
  `GATE_WOULD_BLOCK` while setting `engine_can_send="True"` — a gate that is deliberately non-enforcing in alert-only
  mode. That is operator-selected policy (category 9) rather than a block, but it is the mechanism by which a real gate
  can be inert, and none of the ten categories describes it.
- **Non-blocking vocabulary excluded from the table:** `ENTRY`, `EXIT`, `REDUCE`, `ENTRY_ALLOWED`, `EXIT_ALLOWED`,
  `SEND_ALLOWED`, `LONG`, `SHORT`, `FLAT`, `SELL`, `GREEN`, `AMBER`, `CRITICAL`, `WARN`, `TERMINAL`, `NON_TERMINAL`,
  `UNCLASSIFIED`, `ACTIVE`, `MANUAL`, `RETRY`, `COPYING`, `CLOSE_ONLY`, `DISABLED`, `WS_DISABLED`, `SNAPSHOT_OK`,
  `FILLS_COMPLETE`, `POLL_*`, `COPY_ACCOUNT_POLLED`, `NO_INTENT`, `NO_MATCHING_INTENT`, `SLOW_*`, `DRY_RUN`, `APPLIED`.
- **Count challenge.** If a reviewer's grep yields a different total, the difference will be in the collapsing rule
  (which vocabulary is dropped, which occurrences are folded into one row), not in the extraction. The 358-row
  intermediate set is reproducible with the greps at the top; the 210 figure is the reviewed set after collapsing.