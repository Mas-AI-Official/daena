## WHAT_WE_DID_NOT_ADD (2025-12-13)

This upgrade explicitly avoided adding complexity that would slow the system down or make it harder to debug.

### Not added (by policy)
- **No new authentication layers** (no login/session/JWT changes required for runtime)
- **No encryption / crypto layers** (NBMF/EDNA are memory layers, not encryption layers)
- **No custom RSA / experimental security**
- **No React / Next / Node**
- **No cloud-only default providers** (cloud is opt-in, local-first remains default)
- **No duplicated “v2” services** (no `*_v2`, `operator2`, `automation_new` style forks)

### Not added (to keep stability)
- **No full “single-page HTMX shell refactor”** across every template.
  - Reason: many templates contain heavy inline JS initialization; aggressive HTMX swapping of whole pages can break script lifecycle.
  - Instead: we added Manus-style **internal panels** (Operator) inside the dashboard and kept navigation reliable.











