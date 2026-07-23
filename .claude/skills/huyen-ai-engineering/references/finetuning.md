# Finetuning: when (vs. RAG vs. prompt) and how (PEFT/LoRA/quantization) (Huyen Ch. 7)

## Produce
An **adaptation decision + finetuning plan**: a verdict on prompt → RAG → finetune (with the *information vs. behavior* diagnosis), and if finetuning, the technique choice (full / partial / PEFT-LoRA / QLoRA / merging), a memory-footprint estimate, and the base-model + framework + hyperparameter picks.

Fire this when someone asks "should I finetune?", "finetune vs. RAG vs. prompt?", or is choosing/configuring a finetuning method (LoRA rank, QLoRA, model merging). This is the most resource-intensive adaptation rung — gate it behind the decision framework.

## Trigger checks
- "Should I finetune my model?" / "finetune vs. RAG vs. prompt engineering?"
- LoRA / PEFT / QLoRA / adapters / how much GPU memory to finetune
- "Will finetuning fix this?" (wrong facts vs. wrong format/style)
- Model merging, multi-task finetuning, distillation, quantization for memory
- Interview: "When would you finetune?" / "Explain LoRA / PEFT / quantization"

## How to apply

### 1. Decide: should you finetune at all? (the framework)
Finetuning adjusts weights; it's costlier than prompting in data, hardware, AND ML talent. **Try prompting first** (systematically — the common anti-pattern is "prompting doesn't work" after minimal, unsystematic prompt experiments). Finetuning is **transfer learning** — it improves *sample efficiency* (hundreds of examples, not millions) by "unlocking capabilities the model already has."
**Reasons to finetune**: improve task/domain quality, enforce **structured-output format** (its most common use), mitigate bias (curated counter-data), distill a big model into a small one, or beat a much larger model on a narrow task (Grammarly's finetuned Flan-T5 beat a GPT-3 variant at 60× smaller).
**Reasons NOT to**: it can **degrade other tasks** (finetune for "change orders" → worse at recommendations; fix by finetuning on all tasks or using separate/merged models); high up-front cost + continual maintenance (data, ML training knowledge, serving, and the fast-moving-base-model treadmill — a new base may outpace your finetune). Beware "general models can't do domain tasks" — GPT-4-0314 beat the purpose-built BloombergGPT on financial benchmarks.

### 2. Finetuning vs. RAG: diagnose the failure
**Finetuning is for form; RAG is for facts.**
- **Information-based failures** (wrong/outdated/missing facts, hallucination) → **RAG**. RAG beat finetuning on current-events QA (and RAG+base beat RAG+finetuned — finetuning can hurt elsewhere).
- **Behavior-based failures** (correct but irrelevant, or wrong output format/syntax — semantic parsing, uncommon SQL dialects, malformed HTML) → **finetuning**.
If both: **start with RAG** (easier — no training data/hosting; begin with BM25, not vector DBs). They're complementary (RAG on a finetuned model helped 43% of the time in one study — but not the other 57%).

### 3. The adaptation workflow (define eval first)
Before any adaptation, **define eval criteria + pipeline** (Ch. 4). Then: (1) prompt → (2) add examples (1–50) → (3) if missing info, RAG (start term-based) → (4) branch: more-advanced RAG for persisting info failures, **finetune for persisting behavior failures** (note: advanced RAG adds *inference* complexity; finetuning adds *model-development* complexity but leaves inference unchanged) → (5) combine RAG + finetuning.

### 4. Understand the memory bottleneck (back-of-napkin math)
Memory is *the* finetuning bottleneck; finetuning needs far more than inference because of backpropagation. Footprint drivers: **# params, # trainable params, numerical precision.**
- **Inference** ≈ N × M × 1.2 (weights + ~20% activations/KV). 13B @ 2 bytes ≈ 26 GB × 1.2 ≈ 31 GB; 70B ≈ 140 GB for weights.
- **Training** = weights + activations + **gradients + optimizer states** (scale with *trainable* params). Each trainable param: 1 gradient + 0–2 optimizer states (SGD 0, momentum 1, **Adam 2**). 13B full-finetune w/ Adam @ 2 bytes = 13B × 3 × 2 = **78 GB** just for grads+optimizer; 1B trainable = only 6 GB. (Activation memory can dwarf weights; mitigate with **gradient checkpointing**/recomputation.)
- **Two levers to fit hardware**: reduce trainable params (→ PEFT) or reduce precision (→ quantization). Or use hardware better (CPU offloading/DeepSpeed).

### 5. Quantization (the cheap memory win)
Convert to fewer bits — straightforward, generalizes. FP32(4B)/FP16/BF16(2B)/INT8/INT4. **BF16 = more range, less precision than FP16** (load a model in the format it was released in — Llama 2 was BF16; loading as FP16 degraded it). **Inference**: lower precision is standard (PTQ — post-training quantization — is most common and free in PyTorch/TF/HF); also speeds compute + bigger batches. **Training** is precision-sensitive → **mixed precision** (high-precision weight copy + low-precision grads/activations) or QAT (learn to be good at low precision). 1-bit frontier (BitNet b1.58 ≈ 16-bit Llama 2 up to 3.9B). Downside: small value changes compound; out-of-range → inf.

### 6. PEFT and LoRA (the dominant technique)
Full finetuning = all params trainable (7B FP16 + Adam ≈ 56 GB — exceeds most GPUs). Partial finetuning (freeze layers) is *parameter-inefficient* (~25% of params for full-finetune parity). **PEFT** = full-finetune-level performance with orders-of-magnitude fewer trainable params (Houlsby adapters: within 0.4% of full finetuning at 3% trainable). Two buckets: **adapter-based** (add modules — LoRA, BitFit, IA3) and **soft prompts** (trainable continuous vectors prepended to input — prefix/P/prompt tuning).
**LoRA** (dominant): decompose a weight matrix W into A(n×r)·B(r×m), train only A,B, merge back (W' = W + (α/r)·AB) — **no extra inference latency** (unlike adapter layers). Works because pre-trained LLMs have low **intrinsic dimension** (4.7M trainable for GPT-3 = 0.0027% of full). Config: apply to attention matrices (W_q,W_k,W_v,W_o — if only two, **query+value**); **rank r ≈ 4–64** usually enough (bigger r often doesn't help, can overfit); α:r ratio ~1:8–8:1 (experiment). **Multi-LoRA serving**: keep adapters separate → one base W + N small (A,B) pairs (100 customers: 1.68B params merged vs. 23.3M separate) + fast task-switching (Apple ships per-feature adapters on-device). **QLoRA**: store weights in 4-bit (NF4), dequant to BF16 for compute + paged optimizers → 65B finetuned on one 48 GB GPU (reducing LoRA *params* barely helps — quantize the *base weights*). Tradeoff: quant/dequant adds training time.

### 7. Model merging + multi-task (combine models)
Merging combines multiple models (often same-base finetunes) into one for better performance and/or smaller footprint — can run without GPUs. Best path for **multi-task** (vs. simultaneous finetuning = more data, or sequential = **catastrophic forgetting**): finetune per task in parallel, then merge. Approaches: **summing** (linear combination / SLERP; **task vectors** = finetuned − base enable task arithmetic; prune redundant params first — TIES/DARE), **layer stacking** (frankenmerging; build MoE / upscale, needs further finetuning), **concatenation** (not recommended — no memory savings). Distinct from **ensembling** (combine outputs, keep models intact — higher inference cost).

## Common failure modes
- **Finetuning before systematic prompting.** Jumping to finetune after weak prompt experiments; usually prompting was the unfixed problem.
- **Finetuning for facts.** Trying to inject knowledge/freshness via finetuning — that's RAG's job; finetuning can even worsen hallucination on low-quality data.
- **Single-task tunnel vision.** Finetuning for one query type and silently degrading the others.
- **Wrong precision load.** Loading a BF16 model as FP16 (or vice versa) and blaming the model for poor quality.
- **Memory surprise.** Not estimating grads+optimizer (Adam ×3) before picking hardware → OOM.
- **Cranking LoRA rank.** Assuming bigger r = better; it plateaus and can overfit; quantizing base weights (QLoRA) saves far more than shrinking adapters.
- **Sequential multi-task finetuning.** Inducing catastrophic forgetting instead of parallel-finetune-then-merge.
- **Ignoring the base-model treadmill.** Finetuning without a policy for when a new base model outpaces your finetune.

## Interview signal
**AI-Engineer / FDE framing:** The classic question is "finetune vs. RAG vs. prompt?" — the senior answer is the **information-vs-behavior diagnosis** ("finetuning is for form, RAG is for facts; start with RAG if both") plus knowing the memory math (Adam ×3 trainable params) and *why* LoRA/PEFT work (low intrinsic dimension; LoRA merges back so no inference latency; QLoRA quantizes the base, not the adapter). FDE loops value that you gate finetuning behind prompting + eval, not reach for it first.
**One crisp talking point:** *"Finetuning is for form, RAG is for facts — so I diagnose the failure first: wrong or stale information goes to RAG, wrong format or style goes to finetuning, and if it's both I start with RAG because it's cheaper to operate. When I do finetune I reach for LoRA — it hits near-full-finetune quality at a fraction of a percent of trainable params because pre-trained models have low intrinsic dimension, and it merges back into the weights so there's no inference latency. For memory I quantize the base with QLoRA rather than shrinking the adapter, since the optimizer states under Adam — three values per trainable param — are what actually blow up the footprint."*

## Practitioner checklist
- [ ] Prompting exhausted systematically before considering finetuning
- [ ] Failure diagnosed: information-based → RAG, behavior-based → finetune (both → start RAG)
- [ ] Eval criteria + pipeline defined before adapting; progress benchmarked at each step
- [ ] Memory estimated (weights + activations + grads + optimizer; Adam ×3 on trainable params) vs. hardware
- [ ] Technique chosen: full / partial / **LoRA** / **QLoRA** / merging — with rationale
- [ ] LoRA configured (target matrices incl. query+value; rank 4–64; α:r tuned); serving mode (merged vs. multi-LoRA) chosen
- [ ] Quantization plan (PTQ for inference; mixed-precision/QAT for training); model loaded in its intended format
- [ ] Multi-task via parallel-finetune-then-merge (avoid catastrophic forgetting); base-model-upgrade policy set

## References
- *AI Engineering* (Huyen, O'Reilly 2024), Ch. 7 (pp. 594–693): Finetuning Overview, When to Finetune, Finetuning vs. RAG, Memory Bottlenecks, Quantization, PEFT/LoRA/QLoRA, Model Merging, Finetuning Tactics.
- Sibling docs: `prompt-engineering.md` + `rag-and-retrieval.md` (the cheaper rungs to exhaust first), `foundation-models.md` (pre/post-training, structured outputs, classifier heads), `dataset-engineering.md` (the instruction/preference data finetuning needs; distillation), `inference-optimization.md` (quantization for serving; deeper memory math), `evaluating-ai-systems.md` (eval pipeline that gates each rung).
- Related skills: `claude-api` (which models support finetuning + how), `mlsd-coach` (adaptation choice in a system-design answer).
