# Architecture and User Feedback: end-to-end system + the data flywheel (Huyen Ch. 10)

## Produce
Two artifacts: (1) an **incremental architecture plan** — the staged build from "query → model → response" up through context, guardrails, router/gateway, caching, and agent patterns, plus the monitoring/observability and orchestration layers; and (2) a **user-feedback design** — what conversational signals to extract, when/how to collect them without hurting UX, feeding the data flywheel.

Fire this when someone is designing the end-to-end system for an FM app, adding guardrails/routing/caching/observability, or building a feedback loop. This is the capstone that ties every other doc together.

## Trigger checks
- "What's the architecture for an LLM app?" / "how do I put this together end-to-end?"
- Guardrails (input/output, PII), model router, model gateway, caching (exact/semantic)
- Monitoring/observability for LLM apps, logs/traces/drift, orchestration (LangChain etc.)
- "How do I collect user feedback?" / thumbs / preference data / data flywheel
- Interview: "Design a production LLM application" / "How do you monitor / get feedback?"

## How to apply

### 1. Build the architecture incrementally (start simplest, add to fix a real problem)
Start: **query → model API → response** (no context, guardrails, optimization). Then add components in this common (not mandatory) order:
1. **Enhance context** — retrieval (text/image/tabular) + tools (web/news/APIs); context construction = feature engineering for FMs; near-universally supported but providers differ (doc limits, chunk config, parallel tool execution). (See `rag-and-retrieval.md` / `agents.md`.)
2. **Guardrails** — **input guardrails** protect against leaking private data to external APIs (PII detection → block or **mask/unmask via a reverse PII dictionary**) and bad prompts (see `prompt-engineering.md`); **output guardrails** catch failures (quality: malformed/hallucinated/bad; security: toxic/PII/tool-exec/brand-risk) and define a handling policy (**retry** — exploit probabilism; parallel retry to cap latency; **human fallback** on anger/loops/keywords). Track BOTH failure rate AND **false-refusal rate**. Tradeoffs: reliability vs. latency; guardrails fight streaming mode (can't score partial output); self-host vs. API shifts which guardrails you need.
3. **Router + gateway** — **router** (intent classifier / next-action predictor / memory router) sends queries to specialized or cheaper models, rejects out-of-scope, asks for clarification; small/fast/cheap; routing usually *before* retrieval (route → retrieve → generate → score). **Gateway** = unified interface to all models (swap one place when an API changes) + access control + cost management + fallback/rate-limit handling + logging/load-balancing.
4. **Caches** — **exact caching** (same item → cached result; LRU/LFU/FIFO eviction; don't cache user-specific/time-sensitive queries; **beware caching user-specific answers → data leak across users**) and **semantic caching** (reuse semantically-similar via embeddings + vector search + threshold — dubious value: many failure points, can return wrong answers, costs a vector search; only worth it at high hit rate). (Inference-level KV/prompt cache → `inference-optimization.md`.)
5. **Agent patterns + write actions** — loops, parallel, conditional branching (feed responses back); **write actions** (email/order/transfer) make the system far more capable AND far riskier — gate with utmost care (see `agents.md`).
Each addition increases capability *and* failure modes → observability matters more.

### 2. Make it observable (designed in, not bolted on)
Goal = mitigate risks (failures, attacks, drift) + discover opportunities. DevOps-derived quality metrics: **MTTD** (time to detect), **MTTR** (time to resolve), **CFR** (change failure rate — if unknown, redesign for observability). Evaluation and monitoring must couple (eval metrics → monitoring metrics; monitoring issues → eval pipeline). **Monitoring** = track; **observability** = infer internal state from outputs (debug without shipping new code).
- **Metrics** — design *around the failure modes you want to catch*, not metrics-for-metrics' sake. Easiest: format failures (invalid JSON, fixable vs. not). Then factual consistency/quality (AI judges), safety/toxicity/PII, guardrail-trigger + refusal rate, abnormal queries. Conversational signals (early-stop rate, turns/conversation, tokens in/out, output distribution drift). Latency (TTFT/TPOT/total, per-user). Cost (tokens, TPS, RPS vs. rate limits). Per-component (RAG: context relevance/precision). Correlate to **north-star business metrics** (DAU, session duration, subscriptions). Spot-check vs. exhaustive; break down by user/release/prompt-version/type/time.
- **Logs** — **log everything** (configs: endpoint/model/sampling/prompt template; query, final prompt, output, intermediate outputs, tool calls + outputs, component lifecycle) with tags/IDs; AI-powered log analysis; still **manually inspect production data daily** (devs' sense of good/bad evolves → better prompts + eval).
- **Traces** — link events into a request's full execution path (query → actions → docs retrieved → final prompt → response) with per-step time + cost; pinpoint exactly where a failed query went wrong.
- **Drift detection** — system-prompt changes (template edits/typo fixes — add logic to catch), user-behavior changes (users adapt; gradual metric shifts need root-cause investigation), underlying-model changes (silent API updates — GPT-4 March vs. June; Voiceflow −10% on a version bump).

### 3. Orchestrate (chain components — but not too early)
An orchestrator does **component definition** + **chaining** (function composition: process query → retrieve → build prompt → generate → evaluate → return/route-to-human), passing data between steps and flagging format/component failures. **Don't reach for one first** — external tools add complexity and abstract away debuggability; start without one. When you adopt one (LangChain/LlamaIndex/Haystack), evaluate **integration/extensibility**, **complex-pipeline support** (branching/parallel/error handling), and **ease-of-use/perf/scalability** (avoid hidden API calls + added latency). Parallelize independent steps (routing + PII removal) for latency. (Distinct from general workflow orchestrators like Airflow.)

### 4. Design the user-feedback loop (the data flywheel)
User feedback in AI plays a bigger role than in normal software: it's **proprietary data → competitive advantage** (the flywheel from `dataset-engineering.md`). It's user *data* — respect privacy, disclose use.
- **Explicit feedback** (thumbs/stars/votes) — easy to interpret, but extra user effort → sparse + response-biased (unhappy users over-report).
- **Implicit / conversational feedback** — abundant but noisy; the conversational interface makes giving feedback easy and extracting it hard. **Natural-language feedback**: early termination (going badly), error correction ("No, …"/"I meant"/rephrase/"Bill is the suspect not the victim"), confirmation requests ("Are you sure?"), **user edits** (strong signal + free **preference data**: original = losing, edited = winning), complaints (the FITS taxonomy), sentiment. Model-side: **refusal rate**. **Action feedback**: regeneration (dissatisfaction OR wanting options — stronger signal under usage-based billing), conversation organization (delete = bad, rename = good content/bad title), conversation length (good for companions, bad for support), dialogue diversity (low + long = stuck in a loop). Interpreting implicit signals needs user studies (sharing can be positive or negative) — add corroborating signals to disambiguate.
- **When to collect**: at signup (calibration — necessary for Face ID, optional + neutral-default elsewhere), when something bad happens (downvote/regenerate/switch model; let users still finish the task — edit the category, inpainting, human handoff), when the model has **low confidence** (show two options → comparative preference data; partial vs. full responses tradeoff — Gemini shows partials). Apple guideline: don't ask for both positive and negative (good results should be the default; asking implies they're exceptional) — but limited positive feedback reveals loved features (show to 1% to avoid clutter/bias).
- **How to collect**: seamless, non-intrusive, easy to ignore, incentivized. Midjourney's upscale/vary/regenerate buttons encode implicit strength signals; Copilot's Tab-to-accept/keep-typing-to-reject. **Integrated products beat standalone** for feedback (Gmail knows if a draft was sent; ChatGPT doesn't).

## Common failure modes
- **Over-architecting early.** Adding router/gateway/cache/orchestrator before a real need; each adds failure modes and obscures debugging.
- **Observability as afterthought.** Not designing logs/traces in, so MTTD/MTTR are bad when something breaks.
- **Caching data leaks.** Caching a user-specific answer as generic → returning user X's data to user Y.
- **Streaming vs. output guardrails.** Streaming unsafe tokens before the guardrail can block them.
- **Refusal-rate blindness.** Tuning guardrails to zero failures via over-refusal, frustrating legitimate users.
- **Silent drift.** Not detecting system-prompt edits or underlying-model API updates; blaming the app for a provider's change.
- **Explicit-feedback-only.** Relying on sparse, biased thumbs while ignoring rich implicit conversational signals.
- **Intrusive feedback.** Interrupting the workflow or asking for positive feedback in a way that implies good results are exceptional.
- **No flywheel.** Building the app without capturing user feedback as proprietary training data.

## Interview signal
**AI-Engineer / FDE framing:** This is the "design a production LLM system" capstone. Senior signal = building **incrementally** (justify each component by the problem it solves), designing **observability in** (MTTD/MTTR/CFR; logs + traces + drift), treating **write actions** and **caching leaks** as the high-risk surfaces, and — the FDE differentiator — designing the **feedback loop as a data flywheel** that extracts implicit conversational signals (edits → preference data) without hurting UX.
**One crisp talking point:** *"I build the architecture incrementally — query-to-model first, then add context, guardrails, a router and gateway, caching, and agent patterns only as each solves a real problem, because every component adds a failure mode. Observability is designed in, not bolted on: I log everything, trace each request end-to-end, and watch for drift in the system prompt and the underlying model. The piece people under-invest in is the feedback loop — it's the data flywheel and my real moat. I extract implicit conversational signals, like treating a user's edit as a preference pair where the original is the losing response and the edit is the winning one, and I collect it seamlessly so it never interrupts the workflow."*

## Practitioner checklist
- [ ] Architecture built incrementally; each added component justified by a problem (context → guardrails → router/gateway → cache → agent/write)
- [ ] Input + output guardrails (PII mask/unmask; quality + security failures) with retry/human-fallback policy; false-refusal rate tracked
- [ ] Router (intent/next-action) + gateway (unified interface, access/cost control, fallback) where complexity warrants
- [ ] Caching chosen (exact vs. semantic) with eviction + leak protection; user-specific/time-sensitive queries excluded
- [ ] Write actions gated with care; loops/branching designed deliberately
- [ ] Observability designed in: metrics around failure modes, log-everything + traces + drift detection; MTTD/MTTR/CFR tracked; eval↔monitoring coupled
- [ ] Orchestration deferred until needed; independent steps parallelized
- [ ] Feedback loop designed: implicit + explicit signals extracted, collected non-intrusively, fed into the data flywheel (edits → preference data); privacy respected

## References
- *AI Engineering* (Huyen, O'Reilly 2024), Ch. 10 (pp. 852–929): AI Engineering Architecture (context, guardrails, router/gateway, caches, agent patterns), Monitoring & Observability, AI Pipeline Orchestration, User Feedback.
- Sibling docs: this is the capstone — `rag-and-retrieval.md` + `agents.md` (context/tools), `prompt-engineering.md` (guardrail defenses), `evaluating-ai-systems.md` (eval↔monitoring; failure modes), `inference-optimization.md` (KV/prompt cache, routing for cost/latency), `dataset-engineering.md` (the data flywheel this feeds), `planning-ai-applications.md` (the stack this realizes).
- Related skills: `kohavi-controlled-experiments` (A/B-testing changes; north-star metrics; response bias), `claude-api` (provider guardrails, prompt caching, tool use), `kleppmann-data-intensive-systems` (caching/observability/orchestration as general systems concepts), `mlsd-coach` (production system-design framing).
