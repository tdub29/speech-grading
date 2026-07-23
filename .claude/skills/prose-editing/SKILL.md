---
name: prose-editing
description: Apply Zinsser, Clark, Williams/Bizup, and Pinker prose-editing frameworks for wordiness, clutter, clarity, voice, unity, leads/endings, abstraction, nut graf, sentence rhythm, verb strength, characters/actions, cohesion, concision, emphasis, classic style, curse of knowledge, syntax ambiguity, and usage disputes. Triggers: tighten prose, cut clutter, wordy, bureaucratic, corporate, weak opening, flat ending, unfocused, wanders, too abstract, nut graf, gold coins, choppy rhythm, passive, noun-heavy, doesn't flow, buried point, expert prose confusing, split infinitive, usage myth. Load the matching reference file when a specific framework is needed. Do NOT trigger for brand/marketing persuasion (`copywriting`), full documentation structure (`technical-writing`), or owned voice mimicry (`trevor-voice`) when those skills own the task.
---

# prose-editing

Book provenance: **William Zinsser — *On Writing Well***; **Roy Peter Clark — *Writing Tools***; **Joseph M. Williams & Joseph Bizup — *Style: Lessons in Clarity and Grace***; **Steven Pinker — *The Sense of Style***. Load the matching `references/*.md` file when a specific framework is needed.

## When to use

Use this hub when the user's question matches any sub-framework trigger in the frontmatter description. Route to **one or more** reference files (see workflow), read each fully, then execute that framework's process and output format.

Do not improvise a hybrid of multiple frameworks unless the user explicitly asks for a combined pass, or the workflow below recommends chaining.

## Quick routing

| User cue (examples) | Reference |
|---|---|
| Wordy, cluttered, jargon, hedges, pompous, bureaucratic, cut fluff | `references/zinsser-clutter-cut.md` |
| Committee voice, faceless, institutional, no human presence | `references/zinsser-human-audience-pass.md` |
| Weak opening, boring lead, flat ending, throat-clearing intro | `references/zinsser-lead-ending-audit.md` |
| Unfocused, wanders, mixed audience/POV/tense, scope creep | `references/zinsser-unity-contract.md` |
| Too abstract or too anecdotal, detail vs meaning gap | `references/clark-abstraction-ladder.md` |
| Missing "so what," section momentum, reward drought, nut graf | `references/clark-nut-graf-gold-coins.md` |
| Choppy, monotonous, breathless, punctuation rhythm | `references/clark-sentence-rhythm-punctuation.md` |
| Limp sentences, delayed subject/verb, weak verbs, noun stacks | `references/clark-verb-engine-rewrite.md` |
| Can't tell who does what, buried agency, nominalizations | `references/williams-characters-actions.md` |
| Sentences OK but jumpy, doesn't flow, topic chain broken | `references/williams-cohesion-coherence-map.md` |
| Verbose, tangled clauses, phrase bloat, sentence sprawl | `references/williams-concision-shape-pass.md` |
| Point buried in middle, weak sentence/paragraph ending | `references/williams-stress-position-emphasis.md` |
| Self-conscious meta, announcing instead of showing | `references/pinker-classic-style-window.md` |
| True statements pile up, logic jumps, false transitions | `references/pinker-coherence-arcs.md` |
| Expert prose opaque to outsiders, insider assumptions | `references/pinker-curse-knowledge-audit.md` |
| Grammatically legal but misreadable, modifier attachment | `references/pinker-syntax-ambiguity-check.md` |
| Contested grammar rule, editor mark, usage myth dispute | `references/pinker-usage-myth-triage.md` |

## Workflow — diagnose which pass(es) to run

1. **Structure first** — if the piece lacks focus or a reader contract, start with `zinsser-unity-contract.md`; if openings/closings fail, add `zinsser-lead-ending-audit.md` or `clark-nut-graf-gold-coins.md`.
2. **Meaning & logic** — if ideas don't connect across sections, use `pinker-coherence-arcs.md`; if sentences don't flow locally, use `williams-cohesion-coherence-map.md`; if expert readers are lost, use `pinker-curse-knowledge-audit.md`.
3. **Sentence engine** — agency problems → `williams-characters-actions.md`; delayed/weak verbs → `clark-verb-engine-rewrite.md`; wrong emphasis → `williams-stress-position-emphasis.md`.
4. **Surface polish** — cut wordiness → `zinsser-clutter-cut.md` or `williams-concision-shape-pass.md`; rhythm → `clark-sentence-rhythm-punctuation.md`; voice/stance → `zinsser-human-audience-pass.md` or `pinker-classic-style-window.md`.
5. **Safety & correctness** — public/policy/legal misread risk → `pinker-syntax-ambiguity-check.md`; grammar dispute → `pinker-usage-myth-triage.md`.

Chain **2–3 references max** per pass unless the user requests a full editorial stack. Run structure before sentence polish; run clarity before usage triage.

## How to apply

1. Match the user request to a row in **Quick routing** (or the description triggers).
2. Read the corresponding file under `references/` (and any chained references from the workflow).
3. Follow each reference's framework, steps, failure modes, and output artifact format.
4. Return the reference output artifact(s); add cross-reference notes only when the reference requires it.

## Common failure modes (hub-level)

- **Wrong reference** — loading one sub-framework when another row in Quick routing fits better (e.g. clutter-cut when the issue is missing actors).
- **Router-only answer** — summarizing the hub without loading the reference's full framework.
- **Polish before structure** — tightening sentences in a piece that needs unity or nut-graf work first.
- **Skill overlap** — using this hub for marketing copy, full doc architecture, or Trevor voice when `copywriting`, `technical-writing`, or `trevor-voice` own the task.
- **Retired atomic names** — legacy per-framework skill folders were collapsed into this hub; use `references/` only.
- **Over-chaining** — running four or more references when the user asked for one fix.

## References

- [references/zinsser-clutter-cut.md](references/zinsser-clutter-cut.md)
- [references/zinsser-human-audience-pass.md](references/zinsser-human-audience-pass.md)
- [references/zinsser-lead-ending-audit.md](references/zinsser-lead-ending-audit.md)
- [references/zinsser-unity-contract.md](references/zinsser-unity-contract.md)
- [references/clark-abstraction-ladder.md](references/clark-abstraction-ladder.md)
- [references/clark-nut-graf-gold-coins.md](references/clark-nut-graf-gold-coins.md)
- [references/clark-sentence-rhythm-punctuation.md](references/clark-sentence-rhythm-punctuation.md)
- [references/clark-verb-engine-rewrite.md](references/clark-verb-engine-rewrite.md)
- [references/williams-characters-actions.md](references/williams-characters-actions.md)
- [references/williams-cohesion-coherence-map.md](references/williams-cohesion-coherence-map.md)
- [references/williams-concision-shape-pass.md](references/williams-concision-shape-pass.md)
- [references/williams-stress-position-emphasis.md](references/williams-stress-position-emphasis.md)
- [references/pinker-classic-style-window.md](references/pinker-classic-style-window.md)
- [references/pinker-coherence-arcs.md](references/pinker-coherence-arcs.md)
- [references/pinker-curse-knowledge-audit.md](references/pinker-curse-knowledge-audit.md)
- [references/pinker-syntax-ambiguity-check.md](references/pinker-syntax-ambiguity-check.md)
- [references/pinker-usage-myth-triage.md](references/pinker-usage-myth-triage.md)
