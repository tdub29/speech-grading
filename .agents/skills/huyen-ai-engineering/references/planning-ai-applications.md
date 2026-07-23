# planning-ai-applications (Huyen Ch1)

Decide **whether and how** to build an AI/foundation-model application before any code: use-case selection, build-vs-buy, role-of-AI framing, defensibility, success metrics, and the AI-engineering stack. The artifact is a **go / no-go + scoping memo** with a chosen stack layer and usefulness thresholds.

## When to pull this

- Someone says "we should add AI to X" and you need to pressure-test the use case before committing.
- Choosing build-your-own-model vs. adapt-a-foundation-model vs. buy-a-product.
- Sizing effort: a demo took a weekend, now someone wants a production estimate.
- Defining what "good enough to ship" means (usefulness threshold) and how AI maps to a business metric.
- Interview: "How would you scope/approach an LLM feature for product X?"

## The decision flow

### 1. Use-case evaluation — *why* build it (risk vs. opportunity)

Rank the motivation, high to low risk:
1. **Business continuity** — competitors with AI make you obsolete (Gartner: 7% cited this). If AI is existential, build in-house, highest priority.
2. **Profit/productivity opportunity** — cheaper acquisition, better retention, lead-gen. Most companies. Buy options are fine here.
3. **Don't-want-to-be-left-behind** — exploratory R&D. Fine if you can afford it; don't chase every hype train.

If existential → favor in-house. If opportunity → favor buy.

### 2. Role of AI in the product (Apple's framing)

Three axes that set the quality bar:
- **Critical vs. complementary** — does the app work without AI? Face ID (critical) vs. Gmail Smart Compose (complementary). More critical → higher accuracy/reliability bar.
- **Reactive vs. proactive** — responds to a request (chatbot) vs. surfaces opportunistically (traffic alerts). Reactive usually needs to be fast; proactive can precompute but needs a **higher quality bar** (uninvited = annoying if bad).
- **Dynamic vs. static** — continuously updated per-user (personalization, ChatGPT memory) vs. periodically (object detection).

### 3. Role of humans — human-in-the-loop ladder

Microsoft's **Crawl-Walk-Run**:
1. **Crawl** — human involvement mandatory (AI drafts, human sends).
2. **Walk** — AI interacts with internal employees.
3. **Run** — increased automation, possibly direct external-user interaction.

Advance a rung only when the prior rung's acceptance rate clears a bar (e.g., 95% of AI suggestions used verbatim → let users hit AI directly for those cases).

### 4. Build vs. buy

The "classic buy-or-build question." Adapting an existing powerful model is *far* cheaper than building from scratch ("ten examples and one weekend versus 1 million examples and six months"). Default to adapting unless (a) AI is existential or (b) you need a small/cheap task-specific model. Beware: the best option today can flip tomorrow (provider price cuts, provider going out of business).

### 5. Defensibility (if selling AI as a standalone product)

Low entry barrier cuts both ways. Two moat traps:
- **Model-subsumption risk** — if your value-add is "ChatGPT can't parse PDFs well," you die when it can. Open-source-hosted angle can survive (in-house hosting buyers).
- **Feature-of-a-bigger-product risk** — "what stops Google allocating 3 engineers to clone this in two weeks?"

Three competitive advantages: **technology** (mostly equalized by FMs), **data** (nuanced — incumbents have more, but first-mover usage data is a real moat), **distribution** (usually belongs to incumbents). Counter-examples that won anyway: Calendly, Mailchimp, Photoroom.

### 6. Set expectations — success + usefulness thresholds

- **Business metric first** (e.g., % of tickets automated, response-time cut, labor saved).
- **Usefulness threshold** — how good before it ships, across metric groups: **quality**, **latency** (TTFT = time to first token, TPOT = time per output token, total latency), **cost per inference request**, plus interpretability/fairness.
- Always track **user satisfaction** separately — answering more messages ≠ happier users.

### 7. The last-mile / maintenance trap

"The journey from 0 to 60 is easy; 60 to 100 is exceedingly challenging." LinkedIn: 1 month to 80% of target experience, **4 more months** to pass 95%. Plan for it. Maintenance adds AI's fast-change tax: model deprecations, prompt re-tuning per model swap, regulation (GDPR ~$9B compliance cost industry-wide), IP risk on models trained on others' data.

## The AI-engineering stack (the at-a-glance map)

Three layers, build top-down:
| Layer | Responsibilities | Ref doc |
|---|---|---|
| **Application development** | evaluation, prompt engineering + context construction, AI interface | evaluating-ai-systems, prompt-engineering, rag-and-agents, architecture-and-user-feedback |
| **Model development** | modeling/training, dataset engineering, inference optimization | foundation-models, finetuning, dataset-engineering, inference-optimization |
| **Infrastructure** | serving, data/compute management, monitoring | architecture-and-user-feedback |

## What changed vs. traditional ML (the interview staple)

| Dimension | Traditional ML | AI engineering |
|---|---|---|
| Model | train your own | adapt someone else's |
| Focus | modeling + training | **adaptation + evaluation** |
| Compute/latency | smaller models | bigger, slower, costlier → inference optimization matters more |
| Outputs | mostly close-ended (easy to grade) | open-ended → **evaluation is the hard problem** |
| Dataset work | feature engineering, tabular | dedup, tokenization, context retrieval, quality control, unstructured |
| Workflow | data → model → product | **product → (then) data + model** (iterate fast) |
| Skillset | Python/ML-centric | closer to full-stack (JS SDKs, interfaces) |

Two adaptation families: **prompt-based** (no weight updates — easier, less data, experiment widely) vs. **finetuning** (weight updates — more data/complexity, unlocks new tasks).

Terminology trap: *training ≠ prompt engineering.* Feeding context into the model is prompting, not training/finetuning. Pre-training (from scratch, ~98% of compute) vs. finetuning (continue training) vs. post-training (finetuning done by the model developer).

## Practitioner checklist

- [ ] Stated the *why* (continuity / opportunity / explore) and let it drive build-vs-buy.
- [ ] Classified AI's role (critical/complementary, reactive/proactive, dynamic/static) → set the quality bar.
- [ ] Placed humans on the Crawl-Walk-Run ladder with an advancement criterion.
- [ ] Picked the moat (data/distribution) honestly; named the subsumption risk.
- [ ] Defined the business metric AND the usefulness threshold (quality, latency TTFT/TPOT, cost).
- [ ] Budgeted the 60→100 last mile, not just the demo.
- [ ] Chose the starting stack layer (almost always application development first).

## Interview signal

This is the **opening framing question** in nearly every AI-Engineer/FDE loop: "A PM wants to add AI to feature X — walk me through it." Weak answers jump to "use GPT-4 with a RAG pipeline." Strong answers establish *why* (continuity vs. opportunity), classify the role of AI (critical/complementary → sets the reliability bar), define the **usefulness threshold and business metric before touching a model**, and name the last-mile risk.

> Senior talking point: *"The cheap demo is a trap — the journey from 0 to 60 is a weekend, 60 to 100 is months. So before I build, I pin the usefulness threshold to a business metric and decide where AI sits on the human-in-the-loop ladder; that tells me both the reliability bar I'm engineering toward and whether I should be adapting a model at all versus buying."*

## References

- *AI Engineering: Building Applications with Foundation Models*, Chip Huyen (O'Reilly, 2024), Ch. 1.
- Sibling refs: `foundation-models` (the model layer this plans around), `evaluating-ai-systems` (the usefulness-threshold mechanics), `architecture-and-user-feedback` (where the maintenance/feedback loop lands).
- Related skills here: `mlsd-coach` (ML system-design framing), `kohavi-controlled-experiments` (measuring the business-metric lift online).
