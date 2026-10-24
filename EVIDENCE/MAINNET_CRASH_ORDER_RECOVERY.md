# Mainnet crash and ambiguous-send recovery

This procedure supports reconciliation only. It is not approval to start or resume mainnet sending; all separate product and controller gates still apply.

## After a crash or uncertain send

1. Keep new exposure-increasing sends held under the existing authorized control process. Do not edit `CONTROL_STATE.json` as part of this procedure. Do not resend, cancel, or reprice during discovery.
2. Record the incident time, process identity, build SHA, state directory, and relevant audit-file row counts. Preserve audit and fallback files unchanged.
3. For each pending or ambiguous attempt, use its durable attempt record to obtain the exact client order ID (CLOID). Check the fallback spill as well as the live audit before classifying it. Do not infer ownership from coin, side, size, or timestamp.
4. An authorized operator performs a **read-only lookup for each exact CLOID** against the mainnet order-status endpoint. Record the lookup time and returned status. Do not query positions or enumerate account orders for this procedure.
5. If no match or an ambiguous response is returned, keep the attempt held and repeat the same read-only CLOID lookup after the venue's visibility delay. Do not blindly retry a send.
6. Match only an exact CLOID. Reconcile any reported fills and terminal status to the attempt. A resting order remains an identified open order for manual disposition. If the response is missing, conflicting, or identifies an order that cannot be matched to a durable attempt, leave it untouched and escalate for human disposition. **Never cancel or modify an unknown order.**
7. Resume sending only after every ambiguous attempt has a documented disposition, fallback rows have replayed successfully, and the required operator/controller authorization is recorded. Any new send is a separate authorized action after reconciliation.

The assistant does not access mainnet accounts, orders, or credentials. The operator uses their approved, read-only access for the CLOID lookups.

## Wallet-roster changes

Treat the wallet roster as fixed for a running process. Apply roster changes only through an authorized clean stop and subsequent launch with the reviewed configuration; do not assume live edits reload in the active process. Record the reviewed configuration identity with the new run.
