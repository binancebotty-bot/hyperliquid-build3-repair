#!/usr/bin/env python3
"""Generate the certification test matrix (JSON + CSV) from the source documents.

Every record cites its source clause(s). Nothing here grants authority or decides an open item.
Re-runnable: output is deterministic for the same inputs.
"""
import csv, hashlib, json, re, sys
from pathlib import Path

import os
SRC = Path(os.environ.get("HL_CERT_SOURCE_DOCS", "/mnt/project-files/source-docs"))  # copies of the cited source documents (not in the repo)
OUT = Path(os.environ.get("HL_CERT_OUT", Path(__file__).resolve().parent))
B3, B4, MC = "hyperliquid-build3-repair", "hyperliquid-build4", "richard-mission-control-template"

FIELDS = ["id", "area", "feature", "expected_behaviour", "sources", "applicability",
          "open_decisions", "execution_proof", "independent_oracle", "negative_tests",
          "prior_evidence", "result", "evidence_ref", "tested_commit", "tested_at_utc", "notes"]

R = []
def rec(id, area, feature, expected, sources, applicability="APPLIES", ods=(), proof=None,
        oracle=None, neg=(), prior="", notes=""):
    R.append(dict(id=id, area=area, feature=feature, expected_behaviour=expected,
                  sources=list(sources), applicability=applicability, open_decisions=list(ods),
                  execution_proof=proof or DEFAULT_PROOF.get(area, ""),
                  independent_oracle=oracle or DEFAULT_ORACLE.get(area, ""),
                  negative_tests=list(neg) or list(DEFAULT_NEG.get(area, [])),
                  prior_evidence=prior, result="NOT_TESTED", evidence_ref="", tested_commit="",
                  tested_at_utc="", notes=notes))

DEFAULT_PROOF = {
    "ENGINE": "Leader event (testnet-observable) -> desired net per coin -> planner delta -> single sender -> testnet order -> MASTER fill/position",
    "PRICING": "Leader event -> price source actually consulted (logged with timestamp/age) -> order limit price on the wire -> fill price",
    "ORDER": "Planner delta -> order payload as signed (size, side, reduce_only, tif, cloid, asset id) -> exchange response",
    "SETTLE": "Sender response -> in-flight reservation in SERVICE_STATE_FILE -> MASTER userFills + clearinghouseState across all DEX scopes -> reservation cleared",
    "RISK": "UI/config value -> live_config.json -> engine read at decision time -> block/allow recorded in order_intents with reason -> exchange shows (no) order",
    "WALLET": "UI action -> live_config.json / wallet_gate.json write -> running engine reads it (no restart) -> testnet behaviour",
    "UI": "Engine/exchange truth at time T -> API endpoint payload -> rendered cell text at time T (DOM capture)",
    "LIFECYCLE": "Operator command -> process table / PID / lock -> engine status endpoint -> exchange shows zero unintended orders",
    "NETWORK": "Configuration (env/credentials) -> endpoints actually contacted (captured) -> identities used for signing and for truth reads",
    "HEALTH": "Induced condition (WS drop, stale truth, API error) -> engine state -> UI indicator within stated latency",
    "CONTROL": "Envelope on origin/control-mailbox -> wake -> correlated consumption record -> durable state transition",
    "REGRESSION": "Reproduce the historical trigger condition on testnet or recorded replay -> assert the failure cannot occur",
}
DEFAULT_ORACLE = {
    "ENGINE": "Hyperliquid testnet info API read by a script that does not import engine code: clearinghouseState (all perp DEXes), openOrders, userFillsByTime for MASTER; leader fills from mainnet info API",
    "PRICING": "Independent l2Book / allMids snapshot captured at decision time plus the exchange fill record",
    "ORDER": "Exchange order status / userFills for the cloid/oid; asset meta from the same network's info API",
    "SETTLE": "MASTER userFillsByTime per DEX scope and clearinghouseState, read independently of the engine",
    "RISK": "Exchange orders/fills (absence or presence) plus independent recomputation of the limit from config",
    "WALLET": "Exchange positions, orders and fills; config file content hash before/after",
    "UI": "Independent read of the same exchange/engine truth recomputed by a script that does not import HL_Copy_App_SSOT.py",
    "LIFECYCLE": "OS process list, port bindings, exchange open orders/fills during the transition window",
    "NETWORK": "Packet/HTTP capture or request log of hostnames; exchange-side account address of resulting fills",
    "HEALTH": "Wall-clock timestamps of the induced fault versus the UI/status change",
    "CONTROL": "git log of origin/control-mailbox (exact SHAs) and the consumer's durable receipt",
    "REGRESSION": "Exchange truth as above, or recorded-replay expected output computed without engine code",
}
DEFAULT_NEG = {
    "ENGINE": ["restart mid-sequence", "stale leader snapshot", "API 429/timeout", "duplicate/reordered event"],
    "PRICING": ["stale quote beyond TTL", "quote unavailable", "price moves past bound before send"],
    "ORDER": ["exchange reject", "below minimum notional", "size rounds to zero", "unknown asset"],
    "SETTLE": ["ack without fill", "partial fill", "fill on HIP-3 DEX scope", "crash after send before oid persisted"],
    "RISK": ["blank value", "zero", "negative", "non-numeric", "value changed while engine running", "rejected save"],
    "WALLET": ["restart after change", "stale configuration", "rejected update", "API failure during change", "invalid address", "duplicate wallet"],
    "UI": ["source unavailable shows n/a/Unavailable not 0", "stale source flagged", "API error surfaced"],
    "LIFECYCLE": ["second start attempt", "crash mid-transition", "stale lock/PID", "config from previous version"],
    "NETWORK": ["mixed testnet/mainnet endpoints", "signer == master", "missing credential"],
    "HEALTH": ["fault clears and indicator recovers", "flapping"],
    "CONTROL": ["duplicate delivery", "restart while awaiting ruling", "wrong binding", "stale remote ref"],
    "REGRESSION": ["restart at each lifecycle point"],
}

# ---------------------------------------------------------------------------
# 1. Build 3 engine invariants (ARCHITECTURE.md §Non-negotiable invariants, 14 items)
inv = [
 ("One process.", ["ARCH inv1"]),
 ("Exactly one physical production .order() call site.", ["ARCH inv2", "CONTROL_STATE single_order_site"]),
 ("No new dependency without Architect approval.", ["ARCH inv3"]),
 ("No new authoritative persistent trading-state store.", ["ARCH inv4", "CONTROL_STATE persistence_rule"]),
 ("No Build 4 control-plane/platform import.", ["ARCH inv5"]),
 ("No new engine/runtime around Build 3.", ["ARCH inv6"]),
 ("Leader mutable state is isolated by (wallet, coin).", ["ARCH inv7"]),
 ("Startup/recovery truth includes all relevant perp DEX scopes (default + HIP-3/builder); missing required scope fails closed.", ["ARCH inv8", "CONTROL_STATE required_semantics[1]"]),
 ("Exchange truth outranks local replay; the manual follower-position file is not authoritative.", ["ARCH inv9", "FAILURES ROOT-001"]),
 ("API acknowledgement is not settlement; physical sends require independent MASTER fill/position verification.", ["ARCH inv10", "CONTROL_STATE required_semantics[5]"]),
 ("MASTER/trading account and API signer are distinct identities; balance/fills/positions verified on MASTER.", ["ARCH inv11", "CONTROL_STATE required_corrections[0]"]),
 ("Convergence orders move actual toward desired and never blindly flatten unrelated pre-existing inventory.", ["ARCH inv12", "CONTROL_STATE required_corrections[5]"]),
 ("Restart/recovery establishes current truth from fresh external snapshots for verification/reconciliation only; creates ZERO new trade authority.", ["ARCH inv13", "PRODUCT_SEMANTICS B2"]),
 ("No mainnet/LIVE activation without explicit Richard approval.", ["ARCH inv14", "PRODUCT_SEMANTICS §3"]),
]
for i, (t, s) in enumerate(inv, 1):
    proof = None; oracle = None; neg = ()
    if i in (1, 2, 3, 4, 5, 6):
        proof = "Static source census at the certified commit (AST scan for .order( call sites, imports, process spawns, file writers) plus runtime process count"
        oracle = "Independent AST/grep census script not shipped with the engine; OS process list"
        neg = ["census run against a deliberately mutated copy must FAIL (non-vacuous)"]
    rec(f"ENG-INV-{i:02d}", "ENGINE", f"Build 3 invariant {i}", t, [f"{B3}/ARCHITECTURE.md"] + s,
        proof=proof, oracle=oracle, neg=neg,
        prior="G3 PASS (B3-C2A-G3-PASS-ARCHITECT-GATE-1, correction 4a41f33) covers inv 8-13 at unit level; not testnet-certified" if 8 <= i <= 13 else "")

# 2. Frozen trading semantics B1-B4 (PRODUCT_SEMANTICS §2)
sem = [
 ("B1", "Frozen baseline plus genuine post-baseline leader events are the ONLY trading authority; desired exposure derives from that lineage."),
 ("B2", "Current leader position / restart / snapshot create ZERO new trade authority; a snapshot never mints a desired target or order."),
 ("B3", "Follower exchange state is authoritative for ACTUAL exposure and settlement measurement."),
 ("B4", "Snapshot vs lineage divergence is surfaced for adjudication, never converted into a trading decision."),
]
for k, t in sem:
    rec(f"ENG-SEM-{k}", "ENGINE", f"Trading authority {k}", t,
        [f"{B3}/PRODUCT_SEMANTICS.md §2 {k}", f"{B3}/ARCHITECTURE.md Trading-authority precedence"],
        neg=["restart with leader holding a position opened pre-baseline", "snapshot disagrees with lineage", "lineage checkpoint missing/corrupt"])

# 3. Engine product behaviours (PRODUCT_SEMANTICS §1, §4, ARCHITECTURE Completion/Full scope)
eng = [
 ("ENG-001", "Repeated leader ADDs converge to target", "N repeated same-direction leader ADD fills move follower actual toward desired once; no fixed notional minted per fill (TEST-002: 100 ADDs cannot exceed target).", ["ARCH Completion 6", "PRODUCT_SEMANTICS §4.5", "FAILURES TEST-002", "FAILURES LOGIC-001"]),
 ("ENG-002", "Proportional mode end-to-end", "Sleeve = leader position x copy scale; summed per coin; order = desired - actual - in_flight, proven on testnet for open, add, partial reduce, close.", ["PRODUCT_SEMANTICS §1", "ARCH Full scope 1"]),
 ("ENG-003", "Fixed mode end-to-end", "Fixed mode executes using recovered intended semantics, never fixed-notional-per-fill. Until ruled, fixed mode is HOLD fail-closed with ZERO orders and surfaces FIXED_MODE_AUTHORITY_HOLD.", ["PRODUCT_SEMANTICS §5 FIXED-MODE HOLD", "CONTROL_STATE fixed_mode_hold"], "OPEN_DECISION", ["OD-02"]),
 ("ENG-004", "Unit semantics target delta -> order size", "Signed coin delta maps to exchange size with correct szDecimals rounding and side; no unit confusion (coins vs USD).", ["ARCH Completion 3", "PRODUCT_SEMANTICS §4.2"]),
 ("ENG-005", "Multi-wallet aggregation (account-net)", "Several leaders on the same coin net to ONE account-level desired per coin; opposing leaders produce one net order (TEST-006).", ["PRODUCT_SEMANTICS §1", "FAILURES ARCH-008", "FAILURES TEST-006"]),
 ("ENG-006", "Multi-DEX / HIP-3 truth", "Leader and follower snapshots include every perp DEX scope; a HIP-3 position is seen and reconciled.", ["ARCH Completion 4", "ARCH inv8"]),
 ("ENG-007", "Restart / gap recovery", "Kill/restart before send, after send, after partial fill, after full fill, after reject, after cancel: recovers from exchange truth, no local-position replay, zero new authority (TEST-003).", ["ARCH Completion 5", "FAILURES TEST-003", "GUT I24"]),
 ("ENG-008", "Pre-existing unrelated inventory preserved", "Exposure present at baseline that is not engine-owned is never altered by convergence (UNATTRIBUTED_BASELINE).", ["ARCH Completion 8", "ARCH inv12", "GUT I25"]),
 ("ENG-009", "Event-lineage persistence rules", "Lineage persists only in SERVICE_STATE_FILE coupled to processed-event identity; missing/corrupt/stale -> fail closed ZERO authority until deterministic replay.", ["PRODUCT_SEMANTICS §5 EVENT-LINEAGE", "CONTROL_STATE event_lineage_persistence"]),
 ("ENG-010", "Account-net truth only", "Actual-net is MASTER account-net; wallet-local simulated state is never truth; unavailable -> ACCOUNT_NET_TRUTH_UNAVAILABLE with zero authority.", ["PRODUCT_SEMANTICS §5 ACCOUNT-NET", "CONTROL_STATE account_net_truth"]),
 ("ENG-011", "In-flight suppression", "Unsettled sends block overlapping/duplicate authorisation; durable reservation survives stale self.state persist (DURABLE_IN_FLIGHT_STATE_CLOBBER regression).", ["CONTROL_STATE in_flight_suppression", "CONTROL_STATE g3_disposition"]),
 ("ENG-012", "Low-latency copy", "Leader event to order-on-wire latency measured and within an agreed bound on testnet; WS path primary, poll as repair.", ["PRODUCT_SEMANTICS §1", "ARCH Full scope 1"], "OPEN_DECISION", ["OD-19"]),
 ("ENG-013", "Deterministic audit trail", "Every order is traceable leader event -> target -> order -> settlement with ids and timestamps in order_intents/send_attempts.", ["ARCH Full scope 1"]),
 ("ENG-014", "Dropped/duplicated/reordered events", "Final exchange position converges after WS loss, duplication and reordering (TEST-004).", ["FAILURES TEST-004", "GUT I03", "GUT I04"]),
 ("ENG-015", "Sign flip handling", "Leader flip: reduce-only flatten leg first, open leg only after exchange-confirmed flat, never flipping unrelated inventory.", ["convergence_shadow.py docstring", "FAILURES EXC-006", "FAILURES LOGIC-004"]),
 ("ENG-016", "Build 4 leftovers on the shared follower account", "Open orders and positions left on the shared follower account by Build 4 (and by earlier Build 3 runs) are pre-existing unrelated inventory: the engine never adopts, sizes against, amends, cancels, flattens or counts them as owned, and the UI shows them as unowned. Any cleanup is a separate operator decision.", ["ARCH inv12 (pre-existing unrelated inventory preserved)", "history/BUILD_HISTORY_REVIEW.md §7 'Build 4 leftovers' (Boss report)"]),
]
for e in eng:
    id, f, t, s = e[:4]; ap = e[4] if len(e) > 4 else "APPLIES"; ods = e[5] if len(e) > 5 else ()
    rec(id, "ENGINE", f, t, s, ap, ods)

# 4. Pricing
pr = [
 ("PRICE-001", "Authoritative mark for OPEN/INCREASE/FLIP", "One ruled mark source with a proven age bound is used on every OPEN/INCREASE/FLIP path. Currently BLOCKED: no validated-freshness mark reaches apply_fixed_sleeve_event(); fill.price is used with no age check.", ["CONTROL_STATE current_blocker", f"{B3}/G4_C2A_MARK_SOURCE_INVENTORY.md"], "OPEN_DECISION", ["OD-01"]),
 ("PRICE-002", "Public quote freshness", "Cached public executable quote is used only within HL_LIVE_QUOTE_CACHE_TTL_MS (default 1000 ms); older -> refetch; unusable -> EXECUTABLE_QUOTE_UNAVAILABLE.", ["G4_C2A_MARK_SOURCE_INVENTORY trace table", "HL_Live_Copy_Service.py LIVE_QUOTE_CACHE_TTL_MS"]),
 ("PRICE-003", "Entry price bound", "ENTRY/INCREASE never executes worse than the approved bound versus the causative leader reference; the exchange order itself enforces the bound (limit/IOC).", ["GUT I20", "FAILURES R21"], "OPEN_DECISION", ["OD-01", "OD-10"]),
 ("PRICE-004", "PRICE_WAIT", "Unacceptable entry price -> no order, event target preserved; later valid price executes exactly once.", ["GUT I21"], "OPEN_DECISION", ["OD-01", "OD-10"]),
 ("PRICE-005", "Reduction/close never trapped by entry protection", "Entry-price protection and entry caps never block a legitimate reduce/close.", ["GUT I22", "HL_Live_Copy_Service.global_order_cap_block docstring"]),
 ("PRICE-006", "Adverse-diff measure is meaningful", "adverse_diff_pct is computed against an independent executable price, not against the fill price itself (structural zero).", ["G4_C2A_MARK_SOURCE_INVENTORY Consequences"], "OPEN_DECISION", ["OD-01"]),
 ("PRICE-007", "Marketable slippage", "Marketable limit offset (HL_LIVE_AUTO_SEND_MARKETABLE_BPS default 5; UI global 'Marketable slippage %') is applied as configured and shown truthfully.", ["HL_Live_Copy_Service.py LIVE_AUTO_SEND_MARKETABLE_BPS", "HL_Copy_App_SSOT.py gcMktPct"], "OPEN_DECISION", ["OD-10"]),
 ("PRICE-008", "Close adverse diff", "Close adverse diff limit (HL_LIVE_MAX_CLOSE_ADVERSE_DIFF_PCT default 0.25; UI 'Adverse close diff %') applied as configured and cannot trap an exit unless explicitly intended.", ["HL_Live_Copy_Service.py LIVE_MAX_CLOSE_ADVERSE_DIFF_PCT", "HL_Copy_App_SSOT.py gcCloseAdv", "GUT I22"], "OPEN_DECISION", ["OD-10"]),
]
for id, f, t, s, *rest in pr:
    rec(id, "PRICING", f, t, s, *(rest or []))

# 5. Order submission
od = [
 ("ORD-001", "Single sender / single gate", "Every exchange-client order call is dominated by one disable switch and one sender (TEST-007).", ["ARCH inv2", "FAILURES ARCH-009", "FAILURES TEST-007", "GUT I08"]),
 ("ORD-002", "reduce_only correctness", "Reductions are reduce_only, capped by actual account-net, cannot flip.", ["FAILURES LOGIC-004", "FAILURES EXC-007"]),
 ("ORD-003", "Minimum notional", "Orders below the exchange/configured minimum are not sent and do not create target authority or silent residue.", ["HL_Live_Copy_Service.py MIN_ORDER_NOTIONAL=10", "GUT I13", "FAILURES LOGIC-005", "FAILURES EXC-008"], "OPEN_DECISION", ["OD-09"]),
 ("ORD-004", "Size rounding", "Size quantised to asset szDecimals from the SAME network's meta; zero after rounding -> no order.", ["ARCH Full scope 4 'order minimums/rounding'"], "OPEN_DECISION", ["OD-08"]),
 ("ORD-005", "Exactly-once execution identity", "One canonical logical event identity and one deterministic execution identity; ambiguous submission stays UNRESOLVED (no resubmit) until exchange truth resolves it.", ["GUT I06", "FAILURES LOGIC-003"]),
 ("ORD-006", "Pre-send reservation", "Unresolved reservation persisted in SERVICE_STATE_FILE before exchange.order, oid/status attached after response, not cleared on ACK.", ["CONTROL_STATE required_corrections[1..2]"]),
 ("ORD-007", "Per-run send limit", "HL_LIVE_AUTO_SEND_MAX_PER_RUN (default 1) and HL_LIVE_AUTO_SEND_WALLET restriction behave as configured and are visible to the operator.", ["HL_Live_Copy_Service.py LIVE_AUTO_SEND_MAX_PER_RUN", "HL_Live_Copy_Service.py LIVE_AUTO_SEND_WALLET"], "OPEN_DECISION", ["OD-16"]),
 ("ORD-008", "Exchange preflight", "Orders violating exchange semantics are rejected before the exchange call.", ["FAILURES EXC-012"]),
]
for id, f, t, s, *rest in od:
    rec(id, "ORDER", f, t, s, *(rest or []))
rec("ORD-009", "ORDER", "Signing key valid on follower network",
    "Before any order, the engine confirms via userRole on the follower network that its signing key is the follower account or an agent that account approved, and refuses to start otherwise. A definite exchange rejection of the signer ('User or API Wallet ... does not exist') is terminal (SENDER_KEY_NOT_VALID_ON_FOLLOWER_NETWORK), never ORDER_UNKNOWN: it stops all sending until restart, shows a red engine alert, and records a Critical diff for each trade it could not send. Key values are never printed or logged.",
    ["Testnet run 3, 2026-10-09 (mainnet agent key rejected on testnet)", "PR #10 (engine thread)", "ARCH inv11 (signer vs MASTER)"],
    "APPLIES", [],
    proof="Start the engine against the follower network -> userRole read for the signer -> start allowed/refused; inject a signer rejection on send -> terminal state, sending stopped, UI alert and Critical diffs",
    oracle="userRole for the signer and MASTER read independently on the follower network's info API; exchange order history shows no order after the rejection",
    neg=["mainnet agent key on testnet", "agent approved by a different account", "userRole unreadable (timeout/error) -> refuse to start", "malformed key", "rejection mid-run -> no retries, no ORDER_UNKNOWN", "logs and UI contain no key material"],
    prior="test_core_sender_key.py K1-K5 (unit, PR #10) - not testnet-certified")

# 6. Settlement
st = [
 ("SET-001", "ACK is not settlement", "In-flight remains blocking after API ACK until independent MASTER userFills plus resulting position prove fill, or terminal rejection proves no fill.", ["ARCH inv10", "CONTROL_STATE acceptance 'API ACK does not clear in-flight'"]),
 ("SET-002", "Settlement on MASTER across all DEX scopes", "userFillsByTime queried per perp DEX scope with dex param; deterministic dedupe; missing scope fails closed.", ["CONTROL_STATE required_corrections[3]"]),
 ("SET-003", "Terminal reject clears safely", "Clear requires exchange-derived terminal rejection plus post-attempt MASTER no-fill across all scopes; caller boolean alone forbidden.", ["CONTROL_STATE required_corrections[4]"]),
 ("SET-004", "Partial fill", "Ownership advances only by confirmed fill; residual authorised delta remains; no duplicate quantity (TEST-005).", ["GUT I23", "FAILURES TEST-005", "FAILURES LOGIC-011"]),
 ("SET-005", "Crash before oid", "Crash between send and oid persistence reconciles from started_ms + intent attributes and stays blocking if ambiguous.", ["CONTROL_STATE required_corrections[2]"]),
 ("SET-006", "Reconciliation gate before authority", "MASTER net = unattributed baseline + confirmed engine-owned actual +/- unresolved reserved, within tolerance, before any convergence order.", ["CONTROL_STATE required_corrections[6]"]),
 ("SET-007", "Testnet entry certification", "All REAL_TESTNET_ENTRY sub-gates: genuine post-start leader OPEN/INCREASE observed, fill identity verified, fresh leader capital, copy scale correct, expected qty == actual testnet fill, ownership established, reconciliation clean, single physical submission.", [f"{B4}/ACCEPTANCE.md Testnet Certification Gates"]),
 ("SET-008", "Testnet exit certification", "All REAL_TESTNET_EXIT sub-gates: genuine reduction/close observed, reduction fraction correct, attributed qty used, exit fill matches, no capital resizing of exit, ownership updated, reconciliation clean.", [f"{B4}/ACCEPTANCE.md Testnet Certification Gates"]),
]
for id, f, t, s, *rest in st:
    rec(id, "SETTLE", f, t, s, *(rest or []))

# 7. Global controls and risk
gc = [
 ("RISK-001", "Max total live exposure ($)", "gcMaxTotal -> global_controls.max_total_live_exposure_usd; 0/blank = disabled.", "max_total_live_exposure_usd"),
 ("RISK-002", "Max per-asset directional exposure ($)", "gcMaxDir -> max_asset_directional_exposure_usd.", "max_asset_directional_exposure_usd"),
 ("RISK-003", "Max per-wallet exposure ($)", "gcMaxWallet -> max_wallet_exposure_usd.", "max_wallet_exposure_usd"),
 ("RISK-004", "Max per-order notional ($)", "gcMaxOrder -> max_order_notional_usd; blocks NEW ENTRY above cap with BLOCKED_GLOBAL_MAX_ORDER_NOTIONAL; never blocks reduce/close.", "max_order_notional_usd"),
 ("RISK-005", "Marketable slippage %", "gcMktPct -> marketable_bps (UI shows %, stored converted).", "marketable_bps"),
 ("RISK-006", "Adverse close diff %", "gcCloseAdv -> max_close_adverse_diff_pct.", "max_close_adverse_diff_pct"),
 ("RISK-007", "Symbol allowlist", "gcAllowlist -> symbol_allowlist; empty = all allowed.", "symbol_allowlist"),
 ("RISK-008", "Symbol blocklist", "gcBlocklist -> symbol_blocklist.", "symbol_blocklist"),
]
UNWIRED = {"max_total_live_exposure_usd", "max_asset_directional_exposure_usd", "max_wallet_exposure_usd", "symbol_allowlist", "symbol_blocklist", "marketable_bps", "max_close_adverse_diff_pct"}
PARTIAL = {"marketable_bps": "The engine reads global_controls only in global_order_cap (L2696-2716). Auto-send uses env HL_LIVE_AUTO_SEND_MARKETABLE_BPS (L2863), not this saved value.",
           "max_close_adverse_diff_pct": "The engine reads global_controls only in global_order_cap (L2696-2716). The close guard uses the per-wallet key max_close_adverse_diff_pct else env HL_LIVE_MAX_CLOSE_ADVERSE_DIFF_PCT (L1162), not this global value."}
for id, f, t, key in gc:
    note = PARTIAL.get(key) or ("Source census at Build 3 main 5599415: key has NO reader in HL_Live_Copy_Service.py (0 occurrences); the UI saves it but the engine does not enforce it." if key in UNWIRED else "")
    if note: note += " Inferred from source search; must be confirmed by execution."
    rec(id, "RISK", f"Global control: {f}", t + " Saved value must be enforced by the running engine without restart (Boss 2026-10-09: the controls must function; values may be retuned).",
        ["HL_Copy_App_SSOT.py _GLOBAL_CONTROLS_DEFAULTS / render_live_copy_control_panel", "ARCH Full scope 4", "ARCH Full scope 6", "Boss decision, project chat 2026-10-09T12:21Z"],
        "APPLIES", (["OD-06", "OD-10"] if key in PARTIAL else ["OD-06"]) if key in UNWIRED else [],
        prior="test_g4_order_cap.py (unit, in-process) for max_order_notional_usd" if key == "max_order_notional_usd" else "",
        notes=note)
risk = [
 ("RISK-009", "Per-wallet daily loss limit", "daily_loss_limit stops new entries for that wallet when breached, or is labelled display-only. Source census: stored and logged only; no enforcement found.", ["HL_Live_Copy_Service.py LiveWalletConfig.daily_loss_limit", "HL_Copy_App_SSOT.py Add-wallet modal 'Daily loss'"], "OPEN_DECISION", ["OD-07"]),
 ("RISK-010", "Per-wallet max diff %", "max_diff_pct applied as the entry price bound for that wallet.", ["HL_Live_Copy_Service.py max_diff_pct", "HL_Copy_App_SSOT.py Add-wallet modal 'Max diff %'"], "OPEN_DECISION", ["OD-10"]),
 ("RISK-011", "Live wallet cap", "At most 10 service-eligible wallets; 11th is rejected with MAX_WALLETS_EXCEEDED and config unchanged.", ["HL_Copy_App_SSOT.py _enforce_live_copy_cap", "HL_Live_Copy_Service.py MAX_LIVE_WALLETS=10"], "OPEN_DECISION", ["OD-14"]),
 ("RISK-012", "Global safe stop", "One operator action stops all new sends account-wide and is acknowledged by the running engine; it creates zero orders.", ["ARCH Full scope 4 'global enable/disable / safe stop'", "GUT I12", f"{B4}/BUILD4_FINAL_AUTHORITY_MAP.md Modes"], "OPEN_DECISION", ["OD-05"]),
 ("RISK-013", "Live / paper / testnet mode boundaries", "Testnet and mainnet cannot be confused; dry-run/paper sends nothing; mode change itself creates zero orders.", ["ARCH Full scope 4", "GUT I12"], "OPEN_DECISION", ["OD-05", "OD-08"]),
 ("RISK-014", "Stale/uncertain state containment", "UNKNOWN / UNCLASSIFIED / stale state fails closed locally (wallet/coin), never green, never global unless one of the five account-wide hazards.", ["FAILURES LOGIC-015", "FAILURES EXC-020", "GUT I10", f"{B4}/BUILD4_FINAL_AUTHORITY_MAP.md Failure scope"]),
 ("RISK-015", "Emergency close only where intended", "No control closes positions unless explicitly intended; no control bypasses convergence or the single sender.", ["ARCH Full scope 4"]),
 ("RISK-016", "Manual order cap", "HL_LIVE_MAX_MANUAL_ORDER_NOTIONAL_USD (default 25) caps manual sends.", ["HL_Live_Copy_Service.py LIVE_MAX_MANUAL_ORDER_NOTIONAL_USD"]),
]
for id, f, t, s, *rest in risk:
    rec(id, "RISK", f, t, s, *(rest or []))

# 8. Wallet controls (UI-WALLET-xxx). 004 is Boss's worked example.
wal = [
 ("UI-WALLET-001", "Add a leader wallet", "Valid address added via Add-wallet modal: baseline at onboarding, future genuine events only, no historical replay or position catch-up; hot (no restart).", ["ARCH Full scope 3", "GUT I17", "GUT I19", "HL_Copy_App_SSOT.py /api/live-config/add-wallet"]),
 ("UI-WALLET-002", "Remove / archive a leader wallet", "Archive stops future intake; existing owned exposure stays managed until legitimately closed (tombstone); archived wallet can be restored.", ["ARCH Full scope 3", "GUT I18", "HL_Copy_App_SSOT.py /api/live-config/remove-wallet"], "OPEN_DECISION", ["OD-13"]),
 ("UI-WALLET-003", "Enable a leader wallet (LIVE)", "Setting LIVE enables new entries from the next genuine post-change event only; no catch-up to current leader position.", ["ARCH Full scope 3", "GUT I02", "HL_Copy_App_SSOT.py /api/live-config/set-mode"]),
 ("UI-WALLET-004", "Disable a leader wallet", "New entries blocked; existing owned exposure remains safely managed.", ["ARCH Full scope 3", "GUT I18", "HL_Copy_App_SSOT.py OFF button / set-mode", "test_g4_ui_controls.py B_UI_OFF_AFFECTS_ENGINE_TRUTH"], "APPLIES", (),
  "UI action -> config -> running engine -> testnet behaviour", "Exchange positions, orders and fills", ["Restart", "Stale configuration", "Rejected update", "API failure"],
  "test_g4_ui_controls.py B1/B2 in-process (wallet_gate path) — not testnet-certified"),
 ("UI-WALLET-005", "Close-only a leader wallet (CLO)", "Reductions/closes still follow the leader; new entries/increases blocked; applied to the entry component before netting.", ["GUT I12", f"{B4}/BUILD4_FINAL_AUTHORITY_MAP.md 'operator switch applied to the entry component'", "test_g4_ui_controls.py B_UI_CLOSE_ONLY_BLOCKS_NEW_ENTRIES"]),
 ("UI-WALLET-006", "Copy model proportional/fixed", "Per-wallet copy_mode select persists and changes engine sizing; fixed is HOLD fail-closed until OD-02 ruled and the UI says so.", ["ARCH Full scope 3", "PRODUCT_SEMANTICS §5 FIXED-MODE HOLD"], "OPEN_DECISION", ["OD-02"]),
 ("UI-WALLET-007", "Norm base (N)", "norm_base >= 1 persists and changes proportional copy scale as documented.", ["HL_Copy_App_SSOT.py _normalise_live_wallet_payload"]),
 ("UI-WALLET-008", "Fixed notional (F)", "fixed_notional >= 0.01 persists; used only by ruled fixed semantics.", ["HL_Copy_App_SSOT.py _normalise_live_wallet_payload"], "OPEN_DECISION", ["OD-02"]),
 ("UI-WALLET-009", "Leader equity base (B)", "leader_equity_base >= 1 persists and is a sizing input only, never truth or target authority.", ["GUT I13", "HL_Copy_App_SSOT.py _normalise_live_wallet_payload"]),
 ("UI-WALLET-010", "Wallet status and position/target representation", "Each wallet row shows mode, health, current exposure, owned position and target that match engine/exchange truth.", ["ARCH Full scope 3"]),
 ("UI-WALLET-011", "Persistence and restart", "All wallet settings survive engine and UI restart exactly; restart creates no orders.", ["ARCH Full scope 3", "GUT I24"]),
 ("UI-WALLET-012", "Invalid input handling", "Bad address, bad mode (BAD_MODE), bad copy mode (BAD_COPY_MODE), non-numeric/negative values are rejected or clamped exactly as documented, the UI shows the error, config unchanged.", ["ARCH Full scope 3", "HL_Copy_App_SSOT.py _normalise_live_wallet_payload", "test_g4_ui_controls.py B_UNKNOWN_MODE_FAILS_CLOSED"]),
 ("UI-WALLET-013", "USER/account wallet can never be enabled", "Account wallet forced OFF by set-wallet-mode; cannot be purged.", ["test_g4_ui_controls.py B_USER_WALLET_NEVER_ENABLES", "HL_Copy_App_SSOT.py purge_wallet_everywhere"]),
 ("UI-WALLET-014", "Two mode writers agree", "Legacy /api/set-wallet-mode and /api/set-all-modes (wallet_gate.json ON/OFF/CLOSE_ONLY) and Live Copy /api/live-config/set-mode (live_config.json LIVE/CLO/OFF) cannot leave the engine with contradictory authority; the effective mode is shown.", ["HL_Copy_App_SSOT.py set_wallet_mode / set_live_config_mode", "HL_Live_Copy_Service.py apply_wallet_gate"], "OPEN_DECISION", ["OD-05"]),
 ("UI-WALLET-015", "PURGE (admin)", "Purge removes the wallet from app/engine-loaded files; must be refused or safe when the wallet owns exposure.", ["HL_Copy_App_SSOT.py /api/admin/purge-wallet"], "OPEN_DECISION", ["OD-13"]),
 ("UI-WALLET-016", "Include in portfolio (INC)", "INC checkbox only changes combined graph/header aggregation, never trading.", ["HL_Copy_App_SSOT.py /api/wallet-include"]),
 ("UI-WALLET-017", "Wallet meta (tag/colour/note)", "Meta edits are display-only and persist.", ["HL_Copy_App_SSOT.py /api/wallet-meta"]),
 ("UI-WALLET-018", "Duplicate add / re-add archived", "Adding an existing or archived wallet restores the existing record rather than creating a second.", ["HL_Copy_App_SSOT.py add_live_config_wallet"]),
 ("UI-WALLET-019", "Wallet subscription coverage", "A wallet is live only with proven WS subscription + poll coverage + freshness; mismatch blocks that wallet.", ["FAILURES LOGIC-007", "FAILURES EXC-011"]),
]
for w in wal:
    id, f, t, s = w[:4]
    ap = w[4] if len(w) > 4 else "APPLIES"; ods = w[5] if len(w) > 5 else ()
    proof = w[6] if len(w) > 6 else None; oracle = w[7] if len(w) > 7 else None
    neg = w[8] if len(w) > 8 else (); prior = w[9] if len(w) > 9 else ""
    rec(id, "WALLET", f, t, s, ap, ods, proof, oracle, neg, prior)

# 9. UI cells — every displayed cell / control in HL_Copy_App_SSOT.py
SSOT = "HL_Copy_App_SSOT.py"
ui = []
def uicells(prefix, group, labels, truth, src, ods=()):
    for i, l in enumerate(labels, 1):
        ui.append((f"{prefix}-{i:02d}", f"{group}: {l}", truth, [f"{SSOT} {src}", "ARCH Full scope 2", "ARCH Full scope 6", "FAILURES UI-001..003"], list(ods)))

uicells("UI-LCC-HDR", "Command Centre header", ["Wallets n / 10", "Mode counts", "Real order sending", "WS overall", "REAL ORDERS safety pill", "Status message line"],
        "Shows engine truth (configured/eligible wallets, auto-send env state, WS health aggregate); unknown -> n/a/OFFLINE, never green.", "render_live_copy_control_panel header")
uicells("UI-LCC-BTN", "Command Centre button", ["Refresh", "Global Controls (toggle)", "Add wallet (opens modal)", "Global Controls close", "Save Global Controls"],
        "Button performs exactly its action; errors are shown in lcStatus/lcGcStatus.", "render_live_copy_control_panel header-actions")
uicells("UI-LCC-CARD", "Real Account card", ["Portfolio Value", "Unrealized PnL", "Realized PnL", "Open Positions", "Live Exposure", "Last Fill", "Last Reject"],
        "Value equals MASTER exchange truth at snapshot time (Live Exposure currently from manual_live_exposure_estimate — must be labelled or replaced by exchange truth); unavailable -> 'Unavailable'/'n/a'.", "renderCards")
uicells("UI-LCC-GRAPH", "Live graph control", ["Account mode", "Selected Wallet PnL mode", "Exposure mode", "1D", "7D", "ALL", "Start datetime", "End datetime", "Apply", "Reset", "Total PnL line", "Realized PnL line", "Drawdown line", "Y axis labels", "X axis ticks", "Subtitle point counts"],
        "Series derive from exchange account history (unified_portfolio_value, else clearinghouse fallback, labelled) and user closedPnl; ranges filter correctly; <2 points shows the explicit message.", "renderGraph")
uicells("UI-LCC-WTBL", "Live Copy Wallets column", ["Wallet (+LIVE COPY/TRACKED/HISTORICAL)", "Mode / Health (mode, eligibility, WS pill)", "Live PnL R/U/Net + PnL status", "Lead<->Copy Diff Total/Avg/Avg bps/Worst bps", "Execution filled/exits/rejects/blocks", "Risk/Exposure exposure/open pos/DD/MaxDD", "Last Fill", "Controls mode select", "Controls copy model select", "Controls F/N/B inputs", "Save", "CLO", "OFF", "Archive"],
        "Each value matches engine/exchange truth for that wallet; controls write live_config.json and the engine applies them.", "renderWallets")
uicells("UI-LCC-DETAIL", "Wallet detail section", ["A Live Performance", "B Open Positions (Coin/Side/Size/Entry/Mark/uPnL/Exposure/Exchange match)", "C Lead vs Copy / Friction", "D Execution Audit"],
        "Per-wallet detail matches exchange fills/positions attributed to that leader; attribution quality shown.", "walletDetailHtml")
uicells("UI-LCC-POS", "Real Copy Positions column", ["Coin", "Side", "Ledger size", "Exchange size", "Entry px", "Mark px", "Pos value", "Unrealized PnL", "Leader wallet", "Status", "Last OID", "Last updated"],
        "Exchange columns equal MASTER clearinghouseState (all DEX scopes); ledger columns labelled non-authoritative; mismatch visible.", "lcPositionRows", ["OD-08"])
uicells("UI-LCC-EXQ", "Execution Quality column", ["Time", "Wallet", "Coin", "Side", "Status", "Limit px", "Fill avg px", "Size", "OID", "Fill-vs-limit %", "Leader-vs-user %", "Market slip %", "Error"],
        "Rows equal send_attempts joined to order_intents and agree with exchange userFills for each OID.", "lcExecQualRows", ["OD-01"])
uicells("UI-LCC-AUD", "Order Intents / Audit column", ["Time", "Wallet", "Coin", "Side", "Source/Reason", "Status", "Decision", "Decision reason", "Suggested limit", "Diff %", "Manual?", "Intent note", "Real order result"],
        "Every intent shown with its real decision and real order result; no intent without a result after settlement window.", "lcAuditRows")
uicells("UI-LCC-REC", "Reconciliation column", ["Severity", "Wallet", "Coin", "Issue", "Count", "Manual ledger", "Exchange", "Last intent", "Last oid", "Last updated", "Action: Archive ledger row"],
        "Lists every ledger-vs-exchange divergence; archive action touches only the manual ledger row and never trading authority.", "lcReconRows")
uicells("UI-LCC-WS", "WS Health column", ["Wallet", "Current", "Grade", "Thread", "Reconnect/min", "Processed", "Raw msg", "Parsed", "Snap seen", "Snap recovered", "Ignored", "Recent errors", "Lifetime errors", "Stale ms", "Data status", "Last close/error"],
        "Matches live WS health file and the engine's real subscription state; stale beyond HL_LIVE_WS_STALE_MS flagged.", "lcHealthRows")
uicells("UI-LCC-TAB", "Tab", ["Real Copy Positions", "Execution Quality", "Order Intents / Audit", "Reconciliation", "WS Health"], "Tab switches panel without changing data.", "lc-tabbar")
uicells("UI-LCC-ADD", "Add-wallet modal field", ["Wallet address", "Initial mode", "Copy model", "Norm base", "Fixed notional", "Leader equity base", "Max diff %", "Daily loss", "Cancel", "Add wallet submit"],
        "Field value persists exactly to live_config.json via /api/live-config/add-wallet; invalid input rejected with visible error.", "lcAddForm", ["OD-07", "OD-10"])
uicells("UI-SSOT-TOP", "Analytics top bar", ["Normalisation Base", "Mode (proportional/fixed)", "Fixed $", "Fee bps", "Copy friction bps", "Set", "Current mode label", "Updated timestamp", "POLL badge"],
        "Changes only the app-derived MODEL (ui_state.json), never live trading; must be labelled as model so it cannot be mistaken for live engine settings.", "HTML_TEMPLATE top", ["OD-18"])
uicells("UI-SSOT-CARD", "Analytics header card", ["PNL Lead/Copy/Delta", "REALISED Lead/Copy", "UNREALISED Lead/Copy", "DRAWDOWN Lead DD/Copy DD/Copy Max", "MAX DD Lead/Copy", "EXPOSURE Open/Max/Base", "COPYABILITY Avg trade %/$ /Avg pos/Req lev", "ACTIVITY Fills/Exits/Open pos/Win", "DB HEALTH status/cache/builds"],
        "Aggregates only included wallets from engine_truth.json + raw fills; values recomputable independently; model-derived values labelled as model.", "render_page cards", ["OD-18"])
uicells("UI-SSOT-TBL", "Analytics table column", ["WALLET", "LEAD EQ", "COPY EQ", "LEAD REAL", "COPY REAL", "LEAD UNREAL", "COPY UNREAL", "LEAD DD", "COPY DD", "LEAD MAXDD", "COPY MAXDD", "Delta $/%", "PNL/HR", "AVG TRADE %", "WIN%", "AVG POS $", "MAX POS $", "AVG NOTIONAL", "% >= $10", "REQ LEV", "FILLS L/C", "EXITS L/C", "POS L/C", "INC / WALLET MODEL controls", "Column sort (/sort/{column})"],
        "Each cell recomputable from engine SSOT; L/C mismatches flagged DIFF; sort is stable and persists.", "render_page table_head / render_row", ["OD-18"])
uicells("UI-SSOT-PAGE", "Other page/endpoint", ["/wallet/{wallet} detail page (closed trades + actions tables)", "/wallet-meta/{wallet} editor", "/api/state", "/api/metrics", "/api/trades/{wallet}", "/api/equity/{wallet}", "/api/ui-state GET/POST", "/api/norm", "/api/reset-app-history", "/api/snapshot", "/api/live-config", "/api/global-controls GET", "/api/live-ws-health", "/api/live-audit-summary", "Contract warning banner (validate_render_contract)"],
        "Endpoint returns data consistent with the rendered UI; reset/snapshot touch no engine truth (test_g4_ui_controls B_RESET_SAFE / B_SNAPSHOT); contract banner appears on any render-contract error.", "@app routes")
for u in ui:
    rec(u[0], "UI", u[1], u[2], u[3], "APPLIES", u[4])

# Cross-cutting UI truth rules
rec("UI-TRUTH-001", "UI", "Truth tier and freshness on every value", "Every cell carries truth tier (AUTHORITATIVE_EXCHANGE / LOCAL_LEDGER / LEADER_SIGNAL / DISPLAY_ONLY / STALE / BLOCKED / SKIPPED) and age; stale/unavailable affects status.", ["FAILURES UI-001", "FAILURES UI-002", "FAILURES LOGIC-012"], "APPLIES")
rec("UI-TRUTH-002", "UI", "No cosmetic green", "Green derives only from GREEN-ONLY-001 (fresh exchange actual == independently computed desired within tolerance, open orders accounted, one master gate).", ["FAILURES GREEN-ONLY-001", "FAILURES UI-003", "ARCH Full scope 2"])
rec("UI-TRUTH-003", "UI", "UI is read-only observer", "UI never becomes position or target authority; UI outage is not a trading fault; diagnostics never block execution.", ["FAILURES ARCH-006", "GUT I16", f"{B4}/BUILD4_FINAL_AUTHORITY_MAP.md Failure scope"])
rec("UI-TRUTH-004", "UI", "At-a-glance wallet, portfolio and system health", "One screen shows key wallet metrics, overall portfolio performance and system health (engine alive, sending state, truth freshness, WS health, current blocker).", ["Project topic", "ARCH Full scope 2"], "OPEN_DECISION", ["OD-20"])
rec("UI-TRUTH-005", "UI", "Historical Build 3 UI restored, not rebuilt", "The certified UI is the located historical Build 3 UI (HL_Copy_App_SSOT.py) reused with the repaired engine.", ["ARCH Full scope 2"])

# 10. Lifecycle
life = [
 ("LIFE-001", "Simple launch/start", "One documented start command brings up exactly one engine process and the UI; second start does not create a duplicate sender."),
 ("LIFE-002", "Stop", "Stop leaves zero unresolved submissions or reports them; no orders sent during stop."),
 ("LIFE-003", "Clean restart", "Restart recovers from external truth with zero new authority (see ENG-007)."),
 ("LIFE-004", "Status", "A compact status reports process, mode, sending state, truth freshness and single current blocker."),
 ("LIFE-005", "Version identification", "Running engine and UI report the exact source commit; unproven identity is reported UNPROVEN, never inferred."),
 ("LIFE-006", "New-version cutover", "Cutover cannot create duplicate send authority or stale replay; old process stopped and proven gone before new sends."),
 ("LIFE-007", "Rollback / recovery", "Previous version can be restored with state compatibility proven."),
 ("LIFE-008", "Configuration migration/compatibility", "live_config.json / wallet_gate.json / SERVICE_STATE_FILE from the prior version load correctly or fail closed."),
 ("LIFE-009", "Crash / watchdog", "After a crash the engine recovers only into a non-sending or explicitly safe state; operator action needed to resume sending."),
]
for id, f, t in life:
    rec(id, "LIFECYCLE", f, t, ["ARCH Full scope 5", f"{B4}/OPERATIONS.md", f"{B4}/FAILURES.md F25"], "APPLIES", ["OD-12"],
        notes="Requirement is binding (ARCHITECTURE Full scope 5); the Build 3 mechanism (command, lock, version source) is not documented in the source set: OD-12.")

# 11. Network / mainnet readiness
net = [
 ("NET-001", "Credential-only mainnet switch", "Moving testnet -> mainnet requires only credential/endpoint configuration change; every follower-side endpoint (exchange, info, WS, meta, l2Book, MASTER truth) follows the follower network setting; nothing is hard-coded to one network.", ["Project topic", "HL_Live_Copy_Service.py LIVE_ORDER_ENDPOINT vs hardcoded info URLs", "exchange_truth.py HL_INFO_URL", "Boss decision, project chat 2026-10-09T12:21Z"], "APPLIES", ["OD-08"]),
 ("NET-002", "Signer vs MASTER separation", "API signer derived from configured key and MASTER from HL_LIVE_HL_ACCOUNT_ADDRESS are valid and distinct; no arbitrary provider fallback.", ["ARCH inv11", "CONTROL_STATE required_corrections[0]"], "APPLIES", []),
 ("NET-003", "Leader and follower networks set independently", "The leader-data network and the follower network (orders, MASTER truth, settlement, asset meta) are each selected by configuration and can be substituted at will; the certification configuration is leader = MAINNET, follower = TESTNET; the split is explicit and tested.", ["PRODUCT_SEMANTICS §1 'Low-latency copy of MAINNET leader activity'", "Boss decision, project chat 2026-10-09T12:21Z"], "APPLIES", ["OD-08"]),
 ("NET-006", "Mainnet and testnet instances run in parallel", "A mainnet-follower instance and a testnet-follower instance can run at the same time without sharing state files, locks, ports, logs, credentials or order identity; neither can read or write the other's follower.", ["Boss decision, project chat 2026-10-09T12:21Z"], "APPLIES", ["OD-08", "OD-12"]),
 ("NET-007", "Certification copies real active mainnet leaders", "Certification follows real, ideally active, mainnet leader wallets and sends only to our testnet follower account; no synthetic or self-controlled leader is used for certification evidence.", ["Boss decision, project chat 2026-10-09T12:21Z", "TESTNET_MAINNET_ENGINE_PARITY.md (leaders stay on mainnet)"], "APPLIES", []),
 ("NET-004", "LIVE/mainnet activation gate", "No mainnet send is possible without explicit Richard authorisation recorded; MAINNET_WRITE_ACTIONS=0 during certification.", ["ARCH inv14", f"{B4}/ACCEPTANCE.md Production Promotion Gates"], "APPLIES", []),
 ("NET-005", "Same SHA promotion", "The exact certified SHA is what runs on mainnet; identity traceable to the reviewed commit.", [f"{B4}/ACCEPTANCE.md PRODUCTION_SAME_SHA", f"{B4}/FAILURES.md F25"], "APPLIES", []),
]
for id, f, t, s, ap, ods in net:
    rec(id, "NETWORK", f, t, s, ap, ods)

# 12. Health
hl = [
 ("HEALTH-001", "WS health visible", "WS per-wallet state, staleness and reconnects visible; stale > HL_LIVE_WS_STALE_MS (30000) flagged.", ["HL_Live_Copy_Service.py LIVE_WS_STALE_MS", "FAILURES EXC-009"]),
 ("HEALTH-002", "Follower truth freshness visible", "Age of last MASTER truth read visible; stale blocks sizing.", ["FAILURES EXC-001", "FAILURES EXC-019"]),
 ("HEALTH-003", "Current blocker visible", "The current blocking reason (e.g. FIXED_MODE_AUTHORITY_HOLD, ACCOUNT_NET_TRUTH_UNAVAILABLE) is visible to the operator.", ["PRODUCT_SEMANTICS §5", f"{B4}/OPERATIONS.md SINGLE_BLOCKER"]),
 ("HEALTH-004", "Local failure isolation", "One bad wallet/symbol/API response blocks only that key; the five account-wide hazards are the only global stops.", ["GUT I10", f"{B4}/BUILD4_FINAL_AUTHORITY_MAP.md Failure scope"]),
 ("HEALTH-005", "Diagnostics never block", "Certification, UI, Graphify, watchdog and repo diagnostics never block a legitimate execution delta.", ["GUT I16"]),
]
for id, f, t, s in hl:
    rec(id, "HEALTH", f, t, s)

# 13. Agent control system (Mission Control I1-I23 + Gate 0 + OPERATING_PROTOCOL)
mci = Path(SRC, MC, "INVARIANTS.md").read_text()
for m in re.finditer(r"^## (I\d+) — (.+)$", mci, re.M):
    n = int(m.group(1)[1:])
    rec(f"CTRL-{m.group(1)}", "CONTROL", f"Mission Control {m.group(1)}: {m.group(2)}", m.group(2) + " (see source for full rule).",
        [f"{MC}/INVARIANTS.md {m.group(1)} (local working tree, feature/generic-wake-controller 5de53fa)"], "APPLIES", ["OD-15"],
        notes="origin/control-mailbox carries a different INVARIANTS.md (A1-A17); see OD-15.")
rec("CTRL-GATE0", "CONTROL", "Gate 0 CONTROL_EVENT_INGRESS", "Live event-push control proven per PROJECT_GATES Gate 0 acceptance list before product implementation.", [f"{MC}/PROJECT_GATES.md Gate 0", "CONTROL_STATE transport_certification"], prior="CONTROL_STATE transport_certification.current_status=PASS")
rec("CTRL-BIND", "CONTROL", "Controller binding identity", "Exactly one canonical Controller binding; CONTROL_STATE.json and CONTROL_CONTRACT.json agree.", ["CONTROL_STATE bindings.controller_uuid_dispute"], "OPEN_DECISION", ["OD-03"])
rec("CTRL-HWM", "CONTROL", "Gate truth from mailbox, not stale local state", "No component derives gate truth from a stale local CONTROL_STATE.json; 5 invalidated adjudication_log false negatives cannot recur.", ["CONTROL_STATE adjudication_log_disposition"])
rec("CTRL-EVID", "CONTROL", "Evidence discipline", "Every handoff carries TASK_ID, COMMIT_SHA, files changed, LOC, tests executed, outputs, uncertainty, STAND_DOWN_REQUEST.", [f"{B3}/OPERATING_PROTOCOL.md Evidence discipline"])
rec("CTRL-ESC", "CONTROL", "Architect escalation tripwires", ">260 new LOC, >2 production files, second process, new dependency, new persistent store, second send path, invariant change, repeated gate failure -> ARCHITECT_REVIEW_REQUIRED.", [f"{B3}/ARCHITECTURE.md Automatic Architect escalation"], prior="G3 one-gate exception: 400 gross additions accepted (CONTROL_STATE scope_budget)")

# 14. Build 4 frozen invariants I01-I26 (applicability per inherited requirement)
gut = Path(SRC, B4, "GUT_CONTRACT.md").read_text()
APPL = {
 1: ("APPLIES_PROPOSED", []), 2: ("APPLIES", []), 3: ("APPLIES_PROPOSED", []), 4: ("APPLIES_PROPOSED", []),
 5: ("APPLIES_PROPOSED", []), 6: ("APPLIES_PROPOSED", []), 7: ("APPLIES", []), 8: ("APPLIES_PROPOSED", []),
 9: ("ADAPTED_PROPOSED", []), 10: ("APPLIES_PROPOSED", []), 11: ("APPLIES_PROPOSED", []), 12: ("OPEN_DECISION", ["OD-05"]),
 13: ("OPEN_DECISION", ["OD-09"]), 14: ("APPLIES_PROPOSED", []), 15: ("APPLIES_PROPOSED", []), 16: ("APPLIES_PROPOSED", []),
 17: ("APPLIES_PROPOSED", []), 18: ("APPLIES_PROPOSED", ["OD-13"]), 19: ("APPLIES_PROPOSED", []), 20: ("OPEN_DECISION", ["OD-01", "OD-10"]),
 21: ("OPEN_DECISION", ["OD-01", "OD-10"]), 22: ("APPLIES_PROPOSED", []), 23: ("APPLIES", []), 24: ("APPLIES", []),
 25: ("APPLIES", []), 26: ("OPEN_DECISION", ["OD-11"]),
}
NOTE = {2: "Equivalent to PRODUCT_SEMANTICS B2 / ARCH inv13.", 7: "Equivalent to CONTROL_STATE G3 required semantics.",
        9: "Build 4 runtime/active path does not exist in Build 3; Build 3 equivalent is SERVICE_STATE_FILE as sole durable store (ARCH inv4).",
        8: "Build 4 lease mechanism not imported (ARCH inv5); Build 3 meets it via one process + one order site.",
        23: "Equivalent to CONTROL_STATE required_corrections[2] 'partial persists remaining'.", 24: "Equivalent to ARCH inv13.", 25: "Equivalent to ARCH inv12 + UNATTRIBUTED_BASELINE correction."}
for m in re.finditer(r"^### (I\d\d) (\S+)\n(.*?)(?=^### I\d\d |^---|^## )", gut, re.M | re.S):
    n = int(m.group(1)[1:]); body = m.group(3)
    first = " ".join(l.strip() for l in body.strip().split("\n\n")[0].splitlines()).replace("**", "").replace("`", "")
    tests = re.search(r"\*\*Tests:\*\* (.+)", body); prev = re.search(r"\*\*Prevents:\*\* (.+)", body)
    ap, ods = APPL[n]
    rec(f"B4-{m.group(1)}", "REGRESSION", f"Build 4 {m.group(1)} {m.group(2)}", first,
        [f"{B4}/GUT_CONTRACT.md {m.group(1)}"], ap, ods,
        prior=("Build 4 tests: " + tests.group(1)) if tests else "",
        notes=((NOTE.get(n, "") + " ") if NOTE.get(n) else "") + (("Prevents: " + prev.group(1)) if prev else ""))

# 15. Regression catalogue R01-R25
for m in re.finditer(r"^\| (R\d\d) \| (.+?) \| (.+?) \| (\S+?) \|$", gut, re.M):
    rec(f"B4-{m.group(1)}", "REGRESSION", f"Historical regression {m.group(1)}", f"Must not recur: {m.group(2)}",
        [f"{B4}/GUT_CONTRACT.md §D {m.group(1)}"], "APPLIES_PROPOSED", ["OD-04"] if m.group(1) == "R01" else [],
        prior=f"Build 4 coverage {m.group(4).strip('*')}: {m.group(3)}")

# 16. FAILURES.md taxonomy
fz = Path(SRC, B4, "FAILURES.md").read_text()
FAPPL = {"PROCESS-002": ("SUPERSEDED", ["OD-04"], "Superseded for this project by ARCHITECTURE.md product-preservation presumption: repair Build 3, not rebuild."),
         "ARCH-014": ("APPLIES_PROPOSED", [], "ARCHITECTURE.md: the LOC ceiling is a tripwire, not a reason to ship an incomplete repair."),
         "TEST-001": ("OPEN_DECISION", ["OD-04"], "As worded it replays historical leader-POSITION snapshots; under B1/B2 targets derive from events. Needs an applicability ruling."),
         "PRODUCT-001": ("OPEN_DECISION", ["OD-17"], "Wallet-selection gating is a product feature; applicability to Build 3 not stated."),
         "EXC-006": ("APPLIES_PROPOSED", [], "Must respect ARCH inv12 (never flatten unrelated pre-existing inventory)."),
         "TEST-010": ("OPEN_DECISION", ["OD-11"], ""), "VERIFY-008": ("OPEN_DECISION", ["OD-11"], ""), "EXC-017": ("OPEN_DECISION", ["OD-11"], "")}
for m in re.finditer(r"^  - id: (\S+)\n(.*?)(?=^  - id: |^```)", fz, re.M | re.S):
    fid, body = m.group(1), m.group(2)
    def g(k):
        x = re.search(rf"^\s+{k}: \"?(.+?)\"?$", body, re.M); return x.group(1) if x else ""
    name = g("name")
    exp = g("prevention") or g("required_action") or g("must_prove") or g("failure")
    ap, ods, note = FAPPL.get(fid, ("APPLIES_PROPOSED", [], ""))
    rec(f"F-{fid}", "REGRESSION", f"FAILURES {fid} {name}", exp, [f"{B4}/FAILURES.md {fid}"], ap, ods,
        notes=(("Trigger/failure: " + (g("failure") or g("trigger"))) if (g("failure") or g("trigger")) and exp != g("failure") else "") + ((" " + note) if note else ""))
rec("F-GREEN-ONLY-001", "REGRESSION", "Canonical green condition", "Green only when fresh exchange actual == independently computed desired within tolerance, all open orders accounted, every send path under one master gate.", [f"{B4}/FAILURES.md GREEN-ONLY-001"])
for i, p in enumerate(re.findall(r"^  - (.+)$", fz.split("f25_mandatory_proofs:")[1].split("f25_automatic_fail_if:")[0], re.M), 1):
    rec(f"F25-P{i:02d}", "LIFECYCLE", f"F25 proof {i}", p, [f"{B4}/FAILURES.md F25 mandatory proofs"], "ADAPTED_PROPOSED", ["OD-12"])
for i, p in enumerate(re.findall(r"^  - (.+)$", fz.split("f25_automatic_fail_if:")[1].split("f25_authority:")[0], re.M), 1):
    rec(f"F25-X{i:02d}", "LIFECYCLE", f"F25 automatic fail {i}", "Must never happen: " + p, [f"{B4}/FAILURES.md F25 automatic fail"], "ADAPTED_PROPOSED", ["OD-12"])
for i, c in enumerate(re.findall(r"- claim: \"(.+?)\"", fz), 1):
    rec(f"F-CLAIM-{i:02d}", "REGRESSION", "Forbidden claim", f"Never accepted as evidence: '{c}'", [f"{B4}/FAILURES.md Hard forbidden claims"])

# 17. Completion definition (cross-reference)
done = re.findall(r"^\d+\. (.+)$", Path(SRC, B3, "PRODUCT_SEMANTICS.md").read_text().split("## 4.")[1].split("## 5.")[0], re.M)
for i, d in enumerate(done, 1):
    rec(f"DONE-{i:02d}", "CONTROL", f"Measurable DONE {i}", d, [f"{B3}/PRODUCT_SEMANTICS.md §4.{i}", f"{B3}/ARCHITECTURE.md Completion definition"],
        prior="DONE, cea4beb (provenance baseline import)" if i == 1 else "")

# 18. Local-trading evidence (added 2026-10-09): Build 4 Phase 6T testnet protocol, reviewer verdicts,
#     UI audits, and the Build 3 money-incident trail. Paths are relative to source-docs/.
LT = "local-trading"
B4P = f"{LT}/hl-build4-final-closeout/proofs/build4_completion"
B3A = f"{LT}/Hyperliquid scanner/_archive"
B3AU = f"{B3A}/hl_stage2/hl_live_copy_audit"
LWT = f"{LT}/Hyperliquid scanner/LIVE WALLET TRADING"
M1, M2, M3 = (f"{B4P}/PHASE_6T_C_MATRIX_F01_F09.md", f"{B4P}/PHASE_6T_C_MATRIX_F10_F19.md", f"{B4P}/PHASE_6T_C_MATRIX_F20_F27.md")
PROT, TRN = f"{B4P}/PHASE_6T_C_COMPREHENSIVE_TESTNET_PROTOCOL.md", f"{B4P}/PHASE_6T_C_TRANSPORT_REQUIREMENTS.md"
TN_PROOF = "Predeclared Phase 6T-style scenario on testnet through the production engine path only (no direct exchange.order); evidence per class with exchange parity"
TN = [
 # (n, area, title, expected, srcs, applicability, ods, notes)
 (1, "RISK", "Stale leader capital / oversizing", "Leader capital used for an OPEN/INCREASE is proven fresh at the send boundary (Build 4: exchange clock, 300 s ceiling, synchronous refetch); if unproven the whole OPEN/INCREASE is refused; REDUCE/CLOSE never waits on it; a seeded/default capital value never reaches a send; clock skew beyond the ceiling is refused.", [M1 + " F1", f"{B4P}/MILESTONE_01_TRADE_BOUNDARY_FRESHNESS_FROZEN.md"], "OPEN_DECISION", ["OD-22"], "Build 3 copy scale = norm_base / leader_equity_base (configured, default 10,000; HL_Live_Copy_Service.py L106/L1278/L2022), not fresh leader capital. Applies only if OD-22 adopts a fresh-capital denominator; the 'no seeded default reaches a send' part is ENG-VAL-01."),
 (2, "RISK", "Follower materially less liquidation-safe than leader", "Projected post-trade liquidation distance is checked against the MAX distance across contributing leaders, never an average; unsafe entries blocked whole.", [M1 + " F2", f"{B4P}/INVARIANT_PS1_PORTFOLIO_SAFETY.md"], "OPEN_DECISION", ["OD-23"], ""),
 (3, "ENGINE", "Configured follower-capital basis / sizing authority", "Copy scale is computed from the authoritative configured basis; balance changes do not silently move the basis; capital is a basis, not a cap.", [M1 + " F3", f"{B4P}/PHASE_6T_C_F26_READING_A.md", f"{B4P}/MILESTONE_02_CAPITAL_VS_POSITION_PROPORTIONAL_FROZEN.md"], "OPEN_DECISION", ["OD-22"], "Build 3 basis is norm_base / leader_equity_base."),
 (4, "ENGINE", "Exit sizing", "REDUCE/CLOSE is proportional to the attributed (owned) position, never recomputed from fresh leader capital; full close and flip close the owned sleeve exactly; stale capital can never block an exit.", [M1 + " F4", f"{B4P}/MILESTONE_02_CAPITAL_VS_POSITION_PROPORTIONAL_FROZEN.md"], "APPLIES_PROPOSED", [], "Consistent with Build 3 proportional sleeve = leader position x copy scale."),
 (5, "ORDER", "Sub-minimum OPEN/INCREASE escape", "The minimum order notional is enforced at the true execution authority for every OPEN/INCREASE; the execution buffer and reconciliation tolerance are separate quantities and are not conflated.", [M1 + " F5"], "APPLIES", ["OD-09"], "Value ($30 Build 4 vs $10 Build 3 MIN_ORDER_NOTIONAL) is OD-09."),
 (6, "RISK", "Catastrophic limits used as clamps", "Backstop limits (per-order, per-wallet, total, daily count) block the whole order; they never resize/clamp it.", [M1 + " F6", f"{LWT}/PHASE3B_PROPORTIONAL_SIZING_FIXED.md"], "APPLIES_PROPOSED", ["OD-06", "OD-24"], "Phase 3B added a post-sizing clamp (Layer 1) - the pattern F6 forbids. Build 4 values 10k/50k/100k/100 are OD-24."),
 (7, "RISK", "Other-position margin (M_other) omitted", "Margin consumed by the follower's other positions is included in the post-trade safety projection.", [M1 + " F7", f"{B4P}/INVARIANT_PS1_PORTFOLIO_SAFETY.md"], "OPEN_DECISION", ["OD-23"], ""),
 (8, "RISK", "Unresolved A0 / crossAccountValue", "Account value used for safety is resolved from exchange truth; unresolved means refuse the entry.", [M1 + " F8"], "OPEN_DECISION", ["OD-23"], ""),
 (9, "SETTLE", "Namespace collision (XYZ:NBIS vs NBIS)", "HIP-3 / builder-DEX symbols are exact and DEX-scoped everywhere (sizing, orders, ownership, truth, UI); no bare-symbol fallback; no double prefix; meta looked up in the DEX's own universe.", [M1 + " F9", f"{B4P}/WA_VERDICT_04_attempt_01_three_findings.md", f"{B3AU}/full_exchange_audit_latest.md"], "APPLIES", [], "Testnet has no XYZ markets; protocol uses k-prefix markets as analogue - XYZ must be verified separately on mainnet."),
 (10, "SETTLE", "Ambiguous intent / 429 storm", "An ambiguous submission (timeout, 429, unknown result) is never retried blind; it is resolved from exchange truth before any further send for that coin; a 429 storm does not produce duplicates.", [M2 + " F10", PROT], "APPLIES_PROPOSED", [], "Consistent with ACK-is-not-settlement and durable in-flight reservations."),
 (11, "SETTLE", "Ownership / truth fail-open", "Ownership attribution never fails open across any crash point; missing ownership truth refuses new exposure.", [M2 + " F11"], "APPLIES_PROPOSED", [], ""),
 (12, "SETTLE", "Manual reconciliation", "Outside-tolerance divergence is surfaced for manual reconciliation and never auto-closed or auto-adopted.", [M2 + " F12"], "APPLIES", [], "Equivalent to PRODUCT_SEMANTICS B4 (divergence surfaced for adjudication)."),
 (13, "SETTLE", "Reconciliation tolerance / blind catch-up", "Within tolerance follows the normal path; outside tolerance sends nothing; a position difference without genuine fill authority never creates OPEN/INCREASE; retries use the same current mark and tolerance; missing/invalid mark fails closed.", [M2 + " F13", f"{B4P}/MILESTONE_03_RECOVERED_FILL_RECONCILIATION_TOLERANCE_FROZEN.md", f"{B4P}/WA_VERDICT_03_attempt_02_quiet_retry_finding.md"], "APPLIES", ["OD-24"], "No-blind-catch-up equals B2. The $30-at-mark tolerance value is OD-24."),
 (14, "UI", "UI control looks real but does not govern runtime", "Every UI control is proven through VISIBLE -> CLICK -> BACKEND -> PERSISTED -> RUNTIME -> EXECUTION -> REFRESH in a real browser while testnet positions exist.", [M2 + " F14", f"{B4P}/false_control_audit.json"], "APPLIES", ["OD-06"], ""),
 (15, "HEALTH", "Watchdog / supervisor wrong-mode intervention", "Any watchdog predicate exactly matches the engine's own freshness budget; it never changes mode on a different definition of stale.", [M2 + " F15"], "ADAPTED_PROPOSED", ["OD-12"], "Applies to whatever supervision Build 3 uses."),
 (16, "RISK", "Stale risk / account truth at send boundary", "Follower account truth used for an entry decision is fresh at the send boundary; otherwise the entry is refused.", [M2 + " F16", f"{B4P}/MILESTONE_01_TRADE_BOUNDARY_FRESHNESS_FROZEN.md"], "APPLIES_PROPOSED", ["OD-01"], ""),
 (17, "ENGINE", "Trade direction inferred from position", "Trade direction comes only from a genuine leader fill, never from a position snapshot.", [M2 + " F17"], "APPLIES", [], "Equivalent to PRODUCT_SEMANTICS B1/B2."),
 (18, "SETTLE", "Duplicate / recovered / out-of-order fills", "Fills are keyed by exchange identity (Build 4: HL_FILL:<oid>:<tid>:WALLET:<addr>); duplicates, recoveries and reordering are processed exactly once.", [M2 + " F18", f"{B3A}/HYPERLIQUID_FAILURE_ANALYSIS.md #3"], "APPLIES", [], "Earlier builds deduped on (time, px, sz, side) without fill id."),
 (19, "LIFECYCLE", "Startup / restart unintended orders", "STARTUP_UNINTENDED_ORDERS = 0 at every boundary (cold start, restart, crash recovery, config reload).", [M2 + " F19"], "APPLIES", [], "Equivalent to B2 / DONE-4."),
 (20, "LIFECYCLE", "Sender lease / fencing", "At most one sender can submit; a stale holder is fenced out.", [M3 + " F20"], "ADAPTED_PROPOSED", ["OD-12"], "Build 3 mechanism is one process + one .order() site."),
 (21, "RISK", "Open-safety failure traps REDUCE/CLOSE", "No entry-side safety failure (stale capital, risk truth, budget) can block a REDUCE/CLOSE.", [M3 + " F21"], "APPLIES_PROPOSED", [], ""),
 (22, "UI", "UI minimum / config authority confusion", "The UI shows the minimum order value from the authoritative execution config, labelled as such.", [M3 + " F22"], "APPLIES_PROPOSED", ["OD-09"], ""),
 (23, "UI", "UI account / position / open-order / risk truth", "UI account, position, open-order and risk values are multi-DEX exchange truth; the UI never invents reassuring state.", [M3 + " F23", f"{B4P}/UI_TRUTH_AUDIT.json"], "APPLIES", [], ""),
 (24, "NETWORK", "Shared rate-limit / 429 regression", "Request weight is budgeted so background/UI reads cannot starve execution (Build 4: 1200 WU/min split across build, background, execution, SSOT and UI).", [M3 + " F24"], "ADAPTED_PROPOSED", ["OD-24"], ""),
 (25, "LIFECYCLE", "Deployment / control-plane identity", "The running process, release and commit are provably the reviewed ones.", [M3 + " F25"], "ADAPTED_PROPOSED", ["OD-12"], "See F25-P/X records."),
 (26, "RISK", "Allocation / risk-budget enforcement", "Allocation is a sizing basis, not a cumulative budget (Reading A, F26.A-H); safe exact orders are not rejected merely for exceeding it.", [M1 + " F26", f"{B4P}/PHASE_6T_C_F26_READING_A.md"], "OPEN_DECISION", ["OD-22"], ""),
 (27, "RISK", "Margin-state divergence without a fill", "A leader margin/leverage change is risk authority only, never a trade.", [M3 + " F27"], "OPEN_DECISION", ["OD-23"], ""),
]
for n, area, t, e, s, a, o, nt in TN:
    rec(f"TN-F{n:02d}", area, f"Testnet scenario F{n}: {t}", e, s, a, o, proof=TN_PROOF, notes=nt)
rec("TN-PS1", "RISK", "Resulting portfolio safety", "Every OPEN/INCREASE needs both exact sizing and a projected post-trade portfolio within every risk/liquidation constraint; unsafe is blocked whole, never resized; safe exact orders are not rejected for exceeding the capital basis.", [f"{B4P}/INVARIANT_PS1_PORTFOLIO_SAFETY.md"], "OPEN_DECISION", ["OD-23"])

CAMP = [
 ("Bounds frozen before first order", "Campaign bounds (orders, per-order $, gross $, exposure $, positions, open orders, leverage, collateral) are declared and committed before the first order and never changed after seeing results."),
 ("Flat start", "The testnet follower starts flat, or pre-existing inventory is recorded and excluded from every count."),
 ("Market allowlist", "Markets come from a captured testnet universe snapshot; anything else is refused."),
 ("Ambiguous-submission stop", "An ambiguous submission stops the campaign until resolved from exchange truth."),
 ("Cleanup scope", "Cleanup may touch only objects the campaign created on testnet, identified by recorded cloid/oid."),
 ("Abort conditions", "Predeclared abort conditions (bound breach, unexpected order, identity mismatch, leak) halt sending immediately."),
 ("Proof environment identity", "Interpreter, SDK version, commit and config hashes are recorded with the evidence."),
 ("Per-class exchange parity", "Each scenario class passes only with exchange-parity evidence; nothing passes by inference; FAILs are kept permanently."),
 ("Testnet coverage gaps", "Anything testnet cannot exercise (e.g. XYZ HIP-3 markets) is listed and verified on mainnet before mainnet certification."),
]
for i, (t, e) in enumerate(CAMP, 1):
    rec(f"TN-CAMP-{i:02d}", "CONTROL", f"Testnet campaign: {t}", e, [PROT, f"{M3} §E"], "APPLIES_PROPOSED", ["OD-11"],
        proof="Campaign manifest committed before the first order; final report diffed against it",
        oracle="git history of the manifest plus exchange order/fill history for the campaign window")

trn = Path(SRC, TRN).read_text()
for m in re.finditer(r"^\s+(T\d+)\s+(.+)$", trn, re.M):
    rec(f"TN-{m.group(1)}", "NETWORK", f"Testnet transport {m.group(1)}", m.group(2).strip(), [TRN], "APPLIES_PROPOSED", ["OD-08"])
for m in re.finditer(r"^\s+(A\d)\s+(.+?)\s+->\s+(\S.*)$", trn, re.M):
    rec(f"TN-{m.group(1)}", "NETWORK", f"Transport attack case {m.group(1)}", f"{m.group(2).strip()} -> {m.group(3).strip()}", [TRN], "APPLIES_PROPOSED", ["OD-08"],
        proof="Unit/integration test feeding the hostile origin to the real client path", oracle="Request log shows no connection to the hostile origin")

HARN = [
 ("No direct order calls in the harness", "Certification scripts place orders only through the engine's single sender; no proof/test/soak script calls exchange.order directly.", [f"{B4P}/WA_ONE_ENGINE_VERDICT_a8d0641.md", f"{B4P}/WA_VERDICT_TESTNET_HARNESS_REMEDIATION_01.md"]),
 ("Order-site census covers every executable file", "The one-order-site census scans all executable code including proofs, tests, scripts and archives on the run path.", [f"{B4P}/WA_ONE_ENGINE_VERDICT_a8d0641.md"]),
 ("One engine for testnet and mainnet", "Testnet and mainnet run the same engine; only follower endpoints/credentials differ, injected in one place; leaders stay on mainnet.", [f"{B4P}/TESTNET_MAINNET_ENGINE_PARITY.md"]),
 ("Secrets never leak", "Keys are never logged, put in argv or written to evidence; a leak scan over all evidence finds zero.", [TRN]),
 ("Evidence states only what ran", "Reports claim only executed, predeclared checks; overclaims are FAIL.", [f"{B4P}/WA_VERDICT_TESTNET_HARNESS_REMEDIATION_02.md", f"{B4P}/WA_F26_PS1_RESUBMISSION_V2.md"]),
 ("False-control census", "For every UI write endpoint, list fields the engine reads versus fields accepted but ignored; any ignored field is a finding.", [f"{B4P}/false_control_audit.json"]),
 ("Agents do not share a worktree", "Two agents never edit the same worktree concurrently; conflicts are detected and stopped.", [f"{LT}/b4_controller/state/worker_conflict_20260930.json"]),
]
for i, (t, e, s) in enumerate(HARN, 1):
    rec(f"HARN-{i:02d}", "CONTROL", t, e, s, "APPLIES_PROPOSED", ["OD-08"] if i == 3 else (["OD-06"] if i == 6 else []))

VAL = [
 ("No fabricated defaults", "Missing numeric truth is never replaced by a default ('or 0.0', DEFAULT_LEADER_EQUITY_BASE=10000, seeded capital); it fails closed for entries.", [f"{B4P}/WA_VERDICT_04_attempt_02_three_remaining_defects.md", f"{B4P}/WA_VERDICT_05J_exchange_root_residual.md"], "Build 3 code has max(1.0, fnum(raw.get('leader_equity_base'), 10000)) at HL_Live_Copy_Service.py L1278 (code-read, unconfirmed by run)."),
 ("Non-finite values rejected", "NaN, infinity and negative prices/sizes/capital are rejected at ingestion.", [f"{B4P}/WA_PACKET_04_REMEDIATION.md"], ""),
 ("Malformed exchange data rejected", "A malformed margin tier or meta row fails closed; it is never silently skipped.", [f"{B4P}/WA_VERDICT_04_attempt_02_three_remaining_defects.md"], ""),
 ("Maintenance margin from exchange tables", "Maintenance margin uses the exchange marginTables, not a leverage-derived approximation.", [f"{B4P}/WA_REMEDIATION_04_tier_namespace_agg_maintenance.md"], "Relevant only if OD-23 adopts a liquidation projection."),
]
for i, (t, e, s, nt) in enumerate(VAL, 1):
    rec(f"ENG-VAL-{i:02d}", "ENGINE", t, e, s, "APPLIES_PROPOSED", ["OD-23"] if i == 4 else [], notes=nt,
        neg=["field missing", "field null", "NaN/inf", "negative", "wrong type"])

INC = [
 ("REGRESSION", "Large exchange position visible", "Every follower exchange position, of any size and DEX, appears on the live-copy dashboard.", [f"{B3AU}/DASH_MISSING_6K_POSITION_ROOT_CAUSE.txt", f"{B3AU}/HEALTHCHECK_LARGE_POSITION_VISIBILITY_REPORT.txt"], []),
 ("REGRESSION", "Shared-symbol exposure counted", "Wallet exposure includes abs(size) x mark for shared-symbol sleeve rows; no row reports exposure as None while a position exists.", [f"{B3AU}/NEAR_6K_OWNERSHIP_CONFIRMED.txt"], []),
 ("REGRESSION", "Account vs engine position diff surfaced", "The account panel shows exchange positions by coin directly; any engine-vs-account difference is shown as a divergence.", [f"{B3AU}/ACCOUNT_VS_ENGINE_POSITION_DIFF_REPORT.txt"], []),
 ("REGRESSION", "Ledger rows unsupported by exchange", "Ledger positions the exchange does not support are flagged (LEDGER_UNSUPPORTED_BY_EXCHANGE), never shown as owned exposure.", [f"{B3AU}/ORPHAN_RECONCILE_READONLY_NOW.txt"], []),
 ("REGRESSION", "External and residual exposure categorised", "External/unowned and residual account-level exposure are categorised and never adopted as copy sleeves.", [f"{B3AU}/overnight_babysitter_red_report.txt"], []),
 ("REGRESSION", "No duplicate live fills", "Each cloid/oid maps to its fills exactly once; each post-restart oid has exactly one fill record.", [f"{B3AU}/overnight_babysitter_red_report.txt"], []),
 ("REGRESSION", "HIP-3 namespace consistent", "A HIP-3 symbol uses one namespace form (e.g. XYZ:BRENTOIL) across positions, prices, audit and UI.", [f"{B3AU}/full_exchange_audit_latest.md", f"{B3AU}/BRENTOIL_PRICE_SOURCE_MISMATCH.txt"], []),
 ("REGRESSION", "HIP-3 price from its own book", "A HIP-3 market's price is read from that DEX's own book/mids, never from a same-named main-DEX market.", [f"{B3AU}/BRENTOIL_PRICE_SOURCE_MISMATCH.txt", f"{B3AU}/BRENTOIL_MISMATCH_PROBE.txt"], ["OD-01"]),
 ("REGRESSION", "Unknown spot/asset meta fails closed", "A coin whose meta cannot be resolved (e.g. @230, @150) is refused and surfaced, never sent.", [f"{B3AU}/live_repair_resume_report.txt"], []),
 ("REGRESSION", "Unproven send is ACTIVE_RED", "A send attempt that is not proven copied and reconciled is classified ACTIVE_RED and shown until resolved.", [f"{B3AU}/incident_20260518_active_red_attribution.json"], []),
 ("HEALTH", "Engine death is visible", "If the engine process is not running, the UI shows it; status cards never show OK while no engine process exists.", [f"{B3AU}/death_attribution_snapshot.json"], ["OD-20"]),
 ("REGRESSION", "Minimum notional for every lifecycle", "Minimum notional applies to ENTRY/ADD/EXIT; sub-minimum exits are held as dust (DUST_BELOW_MIN_NOTIONAL) and surfaced, not silently dropped.", [f"{B3A}/TRUTH_RESTORATION_SUMMARY.md", f"{B3A}/LIVE_MONEY_REVIEW_FINDINGS.md #6"], ["OD-09"]),
 ("UI", "Displayed target is the gated target", "The UI never displays an ungated desired target the engine would refuse; a blocked target is shown as blocked with its reason.", [f"{LWT}/PHASE3B_PROPORTIONAL_SIZING_FIXED.md"], []),
 ("UI", "No false budget or decorative input", "The UI shows no 'available capital' budget or editable allocation that governs nothing.", [f"{B4P}/F26H_UI_ALLOCATION_AUDIT.md"], ["OD-06"]),
 ("UI", "Close-only with open exposure is visible", "When a wallet is CLOSE_ONLY with an open sleeve, the UI shows the remaining exposure and how it will close.", [f"{LWT}/reports/codex_product_closure_20260716_001233/UI_CONTROL_MATRIX.json"], ["OD-25"]),
 ("UI", "Metric source and freshness shown", "Wallet metrics show whether they are MTM or realised and how fresh they are; a degraded source is visibly flagged.", [f"{B3A}/HYPERLIQUID_FAILURE_ANALYSIS.md #2 #6", f"{B3A}/LIVE_MONEY_REVIEW_FINDINGS.md"], ["OD-18"]),
 ("UI", "PnL fee basis labelled", "PnL is shown net of fees or labelled gross.", [f"{B3A}/LIVE_MONEY_REVIEW_FINDINGS.md #3"], ["OD-18"]),
 ("LIFECYCLE", "Operator control resolves to the running release", "The operator's start/stop/status entry point resolves to the release actually running, and fails closed if it cannot.", [f"{B4P}/FINDING_P1_OPERATOR_LAUNCHER_POINTER_BROKEN.md"], ["OD-12"]),
]
for i, (area, t, e, s, o) in enumerate(INC, 1):
    rec(f"INC-{i:02d}", area, t, e, s, "APPLIES_PROPOSED" if o else "APPLIES", o)

# Build 3 dashboard field proof (2026-05-11): one record per audited field, prior verdict carried.
import csv as _csv
fp_path = f"{B3A}/hl_stage2/acceptance_reports/dashboard_field_proof_20260511_124846.csv"
for i, row in enumerate(_csv.DictReader(open(Path(SRC, fp_path), encoding="utf-8-sig")), 1):
    v = row["PASS_FAIL_NOT_PROVEN"]
    rec(f"UI-FP-{i:03d}", "UI", f"{row['UI_LOCATION']}: {row['FIELD_NAME']}",
        f"Shows {row['SOURCE_KEY_OR_COLUMN']} from {row['SOURCE_DATA_FILE']} as {row['FORMULA']} (provenance {row['PROVENANCE_TYPE']}; rows {row['ROW_TYPE_APPLIES_TO']}; can affect send: {row['CAN_AFFECT_SEND']}; execution truth: {row['IS_EXECUTION_TRUTH']}).",
        [fp_path], "APPLIES", ["OD-21"],
        prior=f"2026-05-11 field proof: {v}" + (f" ({row['FAIL_REASON']})" if row["FAIL_REASON"] else ""),
        notes="Field-level baseline; may overlap UI-LCC-*/UI-SSOT-* cells.")

# Engine base = HL_Live_Copy_Service_Core.py (Boss, 2026-10-09T12:30Z; OD-26 decided). Line refs below are to the
# surviving 7,705-line copy .bak_pre_convergence_wiring_20260602 (sha256 5bda57be...f848). Code-read only; confirm by run.
CORE = "HL_Live_Copy_Service_Core.py (7,705-line, sha256 5bda57be)"
CORE_NOTES = {
 "RISK-004": "Core: max_order_notional_usd read at L1935 and enforced at L2441 and L3250.",
 "RISK-001": "Core: max_total_live_exposure_usd has an accessor (L1929) but no caller was found, so it is not enforced.",
 "RISK-002": "Core: max_asset_directional_exposure_usd is not referenced.",
 "RISK-003": "Core: max_wallet_exposure_usd read at L1931 (per-wallet value overrides the global one) and used at L2444.",
 "RISK-005": "Core: marketable_bps read at L1939 (default env HL_LIVE_MARKETABLE_BPS = 25) and used for pricing at L3210.",
 "RISK-006": "Core: max_close_adverse_diff_pct has an accessor (L1942) but is only reported in status (L5675); no enforcement was found.",
 "RISK-007": "Core: symbol_allowlist (also allow_symbols / allowlist) read at L1944 and applied at L2430.",
 "RISK-008": "Core: symbol_blocklist (also block_symbols / blocklist) read at L1944 and applied at L2430.",
 "RISK-009": "Core: daily loss is not referenced anywhere.",
 "RISK-011": "Core: MAX_WALLETS (env HL_LIVE_WS_MAX_WALLETS, default 10, L145) truncates the leader WS subscription list (L4537, L5757, L6052). A wallet beyond the 10th would be silently unsubscribed rather than rejected.",
 "ORD-001": "Core has four exchange.order() call sites (L2726, L2843, L3350, L3379) behind one gate (L4036). ARCH requires one physical order site; the repair must reconcile this.",
 "ORD-003": "Core: DEFAULT_MIN_NOTIONAL = env HL_LIVE_MIN_NOTIONAL, default 10 (L138); global min_notional read at L1926; the minimum check at L2439 covers ENTRY/ADD only.",
 "UI-WALLET-014": "Core: wallet_gate.json is reloaded each cycle (L6049); CLOSE_ONLY maps to CLO (L1909) and CLO blocks ENTRY/ADD (L2428).",
 "NET-001": "Core: info, WS and exchange URLs come from env HL_INFO_URL, HL_LIVE_WS_URL and HL_LIVE_ORDER_ENDPOINT (L132-134), defaulting to mainnet. One HL_INFO_URL serves both leader and follower reads, so there is no per-side split.",
 "NET-003": "Core: one HL_INFO_URL (L132) is used for leader and follower reads; pointing it at testnet would also move leader reads off mainnet.",
 "TN-F01": "Core: copy scale falls back to leader_equity_base 10,000 when unset (L2419) and norm_base falls back to fixed_notional (L2418).",
 "ENG-VAL-01": "Core: max(1.0, fnum(wc.get('leader_equity_base'), 10000.0)) at L2419.",
 "ENG-003": "Core: fixed_notional() at L1922 is the proven fixed-notional-per-fill defect site.",
}
for r in R:
    legacy = [x for x in r["sources"] if "HL_Live_Copy_Service.py" in x]
    if legacy:
        r["sources"] = [x.replace("HL_Live_Copy_Service.py", "legacy HL_Live_Copy_Service.py") for x in r["sources"]]
        r["notes"] = r["notes"].replace("HL_Live_Copy_Service.py", "legacy HL_Live_Copy_Service.py")
    if r["id"] in CORE_NOTES:
        r["sources"].append(CORE)
        r["notes"] = (CORE_NOTES[r["id"]] + " Code-read of the 2 Jun backup, unconfirmed by run; PRs #4/#6/#7 (merged at main 114e8b4) changed this code, so re-check there." + (" Earlier note (legacy file, superseded base): " + r["notes"] if r["notes"] else "")).strip()
    elif legacy:
        r["notes"] = (r["notes"] + " Source refs are to the legacy file; re-derive against " + CORE + ".").strip()

# Rulings recorded after drafting (Boss, 2026-10-09T13:26Z, implemented in PR #6). A ruled OD is removed from
# open_decisions; a record whose only blocker was a ruled OD becomes APPLIES. Values go in the record notes.
RULED_OD01 = "OD-01 ruled (Boss, 2026-10-09): OPEN/INCREASE/FLIP are priced from a fresh follower-market mid at most 5 s old; with no fresh mid no order is sent."
RULED_SLIP = "Slippage ruled (Boss, 2026-10-09): unset marketable slippage defaults to 0.2%."
for r in R:
    if "OD-01" in r["open_decisions"]:
        r["open_decisions"].remove("OD-01")
        r["notes"] = (r["notes"] + " " + RULED_OD01).strip()
    if r["id"] in ("PRICE-007", "RISK-005"):
        if "OD-10" in r["open_decisions"]:
            r["open_decisions"].remove("OD-10")
        r["notes"] = (r["notes"] + " " + RULED_SLIP).strip()
    if r["applicability"] == "OPEN_DECISION" and not r["open_decisions"]:
        r["applicability"] = "APPLIES"
    if r["id"] in ("PRICE-001", "PRICE-006", "PRICE-007", "RISK-005"):
        r["sources"].append("Boss decision, Network switch thread 2026-10-09T13:26Z")

# Testnet run 3 (2026-10-09, main @ ab7f2b0) findings and Boss's netting ruling (card, 2026-10-09T15:46Z).
RUN3 = "RUN3_FINDINGS.md (testnet run 3, 2026-10-09, project files)"
BOSS_NET = "Boss decision card 2026-10-09T15:46Z (opposite-direction leaders)"
rec("ENG-018", "ENGINE", "Leaders trading opposite ways in one coin",
    "The follower account holds one net position per coin, as the exchange does. When leaders trade opposite ways in the same coin, opposite entries are copied (not skipped) and net on the account; the engine's ledger follows the exchange's net position, while per-leader attribution is kept and shown on screen so each leader's sleeve and PnL stay visible.",
    [BOSS_NET, RUN3 + " F3 (0x7717 STABLE long flattened by 0x7019 short)"], "APPLIES", [],
    proof="Two real mainnet leaders take opposite entries in one coin during a testnet run; capture both sends, the exchange net position, the ledger net and the per-leader sleeves shown in the UI",
    oracle="Testnet clearinghouseState net size per coin vs the sum of the engine's per-leader sleeves; leader fills from the mainnet info API",
    neg=["opposite entries of equal size -> account flat, both sleeves shown", "one leader exits after netting -> exit sized from its own sleeve, account net correct",
         "restart while netted -> attribution restored, no new orders", "ledger net vs exchange net differs -> diff shown and sending stops (SET-009)"],
    notes="Replaces the run 3 question 'block opposite entries or net'. Interplay with leftover inventory: ENG-016.")
rec("ENG-019", "ENGINE", "Main loop keeps up with 10 very busy leaders",
    "With the 10 most active leaders followed, every engine cycle finishes within its budget: duplicate leader fills are de-duplicated before re-processing, and the copy-account poll runs every cycle and is never starved by leader polling.",
    [RUN3 + " F1 (4 cycles in ~3 min, each budget_exceeded; 2,908 duplicate leader fills)"], "APPLIES", [],
    proof="Run against the 10 most active mainnet leaders for at least 30 minutes on testnet; log cycle durations, poll timestamps and duplicate-fill counts",
    oracle="Cycle and poll timestamps from the engine log compared with wall clock; follower fills from the testnet info API vs ledger rows",
    neg=["burst of thousands of historical fills on start-up", "one leader with very high fill rate", "slow info API responses", "429 rate limiting"])
rec("ORD-010", "ORDER", "Leader-to-send delay measured; stale entries take the missed-entry path",
    "For every copy order the delay from the leader's trade to our send is measured and recorded. An ENTRY/ADD whose leader trade is more than 30 s old when it reaches the sender is not sent as a normal copy; it goes through the missed-entry rule (ENG-017). Exits are never dropped for age.",
    [RUN3 + " F2 (one send worker, ~3.5 s per order; delay grew from 7 s to 81 s)"], "APPLIES", ["OD-10"],
    proof="Testnet run with busy leaders: per-order leader time, send time and decision captured; an artificially delayed queue shows entries older than 30 s routed to ENG-017",
    oracle="Leader fill timestamps from the mainnet info API vs testnet order timestamps",
    neg=["entry at 29 s -> normal copy", "entry at 31 s -> missed-entry rule", "exit at 120 s -> still sent", "queue backlog of 50 orders -> delays stay recorded, no unbounded growth"],
    notes="The 30 s threshold came from the engine thread's run 3 follow-up; confirm it with Boss alongside the OD-10 tolerance.")
rec("SET-009", "SETTLE", "Ledger never diverges from the exchange",
    "Every follower fill on the exchange reaches the engine ledger; the ledger's net position per coin always matches the exchange. Any unexplained difference stops new sends and is shown as a Critical diff until resolved.",
    [RUN3 + " F1 (25 fills on exchange, 4 in live_fills.csv; 20 positions the engine thought flat)"], "APPLIES", [],
    proof="After each testnet run, compare exchange fills/positions with ledger rows and net positions; induce a missed copy-account poll and confirm sending stops",
    oracle="Testnet userFillsByTime and clearinghouseState (all DEX scopes) read without engine code",
    neg=["copy-account poll delayed", "fill arrives after restart", "partial fills", "exit refused because ledger thought flat (run 3) must not recur"])

# OD-21 decided (Boss, 2026-10-09T15:07Z): the certified UI is the 13 May "Live Copy Command Centre" file
# (source sha256 fad19d22..., 7,243 lines; repo branch claude/restore-live-screen-0513 @ 38776e0, byte-exact). The previously
# tracked HL_Copy_App_SSOT.py (sha256 c0f9e508...) had the Command Centre markup but no /live-copy route; it was the
# walletproof modelling screen. Records derived from it are re-checked against the 13 May file: an element still
# present is re-pointed; an element absent is SUPERSEDED. Evidence gathered against the old file is void.
UI0513_NAME = "HL_Copy_App_SSOT.py (13 May, sha256 fad19d22)"
UI0513 = Path(SRC, B3, "HL_Copy_App_SSOT_20260513.py").read_text(encoding="utf-8", errors="replace")
for r in R:
    old = [x for x in r["sources"] if x.startswith("HL_Copy_App_SSOT.py") or x.startswith("SSOT ")]
    if not old:
        continue
    syms = set()
    for x in old:
        for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", x.replace("HL_Copy_App_SSOT.py", "")):
            syms.add(tok)
    code_syms = {t for t in syms if ("_" in t or any(c.isupper() for c in t[1:])) and t not in ("Add-wallet",)}
    present = [t for t in code_syms if t in UI0513]
    r["sources"] = [x.replace("HL_Copy_App_SSOT.py", UI0513_NAME) if x in old else x for x in r["sources"]]
    if code_syms and not present:
        r["applicability"] = "SUPERSEDED"
        r["notes"] = (r["notes"] + f" OD-21 decided: element(s) {sorted(code_syms)} not found in the certified 13 May UI; requirement void.").strip()
        if r["id"].startswith("UI-LCC-POS"):
            r["notes"] += " The 13 May positions tab splits OWNED COPY and ACCOUNT-LEVEL rows; its fields are certified by the UI-FP 'Real User Copy Positions' records."
        if r["id"].startswith("UI-SSOT-"):
            r["notes"] += " The 13 May modelling page is render_home (route /, /model); its labelling is OD-18."
    else:
        r["notes"] = (r["notes"] + " OD-21 decided: re-pointed to the certified 13 May UI.").strip()
    if "OD-21" in r["open_decisions"]:
        r["open_decisions"].remove("OD-21")
    if r["prior_evidence"] and "test_g4" in r["prior_evidence"]:
        r["notes"] = (r["notes"] + " Prior evidence void: '" + r["prior_evidence"] + "' ran against the superseded UI file.").strip()
        r["prior_evidence"] = ""
for r in R:
    if r["id"].startswith("UI-FP-"):
        if "OD-21" in r["open_decisions"]:
            r["open_decisions"].remove("OD-21")
        loc = r["feature"].split(":")[0]
        r["notes"] = (r["notes"] + " OD-21 decided: certify against the 13 May UI. Elements named only in the 11 May proof (lcCoreChip, lcWsChip, lcStatsBanner, ACCOUNT-LEVEL ORPHAN section) are absent from the 13 May file; the field must be found by its data, not its element id.").strip()
# Fixing diffs from the UI is not required (Boss, 2026-10-09T15:07Z); diffs must be reported.
for r in R:
    if r["id"] == "UI-LCC-REC-11":
        r["applicability"] = "SUPERSEDED"
        r["notes"] = (r["notes"] + " Not required: Boss reconciles diffs on the exchange; the UI must report them (UI-DIFF-01). If the button stays it must work or be labelled inactive.").strip()
    if r["id"] == "TN-F13":
        r["applicability"] = "ADAPTED_PROPOSED"
        r["notes"] = (r["notes"] + " Boss's missed-entry rule (ENG-017) replaces 'outside tolerance sends nothing' with: report a diff and rest a limit order at the desired price.").strip()
BOSS_MISSED = "Boss, project chat 2026-10-09T15:07Z (missed-entry methodology)"
rec("ENG-017", "ENGINE", "Missed leader entry or add",
    "When a genuine leader ENTRY/ADD was missed (connection gap, rejected or unfilled order) and is recovered from the leader's fills: if the follower can enter now at the leader's price or better, or within tolerance, the engine takes the entry; otherwise it records a diff that is shown in the UI and places a resting limit order at the desired price until it fills or the leader's lineage makes it obsolete.",
    [BOSS_MISSED, "HL_Live_Copy_Service_Core.py MISSED_ENTRY/MISSED_ADD states and ENTRY_ADD_RECOVERY_RESTING", "PRODUCT_SEMANTICS B1 (recovered genuine fills keep authority)"],
    "APPLIES", ["OD-10"],
    proof="Induce a gap on testnet (stop WS/poll) across a real mainnet leader entry; resume; capture recovered fill -> decision (take/diff) -> order payload -> exchange",
    oracle="Leader fill price and time (mainnet info API) vs follower mid at resume and the follower's orders/fills (testnet info API), read without engine code",
    neg=["price same as leader -> entry taken", "price better -> entry taken", "price worse but within tolerance -> entry taken",
         "price worse beyond tolerance -> diff shown + limit at desired price, no marketable order",
         "resting limit later fills -> diff clears, position owned exactly once",
         "leader reduces/closes before the limit fills -> limit cancelled or resized, no orphan exposure",
         "restart while the limit rests -> no duplicate limit, diff still shown",
         "missed ADD (not just ENTRY) follows the same rule",
         "no fresh mid -> no order (OD-01 ruling)",
         "leftover inventory in the same coin is never touched (ENG-016)"],
    notes="Tolerance value and the exact 'desired price' (taken here as the leader's entry price) need confirming; the bound is part of OD-10. This rule replaces Build 4 F13's 'send nothing outside tolerance' for this product.")
rec("UI-DIFF-01", "UI", "Diffs are reported in the live UI",
    "Every diff (missed entry outside tolerance, position mismatch, resting recovery limit, ledger vs exchange difference) is visible in the Live Copy Command Centre with wallet, coin, size, desired vs current price and age, until it clears. Fixing it from the UI is not required.",
    [BOSS_MISSED, UI0513_NAME + " /live-copy Reconciliation tab"], "APPLIES", [],
    neg=["diff created while UI open -> appears on next refresh", "diff clears -> disappears", "restart -> diff still shown", "multi-DEX coin -> namespaced correctly"])
routes = re.findall(r'@app\.(get|post)\("([^"]+)"', UI0513)
for i, (m, path) in enumerate(routes, 1):
    rec(f"UI-ROUTE-{i:02d}", "UI", f"Endpoint {m.upper()} {path}",
        "Responds as its page/control expects; a write persists to the file the running engine reads and the engine applies it without restart; a read returns engine/exchange truth or an explicit unavailable state. An endpoint with no caller in the live UI is listed and either removed or proven harmless.",
        [UI0513_NAME + f" route {path}"], "APPLIES", [],
        neg=["malformed body", "missing config file", "engine not running", "concurrent write"])

# ---------------------------------------------------------------------------
ids = [r["id"] for r in R]
dups = {i for i in ids if ids.count(i) > 1}
assert not dups, dups
OUT.mkdir(parents=True, exist_ok=True)
srcs = {}
for p in sorted(SRC.rglob("*")):
    if p.is_file():
        srcs[str(p.relative_to(SRC))] = hashlib.sha256(p.read_bytes()).hexdigest()
doc = {"schema": "hl_certification_matrix_v1", "generated_by": "certification/gen_matrix.py",
       "result_values": ["NOT_TESTED", "PASS", "FAIL", "BLOCKED"],
       "applicability_values": {"APPLIES": "binding; explicit in Build 3 documents or an exact equivalent is cited",
                                "APPLIES_PROPOSED": "inherited, no conflict found; Controller confirms",
                                "ADAPTED_PROPOSED": "intent applies, Build 4 mechanism does not; Controller confirms",
                                "SUPERSEDED": "explicitly superseded by a cited later document",
                                "OPEN_DECISION": "the requirement itself depends on an unruled decision; cannot be certified until ruled"},
       "open_decisions_field": "decisions that affect the record; on an APPLIES record they constrain how it is tested, not whether it applies",
       "source_sha256": srcs, "records": R}
(OUT / "certification_matrix.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
with open(OUT / "certification_matrix.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
    for r in R:
        w.writerow({k: (" | ".join(v) if isinstance(v, list) else v) for k, v in r.items()})
# Open-decisions register: machine-readable copy of contract §6 (the Markdown table is the source).
md = (OUT / "MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md").read_text()
reg = md.split("## 6. Open decisions register")[1].split("\n## 7.")[0]
ods = []
for line in reg.splitlines():
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    m = re.fullmatch(r"\**(OD-\d+)\**", c[0]) if len(c) == 5 else None
    if m:
        ods.append(dict(id=m.group(1), decision=c[1].replace("**", ""), evidence=c[2], owner=c[3], records_affected=c[4],
                        matrix_records=[r["id"] for r in R if m.group(1) in r["open_decisions"]]))
(OUT / "open_decisions.json").write_text(json.dumps({"schema": "hl_open_decisions_v1", "source": "MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md §6", "decisions": ods}, indent=1, ensure_ascii=False) + "\n")
print(len(ods), "open decisions")
from collections import Counter
print(len(R), Counter(r["area"] for r in R), Counter(r["applicability"] for r in R))
print(Counter(o for r in R for o in r["open_decisions"]))
