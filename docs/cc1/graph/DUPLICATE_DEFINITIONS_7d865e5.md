# DUPLICATE_DEFINITIONS_7d865e5.md

> Graph: commit 7d865e5; graphify-out built 2026-10-31T16:28:45Z (age ~minutes at post time). Produced via graphify (C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe -m graphify update .) plus AST cross-check.

## Duplicate function bodies (identical normalized AST)

### group c2baca963f332193
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:872` utc_now_iso
- `_archive/hl_stage2/HL_Copy_App_SSOT.py:154` utc_now_iso

### group 60006fa6e4b7d5f6
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:2656` row_exchange_order_id
- `_archive/hl_stage2/HL_Copy_App_SSOT.py:1988` _row_exchange_order_id

### group 8a8e39242ba07f8d
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:2669` signed_from_side_size
- `_archive/hl_stage2/HL_Copy_App_SSOT.py:2001` _signed_from_side_size

### group 4709ece214409dcf
- `_archive/hl_stage2/HL_Copy_App_SSOT.py:8497` live_copy_dashboard_json
- `_archive/hl_stage2/HL_Copy_App_SSOT.py:8502` get_live_copy_summary

## Shared top-level constants (defined in both Core and UI)

- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:145` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:91` -> `APPEND_ONLY_DIR`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:74` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:51` -> `BASE_DIR`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:618` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:113` -> `DEFAULT_FIXED_NOTIONAL`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:187` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:92` -> `ERRORS_CSV`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:156` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:100` -> `EXCHANGE_ACCOUNT_SNAPSHOT_FILE`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:148` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:105` -> `LIVE_CONFIG_FILE`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:185` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:103` -> `LIVE_FILLS_CSV`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:195` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:65` -> `MANUAL_WALLETS_FILE`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:157` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:86` -> `RESTING_ENTRY_ORDERS_FILE`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:184` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:96` -> `SEND_ATTEMPTS_CSV`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:197` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:63` -> `UI_STATE_FILE`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:219` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:110` -> `USER_WALLET`
- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py:196` and `_archive/hl_stage2/HL_Copy_App_SSOT.py:64` -> `WALLET_GATE_FILE`

