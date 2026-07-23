# Rule: lean tokens & YAGNI

**Always on. One concern: spend fewer tokens and write less code while preserving correctness.**

This rule applies the useful core of the imported `caveman` and `ponytail` repos at workspace level. Their full skills are installed for explicit use; this rule is the default discipline.

## Communication

- Cut filler, hedging, pleasantries, and repeated restatement.
- Keep technical terms, file paths, commands, code, API names, exact errors, and numbers exact.
- Prefer short direct sentences. Use structure only when it improves scanning.
- Do not compress safety warnings, irreversible-action confirmations, legal/medical/financial caveats, or multi-step instructions where missing words could change order or meaning.
- Do not use a caricature voice unless the user explicitly asks for `caveman`; default is professional and terse.

## Code

Before writing code, climb the Ponytail ladder and stop at the first rung that works:

1. Does this need to exist? If speculative, skip or challenge it.
2. Does this already exist in the codebase? Reuse local helpers and patterns.
3. Does the standard library do it?
4. Does a native platform feature cover it?
5. Does an already-installed dependency solve it?
6. Can the change be one line or one file?
7. Only then write the minimum code that works.

## Guardrails

- Lazy means efficient, not careless. Read the touched flow before choosing a small diff.
- Bug fix means root cause, not symptom. Check sibling callers when touching shared behavior.
- Never simplify away trust-boundary validation, data-loss prevention, security, accessibility basics, required error handling, or explicitly requested behavior.
- Non-trivial logic leaves one small runnable check when practical. Trivial one-liners do not need test scaffolding.
- If an intentional simplification has a known ceiling, name it in a short `ponytail:` comment with the upgrade path.

