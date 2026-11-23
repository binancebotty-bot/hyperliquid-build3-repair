---
name: user-owned-per-dex
description: Keep user-owned exposure distinct by DEX and protect it from copy-engine actions.
---

# User-owned positions by DEX

Require explicit controller authorization and an approved, current source of ownership labels. Never infer ownership from a symbol alone: scope each label to the follower DEX and preserve the source/provenance.

- Label only positions positively classified as user-owned; keep them outside engine-owned copy sleeves.
- Never flatten, cancel, or modify a `USER-OWNED`/orphan position as part of copy cleanup. Never issue a cross-DEX close based on a combined symbol total.
- Flattening is allowed only for positively identified engine-owned exposure with a separate explicit order, using reduce-only actions on that same DEX. Stop if ownership, DEX, or exchange truth is uncertain.
- Verify through the approved reconciliation workflow that ownership remains `USER-OWNED` per DEX and that no copy action was attributed to it.

This checkout has no supported manual flatten command for user-owned positions. Do not invent one or substitute dashboard totals for per-DEX ownership evidence.
