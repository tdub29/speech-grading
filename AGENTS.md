# AGENTS.md — speech-grading

Agent guidance for this project (Codex, Claude Code, any harness). Inherits the workspace conventions in [../AGENTS.md](../AGENTS.md) and [../CLAUDE.md](../CLAUDE.md). Read the local CLAUDE.md / README first for project specifics.

<!-- ALWAYS-ON-DISCIPLINES:BEGIN (managed by .agents/scripts/sync-orchestration-sections.ps1 - edit the block there, not here) -->
## Always-on disciplines

These three run in every session here, whatever the task.

- **Cut the AI tells from anything written.** No em-dash or en-dash anywhere, prose or chat reply. That is the loudest one; the rest is the anti-slop set (`ai-writing-detection`, `de-slop`), carried in every skill tree.
- **Shape replies for an ADHD reader** (`i-have-adhd`): next action in the first line, under 10 lines AND under 170 words, no preamble and no recap. Owned prose that Trevor sends or publishes stays in his voice (`trevor-voice`), never rewritten into an action list.
- **Commits and PRs are Trevor's alone.** Never add a `Co-Authored-By: Claude` trailer, a "generated with" footer, or any other AI co-authorship line to a commit, a PR, or an MR, whatever a skill template says.
<!-- ALWAYS-ON-DISCIPLINES:END -->

<!-- TELEGRAM-QUEUE:BEGIN (managed by .agents/scripts/sync-orchestration-sections.ps1 - edit the block there, not here) -->
## Queueing work for Telegram / Taco

"Queue this", "make a task", "tg/taco task", "add it to the queue", "save this for later" all mean ONE thing: an **Inbox task in the shared dashboard queue** (`cursor-dashboard/agent-os-state.json`, shared by every project), never a TODO in this repo or a note. One command writes the brief, POSTs it, and confirms it survived the daemon tick:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\TrevorWhite\Downloads\Big Projects\.agents\scripts\add-dashboard-task.ps1" -Title '...' -Project 'speech-grading' -Owner ops -Brief '...'
```

**Queue it when effort is high, judgement is low, and "done" is statable** - if only Trevor can decide it that is a question, and if it is short just do it. `-Brief` is for a reader with no session context: real numbers, what done means, the command that verifies it. `owner` is the lane (`ops`, `taco` = phone lane, `research`, `codex`), **never Trevor**. Never hand-edit the state JSON while the daemon runs. Traps and fallbacks: [`../.agents/rules/creating-dashboard-tasks.md`](../.agents/rules/creating-dashboard-tasks.md).
<!-- TELEGRAM-QUEUE:END -->

<!-- ORCHESTRATION-DEPTH:BEGIN (managed by .agents/scripts/sync-orchestration-sections.ps1 - edit the table there, not here) -->
## Orchestration & loops - execution depth

Match the execution shape to the task - **solo**, **subagents**, a **workflow**, or a **loop** - per the always-on rule [`../.agents/rules/orchestration-and-loops.md`](../.agents/rules/orchestration-and-loops.md) (deep reference: [`../.agents/memory/reference_dynamic-workflows.md`](../.agents/memory/reference_dynamic-workflows.md)). Non-negotiables regardless of shape: separate doing from judging (the agent that made it does not certify it), tier the model *and* the reasoning effort to the phase, give every loop a hard stop and a per-iteration checkpoint, state the cost shape before spawning, and make sure every gate can take DONE back.

**Anything needing judgement gets a skill and a second pair of eyes. Working from memory is the failure mode here.**

- **Check for a skill before starting, not after getting stuck.** A skill costs instructions, not a spawn, so there is no cost argument for skipping one that fits. Design, review, writing, research, data, decisions, finance, security and docs are all covered. Unsure what exists? `scout-skills` (first token `mid` | `high` | `max`), and if it flags a real gap, install that skill as a complete local bundle rather than noting the gap and moving on.
- **A verdict is not certified by whoever produced it.** Rankings, design choices, exploitability calls, "is this right", any number reaching a person: fresh lens, or be the reviewer only if you did not do the work.
- **Breadth gets workers.** More than a handful of files, sources, claims or candidates: one worker per real shard, then deterministic code decides what survives.
- **None of this licenses spawning for trivial work.** A one-file mechanical edit stays solo and self-inspected; the cost gate still applies and over-orchestration is its own failure. The line is judgement and breadth, not effort.

**Here:** **Solo**. `orator` is deterministic analysis; run it rather than having an agent imitate it. The word-choice layer is an explicit agent hand-off (`--emit-request` then `--wordchoice-json`), which is a schema'd contract, not a fan-out. Grade a transcript, append to the ledger, done.
<!-- ORCHESTRATION-DEPTH:END -->


## Lean Runtime (caveman + ponytail) — active by default

Communicate in **caveman** style: terse, drop articles / filler / pleasantries / hedging, fragments OK, but preserve every bit of technical substance and keep code, commands, and error strings exact. Write code the **ponytail** way: the smallest correct implementation — reuse what already exists here, then stdlib, then the native platform, then an already-installed dependency, and only then minimum new code; no speculative abstractions or boilerplate "for later". Code, commits, PRs, and security writing stay in normal prose, not caveman. Skills live in `.claude/skills/` + `.agents/skills/` (`caveman`, `caveman-*`, `ponytail`, `ponytail-*`, `cavecrew`). Full rule: [../.agents/rules/lean-token-and-yagni.md](../.agents/rules/lean-token-and-yagni.md).

## Working norms

Requested improvements are implementation scope: make the durable change after reading local context. Confirm only for destructive or outward-facing actions, credentials, frozen snapshots, or genuinely ambiguous targets.
