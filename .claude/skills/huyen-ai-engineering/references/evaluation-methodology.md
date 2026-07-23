# Evaluation Methodology: choosing how to score open-ended outputs (Huyen Ch. 3)

## Produce
An **evaluation-method selection** for a given task: which scoring approach (functional correctness → exact-match/lexical/semantic similarity → AI-as-judge → comparative ranking) fits the output type, *why the alternatives were rejected*, the metric definitions, the judge spec (model + prompt + scoring system), and the bias/limitation guardrails. Paired with `evaluating-ai-systems.md` (Ch. 4), which assembles these methods into a pipeline.

Fire this when someone needs to decide *how to measure* an LLM's output quality — the method, not yet the full pipeline. This is the crown-jewel pairing of the bundle; give it weight.

## Trigger checks
- "How do I evaluate / score / grade my LLM's outputs?" / "evals for X"
- Choosing between exact match, BLEU/ROUGE, embedding similarity, LLM-as-judge
- Setting up an LLM-as-a-judge and worried it's circular/unreliable
- Ranking/comparing models (LMSYS-style, Elo, win rate, leaderboards)
- "Why is my eval flaky / not reproducible?" / interpreting perplexity, cross-entropy
- Interview: "How would you evaluate an open-ended LLM system?" / "Is LLM-as-judge trustworthy?"

## Why FM evaluation is hard (frame the problem first)
1. **Smarter models are harder to grade** — you can't grade a PhD proof by how it sounds; you must fact-check, reason, bring domain expertise → eval gets expensive for sophisticated tasks.
2. **Open-ended kills ground-truth matching** — infinite correct responses; no exhaustive reference list.
3. **Models are black boxes** — provider opacity means you often evaluate by outputs alone.
4. **Benchmarks saturate fast** — GLUE→SuperGLUE in a year; MMLU→MMLU-Pro. Public benchmarks are inadequate and contamination-prone.
5. **Scope expanded** — for general-purpose models, eval must also *discover* new capabilities, not just measure known tasks.
The field under-invests in eval relative to modeling. Don't settle for "word of mouth"/"vibe check"/eyeballing — it's the #1 hidden risk and slows iteration.

## How to apply (the method-selection ladder — try exact first, climb only as needed)

### 1. Can functional correctness be automated? → use it
The ultimate metric: does the system do what it's intended to? Automatable when there's a measurable objective: code (execution accuracy via unit tests → **pass@k**: solved if any of k samples pass all tests; pass@1 < pass@3 < pass@10), text-to-SQL (Spider, BIRD-SQL), game bots (score), optimization (energy saved). Benchmarks: HumanEval, MBPP. If functional correctness is automatable, you rarely need anything subjective.

### 2. Is there reference data? → similarity measurement (exact scores)
Each example is (input, reference responses); references = ground truths/canonical (human- or AI-generated). Four similarity routes, in order of strength:
- **Exact match** — binary; works only for short exact answers (math, trivia). "Contains reference" variant can wrongly accept ("Sept 12, 1929" for a born-year of 1929). Breaks for translation/anything with many valid forms.
- **Lexical similarity** — token/n-gram overlap or edit distance (fuzzy matching). Metrics: BLEU, ROUGE, METEOR, TER, CIDEr. Drawbacks: needs a *comprehensive* reference set (correct answers missing → unfairly low, cf. Fuyu captions); references can be *wrong* (WMT'23); high lexical ≠ better (BLEU similar for correct/incorrect HumanEval solutions). Fading since FMs.
- **Semantic similarity (embedding similarity)** — embed both, compare with **cosine similarity** (1 = identical, −1 = opposite). Metrics: BERTScore, MoverScore. Needs a smaller reference set than lexical, but reliability rides on embedding quality and costs compute. (Technically subjective — embeddings differ by algorithm — but the score given two embeddings is exact.)
- **Ask an evaluator** (human or AI) whether two texts match → leads into AI-as-judge.

> Embedding primer: an embedding is a vector (typically 100–10,000 dims) capturing meaning; good if more-similar items have closer embeddings (MTEB benchmark). Backbone of vector search (Ch. 6), dedup (Ch. 8), clustering, ranking, anomaly detection. CLIP-style joint/multimodal embeddings enable cross-modal (text↔image) comparison.

### 3. No reference / subjective criteria? → AI as a judge
Now the dominant production method (LangChain 2023: 58% of evals). Three usage patterns: **(a) score a response by itself** given the question; **(b) compare to a reference** (True/False same?); **(c) compare two responses** (A or B — also generates preference data for post-training, test-time compute, comparative ranking).
- **Why it works**: fast, cheap vs. humans, no reference needed, criteria-flexible (correctness, toxicity, hallucination, "sounds like Gandalf"), and *explains* its decision (auditable). Strong human correlation in cases (GPT-4↔human 85% on MT-Bench, above human–human 81%; AlpacaEval 0.98 to Chat Arena). Even imperfect, often good enough to get a project off the ground.
- **Spec a judge = model + prompt + sampling params** (change any → different judge). Prompt must state: (1) the task, (2) the criteria (detailed), (3) the scoring system. **Scoring system rules**: classification > numerical for AI judges; discrete > continuous; wider discrete ranges get worse (use ~1–5); include per-score examples + justifications.

### 4. Ranking many models? → comparative evaluation
Pointwise (score each, then rank) vs. **comparative** (models compete; rank from win rates). Comparative is easier for subjective quality ("which song is better" beats "score this song") and powers LMSYS Chatbot Arena. Mechanics: each **match** → winner (allow ties); win rate = % A beats B; a **rating algorithm** (Elo, **Bradley–Terry**, TrueSkill) turns comparisons into scores. (LMSYS moved Elo→Bradley–Terry: Elo was sensitive to evaluator/prompt order.) Ranking is a *predictive* problem — quality = how well it predicts future matches; no ground-truth ranking.

## Language-modeling metrics (interpret, don't fear the math)
- **Entropy** — average information per token; lower = more predictable language.
- **Cross-entropy** H(P,Q) = H(P) + D_KL(P‖Q) — how hard it is for model Q to predict data P; minimized in training; perfect learning → KL=0. Units: **bits** (base 2) or **nats** (base e — PyTorch/TF default).
- **BPC / BPB** — bits per character/byte; cross-entropy normalized for tokenizer/encoding differences → cross-model comparable; also = text compression efficiency.
- **Perplexity (PPL)** = exponential of cross-entropy; "how much uncertainty predicting the next token." Rules of thumb: more *structured* data → lower PPL (HTML < prose); bigger *vocab* → higher PPL; longer *context* → lower PPL. **Uses beyond training**: capability proxy (lower PPL → better downstream, usually); **data-contamination detection** (low PPL on a benchmark ⇒ likely in training data ⇒ distrust the score); **dedup** (add new data only if its PPL is high); **abnormal-text detection** (gibberish → high PPL). **Warning**: post-training (SFT/RLHF) and quantization can *raise* PPL even as task quality improves ("post-training collapses entropy") — PPL is a weak proxy for post-trained models.

## AI-as-judge limitations and biases (the guardrails)
- **Inconsistency** — same input → different scores; mitigate with sampling vars + examples (Zheng: 65%→77.5% consistency) but high consistency ≠ high accuracy, and examples 4× the cost.
- **Criteria ambiguity / non-standardization** — "faithfulness" differs across MLflow (1–5), Ragas (0/1), LlamaIndex (YES/NO); scores aren't comparable across tools, and the judge can drift over time (silently breaking month-over-month tracking). **Rule: don't trust any judge whose model + prompt you can't see; freeze the judge while the app evolves.**
- **Cost & latency** — judging with GPT-4 ~doubles calls per criterion (3 criteria → 4× calls); mitigate with weaker/specialized judges + **spot-checking** (sample a subset, trade confidence for cost). As an inline guardrail, judging before returning adds latency.
- **Biases**: **self-bias** (favors own outputs — GPT-4 +10%, Claude-v1 +25% win rate), **first-position bias** (mitigate: swap orderings / repeat; humans have the opposite, *recency* bias), **verbosity bias** (prefers longer even with errors; weaker in stronger models). Plus privacy/IP if using a proprietary judge.
- **Always supplement** AI judges with exact and/or human evaluation.

## What model can be the judge?
- **Stronger judge** — best judgments + can improve weaker models; but the strongest model has no judge, and you still need a way to rank.
- **Self-evaluation/self-critique** — risky (self-bias) but great for sanity checks and nudging the model to revise ("Is this answer correct? → No, it's 13").
- **Weaker/specialized judge** — judging may be easier than generating; small specialized judges can beat large general ones for a specific criterion. Three types: **reward model** ((prompt, response)→score, e.g. Cappy 360M), **reference-based judge** (BLEURT; Prometheus → 1–5 vs. a rubric), **preference model** ((prompt, r1, r2)→winner; PandaLM, JudgeLM) — valuable because preference data is expensive.

## Comparative-evaluation challenges
- **Scalability** — pairs grow quadratically (LMSYS: 57 models, 244k comparisons ≈ only 153/pair). Lean on transitivity (A>B, B>C ⇒ A>C) — but human preference may be non-transitive; mitigate with uncertainty-reducing match-sampling. New/private models are hard (must re-compare; can shift existing ranks).
- **Standardization/quality control** — crowdsourced votes are hard to game but unstandardized: voters prefer good-sounding-but-wrong answers, many trivial prompts ("hi" ×180, brainteaser ×44) don't discriminate, no RAG/context grounding. Fixes: filter to hard prompts, trained evaluators (Scale), in-product comparisons, or AI judges.
- **Comparative ≠ absolute** — "B beats A 51%" doesn't say if either is *good enough*, and win-rate→business-metric conversion is unknown (1% win-rate delta = huge boost or nothing). **Comparative ≠ A/B testing** (A/B: one output at a time; comparative: many side-by-side). Future is bright: never saturates, captures human preference, hard to game, complements benchmarks (offline) and A/B tests (online).

## Common failure modes
- **Climbing the ladder too early.** Reaching for an LLM judge when functional correctness or exact match would be definitive and cheaper.
- **Unpinned judge.** Letting the judge's model/prompt drift, then attributing the score change to the application.
- **Cross-tool score comparison.** Treating MLflow's "faithfulness 3" as comparable to Ragas's "1."
- **Perplexity on post-trained models.** Using PPL to rank instruction-tuned models, where it's a poor proxy.
- **Preference where correctness is needed.** Asking users to vote on factual/math answers they can't verify → trains misalignment and frustrates users.
- **Lexical-overlap as truth.** Optimizing BLEU/ROUGE and assuming it tracks functional correctness.
- **Reference set assumed complete/correct.** Penalizing right answers absent from references, or scoring against wrong references.

## Interview signal
**AI-Engineer / FDE framing:** Evaluation is *the* differentiator question in applied-AI loops ("evals are surprisingly often all you need"). Senior signal = you climb the ladder deliberately (exact → similarity → judge → comparative), you can defend LLM-as-judge while naming its self/position/verbosity biases and the "freeze the judge, see its prompt" discipline, and you separate comparative ("which is better") from absolute ("is it good enough") and from A/B testing.
**One crisp talking point:** *"I always reach for the most exact method the task allows — functional correctness if it's executable, then reference similarity — and only climb to LLM-as-judge when the output is genuinely open-ended. When I do use a judge, I treat it as a frozen system of model + prompt + scoring, prefer classification over 1–5 scoring, spot-check rather than judge everything, and watch self-bias and verbosity bias. Comparative ranking tells me which model wins; it never tells me whether either is good enough — that needs absolute eval tied to the business metric."*

## Practitioner checklist
- [ ] Output type classified → started at the most exact applicable method
- [ ] Functional correctness checked first (executable/measurable objective?)
- [ ] If reference-based: similarity route chosen (exact/lexical/semantic) + reference quality/coverage audited
- [ ] If judge: model + prompt + scoring system specified and **frozen**; classification or discrete 1–5 scoring; per-score examples included
- [ ] Judge biases checked (self, first-position, verbosity) + mitigation (order-swap, weaker/specialized judge, spot-check)
- [ ] If ranking: comparative vs. pointwise chosen; rating algo named; transitivity/standardization caveats noted
- [ ] Comparative results paired with an absolute "good enough?" check tied to the business metric
- [ ] LM metrics (perplexity/cross-entropy) interpreted correctly (post-training/quant caveat)

## References
- *AI Engineering* (Huyen, O'Reilly 2024), Ch. 3 (pp. 232–314): Challenges, Language-Modeling Metrics, Exact Evaluation (functional correctness, similarity), Embedding intro, AI as a Judge, Comparative Evaluation.
- Sibling docs: **`evaluating-ai-systems.md`** (assembles these methods into a pipeline + model selection — read together), `foundation-models.md` (perplexity/cross-entropy origins, reward models, comparison data), `prompt-engineering.md` (how to prompt the judge well), `rag-and-agents.md` (embeddings → vector search).
- Related skills: `kohavi-controlled-experiments` (online A/B testing — the complement to comparative eval), `mlsd-coach` (eval inside an ML system-design answer).
