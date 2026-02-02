
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Rect, Line, String

C_L1 = colors.mistyrose
C_L2 = colors.lemonchiffon
C_L3 = colors.lightcyan
C_EDNA = colors.darkseagreen
C_EDNA_BOX = colors.honeydew
C_SEC = colors.lavenderblush
C_PROC = colors.whitesmoke
C_HDW = colors.aliceblue
C_TEXT = colors.black
C_LINE = colors.dimgrey

def draw_rect(d, x, y, w, h, color, text="", subtext=None, bold=False, rx=6, ry=6):
    d.add(Rect(x, y, w, h, rx=rx, ry=ry, fillColor=color, strokeColor=C_LINE, strokeWidth=1))
    if text:
        d.add(String(x+w/2, y+h/2 + (6 if subtext else 0),
                     text, fontSize=9, fontName="Helvetica-Bold" if bold else "Helvetica",
                     textAnchor="middle", fillColor=C_TEXT))
    if subtext:
        d.add(String(x+w/2, y+h/2-10, subtext, fontSize=7,
                     fontName="Helvetica", textAnchor="middle", fillColor=colors.darkgrey))

def draw_arrow(d, x1, y1, x2, y2, label=None):
    d.add(Line(x1, y1, x2, y2, strokeColor=C_LINE, strokeWidth=1.4, arrow=True))
    if label:
        d.add(String((x1+x2)/2, (y1+y2)/2 - 8, label, fontSize=7, textAnchor="middle", fillColor=colors.grey))

def fig1_overview():
    d = Drawing(460, 280)
    d.add(Rect(20, 242, 420, 28, rx=5, ry=5, fillColor=C_EDNA, strokeColor=None))
    d.add(String(230, 255, "eDNA GOVERNANCE LAYER (Genome • Epigenome • Lineage • Immune)",
                 fontSize=10, textAnchor="middle", fillColor=colors.white, fontName="Helvetica-Bold"))
    draw_rect(d, 40, 150, 100, 60, C_L1, "L1 (Hot)", "Vector DB (RAM)")
    draw_rect(d, 180, 150, 100, 60, C_L2, "L2 (Warm)", "NBMF Index (NVMe)")
    draw_rect(d, 320, 150, 100, 60, C_L3, "L3 (Cold)", "Compressed (Blob)")
    draw_rect(d, 180, 90, 100, 30, C_PROC, "Memory Router")
    draw_rect(d, 60, 50, 120, 30, C_PROC, "Promotion Logic", "Freq↑ Recency↑")
    draw_rect(d, 280, 50, 120, 30, C_PROC, "Eviction Logic", "Age↑ Freq↓")
    draw_arrow(d, 230, 120, 230, 150)
    draw_arrow(d, 180, 180, 140, 180)
    draw_arrow(d, 280, 180, 320, 180)
    draw_arrow(d, 230, 90, 120, 80)
    draw_arrow(d, 230, 90, 340, 80)
    return d

def fig2_promotion():
    d = Drawing(460, 220)
    draw_rect(d, 30, 150, 100, 50, C_L3, "L3 (Cold)")
    draw_rect(d, 180, 150, 100, 50, C_L2, "L2 (Warm)")
    draw_rect(d, 330, 150, 100, 50, C_L1, "L1 (Hot)")
    draw_arrow(d, 130, 185, 180, 185, "Promote (>10 hits)")
    draw_arrow(d, 280, 185, 330, 185, "Promote (Recent)")
    draw_arrow(d, 330, 165, 280, 165, "Evict (>1hr)")
    draw_arrow(d, 180, 165, 130, 165, "Evict (>7d)")
    draw_rect(d, 180, 60, 100, 40, C_SEC, "Trust Check")
    draw_arrow(d, 230, 150, 230, 100, "Validate")
    return d

def fig3_trust():
    d = Drawing(460, 250)
    draw_rect(d, 20, 180, 120, 50, colors.lightgrey, "Incoming Data")
    draw_rect(d, 170, 180, 120, 50, C_SEC, "L2Q Buffer", "Quarantine State")
    draw_rect(d, 320, 200, 120, 40, C_PROC, "Consensus Check")
    draw_rect(d, 320, 140, 120, 40, C_PROC, "Divergence Check")
    draw_rect(d, 170, 60, 120, 50, colors.gold, "Trust Score")
    draw_rect(d, 20, 60, 120, 50, C_L2, "Promote to L2", "Verified")
    draw_rect(d, 320, 60, 120, 50, colors.lightcoral, "Reject/Sanitize", "Malicious")
    draw_arrow(d, 140, 205, 170, 205)
    draw_arrow(d, 290, 205, 320, 220)
    draw_arrow(d, 290, 205, 320, 160)
    draw_arrow(d, 230, 180, 230, 110)
    draw_arrow(d, 170, 85, 140, 85)
    draw_arrow(d, 290, 85, 320, 85)
    return d

def fig4_encoding():
    d = Drawing(460, 200)
    draw_rect(d, 20, 100, 100, 50, C_PROC, "Input Data")
    draw_arrow(d, 120, 125, 160, 125)
    draw_rect(d, 160, 100, 120, 50, C_EDNA_BOX, "Domain Encoder")
    draw_arrow(d, 280, 140, 320, 160)
    draw_rect(d, 320, 150, 100, 30, C_L3, "Lossless", "Exact storage")
    draw_arrow(d, 280, 110, 320, 90)
    draw_rect(d, 320, 70, 100, 30, C_L1, "Semantic", "Vector Embed")
    draw_rect(d, 160, 20, 260, 30, C_HDW, "NBMF Bytecode Object")
    d.add(Line(420, 165, 440, 125, strokeColor=C_LINE))
    d.add(Line(420, 85, 440, 125, strokeColor=C_LINE))
    d.add(Line(440, 125, 420, 35, strokeColor=C_LINE, arrow=True))
    return d

def fig5_merkle():
    d = Drawing(460, 230)
    draw_rect(d, 180, 180, 100, 40, colors.gold, "Root Hash", "Top-level sig")
    draw_rect(d, 100, 120, 80, 30, C_PROC, "Hash A")
    draw_rect(d, 280, 120, 80, 30, C_PROC, "Hash B")
    draw_rect(d, 40, 60, 90, 30, C_L2, "Event: Promo")
    draw_rect(d, 140, 60, 90, 30, C_L2, "Event: Evict")
    draw_rect(d, 330, 60, 90, 30, C_L2, "Event: Edit")
    d.add(Line(230, 180, 140, 150, strokeColor=C_LINE))
    d.add(Line(230, 180, 320, 150, strokeColor=C_LINE))
    d.add(Line(140, 120, 85, 90, strokeColor=C_LINE))
    d.add(Line(140, 120, 185, 90, strokeColor=C_LINE))
    d.add(Line(320, 120, 375, 90, strokeColor=C_LINE))
    return d

def fig6_edna():
    d = Drawing(460, 260)
    # eDNA banner for context
    d.add(Rect(20, 230, 420, 24, rx=5, ry=5, fillColor=C_EDNA, strokeColor=None))
    d.add(String(230, 241, "eDNA GOVERNANCE LAYER", fontSize=9,
                 textAnchor="middle", fillColor=colors.white, fontName="Helvetica-Bold"))
    # Core storage
    draw_rect(d, 130, 120, 200, 60, colors.lightgoldenrodyellow, "NBMF Storage", "Protected Core", bold=True)
    # Components
    genome = (40, 170, 100, 45); epig = (180, 180, 100, 45); line = (320, 170, 100, 45); imm = (180, 30, 100, 45)
    draw_rect(d, *genome, C_EDNA_BOX, "Genome", "Capabilities", bold=True)
    draw_rect(d, *epig, C_EDNA_BOX, "Epigenome", "Policies", bold=True)
    draw_rect(d, *line, C_EDNA_BOX, "Lineage", "Audit Log", bold=True)
    draw_rect(d, *imm, C_SEC, "Immune", "Defense", bold=True)
    # Connectors (the missing lines)
    def center(box): x,y,w,h = box; return (x+w/2, y+h/2)
    g=genome; e=epig; l=line; i=imm
    # To core
    for bx in (g,e,l,i):
        cx, cy = center(bx); d.add(Line(cx, cy, 230, 150, strokeColor=C_LINE, strokeWidth=1.2))
    # Governance band to components (light vertical tics)
    for bx in (g,e,l):
        cx, cy = center(bx); d.add(Line(cx, 230, cx, cy+25, strokeColor=colors.darkseagreen, strokeWidth=0.8))
    return d

def fig7_immune():
    d = Drawing(460, 200)
    draw_rect(d, 30, 140, 100, 40, C_SEC, "1. Detect", "Anomaly/Breach")
    draw_arrow(d, 130, 160, 180, 160)
    draw_rect(d, 180, 140, 100, 40, colors.orange, "2. Quarantine", "Isolate ID")
    draw_arrow(d, 280, 160, 330, 160)
    draw_rect(d, 330, 140, 100, 40, colors.lightgreen, "3. Rollback", "Restore Root")
    draw_rect(d, 30, 40, 400, 40, C_L2, "NBMF State (L1 / L2 / L3)")
    draw_arrow(d, 230, 140, 230, 80)
    draw_arrow(d, 380, 140, 380, 80)
    return d

def fig8_hw():
    d = Drawing(460, 200)
    draw_rect(d, 20, 80, 120, 60, C_HDW, "Device Manager")
    draw_arrow(d, 140, 110, 180, 110)
    draw_rect(d, 180, 80, 100, 60, C_PROC, "Tensor Router")
    draw_rect(d, 340, 150, 80, 30, C_HDW, "CPU")
    draw_rect(d, 340, 95, 80, 30, C_HDW, "GPU")
    draw_rect(d, 340, 40, 80, 30, C_HDW, "TPU")
    draw_arrow(d, 280, 120, 340, 165)
    draw_arrow(d, 280, 110, 340, 110)
    draw_arrow(d, 280, 100, 340, 55)
    return d

def fig9_cross():
    d = Drawing(460, 220)
    draw_rect(d, 20, 160, 100, 40, colors.mistyrose, "Tenant A", "Raw Data")
    draw_rect(d, 20, 100, 100, 40, colors.mistyrose, "Tenant B", "Raw Data")
    draw_rect(d, 160, 80, 100, 140, C_SEC, "Sanitization", "Strip PII")
    draw_rect(d, 300, 110, 140, 80, C_L2, "Shared Patterns", "Abstract Vectors")
    draw_arrow(d, 120, 180, 160, 180)
    draw_arrow(d, 120, 120, 160, 120)
    draw_arrow(d, 260, 150, 300, 150)
    return d

FIG_FUNCS = [fig1_overview, fig2_promotion, fig3_trust, fig4_encoding, fig5_merkle, fig6_edna, fig7_immune, fig8_hw, fig9_cross]
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
FIG_DETAILS = [
    "The eDNA banner governs a three-tier memory fabric. A policy-aware router mediates movement of memories between tiers while promotion and eviction logic apply frequency, recency, and age signals.",
    "Memories move upward when they are recent or popular and move downward when stale. A trust gate validates promotions to prevent corruption of warm and hot tiers.",
    "Before persistence, new items pass through an L2 quarantine buffer and are scored by consensus and divergence. Only sufficiently trusted items are promoted; others are sanitized or rejected.",
    "Input is encoded via a domain encoder. Lossless mode preserves exact bytes; semantic mode stores vectorized meaning. Both converge into an NBMF bytecode object with metadata.",
    "All promotions and edits append events to a Merkle tree that yields a verifiable root for audits and rollback.",
    "The eDNA layer exposes capability schemas (Genome), policy (Epigenome), notarized history (Lineage), and a defensive Immune module that intervenes on risk. Components are wired to the protected NBMF core via governance connectors (lines) from the band and to the core.",
    "Detections trigger quarantine; if necessary, the system rolls back state to a known good Merkle root to maintain integrity.",
    "A device manager and tensor router dynamically choose CPU, GPU, or TPU targets to balance cost and latency for encoding and retrieval operations.",
    "Tenant data never leaves its boundary; only abstracted artifacts—patterns and vectors—are shared to enable cross-tenant learning without raw data leakage."
]
