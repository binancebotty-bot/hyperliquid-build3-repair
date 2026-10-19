# The runtime-bound rows: 191 that need only evidence, plus 40 that also need a ruling

Generated from `origin/main` (832 rows, the register of record). These rows are **NOT_TESTED** and
**cannot be closed by a worker card**: their `execution_proof` or `independent_oracle` requires executed,
live or testnet evidence. Codex's soak and verifier outputs are the evidence source for them.

The other two buckets, for contrast: rows blocked by an **open decision** (221) wait on a ruling; rows
settleable by **static analysis** (414) are being worked by worker cards.

## The strict partition (the counts must add up)

| bucket | rows |
|---|---:|
| blocked by an **open decision** (some also need runtime evidence) | 221 |
| needs **runtime evidence**, no decision blocking it | 191 |
| settlable by **static analysis** | 414 |
| **total NOT_TESTED** | **826** |

Of the 221 decision-blocked rows, **40 also need runtime evidence** — so they need the ruling *and* the soak output before they can move. An earlier message quoted 231/221/414 as if they summed to 826; they do not, because they overlap by these 40. This file uses a strict partition.

`runtime_any` (patterns match, decision or not) = **231**. That is the group Codex's soak/verifier outputs feed; the 40 with a decision outstanding also need the ruling first.

| area | rows |
|---|---:|
| REGRESSION | 134 |
| ENGINE | 33 |
| WALLET | 14 |
| SETTLE | 6 |
| RISK | 2 |
| LIFECYCLE | 1 |
| UI | 1 |
| **total** | **191** |

## REGRESSION — 134 rows

| rows | what the proof requires |
|---|---|
| B4-I01, B4-I02, B4-I03, B4-I04, B4-I05, B4-I06, B4-I07, B4-I08, B4-I09, B4-I10, B4-I11, B4-I14, B4-I15, B4-I16 … | Reproduce the historical trigger condition on testnet or recorded replay -> assert the failure cannot occur |

## ENGINE — 33 rows

| rows | what the proof requires |
|---|---|
| ENG-INV-07, ENG-INV-08, ENG-INV-09, ENG-INV-10, ENG-INV-11, ENG-INV-12, ENG-INV-13, ENG-INV-14, ENG-SEM-B1, ENG-SEM-B2, ENG-SEM-B3, ENG-SEM-B4, ENG-001, ENG-002 … | Leader event (testnet-observable) -> desired net per coin -> planner delta -> single sender -> testnet order -> MASTER fill/position |
| TN-F04, TN-F17 | Predeclared Phase 6T-style scenario on testnet through the production engine path only (no direct exchange.order); evidence per class with exchange pa |
| ENG-018 | Two real mainnet leaders take opposite entries in one coin during a testnet run; capture both sends, the exchange net position, the ledger net and the |
| ENG-019 | Run against the 10 most active mainnet leaders for at least 30 minutes on testnet; log cycle durations, poll timestamps and duplicate-fill counts |

## WALLET — 14 rows

| rows | what the proof requires |
|---|---|
| UI-WALLET-001, UI-WALLET-003, UI-WALLET-005, UI-WALLET-007, UI-WALLET-009, UI-WALLET-010, UI-WALLET-011, UI-WALLET-012, UI-WALLET-013, UI-WALLET-016, UI-WALLET-017, UI-WALLET-018, UI-WALLET-019 | UI action -> live_config.json / wallet_gate.json write -> running engine reads it (no restart) -> testnet behaviour |
| UI-WALLET-004 | UI action -> config -> running engine -> testnet behaviour |

## SETTLE — 6 rows

| rows | what the proof requires |
|---|---|
| TN-F09, TN-F10, TN-F11, TN-F12, TN-F18 | Predeclared Phase 6T-style scenario on testnet through the production engine path only (no direct exchange.order); evidence per class with exchange pa |
| SET-009 | After each testnet run, compare exchange fills/positions with ledger rows and net positions; induce a missed copy-account poll and confirm sending sto |

## RISK — 2 rows

| rows | what the proof requires |
|---|---|
| TN-F16, TN-F21 | Predeclared Phase 6T-style scenario on testnet through the production engine path only (no direct exchange.order); evidence per class with exchange pa |

## LIFECYCLE — 1 rows

| rows | what the proof requires |
|---|---|
| TN-F19 | Predeclared Phase 6T-style scenario on testnet through the production engine path only (no direct exchange.order); evidence per class with exchange pa |

## UI — 1 rows

| rows | what the proof requires |
|---|---|
| TN-F23 | Predeclared Phase 6T-style scenario on testnet through the production engine path only (no direct exchange.order); evidence per class with exchange pa |

## Note for whoever supplies the evidence

A row is only earned by evidence bound to **that row's** proof. A soak or verifier run that exercises
the engine generally is not row-bound evidence; the artifact must let a reader answer "did *this* row's
assertion hold" without re-running the whole thing. Where an aggregate run does cover a row, cite the
specific check inside it.

---

## CORRECTION (2026-10-19) — "runtime-bound" did not mean "not testable"

This file groups 191 rows whose proof text mentions executed / live / testnet / runtime evidence, and the intake cards
that hit them returned NOT_TESTED on the grounds that no such evidence exists in a clone. **That reasoning conflates two
different things**, and the skill `certification-row-bound-reearn` documents the seam that closes the gap:

*Needing runtime behaviour* is not the same as *needing a running engine*. `HL_Live_Copy_Service_Core` can be imported
and driven **in-process**:

    sys.path.insert(0, str(CORE.parent))
    os.environ.update({"HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(), "HL_LIVE_ENV_FILE": "nonexistent",
                       "HL_LIVE_MOCK_SEND": "0"})
    import HL_Live_Copy_Service_Core as c
    c.follower_mid = lambda coin: 100.0        # pin the price so assertions are exact

with a stubbed exchange. That exercises risk caps, send gates and decision branches without a live engine, a testnet
credential or a soak run.

### What this changes

Rows whose proof is a **decision-branch / cap / gate assertion** are testable offline by a worker card. Rows whose proof
is genuinely an **exchange-side outcome** (a fill, a tx hash, exchange/userFills parity) are not — those still need
Codex's soak and verifier output.

So the 191 is not one bucket. It splits again, and **the split must be measured per row against the row's own
`execution_proof`, not inferred from keyword matches.** This file's grouping is a starting point, not a verdict on
testability.

### The method that earns a row

A row is only earned when the check **would fail for a different row**. The skill's shape:

- **ACTIVE** — config that trips this row's control; expect this row's exact (decision, reason) tuple.
- **CONTROL** — identical except this row's own control value is neutralised; expect ENTRY_ALLOWED / ''.

Assert both. Name every check after its row. That pairing is what makes the evidence row-bound rather than generic — the
defect that got the earlier batches rejected.
