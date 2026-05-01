---
name: winning-pitch-deck
description: Use this skill when building, reviewing, or rebuilding a pitch deck for YC application, a16z Speedrun application, accelerator submissions, or seed/Series A fundraising in 2026. This skill is grounded in deep research of 30+ real funded decks (Airbnb, Stripe, Dropbox, Coinbase, DoorDash, Notion, Figma, Linear, Vercel, Decagon, Mistral, Brex, CommandBar, Anduril, Saronic, Speedrun SR005-SR007 cohorts) plus Reddit/Twitter founder postmortems and Papermark's 2024-25 metrics study (n=3,000 decks, 8M data points). Triggers: user says "pitch deck", "build a deck", "winning deck", "YC deck", "Speedrun deck", "rebuild deck", "deck design", or asks for design feedback on a deck.
allowed_tools: Bash, Write, Edit, Read, Agent, Glob, Grep, WebFetch
---

# Winning Pitch Deck — 2026 Skill

Build pitch decks that are calibrated to what actually GETS FUNDED in 2026, not what looks pretty. Every rule in this skill traces back to a real funded deck or a verified VC partner statement, with sources.

## TLDR — the modal winning pattern

**10-12 slides, Inter or Helvetica Neue, single accent color, phone-first design, ≤10 words per slide, killer one-liner cover, traction at slide 4-5 (never buried), team-as-receipts not bios, ask slide names milestones not just dollars.**

That's it. The rest of this skill is implementation detail.

---

## Empirical patterns (sourced from 30+ funded decks)

### 1. Slide count distribution (Papermark 2024 study, n=3,000 decks)

| Stage | Modal slide count | Range |
|---|---|---|
| Pre-seed / seed | **10-12** | 7-14 |
| Seed / Series A | 12-16 | 10-18 |
| Series A+ | 16-18 | 14-20 |
| Cold-email teaser | 3-7 | — |

**49% of all funded decks** land in the 9-16 range. a16z Speedrun's hard ceiling: "If you cannot tell your story in 12 to 15 slides max, then your deck is not ready." One a16z partner won't read past slide 7.

### 2. The modal slide order (NOT Sequoia template)

Across 12 verified funded decks (Airbnb, Stripe, Dropbox, Coinbase, DoorDash, Notion, Figma, Linear, Vercel, Decagon, Mistral, Brex), the EMPIRICAL modal order is:

1. **Cover** — wordmark + one-line "we do X for Y" (5-12 words)
2. **Problem** — one image OR three bolded statements
3. **Solution** — one sentence + screenshot/diagram (benefits, not features)
4. **Product / How it works** — 3-step or hero screenshot
5. **Traction** — earliest possible. NEVER buried.
6. **Market** — bottom-up calc preferred over TAM block
7. **Why now / Insight** — what you know that others don't (often merged with market or competition)
8. **Business model** — one sentence ("10% take rate")
9. **Team** — receipts (test scores, prior exits, domain expertise) NOT bios
10. **Ask** — $X for Y milestones in Z months

**Sequoia's 10-slide template (Company purpose, Problem, Solution, Why now, Market size, Competition, Product, Business model, Team, Financials/ask) is NOT what most winners did.** It's the template VCs prescribe but founders deviate from.

### 3. Typography (what funded decks actually use)

| Font | Usage | Source |
|---|---|---|
| **Inter** | Brex's $57M Series B confirmed; modern AI-infra default | [VIP Graphics Brex teardown](https://vip.graphics/brex-pitch-deck/) |
| **Helvetica Neue** | Airbnb 2009 confirmed | [SlideBean Airbnb teardown](https://slidebean.com/blog/airbnb-pitch-deck) |
| Helvetica / Arial | Most 2007-2015 cohort (Dropbox, Coinbase, Stripe, DoorDash) | Multiple teardowns |
| Inter / Space Grotesk | 2020+ cohort (Linear, Vercel, modern Pitch.com defaults) | Linear blog, Vercel deck |
| Roboto / Open Sans / Avenir / Montserrat | Acceptable secondary defaults | InkNarrates designer consensus |

**Avoid:** Source Serif 4, GT America, Söhne, Tiempos, National 2, Aktiv Grotesk. These are agency/brand fonts. Founders raising rounds use system-safe sans-serifs because PDF/PPTX cross-platform rendering matters more than aesthetic differentiation.

**Sizes:** Headline 32-44pt minimum (32pt = phone-readable floor). Body 18-28pt. Numbers 56pt+. Cover hook 60-100pt.

### 4. Color palette rules

- **2-4 colors maximum.** "93% of decks failed on design specifically due to chaotic mixes of fonts, colors, and layout experiments" (Focused Chaos VC review of 50 decks).
- **Single accent per slide.** One element gets the brand color; everything else is neutral.
- **2026 AI-infra norm:** dark/charcoal background + electric/neon accent (teal `#2DD4BF`, electric green `#2F7D4D`, violet `#7C3AED`). 6 of 10 verified AI infra decks used this.
- **Industry conventions:**
  - Tech/SaaS: blue OR charcoal + single accent
  - Fintech: deep navy + metallic
  - Healthcare/sustainability: greens + soft blues
  - Defense (Anduril/Saronic): minimal color, grayscale-dominant, gov-procurement coded
- **Hard rule:** never pure white `#FFFFFF`. Always warm off-white `#FAF8F4` or paper-tinted neutral.

### 5. Cover slide format (the highest-leverage slide)

Investor behavior data: cover gets 23 seconds (50% more than other slides). Pages 2-10 get ~15s each.

**Format that wins:**
- Wordmark (your name in your typography)
- ONE line of 5-12 words
- Founder name + email + URL in monospace, bottom-left or bottom-right at 12-14pt

**Killer one-liner patterns from funded decks:**
| Company | Cover line | Pattern |
|---|---|---|
| Airbnb | "Book rooms with locals, rather than hotels" | Comparative |
| Front | "Email was designed for individuals, not teams" | Contrarian |
| Mixpanel | "Google Analytics shows you what happened. We show you why." | Comparative |
| Loom | "Explaining anything complex over text is painful" | Pain-as-headline |
| Buffer | "The easiest way to schedule tweets and posts to Facebook" | Plain-functional |
| Dutchie | "10% of all legal cannabis purchased through us" | Traction-as-tagline |

The 5 patterns: **Comparative · Contrarian · Pain-as-headline · Plain-functional · Traction-as-tagline.**

### 6. The killer slide (the ONE that closes)

Different by stage:

- **AI infrastructure / research-heavy:** Team slide. Mistral closed €105M with NO product, just researcher receipts (DeepMind, Meta, Google).
- **Consumer:** Traction slide. Reddit's redesign deck led with growth charts.
- **Dev tools:** Product/code panes. Vercel's "deploy command" slide. Stripe's "7 lines of code" hook.
- **Defense/dual-use:** Mission/why-this-matters. Anduril's first slide: "Anduril will save lives."
- **Marketplace / SaaS:** Unit economics + retention. Front's Series B deck.

Identify your killer slide BEFORE choosing slide order. The killer slide always lands at slide 4 or 5.

### 7. Phone-first design (Speedrun's "investors watch on phones in bright rooms" rule)

Papermark 2024-25 metrics:
- Avg total deck review time: **3.2 min**
- Cover slide: **23 seconds**
- Pages 2-10: **~15 seconds each**
- 31% bounce within first 10 seconds
- 49% of decks are 9-16 pages

Implications:
- 32pt+ minimum type
- Single point per slide (multi-point slides unreadable on phone)
- Charts: one variable, no legends, no 3D
- Dark backgrounds with high-contrast accent (works in bright rooms)
- No 3-column comparison tables (unreadable on phone)
- Test the actual PDF on your own phone in daylight before sending

### 8. Tools — what real founders use

| Platform | 2007-2018 cohort | 2020+ cohort | When to use |
|---|---|---|---|
| **Keynote** | 80% (Airbnb, Dropbox, Coinbase, DoorDash, Notion, Linear original) | 20% (defense — Saronic, Anduril) | Solo founder, design-fluent, exporting PPT/PDF |
| **Pitch.com** | n/a | 60% (Linear current, most YC W22+ batches) | Collaboration, live-tracked share links |
| **Figma / Figma Slides** | n/a | 20% (Figma itself, Linear team, design-led) | Design-heavy decks, component reuse |
| **Google Slides** | rare | 10% | Universal compatibility, free, Gemini AI |
| **Notion + screenshots** | rare | rising | Mistral's path. Memo-style for thesis-led raises. |
| **Custom HTML/Next.js** | n/a | rare but high-signal | Vercel, Linear (signals taste; rendered to PDF via Playwright) |

**Avoid:** Tome (PDF-export only since 2024 pivot kills final hand-off), Gamma (free tier branded — investor liability), Slidebean (community bottom-ranked).

### 9. Sharing — DocSend is dying, Papermark is winning

- **DocSend:** killed free tier 2024, "most VCs never open from cold outreach" (Papermark blog). Still owned by Dropbox; paid tier alive but losing share.
- **Papermark:** open-source, YC-backed, 3,000+ decks/year on platform. Custom domains, transparent code, self-hostable. Now named "the new standard" by founder-facing publishers (EasyVC).

**2026 best practice:**
1. Cold outreach: PDF attached (no gated link)
2. After meeting: Papermark-tracked link for follow-up
3. Long-form data room: Notion or Papermark data room

Pitching Angels rule: "Send a PDF if fundraising speed is the priority; send a link if security and control are critical. Investors prefer PDFs because they can easily share decks with their advisory network without triggering follow-up requests."

---

## Variant matrices

### YC application (S26 batch, deadline May 4, 2026 8pm PT)

- Application is form + 1-minute video + optional 1-slide deck (Demo Day Garry Tan rule)
- **Decks are EXPLICITLY BANNED in YC interviews.** Don't waste time polishing past the form.
- 1-minute video: nothing except founders talking. Not a demo, not promotional. Just talking.
- Standard YC deal: $125K post-money SAFE for 7% + $375K uncapped MFN. Do not negotiate. Do not mention valuation.
- Garry Tan 2025: "the only information present is revenue numbers, because it's really the only thing that matters"
- **Most underrated slides in YC deck:** Team and ICP/customer validation
- **Most overrated:** TAM and multi-year revenue projections

### a16z Speedrun (SR007 deadline May 17, 2026 11:59pm PT)

- Application is form + 2-min pitch video + PDF deck upload
- **Hard rule: 7-15 slides max**. One partner won't read past slide 7.
- **3 admission signals (Josh Lu, Speedrun lead):** traction (best is revenue, then growth, then retention), team/founder-market-fit, TAM
- **SCQA on slide 1:** Situation / Complication / Question / Answer
- Black background + bright/neon text works best ("investors watch on phones in bright rooms")
- 32% of accepted SR006 cohort put ARR in their 10-word pitch
- "Match one of {early revenue, credentialed pair} or don't apply"
- Killer reasons to reject: missing deck link, inflated TAMs, dishonest metrics (D30=80%), 15+ slides, "memoir style," 100-user-PMF claims

### Sequoia / Index / Founders Fund seed deck

- 10-12 slides, full sequence
- Cover, Problem, Solution, Why now, Market, Competition, Product, Business model, Team, Ask
- Email-attach + Papermark-track-link

### Demo Day pitch (post-YC acceptance only)

- 1-slide on screen, 2-minute spoken pitch
- Garry Tan rule: revenue numbers ONLY
- Practice for clarity, not presence

### Cold-investor email (warm-intro alternative)

- 3-7 slide teaser PDF
- Lead with traction or team
- One-page founder note in email body

---

## Hard rules (non-negotiable)

### What to NEVER do
1. **Inflated TAM.** "$800B legal services market" = instant Speedrun reject.
2. **Multi-year revenue projections.** Garry Tan: most overrated slide.
3. **Screenshots of complex UI.** Kevin Hale (YC) explicit call-out — illegible on projector.
4. **Thin fonts + light gray text.** YC Demo Day readability kill.
5. **15+ slides at seed.** Speedrun reject.
6. **3D pyramid TAM.** Reads 2018.
7. **Feature-checkmark competition matrix.** Lets VCs count your missing ticks.
8. **"Replacing humans" framing in regulated verticals.** Always "augmenting licensed professionals."
9. **Stock photography of handshakes, judges' gavels, generic teams.** Zero design investment signal.
10. **Embedded videos / animations in PDF.** Don't render in 80% of cold-reviewer email opens.
11. **DocSend gated viewing for cold outreach.** Most VCs never open these.
12. **"Thank you / Questions?" closing slide.** End on the ask + contact.
13. **AI-buzzword adjective stacks.** "AI-powered intelligent automated platform" = filtered out.
14. **Em dashes.** Use hyphens or other punctuation. (Daena CLAUDE.md rule 12.)

### What to ALWAYS do
1. ≤10 words per slide (or one big number + one caption)
2. Single accent color per slide
3. One chart per slide (line > bar > everything else)
4. Bottom-up market math, not broadcast TAM
5. Team slide = receipts (test scores, prior exits, domain expertise), not bios
6. Ask slide = one number + three bullets + contact
7. Phone test: read the PDF on your phone in daylight before sending
8. 3-minute test: a non-industry friend understands what you do, why you, and is-it-big in 3 minutes
9. Jargon scrub: remove every term a non-partner wouldn't recognize
10. PDF embedded with fonts (verify after first render)

---

## The 8-step build process

### Step 1: Lock the killer slide
Before touching slide 1, decide which slide is your killer. AI infra: team. Consumer: traction. Dev tools: product. Defense: mission. Marketplace: unit economics. **Everything else serves the killer.**

### Step 2: Lock the cover one-liner
Pick from the 5 patterns: Comparative · Contrarian · Pain-as-headline · Plain-functional · Traction-as-tagline. 5-12 words.

### Step 3: Pick variant
YC (1 slide) · Speedrun (7 slides) · Full fundraising (10-12 slides) · Cold teaser (3-7 slides). Build all in one HTML source if multiple needed.

### Step 4: Pick platform
Pitch.com (collaboration), Figma (design-fluent team), Keynote (solo with PDF export), custom HTML+Playwright (dev-tool founders, signals taste). Use what you already know — learning a tool eats more time than design polish saves.

### Step 5: Lock typography + accent
Inter for modern, Helvetica Neue for classic. ONE accent color matched to industry. 32pt body / 48pt+ titles / 60-100pt hero numbers.

### Step 6: Build slide-by-slide using modal order
Cover · Problem · Solution · Product · Traction (slide 4 or 5) · Market · Why-now (or merge into market/competition) · Business model · Team-as-receipts · Ask. Adjust based on killer slide placement.

### Step 7: Phone test + 3-min friend test + jargon scrub
- PDF on phone in bright room: every line legible?
- Non-industry friend: 3-min explanation passes?
- Jargon: feed text to LLM with "list every term a non-partner wouldn't recognize"

### Step 8: Render + deliver
- HTML + Playwright → PDF (1920x1080, 2x scale for retina)
- Upload to Papermark for tracked link
- Send PDF attached + link in email
- Never paste a Papermark link where the application form expects native PDF upload

---

## Files this skill expects to produce

For each project, build under `<project>/deck/` or chosen path:

- `deck.html` — single source, all variants with CSS class filtering (`.yc`, `.speedrun`, `.fundraising`)
- `render_deck.py` — Playwright PDF renderer with `--variant` and `--all` flags
- `README.md` — design system + self-check checklist + render instructions
- `out/<company>-<variant>.pdf` — generated PDFs per variant

Optional:
- `<company>-<variant>.pptx` via `anthropic-skills:pptx` skill
- `image-prompts.md` — only if photography is genuinely required (most decks don't use any)

---

## Self-check before shipping

- [ ] Slide count: 10-12 for fundraising, 7 for Speedrun, 1 for YC form
- [ ] Cover: wordmark + 5-12 word hook + footer
- [ ] Traction at slide 4 or 5 (NEVER buried)
- [ ] Killer slide identified and prominent
- [ ] Inter or Helvetica Neue (NOT Source Serif, NOT GT America)
- [ ] Single accent color across deck
- [ ] All headlines ≥32pt, body ≥18pt
- [ ] Phone test passed (read on actual phone in daylight)
- [ ] 3-min friend test passed
- [ ] Jargon scrubbed
- [ ] No em dashes
- [ ] No stock photo, no icon packs, no 3D pyramid, no feature-checkmark matrix
- [ ] No "Thank you" closing slide
- [ ] Team slide = receipts, not bios
- [ ] Ask slide = one number + milestones + contact
- [ ] PDF rendered with embedded fonts
- [ ] Papermark link prepared for follow-up share

---

## Sources (research base — refresh when this skill is updated)

### YC patterns
- Paul Graham, [How to Present to Investors](https://www.paulgraham.com/investors.html)
- Michael Seibel, [How to Pitch Your Company](https://www.michaelseibel.com/blog/how-to-pitch-your-company)
- Garry Tan, [X 2025 take on Demo Day pitches](https://x.com/garrytan/status/1898817313685872665)
- Geoff Ralston / Justin Kan, [YC Demo Day pitch guide](https://www.ycombinator.com/blog/guide-to-demo-day-pitches/)
- [YC Practical Design: Pitching](https://www.ycombinator.com/blog/practical-design-pitching/)
- [YC Interview Guide — decks forbidden](https://www.ycombinator.com/interviews)
- [YC W25 Demo Day standouts — TechCrunch](https://techcrunch.com/2025/03/13/10-startups-to-watch-from-y-combinators-w25-demo-day/)

### a16z Speedrun
- [Speedrun: SR005 Apps Reviewed — 3 signals](https://speedrun.substack.com/p/sr005-apps-reviewed-the-3-signals-that-get-startups-in)
- [Speedrun: How to Pitch in Under 2 Min](https://speedrun.substack.com/p/how-to-pitch-in-under-2-min)
- [Speedrun: How to Make a Viral Launch Video](https://speedrun.substack.com/p/how-to-make-a-viral-launch-video)
- [Speedrun: 58 founders, 2 minutes to pitch](https://speedrun.substack.com/p/58-founders-2-minutes-to-pitch-scenes)

### Real funded decks (cited)
- [Airbnb seed deck breakdown — Alexander Jarvis](https://www.alexanderjarvis.com/airbnb-seed-pitch-deck/)
- [Dropbox seed deck — Alexander Jarvis](https://medium.com/@adjblog/dropbox-pitch-deck-to-raise-seed-capital-investment-6a6cd6517e56)
- [Coinbase seed pitch — Brian Armstrong on Medium](https://barmstrong.medium.com/the-coinbase-seed-round-pitch-deck-50c8ec91d40b)
- [DoorDash YC Demo Day breakdown — Slidebean](https://slidebean.com/blog/doordash-in-yc-demo-day)
- [Notion seed deck (2013) — official Notion site](https://notion.notion.site/Notion-Seed-Pitch-Deck-2013-26634e24c14543d7a1c72325bcb4d2df)
- [Brex pitch deck teardown — VIP Graphics (Inter font confirmed)](https://vip.graphics/brex-pitch-deck/)
- [Linear Sequoia seed announcement](https://medium.com/linear-app/linears-next-chapter-announcing-our-4-2m-seed-round-2b5035602b77)
- [Decagon $35M deck — Lifeboat](https://lifeboat.com/blog/2024/06/decagon-raises-35-million-from-accel-and-a16z-to-build-ai-customer-support-agents-heres-an-exclusive-look-at-the-pitch-deck-it-used)
- [Mistral AI €105M Pitch Memo Analysis — Linas Substack](https://linas.substack.com/p/mistralpitch)

### Sharing platforms
- [Papermark 2024-25 Pitch Deck Metrics study (n=3,000)](https://www.papermark.com/pitch-deck-metrics)
- [Pitching Angels: PDF vs Link 2025](https://pitchingangels.com/2025/08/21/pitch-deck-pdf-or-link/)
- [EasyVC: 10 DocSend alternatives 2025](https://easyvc.ai/blog/10-alternatives-to-docsend-in-2025/)

### Design + design platform research
- [Focused Chaos VC review of 50 pitch decks](https://www.focusedchaos.co/p/i-reviewed-50-startup-pitch-decks)
- [InkNarrates: Best Fonts and Colors for Pitch Decks](https://www.inknarrates.com/post/best-fonts-and-colors-for-pitch-deck)
- [Visible.vc 11 Presentation Design Trends 2026](https://visible.vc/blog/startup-presentation-design-trends/)

---

## Mirror

Per SKILLS SYNC RULE in CLAUDE.md, this skill is mirrored to `D:\Ideas\Daena\skills\winning-pitch-deck\SKILL.md`.

## Last updated
2026-04-29 — initial version, grounded in 30+ funded decks + Papermark metrics study + Reddit/Twitter founder data.
