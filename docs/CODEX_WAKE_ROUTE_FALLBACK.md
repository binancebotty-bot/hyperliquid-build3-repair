# Codex wake route — design and scratch proof (FALLBACK, NOT ENABLED)

Status: documented fallback only. Per the authority's decision on 2026-10-27 the 15-minute scan
stands; this must not be enabled until a Codex ops task is actually waiting on it, and not
without an explicit per-thread session id.

## What Codex is on this host
- Desktop app (MSIX `OpenAI.Codex` 26.1021.3705.0) plus bundled CLI at
  `%LOCALAPPDATA%/OpenAI/Codex/bin/<hash>/codex.exe` (version.json 0.163.0), `CODEX_HOME=C:/Users/wigmore/.codex`.
- Sessions: ~263 `rollout-*.jsonl` under `~/.codex/sessions/**`, bursty (several within 2 s).
- Hooks are inbound only (`~/.codex/hooks.json`: PreToolUse graphify + pretool_action_guard;
  notify -> `codex-computer-use.exe turn-ended`).
- **No watched inbox directory, no host-side scanner, no scheduled task.** The ~15-minute cadence is
  Codex's own internal behaviour, so there is nothing on this host to shorten by configuration.

## Design
1. Write the instruction atomically: `MSG-ID.tmp` -> `os.replace` -> `MSG-ID.json`.
2. Fire ONCE: `codex exec resume --last <instruction>`.
3. Gate every send on an append-only `ledger.jsonl` keyed by MSG-ID; a repeat returns
   `duplicate_suppressed` and spawns nothing.

Alternatives rejected: no watched inbox exists, so a `ReadDirectoryChangesW` watcher would be a
resident daemon ticking on nothing; `codex app-server` is experimental with no `daemon status`
subcommand; the Hermes router resolves Hermes sessions only and editing it is out of scope; cron is
excluded by standing rule.

## Measured (scratch target only)
| run | latency, instruction written -> consumer observed |
|---|---|
| 1 | 92.6 ms |
| 2 | 53.8 ms |
| 3 | 54.2 ms |

A duplicate MSG-ID returns `duplicate_suppressed` with no event appended. Real `codex exec
--ephemeral` end-to-end: 8026 / 6440 / 4830 ms including model round-trip; cold `--version`
276–479 ms. Waking is sub-100 ms; time-to-first-output is Codex's own model latency.

## The activation line (deliberately NOT applied)
```python
argv = ["C:/Users/wigmore/AppData/Local/OpenAI/Codex/bin/<hash>/codex.exe",
        "exec", "resume", "--last", instruction]
```
(drop `--ephemeral` for resume — it must persist to continue the thread)

## Residual risks — why it is not enabled
- `--last` is ambiguous under concurrency (263 rollouts, bursts of 3+ within 2 s): a wake can land in
  a different thread than the one being read. A safe version needs an explicit SESSION_ID per
  thread, which is a Codex-side change.
- `resume` drives a CLI turn, not the desktop composer the operator watches.
- Each wake burns a real exec turn (~3.4k tokens) against account usage limits.
- Lock contention with the desktop app can make resume fail; the ledger would mark it fired, so the
  launcher's exit code must be checked or the failure is silent.

## Scratch artefacts
`~/.hermes/cache/scratch/codexwake/{wake_send.py, consumer_standin.py, queue/, ledger.jsonl, events.jsonl}`
— nothing outside scratch was created or modified.
