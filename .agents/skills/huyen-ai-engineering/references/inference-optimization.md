# Inference Optimization: latency, throughput, and cost levers (Huyen Ch. 9)

## Produce
A **latency/cost diagnosis + optimization plan**: identify the bottleneck (compute-bound vs. memory-bandwidth-bound; prefill vs. decode), pick the right metrics (TTFT/TPOT/goodput, throughput, MFU/MBU), and choose model-level and service-level levers (quantization, attention/KV-cache opts, speculative decoding, batching, prefill/decode decoupling, prompt caching, parallelism) with their quality/cost tradeoffs.

Fire this when an LLM app is too slow or too expensive, when evaluating an inference service/framework or accelerator, or when reasoning about latency metrics. (Even API users benefit — it explains what you're paying for.)

## Trigger checks
- "My LLM app is too slow / too expensive — how do I fix it?"
- Latency metrics (TTFT, TPOT, throughput, goodput); percentiles; cost per token/request
- Quantization / KV cache / speculative decoding / batching / prompt caching / parallelism
- Choosing a GPU/accelerator or an inference framework (vLLM, TensorRT-LLM)
- "Why is decoding slow?" / prefill vs. decode / compute- vs. memory-bound
- Interview: "How would you reduce LLM latency/cost?" / "Explain the inference bottleneck"

## How to apply

### 1. Diagnose the bottleneck first (optimization = removing the binding constraint)
- **Compute-bound** (limited by FLOPs) vs. **memory-bandwidth-bound** (limited by data movement) — classified by **arithmetic intensity** (ops per byte; roofline chart). Image generation ≈ compute-bound; **autoregressive LLM inference ≈ memory-bandwidth-bound** (most current AI is bandwidth-bound).
- **Prefill vs. decode**: **prefill** processes input tokens in parallel → **compute-bound** (drives TTFT); **decode** generates one token at a time, loading weights each step → **memory-bandwidth-bound** (drives TPOT). They have different profiles, so production often **decouples** them.
- Compute-bound → more/faster FLOPs (more chips, higher FLOP/s). Bandwidth-bound → higher-bandwidth chips, quantization, KV-cache opts.

### 2. Pick the right metrics (don't optimize blind)
- **Latency** = TTFT + TPOT × (#output tokens). **TTFT** (prefill, input-length-dependent — must be instant for chat), **TPOT** (per-token; ~120 ms / 6–8 tok/s beats reading speed), TBT/ITL. Beware: model-side TTFT ≠ user-side ("time to publish") for CoT/agent queries with hidden steps. **Use percentiles (p50/p90/p95/p99), not averages** — one 3,000 ms outlier skews the mean.
- **Throughput** = output tokens/s (count input/output separately since prefill/decode differ); also RPS/RPM. Directly tied to **cost** (cost/1M tokens = $/h ÷ tok/s; sum prefill + decode cost per request). Latency↔throughput tradeoff (batching 2–3× throughput at TTFT/TPOT cost). → **goodput** = requests/s meeting the SLO (the metric that protects UX).
- **Utilization**: nvidia-smi "GPU utilization" is misleading (busy ≠ efficient). Use **MFU** (observed throughput ÷ theoretical peak FLOP/s; >50% good for training, lower for inference; prefill MFU > decode MFU) and **MBU** (bandwidth used ÷ peak = params × bytes/param × tok/s ÷ peak bandwidth — underscores why quantization helps). Goal is faster+cheaper, not max utilization.

### 3. Know the accelerator (the floor on speed/cost)
GPUs = thousands of small parallel cores (matmul-heavy ML); CPUs = few powerful cores. Evaluate a chip on **FLOP/s** (precision-dependent — lower precision = more ops/s), **memory size + bandwidth** (3-tier hierarchy: CPU DRAM 25–50 GB/s → GPU HBM 256 GB/s–1.5 TB/s → on-chip SRAM >10 TB/s but tiny), and **power** (H100 ≈ 7,000 kWh/yr; electricity is the scaling bottleneck). Inference-specialized chips favor low precision + fast memory over capacity (inference can be up to 90% of deployed ML cost). Three questions: can it run the workload? how fast? how much? (FLOP/s + memory size + bandwidth answer the first two.)

### 4. Model-level optimization (changes the model → may alter quality)
- **Model compression**: **quantization** (weight-only is the most popular, effective, out-of-the-box lever — 32→16 bit halves memory; near the 1-bit floor), **distillation** (small model mimics big), **pruning** (zero/remove params → sparse; harder, less common, hardware-dependent).
- **Overcome autoregressive decode**: **speculative decoding** (cheap draft model proposes K tokens, target verifies in parallel, accepts the longest agreed prefix — turns decode into prefill-like compute; lossless; ~50 LOC in PyTorch; in vLLM/TensorRT-LLM); **inference with reference** (copy draft tokens from the input — great for RAG/coding/multi-turn where output overlaps input; no extra model); **parallel decoding** (break sequential dependency — Lookahead/Jacobi, Medusa's multi-heads + tree attention; needs verification; harder to implement).
- **Attention optimization** (the transformer bottleneck): use a **KV cache** (store K/V vectors to avoid recompute; inference-only; grows linearly with sequence length × batch — can be 3× model weights / tens of GB). Three buckets: **redesign attention** (training-time: local windowed, multi-query, grouped-query, cross-layer attention — Character.AI cut KV cache 20×+), **optimize the KV cache** (vLLM's **PagedAttention**, KV-cache quantization/compression), **write kernels** (FlashAttention fuses ops).

### 5. Kernels + compilers
A **kernel** is hardware-specific optimized code (CUDA/Triton/ROCm) for hot routines (matmul, attention). Techniques: vectorization, parallelization, loop tiling, **operator fusion**. A **compiler** "lowers" model code to hardware, emitting kernels (torch.compile, XLA, TensorRT). PyTorch Llama-7B case: torch.compile → INT8 → INT4 → speculative decoding stacked for big throughput gains.

### 6. Service-level optimization (keeps model intact → no quality change)
- **Batching**: **static** (wait for full batch — first request waits for last), **dynamic** (max time window — caps latency, may underfill), **continuous/in-flight** (return finished responses immediately, slot in new requests — Orca/vLLM; best for variable output lengths).
- **Decouple prefill and decode** onto separate instances (prefill compute-bound + decode bandwidth-bound compete on one GPU, hurting both TTFT and TPOT). Ratio depends on workload/priority (long inputs + TTFT priority → 2:1–4:1; short inputs + TPOT priority → 1:2–1:1).
- **Prompt caching** (context/prefix cache): cache overlapping segments (system prompt, long doc, conversation history) so they're processed once. Huge for long system prompts / chat-with-a-book / multi-turn (Anthropic: up to 90% cost + 75% latency cut; Gemini 75% discount + storage fee). Costs memory.
- **Parallelism**: **replica** (copies — easy, more throughput/latency headroom, more chips; a bin-packing problem), **model/tensor** (split a too-big model across machines — tensor parallelism splits operators, reduces latency + enables big models, adds comms overhead), **pipeline** (stages across machines — adds per-request latency, used more in training), **context/sequence** (for long inputs).
- **Online vs. batch APIs**: online optimizes latency; batch optimizes cost (~50% cheaper, hours of turnaround — synthetic data, periodic reports, reprocessing). **Streaming** returns tokens as generated (lower perceived TTFT, but can't pre-score the response).

### 7. Match technique to workload (the most impactful levers)
Across use cases the biggest wins: **quantization** (general), **tensor parallelism** (latency + big models), **replica parallelism** (simple), **attention optimization** (transformer speed). Then: KV-cache opts matter most for **long context**; prompt caching for **overlapping prompts / multi-turn**; speculative decoding when MFU isn't already maxed.

## Common failure modes
- **Optimizing the average.** Reporting mean latency while a tail of outliers (p99) wrecks UX; use percentiles + goodput.
- **Throughput-only focus.** Maximizing tokens/s/cost and shipping bad UX; goodput (SLO-meeting requests) is the right north star.
- **nvidia-smi utilization theater.** Reading 100% "GPU utilization" as efficient when MFU is 20%.
- **Wrong bottleneck.** Buying higher-FLOP chips for a bandwidth-bound decode workload (or vice versa).
- **Prefill/decode on one box.** Letting prefill jobs starve decode jobs, tanking both TTFT and TPOT.
- **Model-level opts without re-eval.** Quantizing/pruning/distilling and assuming quality is unchanged (it can shift; different API providers show quality variation).
- **Ignoring prompt caching.** Reprocessing a 1,000-token system prompt on every one of a million daily calls.

## Interview signal
**AI-Engineer / FDE framing:** Senior signal = diagnosing **prefill (compute-bound, TTFT) vs. decode (memory-bandwidth-bound, TPOT)** before reaching for a fix, choosing **goodput** over raw throughput, and knowing the highest-leverage levers (quantization, KV-cache/attention opts, speculative decoding, continuous batching, prompt caching, prefill/decode decoupling). Even for API-only roles, explaining *why* output tokens cost ~2–4× input tokens and how prompt caching saves 90% reads as having operated real inference.
**One crisp talking point:** *"LLM inference splits into prefill — compute-bound, sets TTFT — and decode — memory-bandwidth-bound, sets TPOT — so I diagnose which is binding before optimizing, and I disaggregate them onto separate instances so prefill jobs don't starve decode. I track goodput, not raw throughput, because a service that's fast on average but blows the SLO on the tail is a bad experience. My default levers are quantization for memory/bandwidth, KV-cache and attention optimizations for long context, continuous batching for variable output lengths, and prompt caching for long system prompts — Anthropic's prompt cache alone is up to 90% cheaper."*

## Practitioner checklist
- [ ] Bottleneck identified (compute- vs. bandwidth-bound; prefill vs. decode) via roofline/arithmetic intensity
- [ ] Right metrics chosen: TTFT/TPOT in percentiles (not averages), throughput, **goodput** vs. SLO, MFU/MBU
- [ ] Cost modeled per request (prefill + decode); online vs. batch API decided; streaming considered
- [ ] Model-level levers chosen (quantization first; distillation/pruning/speculative decoding) with quality re-eval
- [ ] Attention/KV-cache optimized for long context (PagedAttention, GQA/MQA, FlashAttention)
- [ ] Service-level levers chosen (continuous batching, prefill/decode decoupling, prompt caching)
- [ ] Parallelism chosen for the constraint (replica for latency, tensor for big models, pipeline for training throughput)
- [ ] Accelerator matched to workload (FLOP/s for compute-bound, bandwidth/memory for bandwidth-bound)

## References
- *AI Engineering* (Huyen, O'Reilly 2024), Ch. 9 (pp. 773–851): Understanding Inference Optimization, Performance Metrics, AI Accelerators, Model Optimization, Kernels/Compilers, Inference Service Optimization.
- Sibling docs: `foundation-models.md` (prefill/decode, attention/KV mechanics origin), `finetuning.md` (quantization + numerical formats + memory math), `planning-ai-applications.md` (usefulness threshold: latency TTFT/TPOT + cost), `evaluating-ai-systems.md` (cost/latency as model-selection criteria; Pareto optimization), `architecture-and-user-feedback.md` (caching/routing in the full architecture).
- Related skills: `claude-api` (Anthropic prompt caching, batch API, streaming, per-token pricing), `kleppmann-data-intensive-systems` (throughput/latency/percentiles + caching as general systems concepts).
