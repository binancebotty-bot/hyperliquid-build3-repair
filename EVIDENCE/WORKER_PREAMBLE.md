# Build3 worker preamble

## Checkout isolation (mandatory)

A worker that must create, stage, commit, or push changes MUST use a clone dedicated to its Kanban card. Never commit from the shared `b3_clean` checkout: it is reserved for READ-ONLY inspection. Concurrent cards cannot safely share a Git working tree because they would contend over branch, index, and working-tree state; one leftover conflict can block unrelated work.

From the card's own workspace, use a card-specific path:

```sh
git clone --depth 50 https://github.com/binancebotty-bot/hyperliquid-build3-repair <workspace>/b3-<task_id>
cd <workspace>/b3-<task_id>
git fetch origin <base-ref>
git switch -c <task-branch> <base-ref>
```

Use the exact base ref and branch named in the task. Keep all edits, staging, commits, and pushes inside this card-specific clone. Do not use, reset, clean, or change branches in `b3_clean` when writing. If a task only needs inspection, `b3_clean` may be used read-only; do not mutate its index, refs, or working tree.
