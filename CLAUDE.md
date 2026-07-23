# CLAUDE.md

Guidance for Claude Code when working in this repo. See [README.md](README.md) for the full overview.

## What this project is

"orator" - an open-source Python speech grader: fillers (um/uh/like/you know, pause-gated + context-aware), the signature "got-tripped-up" word-choice layer (hesitation + low ASR confidence + filler/repetition fused on a shared time axis, suggesting a stronger word), and pace/pauses/prosody. Architecture is ASR-decoupled: a pluggable verbatim ASR feeds a canonical `Transcript` that the whole analysis layer consumes, so analysis is unit-tested fully offline from a fixture. `orator` CLI; own `.venv`.

## Orchestration & loops

Match the execution shape to the task - solo, subagents, a workflow, or a loop - per the always-on rule [`../.agents/rules/orchestration-and-loops.md`](../.agents/rules/orchestration-and-loops.md) (deep reference: [`../.agents/memory/reference_dynamic-workflows.md`](../.agents/memory/reference_dynamic-workflows.md)). Separate doing from judging, tier the model to the phase, and give every loop a hard stop. **Here:** the word-choice / tripped-up "LLM" layer is an agent handoff (orator emits a request packet via `--emit-request`, the agent fills findings, `--wordchoice-json` merges them) - treat that as the doing-vs-judging split; analysis is unit-tested offline, most grading work is solo.

## Related

- Workspace root: `../`
- Shared skills: `../.agents/skills/`
- Workspace conventions: `../AGENTS.md`
## Lean Runtime

Caveman + Ponytail are active by default in this project through local skills, hooks, Cursor rules, and MCP entries. Keep communication terse, preserve exact technical details, and choose the smallest correct implementation: existing code, stdlib, native platform, installed dependency, then minimum new code. Full rule: `.agents/rules/lean-token-and-yagni.md`.
## Working Norms

Requested improvements are implementation scope. If Trevor asks to add, apply, install, wire, improve, or make something work here, make the durable project change after reading local context. Confirm only for destructive/outward-facing actions, credentials, frozen snapshots, or genuinely ambiguous targets.
