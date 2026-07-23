---
name: anti-slop-design
description: Make interfaces look designed-on-purpose, not AI-generated. Use when building OR reviewing any UI, website, landing page, dashboard, app shell, component, hero, pricing, footer, or marketing page, and whenever the concern is that a design looks generic, templated, "AI slop", or machine-made — or should look premium, bespoke, and unique. Covers the specific visual tells (blue-purple gradients, glowy pill buttons, Inter/Space-Grotesk/Cormorant defaults, icon-in-a-tile, faux app windows, the SaaS meta-template, grid backgrounds, botched glass/shadows), the absolute correctness rules (content visible by default, clear the cut, actually center it, working controls), and what premium actually looks like (one signature artifact, atmosphere, layered depth, character type, cohesion). Triggers: "does this look AI-generated", "looks like slop", "make it premium/bespoke", "anti-slop", "de-slop the design", design critique, visual polish, "why does this look generic". NOT for code cleanup — that is the `deslop` skill.
version: "1.0.0"
---

# Anti-slop design law

Full law: **read `reference/slop-law.md` before you design or review** (the pols.dev anti-slop design law, verbatim). It is the source of truth. This file is the operating summary.

## When this fires

Any time you build or review a visual interface AND the goal is that it look intentional / premium / unique rather than generated. Load the reference, design against it, then re-check the output against it before calling done.

## Workflow

1. **Before building** — decide the ONE signature first (the focal artifact, the palette, the type voice, the world). Read `reference/slop-law.md` if you have not this session.
2. **While building** — avoid the tells (below), and never gate content on an animation.
3. **Before shipping** — walk the checklist point by point against the actual rendered output. Zoom into clipped edges and "centered" elements and verify pixel-for-pixel. Click every interactive control. Fix what falls short.

Do the re-check silently as work — do not announce "I have read the entire file." The user's explicit direction overrides any default here; if they asked for a thing this law warns against, do exactly what they asked.

## The tells (the reflexive slop defaults — avoid unless chosen on purpose)

- **Color:** blue-to-purple gradients (the #1 tell), any glowy two-hue gradient, saturated accent everywhere, gradient-clipped headline text, the pastel candy-aurora background, the cool blue-charcoal dark base, cream/beige "editorial" default, the UI-kit slop gray.
- **Type:** the whole Google default rotation carrying the brand — Inter, Space Grotesk, Sora, Syne, Archivo, Cormorant, Fraunces, the Didones, JetBrains Mono. Even the "tasteful" swap (Instrument Serif, Bricolage…) is slop when picked by reputation. Signature face should be distinctive/self-hosted (Fontshare, licensed); body can be a true neutral (system-ui is genuinely neutral).
- **Components:** glowy pill buttons, filled+outlined button pair, icon (or logo) inside a colored tile/chip, oversized-icon-in-a-box, tinted pill chips on every label, gradient-icon+text pill, three-tier pricing card with glow+"MOST POPULAR", testimonial quote card, gradient-circle initials avatar, countdown timer, the sun-moon theme toggle, hairline border on every box, the little rule beside an eyebrow, the active-nav dot.
- **Layout:** the split/right-panel hero stack, the default eyebrow→headline→subline→two-buttons stack, kicker+serif-H2 section heads, numbered-steps-beside-a-line, the pre-footer gradient CTA slab, the standard multi-column footer, and above all **the whole SaaS meta-template** (two-col hero → 3 feature cards → tabs → pricing → FAQ → CTA slab → footer). Recoloring a slop layout is still slop.
- **Effects:** background glow blobs, radial halo behind a hero object, card hover-lift ("boop"), underline-fill hovers, botched glass (banding/leak/pop), botched shadows (hard-edged box, the element's own blurred silhouette), the default all-around shadow, faking a shadow with a second box, fixed background that just trails the scroll, grain sitting on top of content.

## The absolute rules (these are correctness, not taste)

- **Content is visible by default.** Never gate the existence of text/controls on an animation, IntersectionObserver, `animation-timeline`, or a Framer `initial opacity:0`. Animate `y`/hover/marquee on already-visible things, never opacity-from-0 that can strand blank.
- **Clear the cut.** Any `clip-path`, notch, `overflow:hidden`, or fixed height must leave content fully inside the visible region — pad past the cut, then zoom the exact edge and verify.
- **Actually center it, then verify.** Numbers in circles, glyphs in tiles, labels in pills — center mathematically AND optically, zoom in, confirm. In SVG remember `dominant-baseline`, not just `text-anchor`.
- **Legible contrast.** Every text (especially a button label on its fill) clears its background by a real value gap.
- **No dead controls.** Anything that looks interactive works, confirmed by a real click. Static props must not look clickable.
- **Align parallel columns** on one grid (title/price/body/list/CTA share baselines; anchor buttons to the bottom); give text real edge gutters.

## What premium actually is (build toward this, don't just avoid the list)

Avoiding every tell still ships slop if nothing was invented. Premium = a point of view executed with conviction:

**uniqueness = one signature artifact + composed atmosphere (not a flat fill) + layered z-depth with overlap/bleed + a character display face + one bespoke silhouette + a treated nav + real specifics.**

Plus: cohesion above all (one palette, one type voice, one world — incoherence beats tells as the loudest failure); authored motion so it is not dead (never gate content on it); real translucency/self-colored edges/grainy-not-banded gradients/considered directional light when used; bespoke geometry over default rectangles; terse copy. Free toolkit to reach for on React/Tailwind: Motion (motion.dev), shadcn/ui, tailark, motion-primitives, kokonut — but de-slop their prebuilt defaults before shipping.

See `reference/slop-law.md` for the full detail, the premium recipes (liquid glass, the signature formula, the premium kit), and the field notes.
