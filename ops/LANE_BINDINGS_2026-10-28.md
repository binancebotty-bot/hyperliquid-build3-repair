# C7 Lane Bindings - 2026-10-28

Primary coder lane L1 (incumbent, renamed by Boss):
- role: Track B close coder, items 1-4
- surface: CDP port 9225, conversation 6ae1cdcb-3dec-83ed-89c6-31d8feb678b9 ("GPT Coder 2")
- branch: gpt/c7-track-b-close-first-20261028 (origin tip a1acc28c0cd9d3a6710783ed08a7b9401475c644)
- proof: nonce b3L16c7b5f037eb8 echoed in the thread; authorisation + amendments delivered, lane replied it will run offline regressions before committing

Independent reviewer lane G3:
- role: reviewer of Track B commits, never the author of what it reviews
- surface: CDP port 9225, conversation 6ae20a24-0334-83ed-b32a-4d1e26037959 ("GPT Reviewer Setup")
- proof: nonce b3G3a49d99a84f64 echoed; acknowledged, awaiting first sha

Matrix runner lane L4:
- role: static and documentation rows of the certification matrix, tested commit a1acc28
- surface: CDP port 9225, conversation 6ae20a33-56a0-83ed-9b94-b4c4a14715ef ("GPT Matrix Reference")
- proof: nonce b3L4bea027467e96 echoed; brief delivered

Lantern note: the earlier Build 3 thread 6ae132cb-afc4-83eb-8c02-2295dd41cb98 reached its conversation maximum on 2026-10-28 and is retired for new work; its evidence lives in control #1 comment 6463164659 and commit 420a467a88f1.

Rules in force for every lane: closes before entries; USER sleeves labelled, never adopted or closed; reduce_only set by the exchange net test only; testnet only; no keys; no mainnet orders; no swap without the controller GO on an exact sha; a lane never certifies its own work.

Real lane counts on this host: 3 GPT lanes bound (above), 1 Codex static reviewer, Hermes controller running the write path. No Luna fleet exists on this host; no DeepSeek proxy is used for code, only for review reads and kanban upkeep within the 3-channel cap.
