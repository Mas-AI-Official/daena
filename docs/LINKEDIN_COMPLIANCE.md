# LinkedIn Compliance

**TL;DR:** Daena never auto-sends on LinkedIn. The backend send endpoint
permanently returns `status=blocked` for the LinkedIn channel. The UI
gives the founder a one-click "Copy + Open LinkedIn" path instead,
which stays inside LinkedIn's ToS.

## Why we refuse to automate LinkedIn sending

LinkedIn's [Professional Community Policies](https://www.linkedin.com/legal/professional-community-policies)
and User Agreement prohibit:

- "Scrape or copy profiles and information of others through any means"
- "Use bots or other automated methods to access the Services, add or
  download contacts, send or redirect messages"
- "Upload or share content that infringes [...] LinkedIn's
  professional community policies"

LinkedIn actively detects automation:

- Device fingerprinting (canvas, WebGL, fonts, screen)
- Mouse/keyboard entropy analysis (robots type at a suspiciously
  regular cadence)
- Session behavior (messaging 50 strangers in 10 minutes is a signal)
- Network-level: headless Chromium, proxy rotation, TLS fingerprints

The penalty is **permanent account restriction with no appeal**, which
for a solo founder often means losing the only inbound-sales channel
you have.

Tools that do automate LinkedIn (PhantomBuster, Dux-Soup, LinkedHelper,
Waalaxy, Expandi, etc.) rely on browser automation and proxy
rotation. They work until they don't. LinkedIn's detection has
improved meaningfully in 2024-2026, and the "grace period" of "my
account survived for N months" is survivorship bias: the bans are
invisible until they land on you.

## What Daena does instead

1. **Generates the draft.** The Marketing Mind (Zephyr) writes a
   personalized first-touch message using the founder brief + prospect
   signals. This is identical to any other channel (email, SMS).
2. **Queues it in the approval surface.** The draft sits in the
   in-process draft store with `status=awaiting_approval`.
3. **Provides Copy + Open LinkedIn.** From the mission drafts modal,
   a single button:
   - Writes `Subject: {subject}\n\n{body}` to the clipboard (if no
     subject, just the body).
   - Opens `https://www.linkedin.com/messaging/` in a new tab.
   - Toast: "Body copied. Paste into LinkedIn and send from your
     own session."
   - **The founder's own LinkedIn session sends the message.** No
     scraping, no browser automation, no ToS violation.
4. **Records the manual handoff.** A "Mark handled" button calls
   the standard send endpoint, which for LinkedIn returns
   `status=blocked, provider=linkedin-manual`. The draft state
   updates so the founder can track which prospects are done.

## Contrast: what Daena DOES automate on LinkedIn

Nothing. The LinkedIn surface is strictly draft-and-hand-off.

If we ever add LinkedIn actions, they will only be:

- Searching your own first-degree connections via the official
  LinkedIn Sales Navigator API, which requires a LinkedIn Marketing
  Developer Platform partnership and is only available to enterprise
  customers. We are not on that path as of 2026.
- Logging activity to CRM via the same official API.

We will never:

- Use headless Chromium or Puppeteer against linkedin.com.
- Route connection requests or InMail through a proxy.
- Scrape profiles.

## Why this is a product feature, not a limitation

Every account we preserve is an account we can eventually market to.
Founders who got their LinkedIn banned by PhantomBuster in 2024 lost
their entire reach overnight. Daena's value proposition is governed
AI; if we automated in ways that burned the founder, we would be
showing instead of telling on the core premise.

Governance is the product.

## Roadmap for LinkedIn (honest path)

Three things are on the menu if the draft-and-click UX feels slow:

1. **Chrome extension** (MVP). A small extension that injects a
   "Load from Daena" button into LinkedIn's own messaging composer.
   User clicks, the composer autofills with the draft. Send is
   triggered by the user inside LinkedIn's own UI. This is how
   Lavender, Reply.io, and other compliant tools work. Estimate: 3-5
   days of work, requires a published Chrome Web Store listing.
2. **Sales Navigator partnership.** Apply to LinkedIn's Marketing
   Developer Platform. This unlocks programmatic search and CRM
   sync but still does not permit messaging. Estimate: 2-3 months
   of review; approval is not guaranteed for companies under ~50
   employees.
3. **Alternative channels.** Email is unconstrained: the `send_email`
   provider already writes RFC-822 `.eml` files to
   `backend/var/outbox/` and can later be wired to SES, Postmark,
   Mailgun, or direct SMTP. Twitter DM API is open (rate-limited).
   If LinkedIn handoff is the bottleneck, most founders find that
   email covers 60-80% of outreach anyway.

See also: `backend/app/services/company_mode_providers.py::send_linkedin`
(the permanent block), `frontend/src/pages/CompanyModePage.tsx`
(the Copy + Open LinkedIn button), and inbox.md TICKET-COMPANY-MODE-03
for the shipping history.
