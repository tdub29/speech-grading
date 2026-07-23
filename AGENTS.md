# AGENTS.md — speech-grading

Agent guidance for this project (Codex, Claude Code, any harness). Inherits the workspace conventions in [../AGENTS.md](../AGENTS.md) and [../CLAUDE.md](../CLAUDE.md). Read the local CLAUDE.md / README first for project specifics.

## Lean Runtime (caveman + ponytail) — active by default

Communicate in **caveman** style: terse, drop articles / filler / pleasantries / hedging, fragments OK, but preserve every bit of technical substance and keep code, commands, and error strings exact. Write code the **ponytail** way: the smallest correct implementation — reuse what already exists here, then stdlib, then the native platform, then an already-installed dependency, and only then minimum new code; no speculative abstractions or boilerplate "for later". Code, commits, PRs, and security writing stay in normal prose, not caveman. Skills live in `.claude/skills/` + `.agents/skills/` (`caveman`, `caveman-*`, `ponytail`, `ponytail-*`, `cavecrew`). Full rule: [../.agents/rules/lean-token-and-yagni.md](../.agents/rules/lean-token-and-yagni.md).

## Working norms

Requested improvements are implementation scope: make the durable change after reading local context. Confirm only for destructive or outward-facing actions, credentials, frozen snapshots, or genuinely ambiguous targets.
