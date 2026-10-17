# UI CERT ARTIFACT SCHEMA — required shape for every UI certification card

**Why this file exists.** Four UI artifacts have now failed adversarial review, and the failures
repeat in the same few places: a claim whose numbers do not reproduce, probe files missing so nothing
can be replayed, and rows mislabelled against the wrong build. Each failure cost a full card cycle to
discover. The fix is to state the required shape ONCE, here, and have every card emit it.

A reviewer must be able to take your artifact **alone** and re-run your probes. If they cannot, the
artifact fails regardless of how good the analysis is.

## The rule that governs all of it

**The certification target is the build that actually serves `/live-copy` — NOT the register commit.**

The register `b142cf88` has **no `/live-copy` route**, so it cannot be the target for UI rows. The
controller ruled that UI rows are certified against the serving build, in a separate UI-only section.

At time of writing the serving build is:

| field | value |
|---|---|
| `serving_commit` | `b5e6d613de36e3020ac28ba2317e6571a5c37e9b` |
| `serving_ssot_sha256` | `658ec8e31eb96d70acc15dc30860334c23612d2e3e9d19fb63ed9ec4e6fa86c2` |

**Verify these yourself** — do not copy them from this file. Get the serving checkout
(`git rev-parse HEAD`, `sha256sum` over its `HL_Copy_App_SSOT.py`) and use what you measure. If it has
moved, cite the new values. Labelling a row `vs register b142cf88` while probing `:8031` is **invalid**.

## Required artifact shape

One JSON document, plus the files it references, committed on your isolated branch.

```json
{
  "card_id": "t_xxxx",
  "serving_commit": "<measured>",
  "serving_ssot_sha256": "<measured>",
  "how_serving_build_was_established": "git rev-parse HEAD + sha256sum over SSOT in <path>",
  "oracle": "what the independent oracle is, and why it is independent (no engine import)",
  "files": ["EVIDENCE/.../probe.py", "EVIDENCE/.../dom_capture.json", "EVIDENCE/.../inspect.py"],
  "rows": [
    {
      "row_id": "UI-FP-025",
      "verdict": "PASS|FAIL|PARTIAL|NOT_TESTED",
      "serving_commit": "<measured>",
      "serving_ssot_sha256": "<measured>",
      "executed_probe": "exactly what was run for THIS row",
      "independent_oracle": "the oracle used for THIS row",
      "observed": "the concrete values observed, with the raw capture file that holds them",
      "reproduces": "the command a reviewer runs to reproduce these numbers"
    }
  ]
}
```

## The two review rules (controller-confirmed additions)

1. **A card may NEVER review or approve its own output.** The reviewer must be a **different card**
   (and a different model from the author). A card that closes with "reviewed and approved" has
   reviewed nothing — that happened (`t_775a0935`) and its approval was void.
2. **The reviewer must RECOMPUTE every number** in a verdict from the oracle itself. Copying a figure
   from the artifact is not verification. This rule has already caught a false PASS: a claimed
   `−$849.98` recomputed to `−$858.21`.

Corollary: **never accept a self-claim as evidence** — not "approved", not "verified", not "committed".
Check the committed object.

## Hard requirements (each has already caused a FAIL)

1. **`row_id`** — the key is `row_id`, not `id`. Every row record, no exceptions.
2. **Per-ROW build binding** — `serving_commit` AND `serving_ssot_sha256` **inside every row record**.
   A single top-level stamp is not sufficient and was a FAIL.
3. **Self-contained and replayable** — commit the probe, the DOM capture and any inspect script, and
   give the exact command to reproduce. **Referenced-but-missing files were a FAIL.**
4. **Numbers must reproduce.** If you report a value, a reviewer recomputing it from the independent
   oracle must get the same number. A claimed `−$849.98` against a recomputed `−$858.21` was a FAIL
   and was the difference between a PASS and a false PASS.
5. **One verdict per row** — with that row's own probe and oracle. Do not emit per-assertion PASS
   entries as row verdicts (one artifact emitted 582 for 6 rows and was rejected).
6. **Every predicate must be able to fail.** A check that cannot fail is not a PASS.
7. **Runtime-earned** — live rendered DOM at `http://127.0.0.1:8031/live-copy`. A synthetic page or
   intercepted fixtures were a FAIL.
8. **READ-ONLY** — never POST/Save to the live service, never touch Edge/CDP 9223 or the `:8031`
   process. If a row's proof would require a write, record `NOT_TESTED` instead.

## Environment (verified — get this wrong and the probe fails while the product is fine)

- Interpreter: `C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe` (3.14 has no playwright)
- `export PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright`
  (the inherited `.hermes/tools` path lacks `chromium_headless_shell-1208`)
- Repo: `C:/Users/wigmore/hyperliquid-build3-repair` (there is no `projects` path segment)

## A tool failure is not a product gap

If your probe cannot run because of the environment above, **fix the environment**. Do not record
`NOT_TESTED` for a tooling failure — that understates the product and is as misleading as a false PASS.
Reserve `NOT_TESTED` for a genuine product-side or decision-side gap, and name it exactly.
