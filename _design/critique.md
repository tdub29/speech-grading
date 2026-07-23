Here's a concise, accurate answer to your query, grounded in the skill docs.

## `claude-opus-4-8` — model id

Use the exact string `claude-opus-4-8` (no date suffix). It's the current default Opus-tier model: 1M context, 128K max output, $5/$25 per MTok.

## `messages.parse()` — structured output (Python)

```python
from pydantic import BaseModel
import anthropic

class ContactInfo(BaseModel):
    name: str
    email: str
    plan: str

client = anthropic.Anthropic()
response = client.messages.parse(
    model="claude-opus-4-8",
    max_tokens=16000,
    messages=[{"role": "user", "content": "Extract: Jane Doe (jane@co.com), Enterprise"}],
    output_format=ContactInfo,
)
contact = response.parsed_output  # validated ContactInfo instance
```

Notes:
- `.parse()` accepts the `output_format=` convenience param (a Pydantic model); `response.parsed_output` is the validated instance.
- The canonical API-level equivalent on `.create()` is `output_config={"format": {"type": "json_schema", "schema": {...}}}` with `additionalProperties: false` and `required` set. The old top-level `output_format` param on `.create()` is deprecated.
- TypeScript: `client.messages.parse({..., output_config: {format: zodOutputFormat(Schema)}})`, read `response.parsed_output` (nullable — guard it).
- Schema limits: no recursion, no numeric/string constraints (`minimum`, `maxLength`, etc.), `additionalProperties` must be `false`. Python/TS SDKs strip unsupported constraints and validate them client-side.
- First request with a new schema pays a one-time compilation cost (24h cache).
- **Incompatible with citations** (400) and with **message prefilling**. Works with streaming, batches, thinking.

## `thinking` — Opus 4.8

Adaptive only:
```python
thinking={"type": "adaptive", "display": "summarized"}
```
- `thinking={"type": "enabled", "budget_tokens": N}` → **400** (`budget_tokens` is removed on Opus 4.7/4.8 and Fable 5).
- `temperature`, `top_p`, `top_k` are also removed → 400.
- `display` defaults to `"omitted"` (empty thinking text in the response); set `"summarized"` to get readable reasoning. The block field is still `block.thinking`.
- Omitting `thinking` entirely runs without thinking. `{"type": "disabled"}` is accepted on Opus 4.8 (it 400s only on Fable 5). With thinking disabled, 4.8 may leak reasoning into the visible answer — keep adaptive on or add a final-answer-only instruction.

## `output_config` effort

```python
output_config={"effort": "high"}  # low | medium | high | xhigh | max
```
- Nested inside `output_config`, not top-level. GA, no beta header. Default is `high`.
- Opus 4.7 added `"xhigh"` (between `high` and `max`); both supported on 4.8. `max` is Opus-4.6+/Sonnet-4.6 only.
- On 4.8, start at `high` and sweep rather than reflexively using `xhigh`/`max`.
- Combine with adaptive thinking. Can coexist with `thinking` and `task_budget` in the same `output_config`.

## Prefill restrictions

Last-assistant-turn prefills (a `messages` array ending in `{"role": "assistant", ...}`) return **400** on Opus 4.8 (and Opus 4.6/4.7, Sonnet 4.6, Fable 5). Replacements:
- **Force JSON/shape** → `output_config.format` (structured outputs).
- **Force a label** → tool with an enum field.
- **Skip preambles** → system-prompt instruction ("Respond directly, no preamble").
- **Continue an interrupted response** → move the continuation into a user turn.
- Few-shot assistant messages *elsewhere* in the conversation are still fine; only the trailing assistant prefill 400s.
- One narrow exception: the Fable 5 fallback-credit prefill claim, where the server accepts an echoed assistant message on credit redemption.
- Note: prefill restriction and structured outputs interact — since prefill is unavailable, `output_config.format` is the supported way to constrain output shape on 4.8.

Relevant skill files: `python/claude-api/tool-use.md` (structured outputs), `python/claude-api/README.md` (thinking, effort, stop reasons), `shared/models.md` (model id), `shared/model-migration.md` (Migrating to Opus 4.8 — prefill/thinking/sampling 400s).