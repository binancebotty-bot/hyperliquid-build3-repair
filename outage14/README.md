# Outage test 14 state (PC, main 4f1c779), for offline replay
- Engine stopped at outage_stop_ms, armed restart at outage_restart_ms (5 min down), 7 LIVE leaders (see live_config.json; key/secret/token fields stripped).
- append_only/*.csv: rows with created_at_ms >= stop - 1 h (headers kept); full files are 0.2-0.3 GB each on the PC.
- clean_core_runtime_state.json, copy_poll_state.json, manual_live_positions.json, network.json: as on disk at 09:3xZ (after the run).
- outage14_ids.txt: leader order hashes of every leader fill in the window (LIVE wallets).
- engine_post_restart_first500.log: first 500 lines of the engine log from the restart.
Secret scan: every 0x+64-hex value is a fill id (processed_leader_fill_ids, last_copy_fill_id, CSV fill ids); no key fields.
