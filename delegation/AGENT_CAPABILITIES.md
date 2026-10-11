# Delegation routes and free models (read from config on Boss's PC, 2026-10-10 14:05Z; no secrets)

## OpenCode (~/.config/opencode/opencode.jsonc) — `opencode run` headless, one clone per run
| agent | model | notes from what we've seen |
|---|---|---|
| orchestrator (default) | opencode/big-pickle | Reads a lot, slow on the 9.6k-line Core file: PR 1 ran 4 h, 280 lines edited, no commit. Good at narrow, well-specified tasks. |
| build | openrouter/cohere/north-mini-code:free | code edits |
| explore / plan | openrouter/nvidia/nemotron-3-ultra-550b-a55b:free | search, planning |
| general | openrouter/openrouter/free | routes to whatever free model is up |
| small_model | opencode/ling-3.0-flash-fin-free | titles/summaries |
Observed: bench test-only task done in ~10 min (d58ba8e); T2 narrow repair-tool change posted its SHA via gh_api.py in ~30 min. Cost $0; limits are the free-tier rate limits. Run at most 2–3 at once.

## Hermes (~/.hermes/config.yaml) — TRANSPORT_ENVELOPE v1 on richard-mission-control-template issue #1
Default model openrouter/free via openrouter. Providers configured: gemini, groq, local-zimablueai, localnov1, openrouter, nous, deepseek, custom-deepseek-free (default models include gemini-3.1-flash-lite, gpt-oss-120b, qwen3-coder:30b-32k local, nemotron-3-ultra:free, laguna-xs-2.1:free, deepseek-v4-flash-thinking). Fallbacks: opencode-free (space-bunny-free, …).
Route target is the single role hermes:implementation-owner; the config names no further worker roster. The Hermes gateway itself can hand off to OpenCode and Ollama. Throughput on our tasks: not yet measured (PR 1 and T1 envelopes outstanding).

## Recommended routing
| task type | best route | why |
|---|---|---|
| Narrow function edit with a clear spec (≤ ~150 lines) | OpenCode, own clone | proven fast (T2) |
| New test file / bench with a fake exchange | OpenCode | proven (bench d58ba8e) |
| Review / adversarial tests of a branch | OpenCode (plan/explore agent) or a second OpenCode run, then a Claude spot-check | cheap second opinion; Claude only reviews the diff |
| Multi-file or large Core refactor (hot path, T1) | Hermes envelope, split into bounded steps; OpenCode only with very narrow steps | big-pickle stalls on the 9.6k-line file |
| Research / log analysis | local offload router (Ollama qwen3-coder / deepseek) or Hermes | free; output is advisory |
| Engine restarts, repairs, anything touching the live testnet engine or keys | Claude on the PC thread | safety rules; never delegated |
