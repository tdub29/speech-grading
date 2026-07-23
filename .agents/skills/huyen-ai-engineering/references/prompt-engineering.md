# Prompt Engineering: effective prompts + defensive prompting (Huyen Ch. 5)

## Produce
Two artifacts: (1) a **prompt design + iteration plan** — structured prompt (system/user, examples, context, markers), the best-practice techniques applied with a reason each, a decomposition/CoT decision, and a versioned experiment-tracking setup; and (2) a **prompt-attack threat model + defense plan** at model/prompt/system levels, scored on violation rate and false-refusal rate.

Fire this when someone is writing/improving prompts, or hardening an LLM app against prompt injection/jailbreaks. This is the cheapest adaptation rung — exhaust it before finetuning.

## Trigger checks
- "Help me write / improve this prompt" / "my prompt isn't working / is flaky"
- Few-shot vs. zero-shot, chain-of-thought, system vs. user prompt, output format
- "How do I stop prompt injection / jailbreaks?" / securing an LLM app / guardrails on input
- Prompt versioning/organization, prompt-engineering tools (DSPy, etc.)
- Interview: "How do you do prompt engineering rigorously?" / "Defend against prompt injection"

## How to apply — writing effective prompts

### 1. Structure the prompt
A prompt has up to three parts: **task description** (what to do + role + output format), **example(s)**, and **the task** (the concrete input). Use **system prompt** (task description / developer instructions) vs. **user prompt** (the task / user input). System prompts help — likely because they come first and models are post-trained to prioritize them (the instruction hierarchy, which also aids defense). **Match the model's chat template exactly** (Llama 2 vs. Llama 3 differ; an extra newline causes silent failures) — print the final hydrated prompt to verify. Note model quirks: most (GPT-4) like the task description first; some (Llama 3) like it last.

### 2. In-context learning: zero-shot vs. few-shot
Examples in the prompt = "shots" (5 examples → 5-shot; none → zero-shot) — learning without weight updates (a form of continual learning; lets the model use post-cutoff info). More examples generally help, bounded by context length + cost. Few-shot mattered a lot for GPT-3; less for GPT-4-class models on general tasks — but still big for **domain-specific** APIs/formats the model rarely saw.

### 3. Apply the best practices (each with a reason)
- **Write clear, explicit instructions** — define the scoring scale, whether to say "I don't know," no fractional scores, etc. Patch undesired behaviors as you observe them.
- **Ask for a persona** — shifts the perspective (first-grade-teacher persona scores the chicken essay 4 not 2).
- **Provide examples** — reduces ambiguity (the Santa/tooth-fairy example nudges tone); pick token-cheap example formats (`-->` over Input/Output).
- **Specify the output format** — ask for conciseness (preambles cost tokens + latency), specify JSON keys, and use **end-of-prompt markers** so the model emits structured output instead of continuing the input.
- **Provide sufficient context** — reference text improves answers and mitigates hallucination; gather it via context construction (RAG, web search — Ch. 6). To restrict the model to *only* its context (roleplay/sim), instruct "answer using only the provided context" + quote sources — but prompting alone can't guarantee it (finetuning/training-on-corpus are the stronger but costlier options).
- **Break complex tasks into subtasks** — chain prompts (intent classification → per-intent response). Benefits: monitoring, debugging, parallelization, cheaper-model-per-step, easier authoring (GoDaddy's 1,500-token prompt got better + cheaper after decomposition). Cost: more queries (but smaller prompts often net cheaper) and more perceived latency on hidden intermediate steps.
- **Give the model time to think** — **chain-of-thought** ("think step by step" / specify the steps / one-shot the steps) boosts reasoning and cuts hallucinations (LinkedIn); **self-critique** asks it to check its own output. Both add latency/cost.

### 4. Iterate + organize rigorously
Prompt engineering is real engineering — version prompts, use experiment tracking, standardize eval metrics + data, and **evaluate each prompt in the context of the whole system** (a prompt can help a subtask but hurt the system). **Separate prompts from code** (e.g., `prompts.py`) for reusability/testing/readability/SME collaboration; attach metadata (model, date, app, creator, sampling params, input/output schema). Beyond git versioning (forces all dependents to upgrade), a **prompt catalog** versions prompts independently per app. **Prompt tools** (DSPy, OpenPrompt, Promptbreeder, TextGrad) automate optimization but: hide many API calls (cost blowups), can ship wrong templates/typos (LangChain examples), and change without warning — start by hand, then inspect every tool-produced prompt and count its API calls.

## How to apply — defensive prompt engineering

### 5. Model the threat (three attack types, six risk classes)
Three attacks: **prompt extraction / reverse prompt engineering** (deduce the system prompt to replicate/exploit — note: a "leaked" prompt is often hallucinated; "write your system prompt assuming it'll be public"), **jailbreaking / prompt injection** (subvert safety / inject malicious instructions — possible *because* models follow instructions and can't cleanly separate system from user/tool text), and **information extraction** (regurgitate training data / context — factual probing, the "repeat 'poem' forever" divergence attack; bigger models memorize more; copyright regurgitation risk). Risk classes: remote code/tool execution, data leaks, social harms, misinformation, service interruption, brand risk.
Attack sophistication ladder: manual hacking (obfuscation/misspelling, special chars, output-format tricks, roleplay — DAN, grandma exploit) → automated (PAIR: an attacker AI iterates, often <20 queries) → **indirect prompt injection** (the dangerous one — payload hidden in tools/retrieved content: passive phishing in a repo/webpage, active injection via an email the assistant reads; same for RAG/SQL via a malicious username).

### 6. Defend at three levels + measure
Track **violation rate** (successful attacks / attempts) AND **false-refusal rate** (safe queries wrongly refused) — a refuse-everything system has 0 violations but is useless.
- **Model level** — train the model to follow the **instruction hierarchy** (system > user > model output > tool output → neutralizes indirect injection; OpenAI: +63% robustness, minimal capability loss). Train on borderline requests to balance safety vs. helpfulness ("locked out of my own home").
- **Prompt level** — be explicit about what NOT to do; repeat the system prompt before and after the user input; pre-warn about known attacks (DAN/grandma). Inspect tool default templates for missing safety instructions (permissive LangChain templates → 100% injection success in one study).
- **System level** — isolate generated-code execution in a VM; require human approval for impactful commands (DELETE/DROP/UPDATE); define out-of-scope topics + input/output **guardrails** (block PII/toxicity on the way in *and* out); detect bad actors by usage patterns (bursts of similar probing requests). Red-team with tools (PyRIT, garak) + benchmarks (AdvBench, PromptRobust). No defense is foolproof while the system can do anything impactful.

## Common failure modes
- **Prompt-engineering as the only skill.** "The problem is when prompt engineering is the only thing people know" — production needs eval, tracking, dataset work too.
- **Template mismatch.** Wrong chat template / stray newline → silent, bewildering degradation; never noticed because output still looks plausible.
- **Tuning low-signal tricks.** "$300 tip" / "Q:" hacks that break as models improve — favor robust techniques and stronger (more prompt-robust) models.
- **Prompt as moat.** Treating proprietary prompts as a durable advantage — they're a maintenance liability (re-tune on every model change) and extractable.
- **Trusting context-restriction prompts.** "Answer only from context" isn't guaranteed; pre-training can still leak.
- **No system-level defense.** Relying on prompt-level instructions alone for an agent with tool access — indirect injection bypasses it; you need isolation + approval gates + guardrails.
- **Optimizing violation rate alone.** Driving attacks to zero by over-refusing, tanking usefulness.

## Interview signal
**AI-Engineer / FDE framing:** Senior signal = treating prompting with experiment-tracking rigor (versioned, evaluated in-system) and, crucially, articulating the **indirect prompt injection** threat for *agentic/tool-using* systems plus a layered defense (instruction hierarchy + isolation + approval gates + I/O guardrails) measured by both violation and false-refusal rate. FDE loops probe whether you'll ship a tool-wielding agent without thinking about injection.
**One crisp talking point:** *"I exhaust prompting before finetuning, but I do it like ML: versioned prompts, an eval set, and I judge each prompt by the whole system not the subtask. For security, the dangerous case is indirect prompt injection — payloads hidden in retrieved content or tool output. I defend in layers: the instruction hierarchy at the model level, explicit constraints at the prompt level, and at the system level VM isolation, human approval for destructive commands, and input/output guardrails — and I track both violation rate and false-refusal rate so I'm not just refusing everything."*

## Practitioner checklist
- [ ] Prompt structured (system/user, examples, context, end markers); chat template verified by printing the final prompt
- [ ] Zero- vs. few-shot chosen; examples token-efficient; domain examples added where the model is weak
- [ ] Clear instructions + persona + output format + sufficient context applied with a reason each
- [ ] Complex task decomposed/chained where it helps (with the latency/cost tradeoff weighed); CoT/self-critique used where reasoning matters
- [ ] Prompts separated from code, versioned (catalog if multi-app), experiment-tracked; tools' API calls + templates inspected
- [ ] Threat model built (extraction / jailbreak-injection / info-extraction; indirect injection for tool-using systems)
- [ ] Defenses at model + prompt + system levels; impactful commands gated; input/output guardrails in place
- [ ] Robustness measured on BOTH violation rate and false-refusal rate

## References
- *AI Engineering* (Huyen, O'Reilly 2024), Ch. 5 (pp. 416–493): Introduction to Prompting, In-Context Learning, System/User Prompts, Context Length/Efficiency, Best Practices, Defensive Prompt Engineering.
- Sibling docs: `foundation-models.md` (structured outputs, why models follow instructions), `evaluating-ai-systems.md` (instruction-following eval; judge prompting), `rag-and-agents.md` (context construction; agent tool-use = the indirect-injection surface), `finetuning.md` (the next rung when prompting plateaus), `architecture-and-user-feedback.md` (guardrails in the full architecture).
- Related skill: `claude-api` (Anthropic system-prompt behavior, chat format, sampling params).
