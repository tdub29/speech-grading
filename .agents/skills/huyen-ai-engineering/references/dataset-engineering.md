# Dataset Engineering: curation, synthesis, and quality (Huyen Ch. 8)

## Produce
A **dataset plan** for adapting/finetuning a model: the data format + curation criteria (quality / coverage / quantity), a quantity-and-mix estimate, an acquisition/annotation strategy (with a guideline), a synthesis plan (rule-based / simulation / AI-powered) where real data is short, and a verification + limitations guardrail.

Fire this when someone is building training/finetuning data, asking "how much data / what quality / how do I generate data," or designing a data flywheel. ("Models are now commodities — data is the differentiator.")

## Trigger checks
- "What data do I need to finetune?" / "how much / what quality?"
- Data curation, annotation guidelines, instruction/preference data formats
- Synthetic data / data augmentation / distillation / data flywheel
- "Can I use AI-generated data?" / model collapse / synthetic-data limitations
- Data coverage/diversity, data mix across training phases
- Interview: "How would you build a finetuning dataset?" / "data-centric AI"

## Frame: data-centric vs. model-centric
**Model-centric** improves AI via the model (architecture/size/training); **data-centric** improves it via the data (processing + high-quality datasets). As fewer firms train from scratch, data is the differentiator. Focus on **post-training data** (instruction/preference) — most relevant to app developers — but pre-training lessons carry over. Curation isn't linear (go back and forth) and is "mostly toil, tears, and sweat."

## How to apply

### 1. Decide the data format (by what you're teaching)
Self-supervised finetuning → **sequences**; instruction finetuning → **(instruction, response)**; preference finetuning → **(instruction, winning, losing)**; reward model → that or **((instruction, response), score)**. Hard behaviors need matching data: **chain-of-thought** (step-by-step responses — tedious to produce, so CoT data is rarer; nearly doubles CoT-task accuracy), **tool use** (often synthesized via simulation — human workflows ≠ efficient AI workflows; may need multi-message turn formats). Decide **single-turn vs. multi-turn** (multi-turn teaches task-solving but is costly to capture). Curation also means *removing* data to *unlearn* bad behaviors (e.g., delete examples with unsolicited rewrites).

### 2. Curate on three criteria (the cooking analogy: quality = ingredient quality, coverage = right mix, quantity = how much)
- **Data quality** — a little high-quality beats a lot of noisy (Yi: 10K curated > 100Ks noisy; LIMA: 1,000 curated examples rival GPT-4 43% of the time). Six characteristics: **relevant, aligned with task requirements** ("aligned" not "correct" — a correct-but-unhelpful answer is bad), **consistent** (across examples/annotators — needs a good annotation guideline), **correctly formatted** (strip HTML/whitespace/casing artifacts), **sufficiently unique** (dedup — duplicates cause bias + contamination), **compliant** (no disallowed PII, license-clean).
- **Data coverage (diversity)** — cover the range and *expression* of real problems (detailed AND short instructions; typos if users have typos; the languages users use). Diversity axes are app-specific (a translator needs topic/style diversity, not language; a global chatbot needs linguistic/cultural diversity). The data **mix differs per training phase** (Llama 3: code+math ≈ half of pre-training/SFT tokens but far less in preference finetuning, which reflects real user preference). Choose the mix to reflect real usage, or run scaling-law experiments. High-quality + diverse beats either alone.
- **Data quantity** — varies wildly. Three drivers beyond quality/diversity: **finetuning technique** (full finetuning needs orders of magnitude more than PEFT/LoRA — tens of thousands+ vs. hundreds), **task complexity**, **base-model proximity** (closer base = fewer examples; bigger base models often need *fewer* finetune examples — opposite of pre-training). With ~100 examples, advanced models finetune better; with ~550K, all converge. **Start with ~50 well-crafted examples** to test if finetuning helps at all (no gain at 50 → more rarely helps, but rule out hyperparameters/quality first), then plot the **performance-gain curve** across data sizes (diminishing returns is typical). Diversity (number of *tasks*) matters too (Flan: gains to ~282 tasks, then plateau). Watch **ossification** (heavy data → training from scratch may beat finetuning, esp. small models). Bound by budget (data $ trades off against compute $).

### 3. Acquire + annotate
Best source = **your own application data** (build a **data flywheel** — perfectly relevant, on-distribution). Check existing datasets first (HF, Kaggle, Google Dataset Search, data.gov — always verify license + lineage; never fully trust). Real curation is mix-and-match (find → filter low-quality → fill gaps with manual + synthetic → re-annotate). **Annotation guidelines are the hardest part** (LinkedIn flagged this) — and are the *same* guidelines as evaluation (another reason to invest in eval first; eval examples can seed synthesis). Don't abandon guidelines halfway and hope the model figures it out.

### 4. Synthesize where real data is short
**Augmentation** = new data from real data (flip a cat image); **synthesis** = mimic real-data properties (often used interchangeably). Five reasons: increase **quantity** (scarce/dangerous real data), **coverage** (targeted: long/short, toxic/safe, adversarial, rare-class, factually-inconsistent for detectors), **quality** (AI can exceed humans on tool-use efficiency, complex math, consistent preference ratings), **privacy** (synthetic patient/claims records), **distillation** (small model imitates big model's outputs).
- **Traditional**: **rule-based/templates** (Faker for transactions/invoices/equations; AlphaGeometry's 100M synthetic problems; image transforms; synonym swap for bias mitigation; **perturbation** for robustness) and **simulation** (self-driving/robotics; rare events; tool-use action sequences; Sim2Real gap).
- **AI-powered**: AI simulates APIs/humans (**self-play** — OpenAI Dota, AlphaGo); paraphrase/translate (back-translation to verify; MetaMath rewrote 15K→400K); **instruction synthesis** (topics→subtopics→instructions→responses — UltraChat, Alpaca's 175 seeds→52K; **reverse instruction** — generate prompts for existing high-quality content to avoid response hallucination; iterative weak-model bootstrapping; long-context data via chunk→Q&A→full-doc-context). Llama 3's coding pipeline (generate problems → solutions → AI-written unit tests → fix errors → translate → back-translate docs; 2.7M examples) is the case study.

### 5. Verify synthetic (and all) data
Quality test = same as any AI output: **functional correctness** (why coding data dominates synthesis — it's verifiable by execution + back-translation) and **AI judges/scorers** (score 1–5 or good/bad; factual-consistency filters; AI-content detector — easy to detect = bad synthetic; topic/anomaly filters; heuristic filters for empty/too-short/too-long/duplicate). Swap order to beat first-position bias (NVIDIA: accept a triplet only if the judge picks the same winner both orderings). Ultimate test = does it improve the model.

### 6. Respect the limits of AI-generated data
Four reasons it won't fully replace humans: **quality control** (garbage in, garbage out — needs reliable verification), **superficial imitation** (imitation models copy *style* not reasoning; training a student on a teacher's solutions it can't actually produce *teaches it to hallucinate* — fix the base model, not the imitation), **model collapse** (recursive training on AI data degrades models irreversibly — Curse of Recursion), and **obscured lineage** (synthesis hides where data came from). Mixing human + AI data usually wins.

## Common failure modes
- **Quantity over quality.** Chasing 100Ks of noisy examples when 1–10K curated would beat them.
- **Skipping the annotation guideline.** Abandoning it midway and hoping the model infers "good" — the #1 reported pipeline pain.
- **Coverage blind spots.** Training data that misses real usage diversity (typos, short instructions, the user's languages) → brittle in production.
- **Distillation-as-reasoning.** Believing imitation transfers capability; it transfers style and can induce hallucination.
- **Unbounded synthetic data.** Recursive AI-data training → model collapse; not mixing in human data.
- **Unverified synthetic data.** Generating at scale without functional-correctness or judge verification.
- **Ignoring ossification.** Finetuning when you have millions of examples and from-scratch (or different approach) would do better.
- **No flywheel.** Not capturing on-distribution application data — the single highest-value source.

## Interview signal
**AI-Engineer / FDE framing:** "Models are commodities; data is the differentiator." Senior signal = the **quality > quantity** stance (LIMA/Yi), the three-criteria curation frame (quality/coverage/quantity), starting with ~50 examples + a performance-gain curve to size the dataset, and a *verifiable* synthesis plan (functional correctness first) that's honest about model collapse and superficial imitation. FDE loops love the **data flywheel** instinct — turning user data into the moat.
**One crisp talking point:** *"I curate on three axes — quality, coverage, quantity — and I'd rather have 1,000 carefully-aligned examples than 100,000 noisy ones; LIMA showed 1,000 can rival GPT-4. I size the dataset empirically: start with ~50 examples, plot the performance-gain curve, and let the slope tell me whether more data pays off. For synthesis I lean on what I can verify — coding data dominates because functional correctness checks it for free — and I stay wary of distillation, because training a small model on a big model's solutions teaches it to imitate style and hallucinate, not to reason. The real moat is a data flywheel on my own on-distribution user data."*

## Practitioner checklist
- [ ] Data format matched to the training phase (sequences / (instr, resp) / (instr, win, lose) / scored)
- [ ] Quality assessed on the six characteristics; annotation guideline written (= the eval guideline)
- [ ] Coverage/diversity axes identified for this app; data mix chosen per phase to reflect real usage
- [ ] Quantity sized empirically (start ~50, performance-gain curve); technique-appropriate (PEFT vs. full); ossification considered
- [ ] Acquisition strategy set (app-data flywheel first; existing datasets license/lineage-checked)
- [ ] Synthesis plan where data is short (rule-based / simulation / AI), with verification (functional correctness / judges) and bias-order swap
- [ ] AI-data limits respected (quality control, no recursive collapse, imitation ≠ reasoning); human+AI mix

## References
- *AI Engineering* (Huyen, O'Reilly 2024), Ch. 8 (pp. 694–772): Data-Centric AI, Data Curation (quality/coverage/quantity), Acquisition & Annotation, Augmentation & Synthesis (traditional + AI-powered), Data Verification, Limitations.
- Sibling docs: `finetuning.md` (what consumes this data; distillation; PEFT data needs), `evaluating-ai-systems.md` (annotation guideline = eval guideline; functional correctness; factual-consistency filters), `foundation-models.md` (post-training data, comparison/preference data, training-data quality→capability), `architecture-and-user-feedback.md` (the feedback loop that feeds the flywheel).
- Related skills: `claude-api` (using Claude to synthesize/verify data; output-license terms for distillation), `mcgilvray-data-quality-project` / `dama-data-management` (general data-quality + governance lineage frames).
