# Foundation Models: reading a model + tuning the sampling knobs (Huyen Ch. 2)

## Produce
Two artifacts: (1) a **model-capability read** — from a model's training data, architecture, size, and post-training, a justified prediction of where it'll be strong/weak and how aligned it is; and (2) a **sampling-knob prescription** — temperature / top-k / top-p / stopping / test-time-compute / structured-output settings tuned to the task, plus a diagnosis of inconsistency/hallucination rooted in the sampling mechanism.

Fire this when someone needs to *understand or configure a model's behavior* — not when scoring outputs (→ `evaluation-methodology` / `evaluating-ai-systems`) or deciding to finetune (→ `finetuning`).

## Trigger checks
- "Why is the model inconsistent / why did it hallucinate?" (and what knob fixes it)
- "What temperature/top-p should I use?" / outputs too boring or too unhinged
- "Why is this model bad at <language/domain>?" / picking a model by data provenance
- "How big a model / GPU do I need?" / parameters vs. tokens vs. FLOPs questions
- Getting reliable JSON/structured output out of a model
- Interview: explain transformers/attention, RLHF, scaling laws, sampling, or hallucination causes

## How to apply

### 1. Read the model from its three levers
Differences trace to **training data**, **architecture + size**, and **post-training**.
- **Training data → capability ceiling.** "A model is only as good as its data." No Vietnamese in → can't translate Vietnamese. English ~46% of Common Crawl → general models far better in English; low-resource languages are worse *and* slower/costlier (Burmese needs ~10× the tokens of English for the same meaning → 10× latency and per-token cost). Domain gaps (protein, fMRI) need curated domain models (AlphaFold, Med-PaLM2). Provenance is a clue: Reddit≥3-upvotes filter, C4, proprietary deals all signal strengths/blind spots.
- **Architecture.** Transformer (attention: Q·K scored, weights V) dominates; it killed seq2seq's two bottlenecks (single-hidden-state + sequential input) by parallelizing input processing. Inference is two phases: **prefill** (parallel, builds K/V for all input tokens) then **decode** (sequential, one token at a time — the latency bottleneck). KV cache growth is why long context is hard. Alternatives (RWKV, SSMs → Mamba, Jamba) chase linear-time long-context but don't change the adaptation playbook.
- **Size — three scale numbers.** **# parameters** (learning capacity; ~2 bytes/param → 7B ≈ 14GB GPU min for inference), **# training tokens** (how much it learned), **# FLOPs** (training cost). Sparsity/MoE breaks the naive count: Mixtral 8x7B = 46.7B params but only ~12.9B active/token → costs like a 12.9B model. Newer-gen beats older same-size (Llama 3-8B > Llama 2-70B on MMLU).
- **Post-training → alignment + usability.** Pre-training optimizes *token-level* completion (a rogue "monster"); post-training optimizes *whole-response* preference. Two steps: **SFT** (behavior-cloning on (prompt, response) demonstration data — turns completion into conversation) then **preference finetuning** (RLHF / DPO / RLAIF — aligns to human preference). Approximate alignment by what steps the maker took.

### 2. Know the RLHF mechanics (interview-critical)
RLHF = (a) train a **reward model** on **comparison data** (prompt, winning, losing) — comparison beats pointwise scoring because absolute scores are noisy; inter-labeler agreement ~73%; a *weaker* model can judge a stronger one (judging is easier than generating); then (b) optimize the SFT model (PPO) to maximize RM score. DPO (Llama 3) drops the RL loop for simplicity. **best-of-N**: skip RL, generate N, keep the RM's top pick.

### 3. Prescribe the sampling knobs
Sampling is why outputs are probabilistic — and the cheapest performance lever.
- **Temperature** — divides logits before softmax. Higher → flatter distribution, more creative/less coherent; lower → sharper, more consistent/boring. ~0.7 balances; T=0 ≈ greedy (pick max logit). Greedy is fine for classification, dull for generation.
- **Top-k** — softmax over only the top k logits (k ≈ 50–500); cuts compute, smaller k = more predictable.
- **Top-p (nucleus)** — smallest set whose cumulative prob ≥ p (≈0.9–0.95); adapts the candidate count to context (2 for yes/no, many for open questions).
- **Stopping** — fixed length (risks mid-sentence cut) or stop tokens/EOS; trades latency/cost vs. malformed output (truncated JSON).
- **Logprobs** — expose them where you can: gold for classification, eval, and debugging ("if probabilities look random, the model hasn't learned").

### 4. Use test-time compute when one sample isn't enough
Generate multiple outputs, then select: highest **average logprob** (length-normalized), **reward-model/verifier** score (a verifier gave ~the boost of a 30× bigger model on math), **majority vote / self-consistency** (Gemini sampled 32 on MMLU), or app heuristic (shortest, first-valid, valid-SQL). Diversify via varied sampling vars. Gains plateau (OpenAI: ~400) and cost scales ~linearly. Latency trick: generate in parallel, show first valid. The less robust the model, the more this helps — but a brittle model is better swapped out.

### 5. Force structured output at the right layer
Five layers, cheapest→strongest: **prompting** (first line; not guaranteed) → **post-processing** (cheap, fixes common repeated mistakes; LinkedIn's defensive YAML parser 90%→99.99%) → **test-time compute** (regenerate until valid) → **constrained sampling** (filter logits by a grammar each step; reliable but per-format grammar, adds latency, less general) → **finetuning** (most general/reliable; classifier head guarantees valid classes). First three are bandages; last two are intensive. Prefer YAML over JSON (fewer tokens).

### 6. Diagnose inconsistency vs. hallucination
- **Inconsistency** = randomness in sampling. Same input→different output, or tiny input change→big output change. Mitigate: cache, fix temperature/top-p/top-k + **seed** (still no 100% guarantee — hardware differs). Slightly-different-input case is harder; lean on prompts + memory.
- **Hallucination** = output not grounded in facts; *not* fully explained by sampling. Two complementary hypotheses: **self-delusion / snowballing** (model can't tell its own generated tokens from given facts; one wrong token compounds) and **knowledge mismatch** (SFT trains it to mimic labeler knowledge it doesn't have → taught to make things up). Mitigations: ask for sources/verification, reward functions that punish fabrication, "say I don't know," concise answers (fewer tokens = less room to fabricate), plus RAG/context (Ch. 6). Note RLHF's effect is mixed (helped per Schulman; worse for InstructGPT).

## Scaling-law talking points
- **Chinchilla**: for compute-optimal training, training tokens ≈ **20× params**; scale model and data equally. Assumes data cheaper than compute; built for dense models on human data (sparse/synthetic = open research).
- **Quality isn't everything in production**: Llama deliberately chose smaller-than-optimal models for usability/cheap inference (Sardana et al. add inference demand to Chinchilla).
- **Last-mile economics**: cost for a fixed accuracy keeps dropping, but each marginal point gets dramatically pricier (cross-entropy 3.4→2.8 nats ≈ 10× data) — yet small loss deltas can mean big downstream-quality differences.
- **Scaling bottlenecks**: running out of public internet **data** (proprietary data becomes the moat; web increasingly AI-generated → model-collapse worry) and **electricity** (data centers 1–2%→4–20% of global power by 2030).
- **Inverse scaling / emergent abilities**: bigger isn't always better (memorization, strong-prior tasks); some abilities only appear at scale, making extrapolation hard.

## Common failure modes
- **Translate-through-English fallacy.** Routing low-resource queries via English loses information (e.g., Vietnamese relational pronouns collapse to I/you) and assumes the model already understands the language.
- **Param-count tunnel vision.** Quoting params while ignoring sparsity/MoE active-params, training tokens, and generation gap.
- **Greedy/T=0 everywhere.** Determinism for classification is fine; for generation it's flat and dull.
- **JSON-mode = correct content.** JSON mode only guarantees valid JSON syntax, not correct fields, and truncation still breaks parsing.
- **Treating hallucination as a sampling bug.** Lowering temperature won't fix factuality; it's a grounding/knowledge problem.
- **Trusting fixed-seed reproducibility.** Same seed ≠ identical output across different hardware/providers.

## Interview signal
**AI-Engineer / FDE framing:** Interviewers want to see that you reach for the *cheapest* behavior lever first — sampling knobs and test-time compute before finetuning — and that you can name *why* a model fails (data provenance, sampling randomness vs. knowledge mismatch) rather than just "the model is bad." Being able to walk attention → prefill/decode → KV cache (and tie it to latency in Ch. 9) reads as senior.
**One crisp talking point:** *"Inconsistency and hallucination are different bugs. Inconsistency is sampling randomness — I fix temperature, top-p, and seed, and cache. Hallucination is grounding — no temperature setting fixes it; I add retrieval, ask for sources, and select across samples with a verifier. Sampling is the most underrated, cheapest lever before I touch weights."*

## Practitioner checklist
- [ ] Model's likely strengths/weaknesses read from training data (language, domain, provenance)
- [ ] Scale understood on all three axes (params incl. sparsity/MoE active, tokens, FLOPs) + GPU memory estimate
- [ ] Post-training pipeline identified (SFT? preference? RLHF/DPO/RLAIF?) → alignment expectation set
- [ ] Sampling knobs set for the task (temperature, top-k/top-p, stopping) with a reason per knob
- [ ] Test-time-compute decision (N, selection method) with cost/plateau acknowledged
- [ ] Structured-output layer chosen (prompt → post-process → constrained → finetune) to fit the validity bar
- [ ] Failure diagnosis separates inconsistency (sampling) from hallucination (grounding)

## References
- *AI Engineering* (Huyen, O'Reilly 2024), Ch. 2 (pp. 119–231): Training Data, Modeling (architecture, size, scaling laws), Post-Training (SFT, RLHF/DPO), Sampling, Test-Time Compute, Structured Outputs, Probabilistic Nature.
- Sibling docs: `evaluation-methodology.md` (cross-entropy/perplexity defined; AI-as-judge mechanics), `finetuning.md` (when to update weights, classifier heads), `inference-optimization.md` (prefill/decode/KV-cache turned into latency levers), `dataset-engineering.md` (the demonstration/comparison data behind post-training).
- Related skill: `claude-api` for Anthropic-specific sampling params, logprobs availability, and model ids.
