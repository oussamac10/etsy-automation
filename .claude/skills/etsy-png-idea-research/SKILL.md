---
name: etsy-png-idea-research
description: Produce evidence-based Etsy PNG product research — keyword and competition analysis, seasonal opportunity, ranked original concepts, and a complete design prompt plus negative prompt for each. Use when the user asks for Etsy product ideas, PNG/clipart/sublimation concepts, niche or keyword research for an Etsy shop, seasonal opportunities, or design prompts for print-on-demand artwork. Never invents sales or search-volume numbers and never promises profit.
---

# Etsy PNG Idea Research

Turn a shop brief into ranked, original PNG product concepts that a person can
approve, generate artwork for, and package as an Etsy draft.

This skill prepares work. It does not predict sales, certify legal safety, or
publish anything.

## Absolute rules

Break any of these and the output is invalid, no matter how good it reads.

1. **Never invent a number.** No search volume, sales count, revenue, conversion
   rate, review count or "trending by X%" unless it was actually observed in a
   cited source. If the number is not in the evidence, it does not exist.
2. **Never promise profit or safety.** No "this will sell", "high demand",
   "trademark-free", "safe to use", "guaranteed". Risk is `low`, `medium`,
   `high` or `unknown` — `safe` is not an available value.
3. **Separate observation from inference.** An observation is what a source
   states. An inference is the reasoning built on top. Label both.
4. **Originality only.** Never copy or paraphrase a seller's title, artwork,
   brand, character, celebrity, lyric or recognisable personal style. Concepts
   must be built from a real differentiator, not a competitor's listing.
5. **Respect access rules.** Use permitted sources and the Etsy API. Never
   scrape Etsy or work around its access controls.
6. **Say when confidence is low.** Thin evidence is a finding, not a gap to fill
   with plausible-sounding text. Label the run low-confidence and propose a
   cheap test instead.

## Step 1 — Record the brief

Before any research, capture and restate:

| Field | Example |
| --- | --- |
| Marketplace | Etsy |
| Country / language | United States / English |
| Buyer | Someone buying a birthday gift for a coworker |
| Physical uses | T-shirt, mug, tote, sticker, wall art |
| Style direction | Retro groovy, hand-drawn, minimal line art |
| Quantity wanted | 5 ranked ideas |
| Season / timing | Autumn 2026, Halloween adjacent |

If a field is missing, ask once. Do not silently assume a country or audience —
both change the whole result.

## Step 2 — Query from at least three angles

A single query returns a single opinion. Run at least three distinct angles, and
prefer five:

- **Broad**: the category itself (`sunflower png`)
- **Long-tail**: qualified intent (`boho sunflower png for tumbler wrap`)
- **Occasion / recipient**: who and when (`teacher appreciation png`)
- **Style**: aesthetic language (`retro groovy floral clipart`)
- **Use case**: the physical product (`sublimation design for canvas tote`)

Record every query you ran, including the ones that returned nothing useful — a
dead angle is evidence too.

## Step 3 — Capture evidence

Every claim needs a record:

```text
query:        "boho sunflower png for tumbler wrap"
url:          https://…
title:        <page or listing title as shown>
observation:  what the source actually states
inference:    what I conclude from it (clearly separated)
source_type:  marketplace | blog | forum | api | trends | other
captured_at:  2026-08-01T14:22:00Z
confidence:   high | medium | low
```

If you cannot cite it, do not assert it.

## Step 4 — Build keyword clusters

Group natural buyer language, not keyword soup:

- **Primary phrase** — what the buyer types
- **Attributes** — colour, style, format, transparency
- **Recipient / occasion** — mum, teacher, birthday, Halloween
- **Use cases** — shirt, mug, sticker, wall art

For each cluster note the **competition signal** you observed (saturated,
crowded-but-differentiable, thin) and say what you saw that made you say it.

## Step 5 — Seasonal opportunity

For each cluster, state:

- the season or event it attaches to;
- how far ahead buyers shop for it, if a source says so;
- whether the listing would be evergreen, seasonal, or both;
- and whether *right now* is early, on-time or late for it.

Never invent a seasonality curve. If no source supports one, say the timing is
unknown and treat it as a test.

## Step 6 — Generate original concepts

Each concept needs a real differentiator — a specific subject, an unusual
combination, a niche audience, a use-case fit or a compositional idea. "Same
thing but prettier" is not a differentiator.

For every concept produce:

- concept name and one-line description
- the buyer and the moment they buy
- the differentiator, stated plainly
- intended physical products
- exact phrase, if the design carries text
- risk notes

## Step 7 — Score and rank

Score each idea 1–5 on seven criteria, then weight:

```text
0.20 × demand signal
0.15 × competition opportunity
0.15 × seasonal timing
0.15 × buyer clarity
0.15 × differentiation
0.10 × product versatility
0.10 × IP safety
```

Show the breakdown, not only the total. A 3.9 built on `demand: 2` is a
different proposition from a 3.9 built on `differentiation: 5`, and the person
approving it needs to see which.

If evidence was thin, mark the run **low confidence** and propose the cheapest
test that would resolve it.

## Step 8 — Write the design prompt for every idea

Each idea gets a self-contained **positive prompt** covering all of:

- subject and supporting elements
- composition and visual hierarchy
- style — described in your own words, never "in the style of <living artist>"
  and never copying a seller
- palette
- outlines, level of detail, texture
- intended products
- isolated artwork on a transparent background, clean uncropped edges
- high-resolution print intent

**Typography is separate.** When spelling matters, the prompt must ask for *no
text*. Store the exact phrase on its own with font, layout, colour and placement
instructions — the phrase is rendered deterministically later, not generated.

### Negative prompt

Every idea also gets a negative prompt rejecting at least:

```text
background, backdrop, scene, mockup, garment, model, hands, watermark,
signature, logo, trademark, brand name, copyrighted character, celebrity
likeness, copied artist style, text, letters, misspelled words, illegible text,
cropped subject, cut-off edges, jpeg artifacts, noise, blur, extra fingers,
malformed anatomy, duplicate limbs, low resolution
```

### Transparent-background requirement

State the requirement in the prompt, then **verify it afterwards**. Generators
do not guarantee transparency, exact pixel dimensions, DPI or spelling.

An output is only acceptable when a check confirms:

- PNG with an alpha channel that contains genuinely transparent pixels — an
  all-opaque alpha channel is not a transparent PNG;
- no unexpected opaque corner pixels or background halo;
- the subject is uncropped, with the configured safe margin intact;
- pixel dimensions recorded as measured, not as requested.

Never claim a DPI value as proof of print quality. Pixel dimensions and visual
QA are what matter.

## Step 9 — Preliminary IP screening

For every phrase and every recognisable element, do a **preliminary** screen:

- Is the phrase a known slogan, brand, lyric or catchphrase?
- Does the subject resemble a protected character, logo or celebrity?
- Does the style copy an identifiable living artist or a specific seller?
- Does a public trademark source show a live mark for this phrase in a relevant
  class?

Record what you checked, what you found, and the residual risk as `low`,
`medium`, `high` or `unknown`.

State plainly, every time: **this is not a clearance search and not legal
advice.** A human must confirm before anything is published, and a professional
search is the only thing that settles it.

## Step 10 — Hand off to the approval gates

Research output feeds three human gates. None can be skipped or automated.

1. **Idea approval** — the owner picks one concept from the ranked list. A
   rejected idea never reaches artwork generation.
2. **Artwork approval** — the owner picks one generated artwork. A rejected
   artwork never enters production.
3. **Trademark confirmation and Etsy publication** — the owner acknowledges the
   IP review and approves the final listing. The system creates a **draft**
   only; publishing is always a separate, human action.

## Output format

```markdown
## Brief
<the restated brief>

## Queries run
<angle → query, and what it returned>

## Evidence
<table: url | title | observation | inference | source | captured_at>

## Keyword clusters
<cluster → primary phrase, attributes, recipient/occasion, use cases,
 competition signal + what was observed>

## Seasonal opportunity
<cluster → season, timing verdict, evergreen/seasonal, supporting evidence>

## Ranked ideas
### 1. <name> — weighted score X.XX (confidence: high|medium|low)
- Buyer and moment:
- Differentiator:
- Intended products:
- Exact phrase (if any):
- Scores: demand X | competition X | seasonal X | clarity X | differentiation X
  | versatility X | IP safety X
- Risk notes: <low|medium|high|unknown> — <why>

**Positive prompt**
<self-contained prompt>

**Negative prompt**
<rejections>

**Typography** (only when the design carries text)
- Exact phrase:
- Font / weight:
- Layout and placement:
- Colour and contrast:

**Preliminary IP screen**
- Checked:
- Found:
- Residual risk: low|medium|high|unknown
- Not a clearance search; human confirmation required before publishing.

## Confidence and next test
<what the evidence supports, what it does not, and the cheapest test>
```

## Refusals

Decline, and say why in one sentence, if asked to:

- copy a specific seller's listing, artwork or style;
- use a brand, character, celebrity or lyric;
- produce search volume, sales or revenue figures that were not observed;
- state that an idea is safe, trademark-free, guaranteed or profitable;
- scrape Etsy or bypass its API access rules;
- publish or activate a listing automatically.

Then offer the nearest legitimate alternative.
