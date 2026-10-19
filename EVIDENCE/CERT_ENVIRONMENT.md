
## :8031 serving-process binding (2026-10-19)

UI certification requires binding a capture to what the process actually serves. For the live Command Centre:

| field | value |
|---|---|
| PID | 41124 (`pythonw.exe`) |
| process start | 2026-10-18T23:15:14+01:00 |
| command line | `...\Python311\pythonw.exe HL_Copy_App_SSOT.py` (relative path — cwd matters) |
| working dir | `C:\Users\wigmore\trading_stack\hl-build3-testnet-cert\_archive\hl_stage2` |
| launch source | `C:/Users/wigmore/trading_stack/_tools/launch_8031_live.txt` |
| audit dir | `...\_archive\hl_stage2\hl_live_copy_audit_testnet` |
| **source commit** | **none — that directory is NOT a git repository** |
| script sha256 | `b45ff9af2182944a1fabd98b6369d0ad7dd7d215062abec3bdc20dfd75e9e7c2` |
| script mtime | 2026-10-18 21:19:57 +0100 (predates process start — consistent) |

**Because there is no git repo, bind by content hash, not commit.** Record:

```
serving_binding_type  = content_sha256
serving_script_sha256 = <sha256 of the served HL_Copy_App_SSOT.py>
serving_pid           = 41124
serving_process_start = 2026-10-18T23:15:14+01:00
source_commit         = null
```

Re-verify the hash at test time — if it has changed, the process was restarted and the capture must be re-taken.
Do not ask for a commit that cannot exist, and do not invent one.

## The matrix's UI source EXISTS — located 2026-10-19

The matrix declares `source_sha256["hyperliquid-build3-repair/HL_Copy_App_SSOT_20260513.py"] =
fad19d220d7af13d48a3eec664c56a32b31624d671b00e2f80ec2dc9062a29b0`, referenced by 254 rows. No file in the git repo
matched it, which blocked UI certification.

**It was not missing — it is on disk, outside version control:**

| field | value |
|---|---|
| path | `C:\Users\wigmore\trading_stack\build3-live-screen-0513-view\hl_stage2\HL_Copy_App_SSOT.py` |
| sha256 | `fad19d220d7af13d48a3eec664c56a32b31624d671b00e2f80ec2dc9062a29b0` — **exact match to the matrix** |
| mtime | 2026-05-13 08:18:03 (matches the "13 May" label) |
| git | **not a repository** |
| sibling | `ui_8023.log` — this tree was served on port 8023 |

## Three distinct files, do not conflate them

```
fad19d22…  build3-live-screen-0513-view/hl_stage2/            <- what the REGISTER certifies
4574ca72…  hyperliquid-build3-repair/_archive/hl_stage2/      <- what the REPO holds
b45ff9af…  hl-build3-testnet-cert/_archive/hl_stage2/         <- what :8031 ACTUALLY SERVES
```

**Consequence:** a capture of the live `:8031` page certifies the app that is running (`b45ff9af`), not the source the
register names (`fad19d22`). To certify UI rows against the register, the app must be started from
`build3-live-screen-0513-view` — or the register's `source_sha256` must be corrected to the file actually served.

Until one of those happens, no UI row can be bound to its declared source. Do not certify against `:8031` as-is and
call it a register row.

## :8032 isolated instance (found running 2026-10-19)

A second, isolated Command Centre instance exists. It is the fixture the control-write cards required.

| field | value |
|---|---|
| endpoint | `http://127.0.0.1:8032` |
| PID | 30580 |
| command | `python -m uvicorn HL_Copy_App_SSOT:app --host 127.0.0.1 --port 8032` |
| started | 2026-10-18T19:43:11+01:00 |
| workspace | `C:\Users\wigmore\trading_stack\hl-build3-testnet-cert-8032\_archive\hl_stage2` |
| served source sha256 | `658ec8e31eb96d70…` — **different** from live `:8031`'s `b45ff9af2182944a…` |
| controls | `/api/global-controls` returns `{"ok":true,...}` with all limits `0.0` (fresh state) |

**Isolation evidence:** separate workspace tree, different served source hash, zeroed controls. Control-write tests
run against this instance, never against `:8031`.

**Every control test must record the live config's sha256 before and after.** If it changes, the test mutated live
configuration and that is a defect, not a pass.

## :8031 route change and restart (2026-10-19 08:34)

The UI route moved to the root. **`/live-copy` now returns HTTP 404 — do not use it.**

| path | status |
|---|---|
| `/` | **200 — serves "HL Copy Engine SSOT" (full HTML + styles)** |
| `/live-copy`, `/live-copy/`, `/live_copy`, `/livecopy`, `/dashboard`, `/panel`, `/copy`, `/api/live-copy`, `/api/wallets`, `/wallets` | 404 |
| `/api/global-controls` | 200 |

The serving process **restarted at 2026-10-19T08:34:35+01:00**, PID 41124 → **26336**. Served source hash unchanged
(`b45ff9af2182944a…`), file mtime 2026-10-18 21:19:57 — the file predates the process start, so the process rule holds.

**Any UI capture made before 08:34 is stale.** Record the PID and start time with every capture, and request `/`,
not `/live-copy`.

## UI source binding — RESOLVED 2026-10-19 (controller ruling + independent confirmation)

**Content-hash binding is the standard.** Two live surfaces, two different sources, both legitimate for different rows:

| | **:8023** | **:8031** |
|---|---|---|
| title | `Live Copy Dashboard` | `HL Copy Engine SSOT` |
| PID | 15760 (started 08:40:25 +01:00) | 26336 (restarted 08:34:35 +01:00) |
| served sha256 | **`fad19d220d7af13d…`** | `b45ff9af2182944a…` |
| source path | `trading_stack/build3-live-screen-0513-view/hl_stage2/HL_Copy_App_SSOT.py` | `trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/HL_Copy_App_SSOT.py` |
| command | `python -m uvicorn HL_Copy_App_SSOT:app --host 127.0.0.1 --port 8023` | `HL_Copy_App_SSOT.py` |
| `/live-copy` | **200** | **404** (route moved to `/`) |

**`:8023` serves `fad19d22…` — the exact hash the register declares in `source_sha256` and cites in 254 rows.** Verified by
hashing both candidate files, not by trusting the port.

### Rules for every UI row

1. **Bind to the surface that actually serves the source the row names.** Rows declaring `fad19d22…` test against
   **`:8023`** (PID 15760). Rows testing the archived copy test against **`:8031`** (PID 26336, `/`, not `/live-copy`).
2. Record **all four** with every capture: served sha256, PID, process start time, config path.
3. **Do NOT start `:8031` from the 13 May tree** — it would change what a live surface serves.
4. **Do NOT rewrite the 254 citations wholesale.** Re-label only rows whose cited hash differs from what they were
   actually tested against — those are the mislabelled ones.
5. Any capture taken before the 08:34 restart is stale. Re-capture.

A 404 from `/live-copy` on `:8031` is a moved route, not missing evidence.

## Register regeneration: missing inputs (recorded so no card rediscovers it)

`certification/gen_matrix.py` line 11:

    SRC = Path(os.environ.get("HL_CERT_SOURCE_DOCS", "/mnt/project-files/source-docs"))

It reads four documents from a `source-docs` tree that mirrors the repos. On this host:

| input | status |
|---|---|
| `hyperliquid-build3-repair/PRODUCT_SEMANTICS.md` | present |
| `richard-mission-control-template/INVARIANTS.md` | present |
| `hyperliquid-build4/GUT_CONTRACT.md` | **MISSING** |
| `hyperliquid-build4/FAILURES.md` | **MISSING** |

**No `source-docs` directory exists anywhere on this box.** The mirror was never reconstructed for this environment.

### CORRECTION — the six `GUT_CONTRACT.md` copies are identical, not divergent

I reported earlier that six candidate copies existed **with different hashes**. That was wrong. All six hash to
**`71dffee1932040ef`**:

    b4-hotfix-standalone  b4-verify-clean  b4_11r266
    b4_epoch_candidate_20261007  b4_hotfix_clone  b4_kpepe_clean_20261007

So there is no version ambiguity for that file. `FAILURES.md` is still absent everywhere and its version is unestablished.
Which copy is authoritative remains a decision for whoever built the register — do not guess.

### The overlay cannot change a verdict

`certification/results/apply_verified_results.py` assigns verdicts from a **hardcoded dict**, not from the evidence JSON.
Line 94, on every ref including the cert branch:

    "ENG-INV-02": ("PASS", E11, "2026-10-14T09:05:00Z", P11),

The only `json.load` in the script (line 731) reads `certification_matrix.json` itself; no result file sets a row
verdict. Therefore **no row verdict can be changed by running the overlay** — it can only re-apply the verdicts
already written into it. Changing ENG-INV-02 to FAIL requires editing that file, which is expressly prohibited.

Combined with `gen_matrix.py` being unrunnable, the register is **frozen for corrections** on this host: it can be
published as-is, but it cannot be rebuilt and its verdicts cannot be revised.

## The six hashes, with provenance (ruling item 4, 2026-10-19)

Every distinct state of `HL_Copy_App_SSOT.py` found on this host, and where each comes from. **`c0f9e508` resolves to
no file, so no row may rely on it.**

| hash | provenance | resolves to a file? |
|---|---|---|
| `fad19d22…` | `trading_stack/build3-live-screen-0513-view/hl_stage2/HL_Copy_App_SSOT.py` — the 13 May tree, never committed; **served by `:8023` (PID 15760)** | **yes**, on disk |
| `658ec8e3…` | the file **at `tested_commit 89b3bc7`**, `_archive/hl_stage2/HL_Copy_App_SSOT.py` | yes, via git |
| `c0f9e508…` | **declared by the cert-branch register** (`cert/local-main-b142cf8`) | **NO — matches nothing on this box** |
| `7468ab51…` | the file at the cert branch's **own HEAD**, `_archive/hl_stage2/` | yes, via git |
| `4574ca72…` | the file at **`origin/main`**, `_archive/hl_stage2/` | yes, via git |
| `b45ff9af…` | `trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/` — **served by `:8031` (PID 26336)** | **yes**, on disk |

Also observed, current working tree: `bb7b9cc3…` (`_archive/hl_stage2/HL_Copy_App_SSOT.py`).

### Binding rules (ruling items 3 and 5)

- **UI rows bind to the content hash actually served at capture time**: `b45ff9af` on `:8031 `/``, `fad19d22` on
  `:8023 /live-copy`.
- **Do not reconcile old rows against `89b3bc7` or the `658ec8e3` file** — neither is the served surface, and captures
  taken before the 08:34:35 restart are stale.
- **The register of record is `origin/main` (832 rows).** The 790-row cert branch is evidence only.
- **A results merge never changes `source_sha256`.** Any change to the source declaration is its own commit, with its
  own review and a stated reason.

## Why `origin/main` reads as all NOT_TESTED — the overlay is not on it

Verified 2026-10-19:

| ref | `certification/results/apply_verified_results.py` |
|---|---|
| `origin/main` (819050c, 832 rows) | **ABSENT** |
| `origin/cert/local-main-b142cf8` (790 rows) | PRESENT |
| local `HEAD` / `main` (47b898f, 790 rows) | PRESENT |
| `oc/ledger-fix-v2` | ABSENT |
| `hermes/t_23fc77ee` | ABSENT |

**`origin/main` is raw `gen_matrix.py` output with no overlay applied.** That is why it shows PASS 4 / FAIL 2 /
NOT_TESTED 826: those are the generator's own defaults, not a certification result. The 579 PASS exist only where the
overlay has been run — the cert branch.

### Consequences

1. **Overlay verdicts are literals in that file.** They are not read from result files; `run` cannot change one, only
   `edit` can. The controller authorised a reviewed one-line edit for ENG-INV-02 (comment `6263261285`).
2. **Any overlay edit must branch from `origin/cert/local-main-b142cf8`**, because that is the only ref carrying the file.
3. **A merge to `main` must include the overlay itself**, or the published register will revert to all-NOT_TESTED the
   moment it is regenerated. This is a structural part of the merge, not a detail.
4. Rows can only be corrected through reviewed edits to that file — there is no data-driven path.

### Evidence check

All 18 verdict literals in the overlay reference an evidence file that **exists in the working tree**. No orphan
literals found in that file at this time.
