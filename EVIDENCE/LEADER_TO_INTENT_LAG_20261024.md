# Leader-to-intent lag by wallet and coin (2026-10-24)

Window: `created_at >= 2026-10-24T16:24:18Z` on `send_attempts.csv` (run8/state_20261024/append_only). Rows in window: **588** (ts 2026-10-24T16:24:53.549399+00:00 .. 2026-10-24T20:22:37.427709+00:00). Percentiles: linear interpolation. Read-only; no engine action.

Overall: leader_to_intent p50 1028.0 ms, p95 13488.6 ms, max 5774678.0 ms. queue_wait p50 664.0 ms, p95 2299.0 ms, max 13779.0 ms.

## Top 10 by wallet (ordered by leader_to_intent p95 desc; 4 groups)

| Wallet | n | l2i p50 | l2i p95 | l2i max | qw p50 | qw p95 | qw max |
|---|---|---|---|---|---|---|---|
| `0x7717a7a245d9f950e586822b8c9b46863ed7bd7e` | 202 | 1027.5 | 1077601.3 | 5774678.0 | 661.5 | 2995.4 | 13779.0 |
| `0xd4c1f7e8d876c4749228d515473d36f919583d1d` | 68 | 1054.5 | 2417.0 | 2801.0 | 679.5 | 2047.4 | 2424.0 |
| `0x21ca98106c69bff036a194648ba30388ccbe811d` | 1 | 1681.0 | 1681.0 | 1681.0 | 1284.0 | 1284.0 | 1284.0 |
| `0xbee0000c04ee2efe66234bec57f7eaf38818fbca` | 2 | 928.0 | 1010.8 | 1020.0 | 511.5 | 585.8 | 594.0 |

## Top 10 by coin (ordered by leader_to_intent p95 desc; 57 groups)

| Coin | n | l2i p50 | l2i p95 | l2i max | qw p50 | qw p95 | qw max |
|---|---|---|---|---|---|---|---|
| `NXPC` | 4 | 1648.0 | 4908792.2 | 5774678.0 | 755.0 | 1534.4 | 1621.0 |
| `DYM` | 7 | 1035.0 | 4375037.8 | 4638685.0 | 516.0 | 693.2 | 697.0 |
| `GRIFFAIN` | 4 | 777.0 | 3664151.3 | 4310627.0 | 307.0 | 442.9 | 458.0 |
| `S` | 3 | 4283.0 | 3655896.2 | 4061631.0 | 2470.0 | 3775.0 | 3920.0 |
| `AZTEC` | 2 | 1777695.0 | 3376554.0 | 3554205.0 | 781.0 | 781.0 | 781.0 |
| `TIA` | 7 | 1914.0 | 3030368.7 | 4323171.0 | 940.0 | 12324.8 | 13432.0 |
| `GRASS` | 5 | 1107.0 | 1918998.0 | 2397946.0 | 694.0 | 2510.7 | 2826.0 |
| `XMR` | 10 | 1172.5 | 1146547.7 | 1267793.0 | 680.0 | 1086.8 | 1134.0 |
| `INJ` | 2 | 541423.5 | 1027737.1 | 1081772.0 | 699.0 | 699.0 | 699.0 |
| `BTC` | 16 | 1037.5 | 934916.5 | 3733057.0 | 673.0 | 1310.9 | 1810.0 |

## Thresholds

| threshold | attempts | share |
|---|---|---|
| > 10000 ms | 17 | 6.2% |
| > 60000 ms | 12 | 4.4% |

## Cross-reference: long tail vs missed entries

Missed-genuine intents (MISSED_ENTRY_IOC_NO_MATCH / MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN) found: 25. Rested-then-cancelled (ENTRY_LIMIT_RESTING_PRICE_MOVED) found: 17.

Worst 50 send attempts by leader_to_intent (5774678.0 .. 1728.0 ms): 50 distinct intents. Of those, 2 belong to the missed set and 1 to the rested set. Of the 25 missed intents, only 25 appear in this window's send attempts at all; of the 17 rested, 17 do.

Top-50 wallet concentration: [('0x7717a7a245d9f950e586822b8c9b46863ed7bd7e', 40), ('0xd4c1f7e8d876c4749228d515473d36f919583d1d', 10)]. Top-50 coin concentration: [('ETH', 10), ('CHIP', 5), ('TIA', 4), ('USELESS', 3), ('ANIME', 3), ('NXPC', 2)].

No balances, keys or credentials are reproduced here.
