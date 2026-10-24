# J28 TESTNET manual startup

Recorded for run8 on 2026-10-24. Use the clean checkout at `C:\tmp\v31_bf40a9d-clean-20261024` (source SHA `bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847`) and the run8 state directory below. Confirm no tracked Core PID is alive, the shared Core lock is free, the state directory does not exist, and port 8031 is unused before starting.

```powershell
$env:HL_LIVE_AUDIT_DIR='C:\Users\wigmore\trading_stack\hl-build3-testnet-cert-evidence\run8\state_20261024'
$env:HL_FOLLOWER_NETWORK='testnet'
$env:HL_LIVE_WS_ENABLED='1'
$env:HL_BUILD_SHA='bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847'
$env:HL_APP_PORT='8031'
$env:HL_USER_WALLET='0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'
$env:HL_LIVE_GLOBAL_LOCK_FILE='C:\Users\wigmore\AppData\Local\HL_Live_Copy_Service_Core\engine-global.lock'
$env:HL_LIVE_AUTO_SEND_ENABLED='0'

Start-Process `
  -FilePath 'C:\Users\wigmore\AppData\Local\Python\bin\pythonw.exe' `
  -ArgumentList @('C:\tmp\v31_bf40a9d-clean-20261024\_archive\hl_stage2\HL_Live_Copy_Service_Core.py', '--ws', '--loop', '--interval', '10', '--poll-live', '--poll-copy') `
  -WorkingDirectory 'C:\tmp\v31_bf40a9d-clean-20261024\_archive\hl_stage2' `
  -WindowStyle Hidden -PassThru
```

Start the local UI service from the same checkout and environment, in `_archive\hl_stage2`:

```powershell
& 'C:\Users\wigmore\AppData\Local\Python\bin\python.exe' -u 'HL_Copy_App_SSOT.py'
```

The run8 startup used the Core command above. The initial hidden UI launch exited; the command shown for the UI is the server invocation that started successfully on `127.0.0.1:8031`. The UI `/api/global-controls` response must show the run8 state directory before relying on it.

The five TESTNET global caps are `max_order_notional_usd=250`, `max_wallet_exposure_usd=400`, `max_asset_directional_exposure_usd=300`, `max_total_live_exposure_usd=900`, and `max_daily_loss_usd=100`. Keep the master send gate OFF until the expected 10 LIVE / 6 CLO / 3 OFF wallet roster, caps, state freshness, and healthy Core checks are verified.
