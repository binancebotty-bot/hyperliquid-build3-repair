# B3-CERT t_a78e24ee - UI-FP corrective, 6 rows re-labelled against the SERVING build

**Corrective of `t_ab0d0f07`**, which review `t_2016d9f8` FAILED for a labelling violation: all six
rows said *"vs register b142cf88"* while the probes ran against `:8031`. The observations were sound;
the label was wrong, and a wrong label blocks certification.

Schema followed: `EVIDENCE/UI_CERT_ARTIFACT_SCHEMA.md` @ `aa3384f`.

## The serving build, measured (not copied)

| field | value |
|---|---|
| `serving_commit` | `6cf5dcf671b791e8f833060458f00cb7bb7bcdb5` |
| `serving_ssot_sha256` | `658ec8e31eb96d70acc15dc30860334c23612d2e3e9d19fb63ed9ec4e6fa86c2` |
| serving checkout | `C:/Users/wigmore/trading_stack/hl-build3-testnet-cert` |
| SSOT path | `<checkout>/_archive/hl_stage2/HL_Copy_App_SSOT.py` (492597 B, mtime 2026-10-16 23:42:46 +0100) |
| `git rev-parse HEAD` | `6cf5dcf6...` |
| worktree == HEAD for the SSOT? | **True** (disk sha256 == `git show HEAD:` blob sha256) |

How: `git -C <checkout> rev-parse HEAD`; `sha256sum <checkout>/_archive/hl_stage2/HL_Copy_App_SSOT.py`;
`git -C <checkout> show HEAD:_archive/hl_stage2/HL_Copy_App_SSOT.py | sha256sum`. Measured by the probe
itself and stored in the capture - the artifact is generated **from** the capture, so no value is typed by hand.

The identity is pinned at runtime too: the serving app reports its own state folder through
`/api/global-controls -> networks.state_dir` = `<checkout>/_archive/hl_stage2/hl_live_copy_audit_testnet`,
which is the folder the app actually reads. That makes "which build is this?" an observation, not an assumption.

## Verdicts (one per row, `row_id` key, per-row build binding)

| row_id | area | prior (register) | this card | basis |
|---|---|---|---|---|
| UI-FP-030 | Graph range controls | FAIL | **PASS** | lcGraphScale/Start/End render; scale buttons re-filter CLIENT-SIDE; label changes ALL -> 7D -> 1D; **zero non-GET requests** |
| UI-FP-041 | Lead-copy avg bps | FAIL | **PASS** | rendered "Avg bps: N" == served `live_leader_performance[wallet].avg_diff_bps`; 9 matched / 0 mismatched; 6 null-source rows render `n/a`, none render `0` |
| UI-FP-048 | Open pos | FAIL | **PASS** | rendered "Open pos: N" == served `open_position_count`; 15/15 exact, 0 mismatched |
| UI-FP-052 | Controls mode | FAIL | **PARTIAL** | `select[name=mode]` renders, options [LIVE,CLO,OFF], value == API 15/15; handler posts `/api/live-config/set-mode` + `/set-wallet` (declared in the serving source); execution-truth leg NOT TESTED under the read-only mandate |
| UI-FP-054 | Controls fixed notional | FAIL | **PARTIAL** | `input[name=fixed_notional]` renders, value == API 15/15; handler posts `/set-wallet`; execution-truth leg NOT TESTED |
| UI-FP-055 | Controls norm base | FAIL | **PARTIAL** | `input[name=norm_base]` renders, value == `/api/ui-state.norm_base` 15/15; handler posts `/set-wallet`; execution-truth leg NOT TESTED |

Tally: **3 PASS, 3 PARTIAL, 0 FAIL, 0 NOT_TESTED**. One verdict per row.

## Why the prior six FAILs were false reds

`certification/results/UI_CORRECTION_2d29211.json` reported `element not found` for all six cells
(`transfer`, `copy_model`, `hover`, `search`, `export`, `import`). Re-probed at element level, all six
render and bind to their declared source. The reds were bad selectors, not missing UI. This card does
**not** blanket-confirm them: it records the verdict the rendered DOM plus the served oracle supports,
and holds the three `execution truth: YES` rows at PARTIAL because the read-only mandate forbids the
mutation those legs need.

## Numbers that move

The graph label's point/fill counts are a **live growing series**. Three readings, all honest, all of
the same system at different moments:

- earlier attempt (`t_ab0d0f07`): `ALL 147 pts / 47193 fills`
- first run of this card's own probe: `ALL 182 pts / 49537 fills`
- second run of the **same script**, minutes later: `ALL 184 pts / 49800 fills`

The count moving between two runs of the same script is the proof that this is live data, not a
fixture. The reproducible facts are the **label change** across scales and the **absence of any write
request**; the verdict rests on those, not on a frozen count. A reviewer recomputing the counts gets
today's series - expected, and stated in the row rather than hidden. The artifact is generated from the
capture, so it carries whatever the latest run saw.

## Read-only

`read_only=true`, `engine_import=false`, `requests_non_get=[]`. No POST/Save to the live service; the
`:8031` process and Edge/CDP 9223 were not touched. No matrix edit - the overlay is the consolidation
owner's step.

## Reproduce

Two **distinct** reproductions, run in sequence by one command that **exits 0**:

- **Leg 1 - the probe** reproduces the live **observations**: a fresh GET-only DOM/API run. Its
  capture legitimately differs from the committed one, because the exchange graph is a live growing
  series (the README's own "numbers that move" section is the proof).
- **Leg 2 - the generator** reproduces the **published artifact** byte-identically, and only from the
  **frozen** capture. Hence the explicit `git checkout --` restore between the legs.

Run from the worktree root (one path segment only: the repo already **is** the worktree):

```
cd C:/Users/wigmore/hyperliquid-build3-repair/.worktrees/t_a78e24ee
export PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright
C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe EVIDENCE/ui_fp/scripts/probe_ui_fp_6rows_t_a78e24ee.py
git checkout -- EVIDENCE/ui_fp/raw/probe_t_a78e24ee_raw.json
C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe EVIDENCE/ui_fp/scripts/make_artifact_t_a78e24ee.py
```

This is the exact string published as `reproduce_all` in the artifact. The `git checkout --` restores
the frozen capture after the probe overwrites it; without that restore the generator's own
blob-equality guard **correctly** aborts (`RAW_DIGEST_MISMATCH` / `LIVE_DATA_DRIFT`) and the chain
exits 1. The abort is the guard working, not a defect - and the guard's message now names live-data
drift, not an EOL leak, when both sides have CR count 0.

To reproduce **only the published artifact** (no probe, from the committed capture):

```
cd C:/Users/wigmore/hyperliquid-build3-repair/.worktrees/t_a78e24ee
C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe EVIDENCE/ui_fp/scripts/make_artifact_t_a78e24ee.py
```

### Digest integrity (why the raw hash verifies against the commit)

`core.autocrlf=true` on this host rewrites LF to CRLF on checkout, so a digest taken from the
working-tree file would not match the committed blob. Two guards fix that:

1. `EVIDENCE/ui_fp/.gitattributes` pins `*.json` to `text eol=lf`, so the working tree and the
   blob are byte-identical for the captures.
2. `make_artifact_t_a78e24ee.py` computes each published `file_sha256` from the **committed blob**
   (`git cat-file blob HEAD:<path>`) and **aborts** if the on-disk raw capture disagrees with its blob.
   It also emits `raw_digest_verification` with both digests and `verified_disk_equals_blob`.

Verify a published digest against the commit, not the working tree:

```
git cat-file blob HEAD:EVIDENCE/ui_fp/raw/probe_t_a78e24ee_raw.json | sha256sum
```

The first command writes `raw/probe_t_a78e24ee_raw.json`; the second regenerates the artifact **from**
that capture. Every figure in the JSON is derived from the capture, not typed.

## Files

- `F_UI_FP_030_041_048_052_054_055_t_a78e24ee.json` - the artifact (6 rows, per-row build binding)
- `raw/probe_t_a78e24ee_raw.json` - the capture the artifact is generated from
- `scripts/probe_ui_fp_6rows_t_a78e24ee.py` - the read-only probe
- `scripts/make_artifact_t_a78e24ee.py` - the generator

## Interpreter / environment

playwright is installed **only** under Python 3.11; `PLAYWRIGHT_BROWSERS_PATH` must point at
`C:/Users/wigmore/AppData/Local/ms-playwright` (the inherited `.hermes/tools` path lacks
`chromium_headless_shell-1208`). Repo path has no `projects` segment.
