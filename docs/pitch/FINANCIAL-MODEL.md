# Daena Financial Model

*MAS-AI Technologies Inc. | April 2026 | For investor discussion*

This document is a transparent projection, not a forecast. Every assumption is labeled. Actuals will vary.

---

## Pricing Tiers

| Tier | Monthly Price | Annual Price | Typical Usage | Target Segment |
|---|---|---|---|---|
| FREE | $0 | $0 | 100 messages / day, Ollama only | Privacy-first devs, students, self-hosters |
| PRO Starter | $29 | $290 | 2,000 messages / mo, all providers | Power users, indie devs, side projects |
| PRO Team | $99 | $990 | 10,000 messages / mo, 5 seats, Council mode | Small agencies, 2-10 person teams |
| ENTERPRISE | $500+ | $5,000+ | Unlimited, SSO, tenant isolation, on-prem option | Regulated industries, 50+ seats |

Overage billing on PRO: $0.01 per 100 messages. Enterprise is custom.

---

## Unit Economics

### Cost per conversation (average 2,000 tokens)

| Runtime | Cost per 1M tokens in | Cost per 1M tokens out | Cost per conversation |
|---|---|---|---|
| Ollama local | 0 | 0 | 0 (user hardware) |
| Daena vLLM cloud | $0.40 | $0.80 | $0.0012 |
| Claude Sonnet | $3.00 | $15.00 | $0.018 |
| GPT-4o | $2.50 | $10.00 | $0.0125 |
| Groq Llama | $0.05 | $0.08 | $0.00013 |

**Blended expected cost per PRO conversation**: $0.008 (model router biases toward low-cost providers for trivial queries).

### Gross margin by tier

| Tier | Avg monthly usage | COGS per user | Revenue | Gross margin |
|---|---|---|---|---|
| FREE | 50 conversations | $0 (local) | $0 | n/a (lead gen) |
| PRO Starter | 1,200 conversations | $9.60 | $29 | 67% |
| PRO Team | 6,000 conversations | $48 | $99 | 51% |
| ENTERPRISE | 80,000 conversations | $640 + $150 infra | $2,500 avg | 68% |

Gross margin improves with scale: bulk provider discounts at $50K+ MRR, self-hosted vLLM cheaper than API at high volume. Target blended GM 75% by month 18.

---

## 24-Month Scenarios

### Conservative (solo founder, no hires, organic only)

| Month | FREE users | PRO users | ENT contracts | MRR | Cumulative burn |
|---|---|---|---|---|---|
| 3 | 50 | 5 | 0 | $145 | $6,000 |
| 6 | 200 | 20 | 1 | $1,080 | $16,000 |
| 12 | 800 | 80 | 3 | $5,820 | $40,000 |
| 18 | 2,000 | 200 | 8 | $18,200 | $50,000 |
| 24 | 4,000 | 400 | 15 | $38,600 | $45,000 |

Break-even at month 20. Runway need: ~$60K for 24 months if founder draws minimum.

### Base (one senior hire at month 3, paid marketing month 6+)

| Month | FREE users | PRO users | ENT contracts | MRR | Cumulative burn |
|---|---|---|---|---|---|
| 3 | 100 | 15 | 0 | $435 | $10,000 |
| 6 | 600 | 80 | 2 | $3,820 | $55,000 |
| 12 | 3,000 | 400 | 10 | $20,600 | $160,000 |
| 18 | 10,000 | 1,200 | 25 | $75,800 | $220,000 |
| 24 | 25,000 | 3,000 | 60 | $216,000 | $150,000 |

Break-even month 22. Runway need: ~$300K for 24 months.

### Aggressive (YC S26 accepted, $500K check, 3 hires by month 6)

| Month | FREE users | PRO users | ENT contracts | MRR | Cumulative burn |
|---|---|---|---|---|---|
| 3 | 300 | 30 | 1 | $1,370 | $30,000 |
| 6 | 2,000 | 300 | 8 | $12,700 | $180,000 |
| 12 | 15,000 | 2,500 | 40 | $125,500 | $450,000 |
| 18 | 50,000 | 8,000 | 120 | $420,000 | $200,000 MRR surplus |
| 24 | 150,000 | 25,000 | 300 | $1,325,000 | Net positive |

Break-even month 16. Post-money target: $8-12M Series A at month 18.

---

## Assumptions (the ones that matter)

1. **Cost per conversation stays below $0.01 blended.** Valid if model router works and Groq/Ollama share stays > 60% of volume.
2. **FREE-to-PRO conversion: 10%.** Industry benchmark for dev tools. Daena's governance angle may lift this.
3. **PRO churn: 5% monthly.** Aggressive. Typical indie dev tool is 8-12%. Daena's audit trail + memory make it sticky.
4. **ENTERPRISE sales cycle: 60 days.** Faster than typical enterprise because Daena can be deployed locally for evaluation without procurement.
5. **CAC: $20 PRO, $800 ENTERPRISE.** Mostly organic Phase 1-3 (HN, r/LocalLLaMA, Product Hunt, YC). Paid acquisition begins Phase 4.
6. **GPU infra cost: $150-400 / mo.** Single L4 on GCP covers FREE + PRO Ollama fallback to month 12. Scaling to T4 + L40S cluster at month 12+.
7. **Compliance revenue multiplier: 3x.** ENTERPRISE with SOC2 + HIPAA audit trail justifies 3x standard price. Audit is Daena's native architecture, not a custom build.

---

## Use of Funds (pre-seed ask)

| Category | Amount | Duration | What it buys |
|---|---|---|---|
| Founder runway | $90K | 12 months | Masoud full-time, no side work |
| Senior engineer | $150K | 12 months | Scale Living Company execution, enterprise features |
| GPU + infra | $30K | 12 months | vLLM cloud, GCP, Cloudflare, monitoring |
| Marketing + content | $15K | 12 months | Demo videos, blog posts, PH launch, conference |
| Legal + IP | $15K | 12 months | Additional provisional patents, incorporation, terms |
| **Total** | **$300K** | | |

Investor conversation dictates actual round size and terms.

---

## Key risks (the ones most likely to bite)

1. **OpenClaw or Anthropic ships governance natively.** Moat eroded. Mitigation: Daena's governance is architecture, not a wrapper. Replicating it requires a full rebuild, not a patch.
2. **Enterprise sales cycle longer than 60 days.** Runway pressure. Mitigation: PRO revenue covers burn at 3K users in base case.
3. **Hosted OAuth broker cost.** Per inbox Work C decision, Daena deferred the broker and committed to MCP-first. Lower infra cost, higher setup friction. If MCP adoption stays niche, user friction becomes a growth tax.
4. **Laevateinn open-source backfire.** If the community forks the engine + strips governance, Daena becomes a reference implementation without the moat. Mitigation: MIT license on Laevateinn only, governance/NBMF remain proprietary.

---

## Disclaimer

This is a founder projection for internal planning and investor discussion. Numbers reflect best available information as of April 2026. Actuals will differ. MAS-AI Technologies Inc. makes no forward-looking guarantees.
