---
name: huyen-ai-engineering
description: Apply Chip Huyen's "AI Engineering: Building Applications with Foundation Models" to build, evaluate, and ship production LLM/foundation-model applications. Use when the user is building or scoping an AI/LLM app, choosing or evaluating a foundation model (build-vs-buy, API-vs-self-host), designing or debugging evals/evaluation of open-ended LLM outputs (functional correctness, similarity, LLM-as-judge, comparative ranking, eval pipelines), doing prompt engineering or defending against prompt injection/jailbreaks, building RAG (retrieval, vector search, chunking, reranking, hybrid search) or agents (tools, planning, function calling, memory, failure modes), deciding finetuning vs. RAG vs. prompting (PEFT/LoRA/QLoRA, quantization), engineering training/finetuning datasets (curation, synthetic data, quality), optimizing inference (latency/TTFT/TPOT, throughput, cost, KV cache, batching, speculative decoding), designing end-to-end AI architecture (guardrails, routing, gateways, caching, observability, orchestration), building user-feedback loops / data flywheels, or prepping for AI-Engineer / Applied-AI / Anthropic-FDE / LLM-app-team interviews. Triggers: AI engineering, foundation models, LLM application, build LLM app, evals, LLM evaluation, evaluate LLM outputs, LLM-as-judge, prompt engineering, prompt injection, jailbreak, RAG, retrieval-augmented generation, vector search, embeddings retrieval, agents, tool use, function calling, agent planning, finetuning, LoRA, PEFT, QLoRA, quantization, RAG vs finetuning, dataset engineering, synthetic data, data flywheel, inference optimization, latency, TTFT, TPOT, throughput, KV cache, speculative decoding, prompt caching, model routing, guardrails, AI app architecture, observability, AI Engineer interview, Applied AI, FDE interview. Route to ONE reference file per task. DO NOT TRIGGER FOR: pure data-warehouse/dimensional modeling (kimball-dimensional-modeling), OLTP/distributed-systems internals (kleppmann-data-intensive-systems), online A/B-test statistics in isolation (kohavi-controlled-experiments), or classical (non-foundation-model) ML system design (mlsd-coach / huyen-ml-systems-design) — though those are natural siblings.
---

# huyen-ai-engineering

Book provenance: **Chip Huyen — AI Engineering: Building Applications with Foundation Models** (O'Reilly, 2024). This hub routes to a `references/*.md` file per task. Each reference makes you **produce an artifact** (decision tree, checklist, tradeoff table, diagnosis, or talking points) — not a summary — and carries an **Interview signal** subsection (AI-Engineer / FDE framing + one senior talking point) and a **practitioner checklist**.

## When to use

Use this hub when the user is building, evaluating, optimizing, or interviewing for **production foundation-model applications** — anything matching a trigger in the frontmatter. Route to **one** reference, read it fully, then execute that doc's process and output its artifact.

Don't improvise a hybrid of multiple references unless the user explicitly asks for a combined pass.

## The AI-engineering decision flow (at a glance)

The book's spine — **adaptation, not training; evaluation is the dominant hard problem; cheapest rung first**:

1. **Plan** the app: use-case tier → role of AI → usefulness threshold → last-mile plan → the 3-layer stack. → `planning-ai-applications`
2. **Understand the model** you'll use (data / architecture / size / post-training) and tune the cheap behavior levers (sampling, test-time compute). → `foundation-models`
3. **Evaluate** — the crown jewel, two docs: pick the *method* (functional correctness → similarity → LLM-as-judge → comparative), then build the *pipeline* + select the model. → `evaluation-methodology` + `evaluating-ai-systems`
4. **Adapt, cheapest rung first**: **prompt** → **RAG** (facts) / **agents** (tools+actions) → **finetune** (form). → `prompt-engineering`, `rag-and-retrieval`, `agents`, `finetuning`
5. Feed it **data** (curation, synthesis, quality). → `dataset-engineering`
6. Make it **fast + cheap** (latency/throughput/cost levers). → `inference-optimization`
7. **Assemble + observe + learn**: end-to-end architecture, guardrails, routing, caching, monitoring, and the user-feedback **data flywheel**. → `architecture-and-user-feedback`

> Mantra: *finetuning is for form, RAG is for facts; exhaust prompting first; and an eval pipeline is what turns a demo into a product.*

## Quick routing

| User cue (examples) | Reference |
|---|---|
| "Should we build this AI feature?", build-vs-buy, role of AI, success metrics/usefulness threshold, scoping an LLM app, the AI stack, AI-vs-ML engineering | `references/planning-ai-applications.md` |
| Why is the model inconsistent/hallucinating?, temperature/top-p/top-k, sampling, transformers/attention, RLHF, scaling laws, structured output, params vs. tokens vs. FLOPs | `references/foundation-models.md` |
| How do I score/grade open-ended LLM outputs?, exact match vs. BLEU vs. embeddings vs. LLM-as-judge, comparative ranking/Elo, perplexity, flaky evals | `references/evaluation-methodology.md` |
| Build an eval pipeline, what criteria/metrics (factual consistency, safety, instruction-following), model selection, build-vs-buy axes, public benchmarks/contamination, eval-set size | `references/evaluating-ai-systems.md` |
| Write/improve prompts, few-shot/CoT/system prompts, prompt versioning, prompt injection/jailbreak defenses, guardrail violation vs. false-refusal rate | `references/prompt-engineering.md` |
| Build/improve RAG, term vs. embedding vs. hybrid retrieval, vector DB/ANN, chunking, reranking, query rewriting, RAG-vs-long-context, multimodal/tabular RAG | `references/rag-and-retrieval.md` |
| Build an agent, tools/function calling, planning (plan→validate→execute, ReAct/Reflexion), memory, agent failure modes/evaluation | `references/agents.md` |
| Should I finetune? finetune vs. RAG vs. prompt, PEFT/LoRA/QLoRA, quantization, finetuning memory math, model merging, distillation | `references/finetuning.md` |
| What/how-much training data?, data quality/coverage/quantity, annotation guidelines, synthetic data, data flywheel, model collapse | `references/dataset-engineering.md` |
| App too slow/expensive, TTFT/TPOT/throughput/goodput, KV cache, speculative decoding, batching, prompt caching, parallelism, choosing a GPU/inference framework | `references/inference-optimization.md` |
| End-to-end AI architecture, guardrails, model router/gateway, caching (exact/semantic), observability (logs/traces/drift), orchestration, user feedback / data flywheel | `references/architecture-and-user-feedback.md` |

## How to apply

1. Match the request to a **Quick routing** row (or a frontmatter trigger).
2. Read the corresponding `references/` file in full.
3. Follow that reference's "How to apply" steps and produce its **artifact** (decision, checklist, tradeoff table, diagnosis, or interview talking points).
4. For interview prep, surface that doc's **Interview signal** subsection.
5. Return the artifact; add cross-references to sibling docs only when the task spans rungs (e.g., "prompt vs. RAG vs. finetune").

## Common failure modes (hub-level)

- **Skipping eval.** Jumping to prompt/RAG/finetune without an eval pipeline — the book's central warning ("evals are surprisingly often all you need"; evaluation is the biggest bottleneck to AI adoption).
- **Wrong rung.** Reaching for finetuning when prompting/RAG would do, or finetuning for facts (that's RAG) — see `finetuning`.
- **Router-only answer.** Summarizing this hub without loading the reference's full framework.
- **Demo-as-product.** Forgetting the last-mile (60→100) reality from `planning-ai-applications`.
- **Hybrid drift.** Blending multiple references' processes unless a combined pass was requested.

## References

- [references/planning-ai-applications.md](references/planning-ai-applications.md) — Ch. 1: use-case selection, build-vs-buy, role of AI, defensibility, usefulness threshold, the AI-engineering stack, what changed vs. traditional ML.
- [references/foundation-models.md](references/foundation-models.md) — Ch. 2: reading a model (data/architecture/size/post-training/RLHF) + tuning the sampling knobs (temperature/top-k/top-p, test-time compute, structured output, inconsistency vs. hallucination).
- [references/evaluation-methodology.md](references/evaluation-methodology.md) — Ch. 3 (crown jewel): choosing the eval method — functional correctness → similarity → AI-as-judge → comparative ranking; LM metrics (perplexity/cross-entropy).
- [references/evaluating-ai-systems.md](references/evaluating-ai-systems.md) — Ch. 4 (crown jewel): eval criteria, model selection (build-vs-buy, benchmarks, contamination), and building the evaluation pipeline.
- [references/prompt-engineering.md](references/prompt-engineering.md) — Ch. 5: effective prompts (in-context learning, CoT, decomposition, versioning) + defensive prompting (injection/jailbreak defenses).
- [references/rag-and-retrieval.md](references/rag-and-retrieval.md) — Ch. 6 (RAG half): retrieval algorithms (term/embedding/hybrid), vector search, chunking, reranking, query rewriting, multimodal/tabular RAG, retrieval eval.
- [references/agents.md](references/agents.md) — Ch. 6 (agents half): tools, planning, function calling, memory, agent failure modes & evaluation.
- [references/finetuning.md](references/finetuning.md) — Ch. 7: when to finetune (vs. RAG vs. prompt), memory math, quantization, PEFT/LoRA/QLoRA, model merging.
- [references/dataset-engineering.md](references/dataset-engineering.md) — Ch. 8: curation (quality/coverage/quantity), acquisition/annotation, augmentation & synthesis, verification, data flywheel.
- [references/inference-optimization.md](references/inference-optimization.md) — Ch. 9: bottlenecks (prefill/decode, compute vs. bandwidth), metrics (TTFT/TPOT/goodput/MFU/MBU), model- and service-level levers.
- [references/architecture-and-user-feedback.md](references/architecture-and-user-feedback.md) — Ch. 10: end-to-end architecture (context/guardrails/router/gateway/cache/agent), observability, orchestration, and user feedback.

- **Book:** Chip Huyen — *AI Engineering: Building Applications with Foundation Models* (O'Reilly, 2024).
- **Sibling skills:** `claude-api` (Anthropic SDK — model ids, pricing, sampling, tool use, caching; pair with most references), `kohavi-controlled-experiments` (online A/B testing — complements offline/comparative eval), `mlsd-coach` (ML system-design interview drill), and companion `huyen-ml-systems-design` (Huyen's earlier *Designing Machine Learning Systems* — classical ML lifecycle; this skill is the foundation-model successor).
