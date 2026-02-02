# generate_patent.py
# Clean, centered, monochrome PPA generator for NBMF-eDNA
# Fixes: alignment, color, TODO/SOURCE leakage, fee amount, 9-figure set.

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, String, Polygon
from reportlab.lib.units import inch

# ---------------- CONFIG ----------------
FILENAME = "NBMF_Patent_Application_2.pdf"

TITLE = "Neural-Backed Memory Fabric with Enterprise Digital DNA (NBMF-eDNA)"
FILING_DATE = "2025-01-15"

# Enter the fields you want. Empty strings are safely omitted from the output.
INVENTOR_NAME = "Masoud Masoori"
INVENTOR_CITY = "Richmond Hill"
INVENTOR_REGION = "ON"
INVENTOR_COUNTRY = "Canada"
CONTACT_EMAIL = ""
CONTACT_ADDRESS = ""

# If you prefer a minimal spec (no “Examples & Benchmarks” table), set False:
INCLUDE_BENCHMARKS = False
# ----------------------------------------


def _styles():
    styles = getSampleStyleSheet()
    s = {
        "title": styles["Title"],
        "h1": ParagraphStyle(
            name="H1", parent=styles["Heading1"], spaceBefore=14, spaceAfter=10
        ),
        "h2": ParagraphStyle(
            name="H2", parent=styles["Heading2"], spaceBefore=10, spaceAfter=8
        ),
        "body": ParagraphStyle(
            name="Body", parent=styles["BodyText"], leading=13, spaceAfter=6
        ),
        "caption": ParagraphStyle(
            name="Caption", parent=styles["BodyText"], alignment=1,  # center
            fontName="Times-Italic", fontSize=9, spaceAfter=14, spaceBefore=4
        ),
    }
    return s


# ---------- Helpers: center drawings & monochrome primitives ----------
def center(drawing, width=6.25 * inch):
    """Wrap a Drawing in a single-cell table to center it."""
    t = Table([[drawing]], colWidths=[width])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return t


def BW_Rect(x, y, w, h, stroke=1.2):
    return Rect(x, y, w, h, strokeColor=colors.black, fillColor=colors.white, strokeWidth=stroke)


def BW_Circle(cx, cy, r, stroke=1.2):
    return Circle(cx, cy, r, strokeColor=colors.black, fillColor=colors.white, strokeWidth=stroke)


def BW_Line(x1, y1, x2, y2, stroke=1.0, dash=None):
    ln = Line(x1, y1, x2, y2, strokeColor=colors.black, strokeWidth=stroke)
    if dash:
        ln.strokeDashArray = dash
    return ln


def BW_String(x, y, text, size=9):
    return String(x, y, text, fontSize=size, fillColor=colors.black)


def BW_Diamond(cx, cy, w, h, stroke=1.2):
    # Polygon diamond centered at (cx,cy)
    pts = [cx, cy + h/2, cx + w/2, cy, cx, cy - h/2, cx - w/2, cy]
    return Polygon(pts, strokeColor=colors.black, fillColor=colors.white, strokeWidth=stroke)


# ---------- Figure drawings (monochrome, consistent sizes) ----------
def fig1_overview():
    d = Drawing(460, 300)
    d.add(BW_String(150, 275, "Enterprise Digital DNA (eDNA): Genome • Epigenome • Lineage • Immune", 10))
    d.add(BW_Line(20, 268, 440, 268, 1.0))

    # L1/L2/L3 blocks
    d.add(BW_Rect(30, 185, 120, 60)); d.add(BW_String(60, 215, "L1 — Hot (Vector DB)", 8))
    d.add(BW_Rect(170, 185, 120, 60)); d.add(BW_String(185, 215, "L2 — Warm (NBMF+AES-256)", 8))
    d.add(BW_Rect(310, 185, 120, 60)); d.add(BW_String(323, 215, "L3 — Cold (Compressed)", 8))

    # Router & controllers
    d.add(BW_Rect(170, 120, 120, 40)); d.add(BW_String(195, 135, "Memory Router", 9))
    d.add(BW_Rect(45, 80, 150, 30));  d.add(BW_String(55, 92, "Promotion: freq↑, recency↑, trust↑", 8))
    d.add(BW_Rect(265, 80, 150, 30)); d.add(BW_String(280, 92, "Eviction: age↑, frequency↓", 8))

    # Arrows
    for (x1, y1, x2, y2) in [(90, 185, 230, 160), (230, 160, 350, 185),
                             (350, 245, 230, 160), (230, 160, 90, 245),
                             (230, 120, 120, 95), (230, 120, 320, 95)]:
        d.add(BW_Line(x1, y1, x2, y2, 1.0))

    # Agents band
    d.add(BW_Rect(30, 25, 400, 35)); d.add(BW_String(75, 45, "Multi-Agent System • Departments • CMP Bus", 9))
    d.add(BW_Line(230, 120, 230, 60, 1.0)); d.add(BW_Line(230, 60, 230, 60, 1.0))
    return d


def fig2_promotion():
    d = Drawing(460, 260)
    # L3->L2->L1 chain
    d.add(BW_Rect(30, 175, 120, 50));  d.add(BW_String(75, 195, "L3 (Cold)", 9))
    d.add(BW_Rect(170, 175, 120, 50)); d.add(BW_String(210, 195, "L2 (Warm)", 9))
    d.add(BW_Rect(310, 175, 120, 50)); d.add(BW_String(350, 195, "L1 (Hot)", 9))

    # Promotion arrows
    d.add(BW_Line(150, 200, 170, 200, 1.0)); d.add(BW_String(152, 208, "Promote if access>10 & trust≥0.7", 7))
    d.add(BW_Line(290, 200, 310, 200, 1.0)); d.add(BW_String(293, 208, "Promote if recency<1h", 7))

    # Eviction arrows (back)
    d.add(BW_Line(430, 190, 310, 190, 1.0)); d.add(BW_String(350, 175, "Evict if age>1h", 7))
    d.add(BW_Line(290, 190, 150, 190, 1.0)); d.add(BW_String(195, 175, "Evict if age>7d", 7))

    # Validation path
    d.add(BW_Rect(30, 95, 135, 45)); d.add(BW_String(50, 115, "New Memory (L2Q)", 9))
    d.add(BW_Rect(180, 95, 120, 45)); d.add(BW_String(195, 115, "Trust Score", 9))
    d.add(BW_Rect(320, 95, 120, 45)); d.add(BW_String(335, 115, "Decision: Promote/Reject", 9))
    d.add(BW_Line(165, 118, 180, 118, 1.0)); d.add(BW_Line(300, 118, 320, 118, 1.0))
    return d


def fig3_trust_L2Q():
    d = Drawing(460, 260)
    d.add(BW_Rect(20, 180, 140, 50));  d.add(BW_String(45, 200, "Incoming Data", 9))
    d.add(BW_Rect(170, 180, 140, 50)); d.add(BW_String(205, 200, "L2Q Buffer", 9))
    d.add(BW_Rect(330, 195, 120, 60)); d.add(BW_String(340, 225, "Multi-Model Consensus", 8))
    d.add(BW_Rect(330, 130, 120, 50)); d.add(BW_String(345, 155, "Divergence Check", 8))
    d.add(BW_Rect(170, 60, 140, 50));  d.add(BW_String(205, 82, "Trust Score", 9))
    d.add(BW_Rect(20, 60, 140, 50));   d.add(BW_String(35, 82, "Promote to L2", 9))
    d.add(BW_Rect(330, 60, 120, 50));  d.add(BW_String(350, 82, "Reject / Sanitize", 9))

    for (x1, y1, x2, y2) in [(160, 205, 170, 205), (310, 205, 330, 225),
                             (310, 205, 330, 155), (240, 180, 240, 110),
                             (240, 85, 90, 85), (240, 85, 330, 85)]:
        d.add(BW_Line(x1, y1, x2, y2, 1.0))
    return d


def fig4_encoding():
    d = Drawing(460, 260)
    d.add(BW_Rect(20, 180, 110, 45));  d.add(BW_String(45, 200, "Input Data", 9))
    d.add(BW_Rect(140, 180, 140, 45)); d.add(BW_String(150, 200, "Domain Encoder", 9))
    d.add(BW_Rect(290, 180, 90, 45));  d.add(BW_String(300, 200, "Latent Vector", 9))

    d.add(BW_Rect(390, 205, 60, 30));  d.add(BW_String(395, 220, "Lossless", 8))
    d.add(BW_Rect(390, 165, 60, 30));  d.add(BW_String(393, 180, "Semantic", 8))

    d.add(BW_Rect(220, 70, 230, 60))
    d.add(BW_String(230, 100, "NBMF Bytecode + Metadata (emotion, trust, provenance)", 8))

    for (x1, y1, x2, y2) in [(130, 202, 140, 202), (280, 202, 290, 202),
                             (335, 202, 390, 220), (335, 202, 390, 180),
                             (420, 205, 340, 120), (420, 180, 340, 120)]:
        d.add(BW_Line(x1, y1, x2, y2, 1.0))
    return d


def fig5_merkle():
    d = Drawing(460, 260)
    # Events
    d.add(BW_Rect(30, 190, 140, 45));  d.add(BW_String(40, 212, "Promotion #1 (L3→L2)  h1", 8))
    d.add(BW_Rect(170, 190, 140, 45)); d.add(BW_String(180, 212, "Promotion #2 (L2→L1)  h2", 8))
    d.add(BW_Rect(310, 190, 120, 45)); d.add(BW_String(320, 212, "Eviction (L1→L2)  h3", 8))

    # Root + ledger
    d.add(BW_Rect(170, 110, 140, 45)); d.add(BW_String(185, 132, "Merkle Root R = H(h1||h2||h3)", 8))
    d.add(BW_Rect(30, 110, 120, 45));  d.add(BW_String(45, 132, "NBMF Ledger (tx ids)", 8))
    d.add(BW_Rect(320, 110, 120, 45)); d.add(BW_String(340, 132, "Proof Path → R", 8))

    for (x1, y1, x2, y2) in [(100, 190, 240, 155), (240, 190, 240, 155), (370, 190, 240, 155),
                             (90, 155, 90, 155), (320, 155, 300, 155)]:
        d.add(BW_Line(x1, y1, x2, y2, 1.0))
    return d


def fig6_edna():
    d = Drawing(460, 280)
    d.add(BW_Rect(20, 200, 130, 60));  d.add(BW_String(35, 230, "Genome (Capabilities)", 8))
    d.add(BW_Rect(170, 200, 130, 60)); d.add(BW_String(183, 230, "Epigenome (ABAC, Retention, SLO)", 8))
    d.add(BW_Rect(320, 200, 120, 60)); d.add(BW_String(333, 230, "Lineage (Merkle Proofs)", 8))
    d.add(BW_Rect(170, 120, 130, 60)); d.add(BW_String(190, 150, "Immune (Anomaly/Breach)", 8))
    d.add(BW_Rect(60, 40, 340, 50));   d.add(BW_String(180, 65, "NBMF Storage & Access (L1/L2/L3)", 9))

    for (x1, y1, x2, y2) in [(85, 200, 230, 90), (235, 200, 230, 90), (380, 200, 230, 90), (235, 120, 230, 90)]:
        d.add(BW_Line(x1, y1, x2, y2, 1.0))
    return d


def fig7_immune():
    d = Drawing(460, 260)
    d.add(BW_Rect(20, 190, 130, 50));  d.add(BW_String(30, 210, "Detections: anomaly, breach, inject", 8))
    d.add(BW_Rect(170, 190, 130, 50)); d.add(BW_String(190, 210, "Actions: quarantine, quorum, rollback", 8))
    d.add(BW_Rect(320, 190, 120, 50)); d.add(BW_String(335, 210, "State: demotions, alerts, audit", 8))
    d.add(BW_Rect(60, 70, 340, 60));   d.add(BW_String(170, 100, "NBMF L1/L2/L3 (affected records)", 9))

    for (x1, y1, x2, y2) in [(150, 215, 170, 215), (300, 215, 320, 215), (230, 190, 230, 130)]:
        d.add(BW_Line(x1, y1, x2, y2, 1.0))
    return d


def fig8_hardware():
    d = Drawing(460, 260)
    d.add(BW_Rect(30, 180, 140, 60));  d.add(BW_String(45, 210, "DeviceManager", 9))
    d.add(BW_Rect(190, 180, 120, 60)); d.add(BW_String(205, 210, "Tensor Router", 9))
    d.add(BW_Rect(330, 200, 100, 40)); d.add(BW_String(360, 220, "CPU", 9))
    d.add(BW_Rect(330, 150, 100, 40)); d.add(BW_String(360, 170, "GPU", 9))
    d.add(BW_Rect(330, 100, 100, 40)); d.add(BW_String(360, 120, "TPU", 9))
    d.add(BW_Rect(30, 60, 140, 50));   d.add(BW_String(40, 85, "Batch Optimizer", 9))

    for (x1, y1, x2, y2) in [(170, 210, 190, 210), (310, 220, 330, 220),
                             (310, 170, 330, 170), (310, 120, 330, 120),
                             (100, 110, 100, 180)]:
        d.add(BW_Line(x1, y1, x2, y2, 1.0))
    return d


def fig9_cross_tenant():
    d = Drawing(460, 260)
    d.add(BW_Rect(20, 190, 120, 50));  d.add(BW_String(40, 210, "Tenant A — Raw", 9))
    d.add(BW_Rect(20, 120, 120, 50));  d.add(BW_String(40, 140, "Tenant B — Raw", 9))
    d.add(BW_Rect(20, 50, 120, 50));   d.add(BW_String(40, 70, "Tenant C — Raw", 9))
    d.add(BW_Rect(170, 140, 140, 60)); d.add(BW_String(180, 170, "Sanitization Layer", 9))
    d.add(BW_Rect(330, 185, 110, 50)); d.add(BW_String(335, 205, "Abstract Pattern Repo", 8))
    d.add(BW_Rect(330, 85, 110, 50));  d.add(BW_String(335, 105, "Reusable Patterns", 8))

    for (x1, y1, x2, y2) in [(140, 215, 170, 170), (140, 145, 170, 170), (140, 75, 170, 170),
                             (310, 170, 330, 205), (385, 185, 385, 135), (310, 170, 330, 110)]:
        d.add(BW_Line(x1, y1, x2, y2, 1.0))
    return d


def build_pdf():
    styles = _styles()
    doc = SimpleDocTemplate(
        FILENAME,
        pagesize=LETTER,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch
    )
    story = []

    # Title page
    story.append(Paragraph("<b>PROVISIONAL PATENT APPLICATION</b>", styles["title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Title:</b> {TITLE}", styles["h1"]))
    story.append(Paragraph(f"<b>Filing Date:</b> {FILING_DATE}", styles["body"]))
    inv_line = f"<b>Inventor(s):</b> {INVENTOR_NAME}"
    loc_bits = [b for b in [INVENTOR_CITY, INVENTOR_REGION, INVENTOR_COUNTRY] if b]
    if loc_bits:
        inv_line += " — " + ", ".join(loc_bits)
    story.append(Paragraph(inv_line, styles["body"]))
    if CONTACT_EMAIL:
        story.append(Paragraph(f"<b>Contact:</b> {CONTACT_EMAIL}", styles["body"]))
    if CONTACT_ADDRESS:
        story.append(Paragraph(f"<b>Address:</b> {CONTACT_ADDRESS}", styles["body"]))
    story.append(Spacer(1, 16))

    # Abstract
    story.append(Paragraph("<b>Abstract</b>", styles["h1"]))
    story.append(Paragraph(
        "A system and method for a Neural-Backed Memory Fabric (NBMF) integrated with an Enterprise Digital DNA (eDNA) "
        "governance layer to manage multi-agent artificial intelligence architectures. The system utilizes a hierarchical "
        "three-tier memory structure (L1/L2/L3) with content-addressable storage and near-duplicate detection, while the eDNA "
        "layer enforces policies via Genome/Epigenome, notarizes lineage using Merkle proofs, and provides an Immune subsystem "
        "for quarantine and rollback.",
        styles["body"]
    ))

    # Background
    story.append(Paragraph("<b>Background of the Invention</b>", styles["h1"]))
    story.append(Paragraph("<b>Field of the Invention</b>", styles["h2"]))
    story.append(Paragraph(
        "The invention relates to artificial intelligence and distributed computing, specifically to memory and governance "
        "architectures for multi-agent systems.", styles["body"]))
    story.append(Paragraph("<b>Description of Related Art</b>", styles["h2"]))
    story.append(Paragraph(
        "Existing approaches struggle with context limits, storage cost/latency, insufficient access control, and the lack of "
        "cryptographically verifiable lineage for agent memory and actions.", styles["body"]))

    # Summary
    story.append(Paragraph("<b>Summary of the Invention</b>", styles["h1"]))
    story.append(Paragraph(
        "The invention provides an NBMF memory substrate with L1/L2/L3 tiers under an Enterprise Digital DNA (eDNA) governance "
        "layer. The eDNA comprises Genome (capabilities), Epigenome (policies/ABAC), Lineage (cryptographic notarization), and "
        "Immune (detection, quarantine, rollback). A trust pipeline validates new memories prior to promotion.",
        styles["body"]
    ))

    # Brief Description of the Drawings (9 figures)
    story.append(Paragraph("<b>Brief Description of the Drawings</b>", styles["h1"]))
    bdd = [
        "FIG. 1 illustrates the NBMF System Overview (L1/L2/L3, router, controllers, eDNA banner).",
        "FIG. 2 shows the promotion/eviction pipeline with thresholds and validation.",
        "FIG. 3 depicts the trust pipeline with L2Q quarantine, consensus, divergence, and scoring.",
        "FIG. 4 shows the neural bytecode encoding in lossless and semantic modes.",
        "FIG. 5 depicts Merkle-notarized lineage for promotions/evictions and proof paths.",
        "FIG. 6 illustrates the eDNA governance layer (Genome, Epigenome, Lineage, Immune) governing NBMF.",
        "FIG. 7 shows the Immune system workflow and its impact on NBMF tiers.",
        "FIG. 8 shows hardware abstraction: DeviceManager, router, and CPU/GPU/TPU paths.",
        "FIG. 9 shows cross-tenant learning using sanitized artifacts without raw data leakage."
    ]
    for line in bdd:
        story.append(Paragraph("• " + line, styles["body"]))

    # Detailed Description + Figures
    story.append(PageBreak())
    story.append(Paragraph("<b>Detailed Description</b>", styles["h1"]))

    # FIG 1
    story.append(center(fig1_overview()))
    story.append(Paragraph("FIG. 1 — NBMF System Overview.", styles["caption"]))

    # FIG 2
    story.append(center(fig2_promotion()))
    story.append(Paragraph("FIG. 2 — Promotion and Eviction Pipeline.", styles["caption"]))

    # FIG 3
    story.append(center(fig3_trust_L2Q()))
    story.append(Paragraph("FIG. 3 — Trust Pipeline with L2Q Quarantine.", styles["caption"]))

    # FIG 4
    story.append(center(fig4_encoding()))
    story.append(Paragraph("FIG. 4 — Neural Bytecode Encoding (Lossless vs Semantic).", styles["caption"]))

    # FIG 5
    story.append(center(fig5_merkle()))
    story.append(Paragraph("FIG. 5 — Merkle-Notarized Lineage.", styles["caption"]))

    # FIG 6
    story.append(center(fig6_edna()))
    story.append(Paragraph("FIG. 6 — eDNA Governance Layer.", styles["caption"]))

    # FIG 7
    story.append(center(fig7_immune()))
    story.append(Paragraph("FIG. 7 — Immune System Workflow.", styles["caption"]))

    # FIG 8
    story.append(center(fig8_hardware()))
    story.append(Paragraph("FIG. 8 — Hardware Abstraction (DeviceManager).", styles["caption"]))

    # FIG 9
    story.append(center(fig9_cross_tenant()))
    story.append(Paragraph("FIG. 9 — Cross-Tenant Learning via Sanitized Artifacts.", styles["caption"]))

    # Enablement (concise, no placeholders)
    story.append(Paragraph("<b>Enablement</b>", styles["h2"]))
    story.append(Paragraph(
        "One implementation uses Python for orchestration, a compiled module for CAS/SimHash, and a vector index for L2. "
        "Policies may be declarative (e.g., JSON/YAML). Deployment can target CPU/GPU/TPU via a device manager.",
        styles["body"]
    ))

    # (Optional) Examples & Benchmarks — only if requested and without TODO tokens
    if INCLUDE_BENCHMARKS:
        story.append(PageBreak())
        story.append(Paragraph("<b>Examples & Benchmarks</b>", styles["h1"]))
        story.append(Paragraph(
            "Representative latency and storage measurements depend on hardware and workload; values below are illustrative and "
            "non-limiting.", styles["body"]))
        data = [
            ["Metric", "Illustrative Value"],
            ["L1 retrieval latency (95th)", "≤ 25 ms"],
            ["L2 retrieval latency (95th)", "≤ 120 ms"],
            ["Cold recall (on-demand)", "≤ 500 ms"],
            ["Lossless compression (storage)", "~13×"],
            ["Semantic compression (similarity)", "≥ 95%"],
        ]
        t = Table(data, colWidths=[3.0*inch, 3.0*inch])
        t.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.6, colors.black),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ]))
        story.append(t)

    # Claims (unchanged conceptually, cleaned of placeholders)
    story.append(PageBreak())
    story.append(Paragraph("<b>Claims (Draft)</b>", styles["h1"]))
    claims = [
        "1. A system comprising an NBMF with first, second, and third tiers; an eDNA layer with Genome, Epigenome, and Lineage; and a router that promotes or demotes memories based on access, age, and trust.",
        "2. The system of claim 1 wherein new memories are held in quarantine and validated by consensus and divergence checks before promotion.",
        "3. The system of claim 1 wherein the Lineage records promotions and evictions using Merkle proofs.",
        "4. The system of claim 1 wherein NBMF encoding operates in lossless or semantic modes with associated compression ratios.",
        "5. The system of claim 1 wherein deduplication uses content hashes and locality-sensitive signatures.",
        "6. The system of claim 1 wherein an Immune component triggers quarantine, quorum, or rollback upon threat detection.",
        "7. The system of claim 1 wherein Epigenome policies implement attribute-based access control and retention.",
        "8. The system of claim 1 further comprising hardware abstraction that routes tensor operations to CPU, GPU, or TPU.",
        "9. The method comprising ingesting input, computing identifiers, validating trust, promoting to tiers, and notarizing lineage.",
        "10. The non-transitory computer-readable medium storing instructions to perform the method of claim 9.",
        "11. The system of claim 1 wherein cross-tenant learning uses sanitized artifacts without raw data leakage.",
        "12. The system of claim 1 wherein the warm tier employs vector indexing for nearest-neighbor retrieval.",
        "13. The system of claim 1 wherein cold archives store compressed memory blocks with on-demand recall.",
        "14. The system of claim 1 wherein a model router selects foundation models based on policy and cost.",
        "15. The system of claim 6 wherein rollback restores to a prior Merkle root.",
        "16. The system of claim 1 wherein the Genome capability schema is immutable during an agent instance.",
        "17. The method of claim 9 wherein ingestion includes redaction or minimization before persistence.",
        "18. The system of claim 1 wherein periodic compaction consolidates warm-tier blocks for archival.",
        "19. The method of claim 9 wherein proof paths verify existence of data without revealing the dataset.",
        "20. The system of claim 1 wherein trust scoring combines consensus agreement and divergence from existing memories.",
    ]
    for c in claims:
        story.append(Paragraph(c, styles["body"]))

    # Figure List (9 items)
    story.append(PageBreak())
    story.append(Paragraph("<b>Figure List</b>", styles["h1"]))
    for line in bdd:
        story.append(Paragraph("• " + line, styles["body"]))

    # Provisional Cover-Sheet Content (no placeholders that say TODO)
    story.append(PageBreak())
    story.append(Paragraph("<b>Provisional Cover-Sheet Content (For Manual Entry)</b>", styles["h1"]))
    story.append(Paragraph(f"• Title: {TITLE}", styles["body"]))
    story.append(Paragraph(f"• Inventor(s): {INVENTOR_NAME}", styles["body"]))
    if loc_bits:
        story.append(Paragraph("• Location: " + ", ".join(loc_bits), styles["body"]))
    if CONTACT_EMAIL:
        story.append(Paragraph(f"• Email: {CONTACT_EMAIL}", styles["body"]))
    story.append(Paragraph("• Entity Status: MICRO (meets income and application count limits).", styles["body"]))
    story.append(Paragraph("• Government Interest: None.", styles["body"]))
    story.append(Paragraph("• Attorney Docket Number: (optional)", styles["body"]))

    # Filing Checklist (correct fee)
    story.append(PageBreak())
    story.append(Paragraph("<b>Filing Checklist (Micro Entity)</b>", styles["h1"]))
    story.append(Paragraph("[] Fee: $75 USD (Provisional, Micro Entity)", styles["body"]))
    story.append(Paragraph("[] Specification (this PDF)", styles["body"]))
    story.append(Paragraph("[] Drawings (figures included in this PDF)", styles["body"]))
    story.append(Paragraph("[] Provisional Cover Sheet (online at USPTO Patent Center)", styles["body"]))

    doc.build(story)


if __name__ == "__main__":
    build_pdf()
    print(f"Success! Wrote {FILENAME}")
