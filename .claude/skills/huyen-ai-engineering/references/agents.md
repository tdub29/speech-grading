# Agents: tools, planning, memory, and failure modes (Huyen Ch. 6, agents half)

## Produce
An **agent design + failure-mode evaluation plan**: the environment + tool inventory definition, a planning architecture (decoupled plan→validate→execute, granularity, control flow, reflection), a memory design (internal/short/long-term), and a failure-mode benchmark (planning, tool, efficiency) with per-mode metrics and HITL/safety gates.

Fire this when someone is building an agent (tool-using, multi-step, ReAct/Reflexion, function calling), debugging why an agent fails, or evaluating one. (Pure retrieval → `rag-and-retrieval.md`.)

## Trigger checks
- "How do I build an agent / tool-using LLM / function-calling app?"
- Agent planning, ReAct, reflection, multi-agent, plan validation
- Tool selection / function calling / which tools to give the agent
- "My agent fails / loops / burns API credits / hallucinates tool calls"
- Agent memory (short vs. long-term), evaluating an agent
- Interview: "Design an agent" / "Why do agents fail and how do you evaluate them?"

## Frame: an agent = environment + actions (tools)
An agent perceives and acts on an environment. **Environment** is set by the use case (a game, the internet, a kitchen, a codebase); **action set** is augmented by its **tools**. AI is the *brain/planner* that reasons, plans a sequence of actions, executes, and judges completion. RAG is a simple agent (retriever = tool). Agents need **more powerful models** because of (1) **compounding errors** — 95%/step over 10 steps = 60%, over 100 steps = 0.6% — and (2) **higher stakes** (tools make failures more impactful). Success = tool inventory × planner strength.

## How to apply

### 1. Tools (the action set)
Three categories — **read-only** (perceive) vs. **write** (act):
- **Knowledge augmentation** (context construction): text/image retrievers, SQL executor, people search, inventory/email/Slack APIs, **web browsing** (keeps the model from going stale; umbrella for search/news/GitHub/social APIs — but opens you to the internet's cesspool).
- **Capability extension**: patch model weaknesses cheaply — calculator (models are bad at math), calendar, unit/timezone converter, translator, **code interpreter** (powerful, but code-injection risk → isolate), and modality bridges (text→image generator, OCR, transcription). Tool use can beat prompting *or* finetuning (Chameleon + 13 tools beat GPT-4 alone).
- **Write actions**: SQL writes, send email, bank transfer — enable end-to-end automation but are dangerous. "Don't give an unreliable AI the authority to initiate bank transfers" → require approval/security. Model-provider support for tools = **function calling**.

### 2. Planning (decouple from execution)
A task = goal + constraints. **Decouple planning from execution** — don't run a 1,000-step plan before validating it (wastes time/money). System becomes 3 components (a **multi-agent** system): **plan generator** → **plan validator** (heuristics: drop plans with invalid tools or >X steps; or AI judge) → **executor**. Use an **intent classifier** to pick tools (and to mark out-of-scope requests IRRELEVANT instead of burning FLOPs). The full loop: **plan generation (task decomposition) → reflect/correct → execute (function calls) → reflect/correct** until done. Humans can sit at any stage (provide/validate/execute) — define the automation level per action; gate risky writes (DB update, code merge) on human approval.
- **FM as planner** — debated (LeCun/Kambhampati: autoregressive LLMs can't plan; "general planning knowledge ≠ executable plans"). Counter: a model *can* backtrack by revising/restarting; may just lack tooling (a world model to predict action outcomes — Hao et al.). FM vs. RL planner: in FM agents the *model* is the planner (prompt/finetune, cheaper); the two will likely merge.
- **Plan generation** — simplest is prompting (system prompt lists tools + examples → outputs an action sequence; exact parameters often inferred from prior tool outputs and can be wrong/hallucinated). Improve via: more/better examples, better tool descriptions, simpler functions, stronger model, finetuning.
- **Function calling** — declare a tool inventory (name, params, docs); per query set tool use to required/none/auto. APIs may guarantee valid function names but **not correct parameter values** — always print + inspect the parameter values.
- **Planning granularity** — detailed plans are hard to generate/easy to execute and vice versa → **plan hierarchically** (high-level then per-step). Prefer **natural-language plans** over exact function names (robust to tool renames, reusable, less hallucination) + a cheap **translator** to executable commands.
- **Complex control flow** — sequential, **parallel** (cuts latency — browse 10 pages at once), if-statement, for-loop; AI determines the flow (harder to generate than exact code). Check what control flows a framework supports.
- **Reflection + error correction** — not mandatory but hugely improves success. **ReAct** (interleave Thought → Act → Observation until done) and **Reflexion** (separate evaluator + self-reflection module proposing a new trajectory) are the canonical patterns; can be same agent (self-critique) or a separate scorer/multi-agent. Cheap to add, big gains; cost = tokens/latency for thoughts/observations.

### 3. Tool selection
More tools = more capability but harder to use (and bigger descriptions strain context). No foolproof guide — experiment: compare tool sets, run **ablations** (remove a tool, measure drop — if no drop, remove it), find tools the agent misuses (re-prompt/finetune or swap), plot tool-call distribution. Different tasks/models prefer different tools. Agents can build new tools from simple ones (Chameleon tool-transition; Voyager skill manager/library).

### 4. Memory (shared with RAG)
Three mechanisms by frequency of use: **internal knowledge** (in the weights; all-task, change only by training/finetuning), **short-term memory** (the context — fast, limited, this-task only), **long-term memory** (external sources via retrieval — persists across tasks, deletable without retraining). Benefits: handle in-session overflow, persist across sessions (personalization), boost consistency, maintain structured-data integrity. Two functions: **management** (add/delete — short-term is capacity-bound, reserve e.g. 30% of context for retrieved long-term, overflow to long-term) and **retrieval** (= RAG retrieval). Management strategies: **FIFO** (simple but can drop the most important early messages), **redundancy removal / summarization** (+ entity tracking), **reflection-based** (insert/merge/replace, handle contradictions — keep newer, or AI-judge which).

### 5. Failure modes + evaluation
Evaluation = detecting failures; more steps = more failure points. Beyond the generic FM failures (Ch. 3–4), agents have:
- **Planning failures** — **tool-use errors** (invalid tool / valid tool wrong #params / valid tool wrong param values), **goal failure** (doesn't solve, or ignores constraints like budget/**time** — a grant proposal finished after the deadline is useless), **reflection error** (insists it's done when it isn't — assigns 40 of 50 people and claims success). Metrics on a (task, tool-inventory) dataset: % valid plans, plans-needed-per-valid-plan, % valid tool calls, rates of invalid-tool / wrong-params / wrong-values.
- **Tool failures** — right tool, wrong output (bad caption / bad SQL); translation errors (NL plan → command); **missing tool** (no internet for a stock-price task). Test each tool independently; print every tool call + output; consult domain experts for missing tools.
- **Efficiency** — steps/task, cost/task, time per action — vs. a human or baseline agent (but human-efficient ≠ AI-efficient: 100 pages is slow for a human, trivial-parallel for an agent).
Benchmarks: Berkeley Function-Calling Leaderboard, AgentOps, TravelPlanner.

## Common failure modes (building agents)
- **Coupled plan + execute.** One prompt that plans-and-runs → a long bad plan burns hours/credits before you notice; decouple and validate first.
- **Too many tools.** Bloated inventory the model can't wield + descriptions that blow the context; ablate down to what's used.
- **Trusting function-call params.** Assuming valid function name = correct arguments; inspect parameter values.
- **No reflection.** Skipping reflect/correct, so the agent compounds errors with no recovery.
- **Exact-function-name plans.** Brittle to tool renames and non-reusable; prefer NL plans + a translator.
- **Ungated write actions.** Letting an agent run DELETE/DROP/transfers without human approval or isolation.
- **Eval only end-to-end.** Not separating planning vs. tool vs. efficiency failures, so you can't fix the right thing.
- **FIFO memory.** Dropping the earliest messages that stated the task's purpose.

## Interview signal
**AI-Engineer / FDE framing:** Agents are the hot, high-risk surface. Senior signal = **decoupling planning from execution** (plan→validate→execute as a multi-agent loop), naming **compounding error** as the reason agents need strong models + reflection, gating **write actions** behind approval/isolation (ties to indirect prompt injection from `prompt-engineering.md`), and evaluating by *failure mode* (planning/tool/efficiency) not a single score.
**One crisp talking point:** *"Agents fail by compounding — 95% per step is 60% over ten steps — so I decouple planning from execution: generate a plan, validate it (heuristics or an AI judge) before running a single tool, and add a reflection loop like ReAct. I keep the tool inventory minimal via ablation, gate any write action behind human approval and sandboxing, and I evaluate by failure mode — invalid tool vs. wrong parameters vs. goal/constraint failure vs. efficiency — because a single success rate hides where to fix it."*

## Practitioner checklist
- [ ] Environment + minimal tool inventory defined (read vs. write actions); write actions gated/sandboxed
- [ ] Planning decoupled from execution: generate → validate (heuristics/AI judge) → execute
- [ ] Intent classifier routes tools + rejects out-of-scope; control flows (parallel?) supported by the framework
- [ ] Plans at the right granularity (hierarchical / natural-language + translator)
- [ ] Function-call parameter values inspected; reflection/error-correction loop (ReAct/Reflexion) in place
- [ ] Tool set pruned by ablation; hard-to-use tools re-prompted/finetuned or swapped
- [ ] Memory designed across internal/short/long-term; management strategy chosen (not naive FIFO)
- [ ] Failure-mode benchmark built (planning/tool/efficiency) with per-mode metrics; time constraint included

## References
- *AI Engineering* (Huyen, O'Reilly 2024), Ch. 6 (pp. 494–593), agent sections: Agent Overview, Tools, Planning, Tool Selection, Failure Modes & Evaluation, Memory.
- Sibling docs: **`rag-and-retrieval.md`** (RAG = an agent whose tool is a retriever; shared memory system), `prompt-engineering.md` (CoT/self-critique underpin planning/reflection; **indirect prompt injection** is the agent's #1 security surface), `evaluating-ai-systems.md` (generic failure modes + eval pipeline), `finetuning.md` (finetuning for plan generation/tool use).
- Related skills: `claude-api` (Anthropic tool-use / function-calling format, agent patterns), `mlsd-coach` (agent design in a system-design interview).
