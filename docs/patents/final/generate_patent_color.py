
from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, String, Polygon
from reportlab.graphics import renderPDF
import os, zipfile

OUT_PDF = "NBMF_Patent_Application_COLOR.pdf"
FIG_DIR = "figures"
ZIP_PATH = "NBMF_eDNA_PPA_COLOR_vFinal.zip"

os.makedirs(FIG_DIR, exist_ok=True)

styles = getSampleStyleSheet()
S_TITLE = styles['Title']
S_H1 = ParagraphStyle(name='H1', parent=styles['Heading1'], spaceBefore=12, spaceAfter=8)
S_H2 = ParagraphStyle(name='H2', parent=styles['Heading2'], spaceBefore=10, spaceAfter=6)
S_BODY = ParagraphStyle(name='Body', parent=styles['BodyText'], leading=13, spaceAfter=6)
S_CAP = ParagraphStyle(name='Cap', parent=styles['BodyText'], alignment=1, fontName='Times-Italic', fontSize=9, spaceAfter=12)

PAL = {
    "nbmf": colors.Color(0.75, 0.87, 1.0),
    "edna": colors.Color(0.78, 0.93, 0.78),
    "router": colors.Color(1.0, 0.97, 0.75),
    "l1": colors.Color(1.0, 0.86, 0.86),
    "l2": colors.Color(1.0, 0.94, 0.75),
    "l3": colors.Color(0.86, 0.95, 1.0),
    "lineage": colors.Color(0.90, 0.90, 1.0),
    "immune1": colors.whitesmoke,
    "immune2": colors.Color(1.0, 0.80, 0.80),
    "immune3": colors.Color(0.83, 0.94, 0.83),
}

def center(drawing, width=6.25*inch):
    t = Table([[drawing]], colWidths=[width])
    t.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")]))
    return t

def Lbl(d, x, y, text, size=9, anchor='start'):
    d.add(String(x, y, text, fontSize=size, fillColor=colors.black, textAnchor=anchor))

def L(x1, y1, x2, y2, stroke=1.0, dash=None, color=colors.black):
    ln = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=stroke)
    if dash: ln.strokeDashArray = dash
    return ln

def R(x, y, w, h, fill=colors.white, stroke=colors.black, rx=0, ry=0, sw=1.0):
    return Rect(x, y, w, h, fillColor=fill, strokeColor=stroke, rx=rx, ry=ry, strokeWidth=sw)

def fig1_overview():
    d = Drawing(480, 300)
    Lbl(d, 240, 280, "Enterprise Digital DNA (eDNA): Genome • Epigenome • Lineage • Immune", 11, 'middle')
    d.add(L(30, 270, 450, 270, 1.0, color=colors.grey))
    d.add(R(40, 190, 120, 60, fill=PAL["l1"])); Lbl(d, 100, 220, "L1 — Hot (Vector DB)", 9, 'middle')
    d.add(R(180, 190, 120, 60, fill=PAL["l2"])); Lbl(d, 240, 220, "L2 — Warm (NBMF+AES-256)", 9, 'middle')
    d.add(R(320, 190, 120, 60, fill=PAL["l3"])); Lbl(d, 380, 220, "L3 — Cold (Compressed)", 9, 'middle')
    d.add(R(180, 130, 120, 40, fill=PAL["router"])); Lbl(d, 240, 150, "Memory Router", 10, 'middle')
    d.add(R(50, 90, 150, 30, fill=colors.whitesmoke));  Lbl(d, 125, 108, "Promotion: freq↑, recency↑, trust↑", 8, 'middle')
    d.add(R(280, 90, 150, 30, fill=colors.whitesmoke)); Lbl(d, 355, 108, "Eviction: age↑, frequency↓", 8, 'middle')
    for (x1, y1, x2, y2) in [(100, 190, 240, 170), (240, 170, 380, 190),
                             (380, 250, 240, 170), (240, 170, 100, 250),
                             (240, 130, 140, 105), (240, 130, 355, 105)]:
        d.add(L(x1, y1, x2, y2, 1.2))
    d.add(R(40, 40, 400, 35, fill=PAL["nbmf"]))
    Lbl(d, 240, 60, "Multi-Agent System • Departments • CMP Bus", 9, 'middle')
    d.add(L(240, 130, 240, 75, 1.0, color=colors.black))
    return d

def fig2_promotion():
    d = Drawing(480, 270)
    d.add(R(40, 180, 120, 50, fill=PAL["l3"])); Lbl(d, 100, 200, "L3 (Cold)", 10, 'middle')
    d.add(R(190, 180, 120, 50, fill=PAL["l2"])); Lbl(d, 250, 200, "L2 (Warm)", 10, 'middle')
    d.add(R(340, 180, 120, 50, fill=PAL["l1"])); Lbl(d, 400, 200, "L1 (Hot)", 10, 'middle')
    d.add(L(160, 205, 190, 205)); Lbl(d, 175, 214, "Promote if access>10 & trust≥0.7", 8, 'middle')
    d.add(L(310, 205, 340, 205)); Lbl(d, 325, 214, "Promote if recency<1h", 8, 'middle')
    d.add(L(460, 195, 340, 195)); Lbl(d, 405, 182, "Evict if age>1h", 8, 'middle')
    d.add(L(310, 195, 160, 195)); Lbl(d, 235, 182, "Evict if age>7d", 8, 'middle')
    d.add(R(40, 100, 135, 45, fill=colors.whitesmoke)); Lbl(d, 107, 122, "New Memory (L2Q)", 9, 'middle')
    d.add(R(200, 100, 120, 45, fill=colors.whitesmoke)); Lbl(d, 260, 122, "Trust Score", 9, 'middle')
    d.add(R(340, 100, 120, 45, fill=colors.whitesmoke)); Lbl(d, 400, 122, "Decision: Promote/Reject", 9, 'middle')
    d.add(L(175, 123, 200, 123)); d.add(L(320, 123, 340, 123))
    return d

def fig3_trust_L2Q():
    d = Drawing(480, 270)
    d.add(R(30, 200, 140, 50, fill=colors.whitesmoke)); Lbl(d, 100, 222, "Incoming Data", 10, 'middle')
    d.add(R(180, 200, 140, 50, fill=colors.whitesmoke)); Lbl(d, 250, 222, "L2Q Buffer", 10, 'middle')
    d.add(R(350, 210, 110, 55, fill=PAL["lineage"])); Lbl(d, 405, 238, "Multi-Model", 8, 'middle'); Lbl(d, 405, 228, "Consensus", 8, 'middle')
    d.add(R(350, 140, 110, 50, fill=PAL["lineage"])); Lbl(d, 405, 160, "Divergence", 8, 'middle'); Lbl(d, 405, 150, "Check", 8, 'middle')
    d.add(R(180, 70, 140, 50, fill=colors.whitesmoke)); Lbl(d, 250, 92, "Trust Score", 10, 'middle')
    d.add(R(30, 70, 140, 50, fill=PAL["l2"])); Lbl(d, 100, 92, "Promote to L2", 10, 'middle')
    d.add(R(350, 70, 110, 50, fill=PAL["l3"])); Lbl(d, 405, 92, "Reject / Sanitize", 9, 'middle')
    for (x1, y1, x2, y2) in [(170, 225, 180, 225), (320, 225, 350, 240),
                             (320, 225, 350, 165), (250, 200, 250, 120),
                             (250, 95, 100, 95), (250, 95, 350, 95)]:
        d.add(L(x1, y1, x2, y2))
    return d

def fig4_encoding():
    d = Drawing(480, 270)
    d.add(R(30, 205, 110, 45, fill=colors.whitesmoke)); Lbl(d, 85, 227, "Input Data", 10, 'middle')
    d.add(R(150, 205, 150, 45, fill=PAL["nbmf"])); Lbl(d, 225, 227, "Domain Encoder", 10, 'middle')
    d.add(R(315, 205, 100, 45, fill=PAL["l2"])); Lbl(d, 365, 227, "Latent Vector", 10, 'middle')
    d.add(R(425, 220, 45, 25, fill=PAL["lineage"])); Lbl(d, 448, 232, "Lossless", 8, 'middle')
    d.add(R(425, 185, 45, 25, fill=PAL["router"]));  Lbl(d, 448, 197, "Semantic", 8, 'middle')
    d.add(R(230, 80, 230, 60, fill=colors.whitesmoke))
    Lbl(d, 245, 110, "NBMF Bytecode + Metadata (emotion, trust, provenance)", 8, 'start')
    for (x1, y1, x2, y2) in [(140, 227, 150, 227), (300, 227, 315, 227),
                             (365, 227, 448, 232), (365, 227, 448, 197),
                             (448, 220, 345, 140), (448, 197, 345, 140)]:
        d.add(L(x1, y1, x2, y2))
    return d

def fig5_merkle():
    d = Drawing(480, 270)
    d.add(R(40, 200, 150, 45, fill=colors.whitesmoke)); Lbl(d, 115, 222, "Promotion #1 (L3→L2)  h1", 8, 'middle')
    d.add(R(200, 200, 150, 45, fill=colors.whitesmoke)); Lbl(d, 275, 222, "Promotion #2 (L2→L1)  h2", 8, 'middle')
    d.add(R(360, 200, 110, 45, fill=colors.whitesmoke)); Lbl(d, 415, 222, "Eviction (L1→L2)  h3", 8, 'middle')
    d.add(R(200, 120, 150, 45, fill=PAL["lineage"])); Lbl(d, 275, 142, "Merkle Root R = H(h1||h2||h3)", 8, 'middle')
    d.add(R(40, 120, 140, 45, fill=PAL["lineage"]));  Lbl(d, 110, 142, "NBMF Ledger (tx ids)", 8, 'middle')
    d.add(R(360, 120, 120, 45, fill=PAL["lineage"])); Lbl(d, 420, 142, "Proof Path → R", 8, 'middle')
    for (x1, y1, x2, y2) in [(115, 200, 275, 165), (275, 200, 275, 165), (415, 200, 275, 165),
                             (110, 165, 110, 165), (420, 165, 400, 165)]:
        d.add(L(x1, y1, x2, y2))
    return d

def fig6_edna():
    d = Drawing(480, 290)
    d.add(R(30, 210, 130, 60, fill=PAL["edna"]));  Lbl(d, 95, 240, "Genome (Capabilities)", 8, 'middle')
    d.add(R(180, 210, 130, 60, fill=PAL["edna"])); Lbl(d, 245, 240, "Epigenome (ABAC, Retention, SLO)", 8, 'middle')
    d.add(R(330, 210, 120, 60, fill=PAL["edna"])); Lbl(d, 390, 240, "Lineage (Merkle Proofs)", 8, 'middle')
    d.add(R(180, 130, 130, 60, fill=PAL["edna"])); Lbl(d, 245, 160, "Immune (Anomaly/Breach)", 8, 'middle')
    d.add(R(70, 50, 340, 50, fill=PAL["nbmf"]));   Lbl(d, 240, 75, "NBMF Storage & Access (L1/L2/L3)", 9, 'middle')
    for (x1, y1, x2, y2) in [(95, 210, 245, 100), (250, 210, 245, 100), (390, 210, 245, 100), (250, 130, 245, 100)]:
        d.add(L(x1, y1, x2, y2))
    return d

def fig7_immune():
    d = Drawing(480, 270)
    d.add(R(30, 200, 140, 50, fill=PAL["immune1"]));  Lbl(d, 100, 222, "Detections: anomaly, breach, inject", 8, 'middle')
    d.add(R(180, 200, 140, 50, fill=PAL["immune2"])); Lbl(d, 250, 222, "Actions: quarantine, quorum, rollback", 8, 'middle')
    d.add(R(330, 200, 120, 50, fill=PAL["immune3"])); Lbl(d, 390, 222, "State: demotions, alerts, audit", 8, 'middle')
    d.add(R(70, 70, 340, 60, fill=PAL["nbmf"]));      Lbl(d, 240, 100, "NBMF L1/L2/L3 (affected records)", 9, 'middle')
    for (x1, y1, x2, y2) in [(170, 225, 180, 225), (320, 225, 330, 225), (250, 200, 250, 130)]:
        d.add(L(x1, y1, x2, y2))
    return d

def fig8_hardware():
    d = Drawing(480, 270)
    d.add(R(40, 200, 140, 60, fill=PAL["nbmf"]));    Lbl(d, 110, 232, "DeviceManager", 10, 'middle')
    d.add(R(200, 200, 140, 60, fill=PAL["router"])); Lbl(d, 270, 232, "Tensor Router", 10, 'middle')
    d.add(R(360, 220, 90, 40, fill=PAL["l2"]));      Lbl(d, 405, 240, "CPU", 10, 'middle')
    d.add(R(360, 170, 90, 40, fill=PAL["l2"]));      Lbl(d, 405, 190, "GPU", 10, 'middle')
    d.add(R(360, 120, 90, 40, fill=PAL["l2"]));      Lbl(d, 405, 140, "TPU", 10, 'middle')
    d.add(R(40, 70, 140, 50, fill=PAL["edna"]));     Lbl(d, 110, 95, "Batch Optimizer", 10, 'middle')
    for (x1, y1, x2, y2) in [(180, 230, 200, 230), (350, 240, 360, 240),
                             (350, 190, 360, 190), (350, 140, 360, 140),
                             (110, 120, 110, 200)]:
        d.add(L(x1, y1, x2, y2))
    return d

def fig9_cross_tenant():
    d = Drawing(480, 270)
    d.add(R(40, 210, 120, 50, fill=PAL["nbmf"]));  Lbl(d, 100, 235, "Tenant A — Raw", 9, 'middle')
    d.add(R(40, 140, 120, 50, fill=PAL["nbmf"]));  Lbl(d, 100, 165, "Tenant B — Raw", 9, 'middle')
    d.add(R(40, 70, 120, 50, fill=PAL["nbmf"]));   Lbl(d, 100, 95, "Tenant C — Raw", 9, 'middle')
    d.add(R(190, 150, 140, 60, fill=PAL["router"])); Lbl(d, 260, 180, "Sanitization Layer", 10, 'middle')
    d.add(R(350, 210, 110, 50, fill=PAL["lineage"])); Lbl(d, 405, 235, "Abstract Pattern Repo", 8, 'middle')
    d.add(R(350, 110, 110, 50, fill=PAL["lineage"])); Lbl(d, 405, 135, "Reusable Patterns", 8, 'middle')
    for (x1, y1, x2, y2) in [(160, 235, 190, 180), (160, 165, 190, 180), (160, 95, 190, 180),
                             (330, 180, 350, 235), (405, 210, 405, 160), (330, 180, 350, 135)]:
        d.add(L(x1, y1, x2, y2, dash=[4,3]))
    return d

FIG_FUNCS = [
    fig1_overview, fig2_promotion, fig3_trust_L2Q, fig4_encoding, fig5_merkle,
    fig6_edna, fig7_immune, fig8_hardware, fig9_cross_tenant
]

FIG_CAPTIONS = [
    "FIG. 1 — NBMF System Overview.",
    "FIG. 2 — Promotion and Eviction Pipeline.",
    "FIG. 3 — Trust Pipeline with L2Q Quarantine.",
    "FIG. 4 — Neural Bytecode Encoding (Lossless vs Semantic).",
    "FIG. 5 — Merkle-Notarized Lineage.",
    "FIG. 6 — eDNA Governance Layer.",
    "FIG. 7 — Immune System Workflow.",
    "FIG. 8 — Hardware Abstraction (DeviceManager).",
    "FIG. 9 — Cross-Tenant Learning via Sanitized Artifacts."
]

def render_figures_to_pdfs():
    paths = []
    for idx, fn in enumerate(FIG_FUNCS, start=1):
        d = fn()
        fig_path = os.path.join(FIG_DIR, f"FIG{idx:02d}.pdf")
        renderPDF.drawToFile(d, fig_path, f"FIG {idx}")
        paths.append(fig_path)
    return paths

def build_pdf():
    doc = SimpleDocTemplate(OUT_PDF, pagesize=LETTER,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.8*inch, bottomMargin=0.8*inch)
    story = []

    story.append(Paragraph("<b>PROVISIONAL PATENT APPLICATION</b>", S_TITLE))
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Title:</b> Neural-Backed Memory Fabric with Enterprise Digital DNA (NBMF-eDNA)", S_H1))
    story.append(Paragraph("<b>Filing Date:</b> 2025-01-15", S_BODY))
    story.append(Paragraph("<b>Inventor(s):</b> Masoud Masoori — Richmond Hill, ON, Canada", S_BODY))
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>Abstract</b>", S_H1))
    story.append(Paragraph(
        "A system and method for a Neural-Backed Memory Fabric (NBMF) integrated with an Enterprise Digital DNA (eDNA) "
        "governance layer to manage multi-agent artificial intelligence architectures. The system utilizes a hierarchical "
        "three-tier memory structure (L1/L2/L3) with content-addressable storage and near-duplicate detection, while the eDNA "
        "layer enforces policies via Genome/Epigenome, notarizes lineage using Merkle proofs, and provides an Immune subsystem "
        "for quarantine and rollback.", S_BODY))

    story.append(Paragraph("<b>Background of the Invention</b>", S_H1))
    story.append(Paragraph("<b>Field of the Invention</b>", S_H2))
    story.append(Paragraph("The invention relates to artificial intelligence and distributed computing, specifically to memory and governance architectures for multi-agent systems.", S_BODY))
    story.append(Paragraph("<b>Description of Related Art</b>", S_H2))
    story.append(Paragraph("Existing approaches struggle with context limits, storage cost/latency, insufficient access control, and the lack of cryptographically verifiable lineage for agent memory and actions.", S_BODY))

    story.append(Paragraph("<b>Summary of the Invention</b>", S_H1))
    story.append(Paragraph(
        "The invention provides an NBMF memory substrate with L1/L2/L3 tiers under an Enterprise Digital DNA (eDNA) governance "
        "layer. The eDNA comprises Genome (capabilities), Epigenome (policies/ABAC), Lineage (cryptographic notarization), and "
        "Immune (detection, quarantine, rollback). A trust pipeline validates new memories prior to promotion.", S_BODY))

    story.append(Paragraph("<b>Brief Description of the Drawings</b>", S_H1))
    for line in [
        "FIG. 1 illustrates the NBMF System Overview (L1/L2/L3, router, controllers, eDNA banner).",
        "FIG. 2 shows the promotion/eviction pipeline with thresholds and validation.",
        "FIG. 3 depicts the trust pipeline with L2Q quarantine, consensus, divergence, and scoring.",
        "FIG. 4 shows the neural bytecode encoding in lossless and semantic modes.",
        "FIG. 5 depicts Merkle-notarized lineage for promotions/evictions and proof paths.",
        "FIG. 6 illustrates the eDNA governance layer (Genome, Epigenome, Lineage, Immune) governing NBMF.",
        "FIG. 7 shows the Immune system workflow and its impact on NBMF tiers.",
        "FIG. 8 shows hardware abstraction: DeviceManager, router, and CPU/GPU/TPU paths.",
        "FIG. 9 shows cross-tenant learning using sanitized artifacts without raw data leakage."
    ]:
        story.append(Paragraph("• " + line, S_BODY))

    story.append(PageBreak())
    story.append(Paragraph("<b>Detailed Description</b>", S_H1))

    for idx, fn in enumerate(FIG_FUNCS, start=1):
        d = fn()
        story.append(center(d))
        story.append(Paragraph(FIG_CAPTIONS[idx-1], S_CAP))

    story.append(Paragraph("<b>Enablement</b>", S_H2))
    story.append(Paragraph(
        "One implementation uses Python for orchestration, a compiled module for CAS/SimHash, and a vector index for L2. "
        "Policies may be declarative (e.g., JSON/YAML). Deployment can target CPU/GPU/TPU via a device manager.", S_BODY))

    story.append(PageBreak())
    story.append(Paragraph("<b>Claims (Draft)</b>", S_H1))
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
        "20. The system of claim 1 wherein trust scoring combines consensus agreement and divergence from existing memories."
    ]
    for c in claims:
        story.append(Paragraph(c, S_BODY))

    story.append(PageBreak())
    story.append(Paragraph("<b>Figure List</b>", S_H1))
    for cap in [
        "FIG. 1 — NBMF System Overview.",
        "FIG. 2 — Promotion and Eviction Pipeline.",
        "FIG. 3 — Trust Pipeline with L2Q Quarantine.",
        "FIG. 4 — Neural Bytecode Encoding (Lossless vs Semantic).",
        "FIG. 5 — Merkle-Notarized Lineage.",
        "FIG. 6 — eDNA Governance Layer.",
        "FIG. 7 — Immune System Workflow.",
        "FIG. 8 — Hardware Abstraction (DeviceManager).",
        "FIG. 9 — Cross-Tenant Learning via Sanitized Artifacts."
    ]:
        story.append(Paragraph("• " + cap, S_BODY))

    doc.build(story)

def main():
    paths = render_figures_to_pdfs()
    build_pdf()
    with open("04_BRIEF_DESCRIPTION_OF_DRAWINGS.txt", "w", encoding="utf-8") as f:
        f.write("\\n".join([
            "FIG. 1 illustrates the NBMF System Overview (L1/L2/L3, router, controllers, eDNA banner).",
            "FIG. 2 shows the promotion/eviction pipeline with thresholds and validation.",
            "FIG. 3 depicts the trust pipeline with L2Q quarantine, consensus, divergence, and scoring.",
            "FIG. 4 shows the neural bytecode encoding in lossless and semantic modes.",
            "FIG. 5 depicts Merkle-notarized lineage for promotions/evictions and proof paths.",
            "FIG. 6 illustrates the eDNA governance layer (Genome, Epigenome, Lineage, Immune) governing NBMF.",
            "FIG. 7 shows the Immune system workflow and its impact on NBMF tiers.",
            "FIG. 8 shows hardware abstraction: DeviceManager, router, and CPU/GPU/TPU paths.",
            "FIG. 9 shows cross-tenant learning using sanitized artifacts without raw data leakage."
        ]))
    with zipfile.ZipFile(ZIP_PATH, 'w') as z:
        z.write(OUT_PDF, arcname="01_SPECIFICATION.pdf")
        z.write("04_BRIEF_DESCRIPTION_OF_DRAWINGS.txt", arcname="04_BRIEF_DESCRIPTION_OF_DRAWINGS.txt")
        for p in paths:
            z.write(p, arcname=f"05_FIGURES/{os.path.basename(p)}")

if __name__ == "__main__":
    main()
