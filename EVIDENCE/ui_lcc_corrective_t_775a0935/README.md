# UI-LCC CORRECTIVE - t_775a0935

Rows: UI-LCC-WTBL-10..14 + UI-LCC-DETAIL-01 (6 rows)
Register of record: b142cf88d389e791160f691aac3d936852b99975 (read-only; NO matrix edit)

## CERT TARGET (ENGINE RULING exception)
This is a UI-ONLY cert section, NOT the main register. The register b142cf88 has NO
/live-copy route, so these UI rows certify against the build that ACTUALLY serves
/live-copy:

    cert_target_build       = b5e6d613de36e3020ac28ba2317e6571a5c37e9b
    cert_target_ssot_sha256 = 658ec8e31eb96d70acc15dc30860334c23612d2e3e9d19fb63ed9ec4e6fa86c2
    cert_target_ssot_path   = C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/HL_Copy_App_SSOT.py
    register_blob_sha256    = 7468ab5188750617b090b56c3e719d73e91f5b4241f4782382ccac1a22989276

The serving build commit and its SSOT sha256 are recorded in EVERY row record
(UI_LCC_CORRECTIVE_t_775a0935.json -> rows[].cert_target_build / .cert_target_ssot_sha256),
as the ENGINE RULING requires, together with rows[].dom_capture_sha256. No build is mixed
inside a row and no capture is reused across builds.

## Route (clears reviewer defect 1)
Probed the LIVE rendered DOM at http://127.0.0.1:8031/live-copy directly in headless
Chromium (Playwright, py3.11). No synthetic ui-cert.local page, no captured-fixture
serving. The page made its own real fetch to /api/live-config, /api/live-ws-health,
/api/live-audit-summary, /api/global-controls (all HTTP 200) and rendered 15 wallet rows.

## Oracle (clears reviewer defect 2)
Independent recompute from engine-written on-disk files - manual_live_positions.json,
live_config.json, append_only/live_fills.csv, append_only/send_attempts.csv - by a script
that does NOT import HL_Copy_App_SSOT.py. Config truth: 15/15 mode, 15/15 copy_mode,
15/15 fixed_notional. Fees rule mirrors _replay_wallet_ledger_pnl (sum of fee column).

## Capture hash tie-out (clears reviewer correction 2)
The single producing probe for the committed capture is probe5.py. It writes
live_dom_capture.html and records the browser HTML sha256 in probe5_result.json.
The browser returns CRLF; the committed file is LF, so the on-disk hash of the
committed bytes was made to equal the declared value by an LF normalization
(fixtie.py, atomic: it verifies the LF-normalized hash equals the declared value
before rewriting, and aborts without writing otherwise).

    producing probe        = probe5.py
    producing_probe_sha256 = ce115ba8fb891139e4c1921da974599c35da0a277ca37c3bfcad88ecca4d5768
    declared_dom_sha256    = 809be3fb0f9a05ae2e1691504a3934218915177c085c8394c6ffbbada1500858
    on_disk_sha256         = 809be3fb0f9a05ae2e1691504a3934218915177c085c8394c6ffbbada1500858
    tie_out                = MATCH

The earlier committed capture f0526ac7d0682d876898f663ae2bb296a664e80557c690620c0e0e35d14faa09
(97/89.02) and the stale declared hashes ab2c92c6 (probe3) and cd89282c (probe4) are
SUPERSEDED - neither of those HTML documents was ever committed, which is exactly why
neither matched the file on disk. The committed capture now reads
"Open Positions (98)" / "Fees: $90.63", which are the values probe5 measured and which
verify5_out.json reconciles against the frozen disk and API at the same instant.

## Time-alignment (removes the earlier apparent staleness)
probe5.py freezes the on-disk engine files on the exact /api/live-audit-summary response
instant, so DOM/API/disk are compared at one time T. The engine appends fills continuously,
so the frozen snapshot - not a later disk read - is the truth source.

## Verdicts (unchanged in substance; the reviewer reproduced them independently)
- UI-LCC-WTBL-10 = NOT_TESTED - F/N render correctly, but the served surface has NO B
  (leader_equity_base) input (0/15 rows), and the negative test fails: ??10/??100 renders
  defaults rather than n/a.
- UI-LCC-WTBL-11..14 = NOT_TESTED - Save/CLO/OFF/Archive buttons exist on all 15 rows and the
  served JS wires them to the real live endpoints, but verifying a write's ACTUAL effect
  requires POSTing to the live service, which is forbidden (read-only). Honest NOT_TESTED,
  never the withdrawn stub {ok:true} PASS.
- UI-LCC-DETAIL-01 = PASS - per-wallet correctness for 0x0104...c703a: rendered B-section
  header 98 == API list 98 == frozen-disk recompute 98; fees DOM 90.63 == API 90.6284 ==
  independent frozen-disk sum 90.6284 (14876 fill rows for this wallet); attribution
  ENGINE_LEDGER_SLEEVES_PARTIAL shown. Coin-size deltas vs disk (KPEPE, KSHIB) show DOM == API,
  i.e. the live append race, not a render error.

## Live-surface binding finding (reported, not fixed - outside this card)
The live /live-copy surface is served by the hl-build3-testnet-cert lineage
(.../hl-build3-testnet-cert/_archive/hl_stage2/HL_Copy_App_SSOT.py, HEAD b5e6d61), NOT the
register blob 7468ab51... . b142cf88 has no /live-copy route. Row verdicts are recorded
against the LIVE serving build per the ENGINE RULING; this section is UI-only.

## Read-only
No POST to the live service. Register untouched. Shared main checkout not written. Isolated
branch hermes/ui-lcc-corrective-t_775a0935.
