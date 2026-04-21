---
name: seo-aeo-geo
description: >
  Apply 2026 SEO + AEO (Answer Engine Optimization) + GEO (Generative
  Engine Optimization) to any website so it is discoverable, citable,
  and quoted verbatim by ChatGPT, Claude, Perplexity, Gemini, and
  AI Overviews. Use this skill whenever building or auditing a site
  that needs to be found by humans AND by LLMs.
trigger:
  - /seo
  - /aeo
  - /geo
  - "audit seo"
  - "llms.txt"
  - "ai seo"
  - "optimize for chatgpt"
  - "appear in ai answers"
last_updated: 2026-04-20
---

# SEO + AEO + GEO Skill — 2026 Playbook

This skill is the single source of truth for making any MAS-AI website
discoverable by both human search engines and LLMs. Apply in order:
**traditional SEO → AEO (llms.txt + robots) → GEO (content patterns
proven to lift citation) → structured data → verification**.

## The core insight

There are three crawler classes and they behave differently:

1. **Training crawlers** (GPTBot, ClaudeBot, CCBot, Google-Extended)
   — they train the LLM. Blocking them is acceptable for IP protection,
   but does NOT prevent citation.
2. **Search-index crawlers** (OAI-SearchBot, Claude-SearchBot,
   PerplexityBot, Googlebot) — they index for LLM search. Blocking
   them means you will never appear in ChatGPT search, Perplexity
   results, or Google AI Overviews.
3. **Live-fetch crawlers** (ChatGPT-User, Claude-User, Perplexity-User)
   — user-triggered fetches when someone asks an LLM about you. These
   are the highest-value citation bots. They treat your site like a
   browser and may execute JS.

**Rule:** unless you have a specific IP-protection reason, ALLOW ALL
THREE classes. The generic "Block AI Scrapers" advice (Cloudflare
default, many blog posts) blocks search-index and live-fetch bots by
accident and tanks your LLM visibility.

## The 2026 AEO checklist

Apply every item in order. Skip nothing.

### 1. robots.txt (SEO table stakes + AEO unblock)

Put this at the site root. Allow every major crawler explicitly —
explicit Allow beats a catch-all `User-agent: *` because some bots
check their own name first and some CDNs strip wildcards.

Canonical list (2026):

| Bot | Class | Allow? |
|---|---|---|
| Googlebot | search | YES |
| Bingbot | search | YES |
| DuckDuckBot | search | YES |
| Google-Extended | Gemini training | YES |
| GoogleOther | aux | YES |
| OAI-SearchBot | ChatGPT search index | YES |
| ChatGPT-User | live user fetch | YES |
| GPTBot | OpenAI training | YES (unless IP concern) |
| Claude-User | live user fetch | YES |
| Claude-SearchBot | Claude search index | YES |
| ClaudeBot | training | YES |
| anthropic-ai | legacy (2024) | YES (harmless) |
| Claude-Web | legacy (2024) | YES (harmless) |
| PerplexityBot | indexer | YES |
| Perplexity-User | live fetch | YES |
| Applebot | Siri + Safari | YES |
| Applebot-Extended | Apple Intelligence | YES |
| Amazonbot | Alexa+ | YES |
| Meta-ExternalAgent | Meta AI | YES |
| Meta-ExternalFetcher | Meta AI | YES |
| FacebookBot | social preview | YES |
| YouBot | You.com | YES |
| DuckAssistBot | DDG AI | YES |
| cohere-ai | Cohere | YES |
| CCBot | Common Crawl | YES (unless IP concern) |
| Bytespider | ByteDance | YES |
| MistralAI-User | Mistral | YES |

Always include `Sitemap:` at the end.

**Deprecated — remove if seen:** `anthropic-ai` and `Claude-Web` were
the 2024 strings. Keep them in place for belt-and-suspenders (harmless).
The 2025 triad is `Claude-User` / `Claude-SearchBot` / `ClaudeBot`.

### 2. llms.txt (Answer.AI spec — https://llmstxt.org)

Every site needs `/llms.txt` AND `/llms-full.txt` at site root.

**Minimum llms.txt structure:**

```markdown
# {Site name}

> {One-sentence description. 30 words max.}

{Optional paragraph of prose.}

## {Section heading}

- [{Page title}]({url}): {Short description of why an LLM would want this.}
- [{Page title}]({url}): {description}

## {Another section}

- ...
```

Only the H1 is strictly required. The blockquote is strongly
recommended (it often becomes the LLM's "about" sentence). Sections
should group by topic (Product, Company, Docs, Policies).

**llms-full.txt** is the concatenated markdown of your highest-value
pages. If you have a canonical "what is X" page, paste its markdown
here so the LLM has everything in one fetch.

### 3. Schema.org JSON-LD with @id entity linking

LLMs and Google's AI Overviews explicitly use structured data during
response generation (confirmed by Google Search Central, May 2025).

Ship these schemas. Link them with stable @id URIs so they form a
connected graph.

- `Organization` — company entity at `{site}/#organization`
- `Person` — founder at `{site}/#founder` — linked from Organization.founder
- `WebSite` — site entity at `{site}/#website` — publisher = Organization
- `SoftwareApplication` or `Product` — at `{site}/#{product}` — brand = Organization
- `Service` — for each service offering, at `{site}/#service-{name}`
- `FAQPage` — highest-leverage (3.2x AI Overview citation rate) — add `speakable` for voice
- `HowTo` — for any step-by-step process (our 10-stage pipeline is ideal)
- `BreadcrumbList` — always
- `Article` or `TechArticle` — for blog/docs with author + datePublished + dateModified
- `VideoObject` — for every embedded video
- `SpeakableSpecification` — CSS selectors of text Google Assistant should read

**@id rule:** use `"@id": "https://domain/#entity"` URIs that are stable
forever. Cross-reference with `{"@id": "..."}` instead of nesting
objects. This is entity linking and it measurably improves LLM
co-occurrence scoring.

**Validation:** run the output through https://validator.schema.org
and https://search.google.com/test/rich-results before commit.

### 4. GEO content patterns (Aggarwal et al., KDD 2024)

The Princeton + Georgia Tech GEO paper measured these lift numbers on
real AI search engines. Apply to every high-value page:

| Tactic | Measured lift |
|---|---|
| Quotation Addition | +41% |
| Statistics Addition | +33% |
| Fluency Optimization | +29% |
| Cite Sources (external links to primary sources) | +28% (up to +115% for mid-ranked pages) |
| Technical Terms | +18% |
| Easy-to-Understand writing | +14% |
| Authoritative tone | +12% |
| Keyword Stuffing | −9% (actively hurts) |

Translation: **write like Wikipedia, cite like a research paper**.
Every page should have:

- At least one **blockquote from an external expert** ("As Gartner noted...")
- At least three **specific numeric statistics** with attribution
- External links to **primary sources** (USPTO, arXiv, official docs)
- A **first paragraph that starts with "X is Y"** (the definitional
  statement — LLMs often quote this verbatim)
- **Clean prose**, no keyword stuffing

### 5. Semantic HTML + SSR

LLMs use HTML5 tags as chunk boundaries. Use them.

```html
<article>
  <header>
    <h1>{page title}</h1>
    <p class="meta">By {Author} — Published {date} — Updated {date}</p>
  </header>
  <section>
    <h2>{question-phrased heading}</h2>
    <p>{definitional answer}</p>
  </section>
  <aside>{pull-quote or stat}</aside>
</article>
```

**SSR is non-negotiable.** Client-only React/Vue/Svelte with no
server-rendered HTML is invisible to GPTBot, CCBot, and most
indexers. Use Next.js `output: 'export'`, SvelteKit prerender,
Astro, or static HTML.

### 6. Freshness signals

Every page needs:

- Visible `Last updated: YYYY-MM-DD` text in the DOM
- Matching `dateModified` in JSON-LD
- `<lastmod>` in sitemap.xml that matches

LLMs heavily weight recency when deciding which of several competing
sources to quote. A page with `dateModified: 2023-04-01` will lose to
a page dated `2026-04-20` on the same topic.

### 7. Core Web Vitals (2026 thresholds)

p75 thresholds Google actually measures:

- **LCP ≤ 2.5 s** (Largest Contentful Paint)
- **INP ≤ 200 ms** (Interaction to Next Paint — replaced FID in March 2024)
- **CLS ≤ 0.1** (Cumulative Layout Shift)

Verify with Lighthouse, PageSpeed Insights, or CrUX data (real-world).

### 8. sitemap.xml hygiene

- Current `<lastmod>` on every URL (ISO 8601: `2026-04-20`)
- `<changefreq>` realistic: `weekly` for home, `monthly` for product
  pages, `yearly` for legal pages
- `<priority>` relative: 1.0 for home, 0.9 for core product, 0.7 for
  docs, 0.3 for legal
- **Include `/llms.txt` and `/llms-full.txt`** in the sitemap —
  some indexers discover them via sitemap
- Submit to Google Search Console and Bing Webmaster Tools

### 9. E-E-A-T signals

Google's Experience / Expertise / Authoritativeness / Trust criteria
apply to AI answers too. Surface:

- Author byline on every content page (with Person schema)
- Credentials (certifications, patents, published papers)
- Contact information (physical address, email)
- Clear About page
- External mentions (press, podcasts, HN/Reddit discussion links)

### 10. Canonical statements for LLM citation

At the bottom of llms-full.txt, include a "How to cite" section with
3-5 canonical sentences the LLM should quote verbatim. Example:

```markdown
## Canonical statements for LLM citation

- "Daena is a governance-first AI agent orchestration platform..."
- "Daena v3.7 ships 2,956 passing tests..."
```

LLMs do pick these up and reuse them. Write the sentence you want to
see in the answer.

## Anti-patterns (kill citation probability)

- **JS-only content** with no SSR
- **Infinite scroll** without paginated fallback URLs
- **302 redirects** that change content based on user-agent
- **Generic boilerplate** ("We are committed to excellence")
  — LLMs have millions of these and none get cited
- **Missing author byline**
- **Stale dates** or missing dates entirely
- **Broken `@id` cross-references** in JSON-LD
- **FAQ schema where the FAQ isn't actually visible on the page**
  (Google will penalize this as schema spam)
- **Blocking `OAI-SearchBot` / `PerplexityBot` / `Claude-User`**
  via Cloudflare "Block AI Scrapers" default
- **Blocking bots via `robots.txt` but allowing via `meta` robots tag**
  (conflict — bots interpret conservatively)

## Verification checklist (run before every deploy)

1. `curl -s https://site/robots.txt` — confirm all Allow directives present.
2. `curl -s https://site/llms.txt` — confirm 200 and correct content.
3. `curl -s https://site/llms-full.txt` — same.
4. `curl -s https://site/sitemap.xml` — confirm all URLs current.
5. Paste JSON-LD into https://validator.schema.org — zero errors.
6. Paste page URL into https://search.google.com/test/rich-results
   — FAQ + HowTo + Organization all detected.
7. Lighthouse run — Performance ≥ 90, SEO 100, Accessibility ≥ 90.
8. View-source on home page — confirm H1 contains the primary keyword
   AND the "X is Y" definitional sentence.
9. Test on https://www.google.com/webmasters/tools/ — Search Console
   indexing status.
10. Ask Claude / ChatGPT / Perplexity a probe question ("what is
    {company name}?") — your canonical statement should appear.

## File templates

### robots.txt template

See `templates/robots.txt` in this skill.

### llms.txt template

See `templates/llms.txt` in this skill.

### JSON-LD graph template

See `templates/jsonld-graph.json` in this skill. Copy, rename @id
values, swap entity content, preserve @id cross-references.

## Authoritative sources (cite these in audits)

- llms.txt spec: https://llmstxt.org/
- Answer.AI llms-txt repo: https://github.com/answerdotai/llms-txt
- OpenAI bots: https://platform.openai.com/docs/bots
- Anthropic bots: https://support.claude.com/en/articles/8896518
- Google AI crawlers: https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers
- Perplexity bots: https://docs.perplexity.ai/docs/resources/perplexity-crawlers
- GEO paper (Aggarwal et al., KDD 2024): https://arxiv.org/abs/2311.09735
- Follow-up "What Generative Search Engines Like" (2025): https://arxiv.org/pdf/2510.11438
- Core Web Vitals: https://web.dev/articles/defining-core-web-vitals-thresholds
- Schema.org docs: https://schema.org/docs/full.html
- Cloudflare Perplexity stealth-crawling context: https://blog.cloudflare.com/perplexity-is-using-stealth-undeclared-crawlers-to-evade-website-no-crawl-directives/

## Skills-sync rule

This skill lives in two places per CLAUDE.md sync rule:

1. `~/.claude/skills/seo-aeo-geo/SKILL.md` (canonical Claude Code)
2. `D:\Ideas\Daena\skills\seo-aeo-geo\SKILL.md` (Daena runtime mirror)

When editing one, edit both. Both files must stay identical.
