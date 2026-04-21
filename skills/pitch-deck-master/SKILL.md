---
name: pitch-deck-master
description: |
  Build, review, or rebuild a pitch deck calibrated to a specific accelerator or investor type.
  Uses research-derived 2026 patterns from accepted YC, a16z Speedrun, and Sequoia-track decks.
  Produces HTML+CSS decks rendered to PDF via headless Chromium — pixel-perfect typography,
  brand-locked palette, accelerator-specific slide count and ask framing.
triggers:
  - "build a pitch deck"
  - "make a pitch deck"
  - "rebuild the deck"
  - "YC deck"
  - "speedrun deck"
  - "fundraising deck"
  - "pitch deck review"
version: 1.0.0
last_updated: 2026-04-21
---

# Pitch Deck Master

Opinionated pitch-deck builder calibrated to what accepted decks at YC, a16z Speedrun, and
Sequoia-track seed rounds actually look like in 2026. Not 2018 "keep it clean" guidance.

## When to use

- Founder asks for a pitch deck for a specific accelerator or investor audience.
- Founder asks to critique or rewrite an existing deck.
- Founder asks for an application-form one-slide summary (YC S25 format).
- Project has or needs a brand system compatible with legal/gov/B2B vertical tone.

## Decision tree — pick the variant

| Audience | Slides | Format | Primary signal |
|---|---|---|---|
| **YC application form** | 1 slide | Large text, ≤10 words total, image-only or type-only | Founder clarity in 30 seconds |
| **a16z Speedrun application** | 5–7 slides | SCQA framing, phone-watchable, bold type, traction front-loaded | Traction is 1, 2, 3; then team; then TAM |
| **YC interview prep (not required)** | 1-minute video + one-liner | No deck on screen | Can you answer "what do you do?" in one sentence |
| **Fundraising round (seed / pre-seed)** | 10 slides | Full Sequoia sequence | Market + team + traction story |
| **Warm-investor email attachment** | 10 slides + Papermark link + PDF attached | Both delivery paths | Read-tracking + frictionless open |

## The canonical 10-slide fundraising sequence (2026)

1. **Title / one-liner.** Wordmark + one declarative sentence. "[Company]: [verb] for [segment]."
   No tagline clutter. No logo density. Airbnb-2009 pattern.
2. **Problem.** Named customer pain, concrete not abstract. One big stat beats three bullets.
3. **Solution.** Benefit-framed ("compress 6-hour prep into 30 minutes"), not feature-framed.
4. **Traction (if any)** — front-load per Speedrun Josh Lu: "traction is number one, two, and
   three. Then team. Then TAM." If zero traction, replace with "Why now."
5. **Why now / earned secret.** Tie to a current inflection (LLMs + legal procurement,
   regulatory change, public data unlock).
6. **Market.** Bottoms-up SAM/SOM. ONE big number + one subtle concentric-rings diagram.
   Never a 3D pyramid.
7. **Product.** Either a single real screenshot in a Chrome-frame mockup, OR a 3-step workflow
   diagram. Kevin Hale (YC) bias: conceptual workflow > UI screenshot because UIs are illegible
   on a projector.
8. **Business model.** ARPU × segment-count. Tier table, three rows max. Sparkline for LTV.
   Never pie charts.
9. **Competition / why we win.** "Earned secret" framing OR 2×2 dot-plot. NEVER feature-
   checkmark grid (lets VCs count your missing ticks).
10. **Team + Ask.** Combined if team is small. Ask slide = one number + three bullets.
    "$X seed · N-month runway · $Y ARR target."

## Accelerator-specific overrides

### YC S26 (Summer 2026, deadline May 4, 2026 8pm PT)
- Application is form + 1-minute video + optional 1-slide deck (new YC S25 format).
- Deck for interview: partners often don't open decks during the 10-minute video interview.
  Have one ready; don't lead with it.
- **Tone rule:** Seibel canon — "raw, ugly, high-content slides (black text, white bg, Arial
  font)" over polished marketing brochures. Signals builder, not sales.
- **Jargon is a kill signal.** Scrub every industry term a non-partner wouldn't immediately
  understand.
- **Standard deal:** $500K = $125K on post-money SAFE for 7% + $375K uncapped MFN SAFE. Do not
  negotiate. Do not mention valuation.

### a16z Speedrun SR007 (deadline May 17, 2026 11:59pm PT)
- Application is form + PDF deck upload. Deck is scored.
- **Format rule:** Josh Lu on record — "maximum 7" slides.
- **Framing rule:** SCQA on slide 1 (Situation / Complication / Question / Answer).
- **Content rule:** "Black background with white or bright neon text works best — many
  investors watch on phones in bright rooms." Target phone legibility.
- **Killers:** missing deck link, inflated TAMs ("$800B legal services market!"), dishonest
  metrics (D30 = 80%), 15+ slides, "memoir style," 100-user-PMF claims.
- **Pattern:** outsider-AI-native founder beats domain veteran (Troy Kirwin's Sept 2025
  thesis). If founder lacks industry background, lead with velocity and AI-native credential.
- **Accepted SR005 precedent:** legal-tech winner had $210K ARR in 3 months and a Harvard CS +
  lawyer founder pair. Match one of {early revenue, credentialed pair} or don't apply.
- **ARR in pitch wins:** 32% of SR006 accepted cohort put ARR directly in the 10-word pitch.
  `"[AI verb] for [vertical] — $Xk ARR in Y weeks"` beats any adjective stack.

### CDL (Creative Destruction Lab) — Toronto
- Deck is part of full application but evaluation is objective-setting capacity more than
  polish. Each cohort session is 1 day of mentor speed-dating.
- **Stream fit matters:** apply to 1–2 streams (AI, Health, Climate, Matter, Space, Defence,
  Fintech). Do not broadcast-apply.

### Antler (pre-idea / pre-team residency)
- Less deck-centric than YC/Speedrun. LinkedIn + track record + in-person interview dominate.
- Score: self-starter trait, domain expertise, full-time commitment, adaptability, problem-
  deconstruction.

### MaRS Capital Program (relaunched Oct 2025)
- Deck + financial model review AFTER the 30–45 min screening call. Not at intake.
- Target: seed / Series A ready with measurable traction.

## Typography (free, production-grade)

- **Display / headings:** Source Serif 4 (Adobe, OFL) — 500, 600, 700.
- **Body / UI:** Inter (Rasmus Andersson, OFL) — 400, 500, 600, 700.
- **Numbers / citations / CLI:** JetBrains Mono (OFL) — 400, 500, 600.

~85% of the premium feel of GT Alpina + Söhne at $0 font spend.

**Hard rules:**
- Max 3 weights across the entire deck.
- Never italicize body.
- Eyebrows and labels only use all-caps, not body.
- 40pt minimum on every slide (Kevin Hale rule). 48pt+ for titles.

## Color (calibrated for 2026)

Default palette if the project has no brand:

| Token | Hex | Role |
|---|---|---|
| `ink` | `#0B1220` | Primary — near-black headings, hero |
| `paper` | `#FAF8F4` | Background (warm off-white) |
| `oxblood` | `#6B1F2E` | **Single accent** — one element per slide |
| `graphite` | `#3A4250` | Secondary text |
| `muted` | `#8A8578` | Metadata, captions |

Deviation matrix:
- Horizontal SaaS → primary accent = signal blue (`#1B4EE8`) or green (`#2F7D4D`).
- Consumer → primary accent = warmer (coral, rust) but still muted.
- Legal / gov / finance → oxblood or navy. **Never gold.** Gold-leaf reads law-firm-brochure.
- Never use pure white `#FFFFFF`. Warm off-white always.

## Design craft rules (2026 — not 2020)

1. **Border radius:** 8px cards, 6px buttons, 0px product screenshots.
2. **Hairline borders, not shadows.** `rgba(0,0,0,0.08)` at 1px. Shadow-heavy elevation
   reads Material-2019.
3. **Asymmetric layout:** left-rail eyebrow + right hero is the 2026 editorial pattern.
   Centered-symmetric reads PowerPoint-2015.
4. **Monospace for numbers.** Reinforces precision.
5. **Single accent per slide.** One element gets the brand color; everything else is
   paper + graphite + muted.
6. **Zero stock photography. Zero generic icon packs.** Type, data-viz, product screenshots.
7. **Data-viz: one chart per slide.** Line > bar > everything else. No pie charts ever.
   No 3D anything.

## Delivery stack (what to actually use in 2026)

- **Build:** HTML + CSS + Playwright → PDF (not python-pptx, not PowerPoint). Gives pixel
  perfect typography with real web fonts.
- **Share:** Papermark (AGPL open-source DocSend alternative) as the read-tracked link
  + always attach the PDF alongside. DocSend is dead — removed free tier, investors dislike.
- **Apply:** Upload PDF directly to accelerator form fields. Do NOT paste a Papermark or
  DocSend link where a native PDF upload is available. Partners rank "click a third-party
  link" below "scroll in the browser viewer."
- **Don't track:** email pixel trackers (Streak, Mailtrack, Yesware, HubSpot). Apple MPP
  destroys the signal, and they add spam-score risk on cold outbound.

## What to never do

1. **Inflated TAM** ("every man, woman, and child in Canada will use Casewright"). Instant
   SR reject per partner roundtable.
2. **Screenshots of complex UI.** Kevin Hale (YC) explicit call-out.
3. **Thin fonts + light gray.** YC Demo Day readability kill.
4. **15+ slides at seed.** Speedrun reject.
5. **3D pyramid TAM.** Reads 2018.
6. **Feature-checkmark competition matrix.** Lets VCs count your missing ticks.
7. **"Replacing humans" framing.** Especially in regulated verticals. Always "augmenting
   licensed professionals."
8. **Stock photography of handshakes, judges' gavels, generic teams.** Zero design investment
   signal.

## Template files this skill expects

When building from scratch, produce:
- `deck.html` — all slides in one file with `page-break-after: always`.
- `render_deck.py` — Playwright script that applies variant placeholders and renders to PDF.
- Variants: at least `speedrun`, `yc`, `fundraising`. Extend as needed.
- Place in `assets/deck/` if project is set up. Otherwise in project root.

## Self-check before shipping

- [ ] Every slide has ≤10 words of body or one big number + one caption.
- [ ] Font sizes ≥40pt. Weights ≤3. One font family.
- [ ] Single accent per slide.
- [ ] TAM is bottom-up with sources, not broadcast-market.
- [ ] Team slide has 1-line bios + 1-line credibility each.
- [ ] Ask slide has one number, three bullets, contact.
- [ ] No stock photography. No icon packs. No gradient anything.
- [ ] Read on a phone in a bright room — still legible?
- [ ] 3-minute read test: can a non-industry friend tell you (1) what we do, (2) why us,
      (3) is it big — in 3 minutes?
- [ ] Scrub jargon. Run text through any LLM with "list every industry term a non-partner
      wouldn't recognize," rewrite each.
- [ ] PDF embedded with fonts. No "Made with Gamma/Tome/Slidebean" watermark.
- [ ] Papermark share has email-gate OFF for VC audience, ON for cold outbound.

## Sources this skill is built on

- YC — Kevin Hale, "How to design a better pitch deck"
- a16z Speedrun — Substack, SR005 apps reviewed (3 signals)
- Sequoia — Writing a business plan (template)
- Harvey.ai — Design system writeup (typography rationale)
- Airbnb 2009 deck (Failory teardown)
- Front Series B 2020 deck (Mathilde Collin Medium post)
- Buffer $500K seed deck (Failory teardown)
- 28 YC S25 one-slide decks (Product Market Fit collection)
- Linear.app, Vercel, Cresta — modern B2B SaaS brand references

Internal research agents: 2026-04-21 three-agent deep-research pass.
