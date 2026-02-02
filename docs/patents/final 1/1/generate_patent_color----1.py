from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Rect, Line, String

# ---------------- COLOR PALETTE ----------------
C_L1 = colors.mistyrose       # Hot Memory
C_L2 = colors.lemonchiffon    # Warm Memory
C_L3 = colors.lightcyan       # Cold Memory
C_EDNA = colors.honeydew      # Governance/eDNA
C_SEC = colors.lavenderblush  # Security/Immune
C_PROC = colors.whitesmoke    # Processes/Logic
C_HDW = colors.aliceblue      # Hardware
C_TEXT = colors.black
C_LINE = colors.dimgrey

def draw_rect_c(d, x, y, w, h, color, text=None, subtext=None):
    d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=color, strokeColor=C_LINE, strokeWidth=1))
    if text:
        d.add(String(x + w/2, y + h/2 + (5 if subtext else -3), text,
                     fontSize=9, fontName="Helvetica-Bold", textAnchor="middle", fillColor=C_TEXT))
    if subtext:
        d.add(String(x + w/2, y + h/2 - 7, subtext,
                     fontSize=7, fontName="Helvetica", textAnchor="middle", fillColor=colors.darkgrey))

def draw_arrow(d, x1, y1, x2, y2, label=None):
    d.add(Line(x1, y1, x2, y2, strokeColor=C_LINE, strokeWidth=1.5, arrow=True))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        d.add(String(mx, my-3, label, fontSize=7, textAnchor="middle", fillColor=colors.dimgrey))

# ---------------- FIGURES ----------------

def fig1_overview():
    d = Drawing(460, 280)
    # Header Band (eDNA)
    d.add(Rect(20, 240, 420, 30, rx=5, ry=5, fillColor=colors.darkseagreen, strokeColor=None))
    d.add(String(230, 250, "eDNA GOVERNANCE LAYER (Genome • Epigenome • Lineage • Immune)",
                 fontSize=10, textAnchor="middle", fillColor=colors.white, fontName="Helvetica-Bold"))
    # Memory Tiers
    draw_rect_c(d, 40, 150, 100, 60, C_L1, "L1 (Hot)", "Vector DB (RAM)")
    draw_rect_c(d, 180, 150, 100, 60, C_L2, "L2 (Warm)", "NBMF Index (NVMe)")
    draw_rect_c(d, 320, 150, 100, 60, C_L3, "L3 (Cold)", "Compressed (Blob)")
    # Router and logic
    draw_rect_c(d, 180, 90, 100, 30, C_PROC, "Memory Router")
    draw_rect_c(d, 60, 50, 120, 30, C_PROC, "Promotion Logic", "Freq↑ Recency↑")
    draw_rect_c(d, 280, 50, 120, 30, C_PROC, "Eviction Logic", "Age↑ Freq↓")
    # Arrows
    draw_arrow(d, 230, 120, 230, 150)
    draw_arrow(d, 180, 180, 140, 180)
    draw_arrow(d, 280, 180, 320, 180)
    draw_arrow(d, 230, 90, 120, 80)
    draw_arrow(d, 230, 90, 340, 80)
    return d

def fig2_promotion():
    d = Drawing(460, 220)
    draw_rect_c(d, 30, 150, 100, 50, C_L3, "L3 (Cold)")
    draw_rect_c(d, 180, 150, 100, 50, C_L2, "L2 (Warm)")
    draw_rect_c(d, 330, 150, 100, 50, C_L1, "L1 (Hot)")
    draw_arrow(d, 130, 185, 180, 185, "Promote (>10 hits)")
    draw_arrow(d, 280, 185, 330, 185, "Promote (Recent)")
    draw_arrow(d, 330, 165, 280, 165, "Evict (>1hr)")
    draw_arrow(d, 180, 165, 130, 165, "Evict (>7d)")
    draw_rect_c(d, 180, 60, 100, 40, C_SEC, "Trust Check")
    draw_arrow(d, 230, 150, 230, 100, "Validate")
    return d

def fig3_trust():
    d = Drawing(460, 250)
    draw_rect_c(d, 20, 180, 120, 50, colors.lightgrey, "Incoming Data")
    draw_rect_c(d, 170, 180, 120, 50, C_SEC, "L2Q Buffer", "Quarantine State")
    draw_rect_c(d, 320, 200, 120, 40, C_PROC, "Consensus Check")
    draw_rect_c(d, 320, 140, 120, 40, C_PROC, "Divergence Check")
    draw_rect_c(d, 170, 60, 120, 50, colors.gold, "Trust Score")
    draw_rect_c(d, 20, 60, 120, 50, C_L2, "Promote to L2", "Verified")
    draw_rect_c(d, 320, 60, 120, 50, colors.lightcoral, "Reject/Sanitize", "Malicious")
    draw_arrow(d, 140, 205, 170, 205)
    draw_arrow(d, 290, 205, 320, 220)
    draw_arrow(d, 290, 205, 320, 160)
    draw_arrow(d, 230, 180, 230, 110)
    draw_arrow(d, 170, 85, 140, 85)
    draw_arrow(d, 290, 85, 320, 85)
    return d

def fig4_encoding():
    d = Drawing(460, 200)
    draw_rect_c(d, 20, 100, 100, 50, C_PROC, "Input Data")
    draw_arrow(d, 120, 125, 160, 125)
    draw_rect_c(d, 160, 100, 120, 50, C_EDNA, "Domain Encoder")
    draw_arrow(d, 280, 140, 320, 160)
    draw_rect_c(d, 320, 150, 100, 30, C_L3, "Lossless", "Exact storage")
    draw_arrow(d, 280, 110, 320, 90)
    draw_rect_c(d, 320, 70, 100, 30, C_L1, "Semantic", "Vector Embed")
    draw_rect_c(d, 160, 20, 260, 30, C_HDW, "NBMF Bytecode Object")
    d.add(Line(420, 165, 440, 125, strokeColor=C_LINE))
    d.add(Line(420, 85, 440, 125, strokeColor=C_LINE))
    d.add(Line(440, 125, 420, 35, strokeColor=C_LINE, arrow=True))
    return d

def fig5_merkle():
    d = Drawing(460, 220)
    draw_rect_c(d, 180, 170, 100, 40, colors.gold, "Root Hash", "Top-level sig")
    draw_rect_c(d, 100, 110, 80, 30, C_PROC, "Hash A")
    draw_rect_c(d, 280, 110, 80, 30, C_PROC, "Hash B")
    draw_rect_c(d, 40, 50, 90, 30, C_L2, "Event: Promo")
    draw_rect_c(d, 140, 50, 90, 30, C_L2, "Event: Evict")
    draw_rect_c(d, 330, 50, 90, 30, C_L2, "Event: Edit")
    d.add(Line(230, 170, 140, 140, strokeColor=C_LINE))
    d.add(Line(230, 170, 320, 140, strokeColor=C_LINE))
    d.add(Line(140, 110, 85, 80, strokeColor=C_LINE))
    d.add(Line(140, 110, 185, 80, strokeColor=C_LINE))
    d.add(Line(320, 110, 375, 80, strokeColor=C_LINE))
    return d

def fig6_edna():
    d = Drawing(460, 250)
    draw_rect_c(d, 130, 100, 200, 60, C_L2, "NBMF Storage", "Protected Core")
    draw_rect_c(d, 20, 180, 100, 50, C_EDNA, "Genome", "Capabilities")
    draw_rect_c(d, 180, 200, 100, 50, C_EDNA, "Epigenome", "Policies")
    draw_rect_c(d, 340, 180, 100, 50, C_EDNA, "Lineage", "Audit Log")
    draw_rect_c(d, 180, 10, 100, 50, C_SEC, "Immune", "Defense")
    return d

def fig7_immune_workflow():
    d = Drawing(460, 200)
    draw_rect_c(d, 30, 140, 100, 40, C_SEC, "1. Detect", "Anomaly/Breach")
    draw_arrow(d, 130, 160, 180, 160)
    draw_rect_c(d, 180, 140, 100, 40, colors.orange, "2. Quarantine", "Isolate ID")
    draw_arrow(d, 280, 160, 330, 160)
    draw_rect_c(d, 330, 140, 100, 40, colors.lightgreen, "3. Rollback", "Restore Root")
    draw_rect_c(d, 30, 40, 400, 40, C_L2, "NBMF State (L1 / L2 / L3)")
    draw_arrow(d, 230, 140, 230, 80)
    draw_arrow(d, 380, 140, 380, 80)
    return d

def fig8_hardware():
    d = Drawing(460, 200)
    draw_rect_c(d, 20, 80, 120, 60, C_HDW, "Device Manager")
    draw_arrow(d, 140, 110, 180, 110)
    draw_rect_c(d, 180, 80, 100, 60, C_PROC, "Tensor Router")
    draw_rect_c(d, 340, 150, 80, 30, C_HDW, "CPU")
    draw_rect_c(d, 340, 95, 80, 30, C_HDW, "GPU")
    draw_rect_c(d, 340, 40, 80, 30, C_HDW, "TPU")
    draw_arrow(d, 280, 120, 340, 165)
    draw_arrow(d, 280, 110, 340, 110)
    draw_arrow(d, 280, 100, 340, 55)
    return d

def fig9_cross_tenant():
    d = Drawing(460, 220)
    draw_rect_c(d, 20, 160, 100, 40, colors.mistyrose, "Tenant A", "Raw Data")
    draw_rect_c(d, 20, 100, 100, 40, colors.mistyrose, "Tenant B", "Raw Data")
    draw_rect_c(d, 160, 80, 100, 140, C_SEC, "Sanitization", "Strip PII")
    draw_rect_c(d, 300, 110, 140, 80, C_L2, "Shared Patterns", "Abstract Vectors")
    draw_arrow(d, 120, 180, 160, 180)
    draw_arrow(d, 120, 120, 160, 120)
    draw_arrow(d, 260, 150, 300, 150)
    return d

# Exports expected by the builder
FIG_FUNCS = [
    fig1_overview, fig2_promotion, fig3_trust, fig4_encoding,
    fig5_merkle, fig6_edna, fig7_immune_workflow, fig8_hardware, fig9_cross_tenant
]

FIG_CAPTIONS = [
    "FIG. 1 — NBMF System Overview.",
    "FIG. 2 — Promotion & Eviction flow with thresholds and validation.",
    "FIG. 3 — Trust & Quarantine pipeline including consensus/divergence checks.",
    "FIG. 4 — Neural encoding into lossless vs semantic NBMF bytecode.",
    "FIG. 5 — Merkle-notarized lineage tree for audit proofs.",
    "FIG. 6 — eDNA components: Genome, Epigenome, Lineage, and Immune modules.",
    "FIG. 7 — Immune workflow: detect, quarantine, and rollback.",
    "FIG. 8 — Hardware abstraction and tensor routing across CPU/GPU/TPU.",
    "FIG. 9 — Cross-tenant isolation with sanitized, shareable artifacts."
]

# Optional longer paragraph placed directly under each figure
FIG_DETAILS = [
    "The eDNA banner governs a three-tier memory fabric. A policy-aware router mediates movement of memories between tiers while promotion and eviction logic apply frequency, recency, and age signals.",
    "Memories move upward when they are recent or popular and move downward when stale. A trust gate validates promotions to prevent corruption of warm and hot tiers.",
    "Before persistence, new items pass through an L2 quarantine buffer and are scored by consensus and divergence. Only sufficiently trusted items are promoted; others are sanitized or rejected.",
    "Input is encoded via a domain encoder. Lossless mode preserves exact bytes; semantic mode stores vectorized meaning. Both converge into an NBMF bytecode object with metadata.",
    "All promotions and edits append events to a Merkle tree that yields a verifiable root for audits and rollback.",
    "The eDNA layer exposes capability schemas (Genome), policy (Epigenome), notarized history (Lineage), and a defensive Immune module that intervenes on risk.",
    "Detections trigger quarantine; if necessary the system rolls back state to a known good Merkle root to maintain integrity.",
    "A device manager and tensor router dynamically choose CPU, GPU, or TPU targets to balance cost and latency for encoding and retrieval operations.",
    "Tenant data never leaves its boundary; only abstracted artifacts—patterns and vectors—are shared to enable cross-tenant learning without raw data leakage."
]
