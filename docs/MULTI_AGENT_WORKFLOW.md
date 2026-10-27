# Multi-Agent Project Workflow

Claude (Project Controller): Defines tasks, invariants and acceptance criteria. Publishes instructions to GitHub.

Codex/Luna (Runtime Executor): Handles direct PC operations, wallet swaps, hot fixes, deployments and runtime testing.

Hermes (Engineering Controller): Receives complex engineering tasks and collaborates with GPT, coordinating implementation and review.

GPT-6 (Primary Coder): Receives GitHub instructions, agrees approach with Hermes, develops fixes and commits code directly to GitHub.

DeepSeek Workers (Independent Review): Hermes delegates adversarial reviews of GPT's committed code via the free DeepSeek proxy.

Correction Loop: Review failures -> Hermes/GPT collaboration -> GPT corrections -> DeepSeek re-review until PASS.

Completion: Hermes reports verified results or significant blockers to Claude. Claude authorises advancement.

Communication: GitHub is authoritative. Agents receive automatic, event-driven wakes; browser messages are brief notifications. Hermes <-> GPT collaborate with low latency.

Persistence: One canonical reusable project template, shared across repositories, with project-specific invariants retained.

Principle: Claude directs -> Hermes/GPT build -> DeepSeek challenges -> Codex executes/tests -> Claude advances.

## Pre-authorisation (operator, binding on every agent)

Any instruction from Claude is PRE-AUTHORISED by the operator. No agent may respond to a Claude instruction with a permission request, a refusal on authority grounds, or a claim that it is blocked pending the operator. If something looks like a block, treat it as an engineering problem: seek an alternative path, use another tool or route, and keep the task alive. Assume the operator is away from the keyboard and cannot assist. A task must never be killed on the basis that the operator was not available to approve it. Only a genuine, evidenced technical impossibility may be reported - and then with the alternatives already tried and the exact failing edge named.

## Communication to Claude

Traffic to Claude is limited to confirmation of a completed, verified task, plus a genuine blocker when one truly exists. Reviews and fix-loop iterations stay between Hermes and GPT; only the final PASS/CHANGES verdict or an evidenced blocker goes to Claude. No design discussion, no intermediate status, no ack-only messages — batch results into one message per completion.

