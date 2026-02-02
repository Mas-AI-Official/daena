from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, String, Polygon
from reportlab.lib.units import inch

# ---------------- CONFIGURATION ----------------
FILENAME = "NBMF_Patent_Final_Colored.pdf"
TITLE = "NEURAL-BACKED MEMORY FABRIC (NBMF) WITH ENTERPRISE-DNA GOVERNANCE"
FILING_DATE = "2025-01-15"

# Inventor Details (Filled)
INVENTOR_NAME = "Masoud Masoori"
INVENTOR_LOC = "Richmond Hill, Ontario, Canada"

# ---------------- COLOR PALETTE ----------------
# Consistent coloring for logical blocks
C_L1 = colors.mistyrose       # Hot Memory
C_L2 = colors.lemonchiffon    # Warm Memory
C_L3 = colors.lightcyan       # Cold Memory
C_EDNA = colors.honeydew      # Governance/eDNA
C_SEC = colors.lavenderblush  # Security/Immune
C_PROC = colors.whitesmoke    # Processes/Logic
C_HDW = colors.aliceblue      # Hardware
C_TEXT = colors.black
C_LINE = colors.dimgrey

# ---------------- DRAWING HELPERS ----------------
def make_caption(text):
    return Paragraph(f"<b>{text}</b>", ParagraphStyle(name="Caption", alignment=1, fontSize=10, spaceBefore=5, spaceAfter=20))

def draw_rect_c(d, x, y, w, h, color, text=None, subtext=None):
    """Draws a rounded colorful rectangle with centered text."""
    d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=color, strokeColor=C_LINE, strokeWidth=1))
    if text:
        d.add(String(x + w/2, y + h/2 + (5 if subtext else -3), text, 
                     fontSize=9, fontName="Helvetica-Bold", textAnchor="middle", fillColor=C_TEXT))
    if subtext:
        d.add(String(x + w/2, y + h/2 - 7, subtext, 
                     fontSize=7, fontName="Helvetica", textAnchor="middle", fillColor=colors.darkgrey))

def draw_arrow(d, x1, y1, x2, y2, label=None):
    """Draws a line with an arrow end."""
    d.add(Line(x1, y1, x2, y2, strokeColor=C_LINE, strokeWidth=1.5, arrow=True))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        d.add(Rect(mx-20, my-5, 40, 10, fillColor=colors.white, strokeOpacity=0)) # bg for text
        d.add(String(mx, my-3, label, fontSize=7, textAnchor="middle", fillColor=colors.dimgrey))

# ---------------- FIGURES (Refined & Colored) ----------------

def fig1_overview():
    """FIG 1: System Overview (The Sunflower/Honeycomb Logic)"""
    d = Drawing(460, 280)
    
    # Header Band (eDNA)
    d.add(Rect(20, 240, 420, 30, rx=5, ry=5, fillColor=colors.darkseagreen, strokeColor=None))
    d.add(String(230, 250, "eDNA GOVERNANCE LAYER (Genome • Epigenome • Lineage • Immune)", 
                 fontSize=10, textAnchor="middle", fillColor=colors.white, fontName="Helvetica-Bold"))

    # Memory Tiers
    draw_rect_c(d, 40, 150, 100, 60, C_L1, "L1 (Hot)", "Vector DB (RAM)")
    draw_rect_c(d, 180, 150, 100, 60, C_L2, "L2 (Warm)", "NBMF Index (NVMe)")
    draw_rect_c(d, 320, 150, 100, 60, C_L3, "L3 (Cold)", "Compressed (Blob)")

    # Router
    draw_rect_c(d, 180, 90, 100, 30, C_PROC, "Memory Router")
    
    # Logic Blocks
    draw_rect_c(d, 60, 50, 120, 30, C_PROC, "Promotion Logic", "Freq↑ Recency↑")
    draw_rect_c(d, 280, 50, 120, 30, C_PROC, "Eviction Logic", "Age↑ Freq↓")

    # Arrows
    draw_arrow(d, 230, 120, 230, 150) # Router -> L2
    draw_arrow(d, 180, 180, 140, 180) # L2 -> L1
    draw_arrow(d, 280, 180, 320, 180) # L2 -> L3
    draw_arrow(d, 230, 90, 120, 80)   # Router -> Promo
    draw_arrow(d, 230, 90, 340, 80)   # Router -> Evict
    
    return d

def fig2_promotion():
    """FIG 2: Promotion Pipeline"""
    d = Drawing(460, 220)
    
    # Tiers
    draw_rect_c(d, 30, 150, 100, 50, C_L3, "L3 (Cold)")
    draw_rect_c(d, 180, 150, 100, 50, C_L2, "L2 (Warm)")
    draw_rect_c(d, 330, 150, 100, 50, C_L1, "L1 (Hot)")
    
    # Flows
    draw_arrow(d, 130, 185, 180, 185, "Promote (>10 hits)")
    draw_arrow(d, 280, 185, 330, 185, "Promote (Recent)")
    
    draw_arrow(d, 330, 165, 280, 165, "Evict (>1hr)")
    draw_arrow(d, 180, 165, 130, 165, "Evict (>7d)")
    
    # Validation
    draw_rect_c(d, 180, 60, 100, 40, C_SEC, "Trust Check")
    draw_arrow(d, 230, 150, 230, 100, "Validate")
    
    return d

def fig3_trust():
    """FIG 3: Trust & Quarantine"""
    d = Drawing(460, 250)
    
    draw_rect_c(d, 20, 180, 120, 50, colors.lightgrey, "Incoming Data")
    draw_rect_c(d, 170, 180, 120, 50, C_SEC, "L2Q Buffer", "Quarantine State")
    
    # Analysis
    draw_rect_c(d, 320, 200, 120, 40, C_PROC, "Consensus Check")
    draw_rect_c(d, 320, 140, 120, 40, C_PROC, "Divergence Check")
    
    # Decision
    draw_rect_c(d, 170, 60, 120, 50, colors.gold, "Trust Score")
    
    # Outcomes
    draw_rect_c(d, 20, 60, 120, 50, C_L2, "Promote to L2", "Verified")
    draw_rect_c(d, 320, 60, 120, 50, colors.lightcoral, "Reject/Sanitize", "Malicious")
    
    # Wiring
    draw_arrow(d, 140, 205, 170, 205)
    draw_arrow(d, 290, 205, 320, 220)
    draw_arrow(d, 290, 205, 320, 160)
    draw_arrow(d, 230, 180, 230, 110) # Buffer -> Score
    draw_arrow(d, 170, 85, 140, 85)   # Score -> Promote
    draw_arrow(d, 290, 85, 320, 85)   # Score -> Reject
    
    return d

def fig4_encoding():
    """FIG 4: Encoding (Lossless vs Semantic)"""
    d = Drawing(460, 200)
    
    draw_rect_c(d, 20, 100, 100, 50, C_PROC, "Input Data")
    draw_arrow(d, 120, 125, 160, 125)
    
    draw_rect_c(d, 160, 100, 120, 50, C_EDNA, "Domain Encoder")
    
    # Split paths
    draw_arrow(d, 280, 140, 320, 160)
    draw_rect_c(d, 320, 150, 100, 30, C_L3, "Lossless", "Exact storage")
    
    draw_arrow(d, 280, 110, 320, 90)
    draw_rect_c(d, 320, 70, 100, 30, C_L1, "Semantic", "Vector Embed")
    
    # Rejoin
    draw_rect_c(d, 160, 20, 260, 30, C_HDW, "NBMF Bytecode Object")
    d.add(Line(420, 165, 440, 125, strokeColor=C_LINE))
    d.add(Line(420, 85, 440, 125, strokeColor=C_LINE))
    d.add(Line(440, 125, 420, 35, strokeColor=C_LINE, arrow=True))
    
    return d

def fig5_merkle():
    """FIG 5: Merkle Lineage Tree"""
    d = Drawing(460, 220)
    
    # Root
    draw_rect_c(d, 180, 170, 100, 40, colors.gold, "Root Hash", "Top-level sig")
    
    # Nodes
    draw_rect_c(d, 100, 110, 80, 30, C_PROC, "Hash A")
    draw_rect_c(d, 280, 110, 80, 30, C_PROC, "Hash B")
    
    # Leaves (Events)
    draw_rect_c(d, 40, 50, 90, 30, C_L2, "Event: Promo")
    draw_rect_c(d, 140, 50, 90, 30, C_L2, "Event: Evict")
    draw_rect_c(d, 330, 50, 90, 30, C_L2, "Event: Edit")
    
    # Lines
    d.add(Line(230, 170, 140, 140, strokeColor=C_LINE))
    d.add(Line(230, 170, 320, 140, strokeColor=C_LINE))
    d.add(Line(140, 110, 85, 80, strokeColor=C_LINE))
    d.add(Line(140, 110, 185, 80, strokeColor=C_LINE))
    d.add(Line(320, 110, 375, 80, strokeColor=C_LINE))
    
    return d

def fig6_edna():
    """FIG 6: eDNA Components"""
    d = Drawing(460, 250)
    
    # Central Storage
    draw_rect_c(d, 130, 100, 200, 60, C_L2, "NBMF Storage", "Protected Core")
    
    # Satellites
    draw_rect_c(d, 20, 180, 100, 50, C_EDNA, "Genome", "Capabilities")
    draw_rect_c(d, 180, 200, 100, 50, C_EDNA, "Epigenome", "Policies")
    draw_rect_c(d, 340, 180, 100, 50, C_EDNA, "Lineage", "Audit Log")
    
    draw_rect_c(d, 180, 10, 100, 50, C_SEC, "Immune", "Defense")
    
    # Connections
    draw_arrow(d, 70, 180, 130, 140)
    draw_arrow(d, 230, 200, 230, 160)
    draw_arrow(d, 390, 180, 330, 140)
    draw_arrow(d, 230, 60, 230, 100)
    
    return d

def fig7_immune_workflow():
    """FIG 7: Immune System Loop"""
    d = Drawing(460, 200)
    
    draw_rect_c(d, 30, 140, 100, 40, C_SEC, "1. Detect", "Anomaly/Breach")
    draw_arrow(d, 130, 160, 180, 160)
    
    draw_rect_c(d, 180, 140, 100, 40, colors.orange, "2. Quarantine", "Isolate ID")
    draw_arrow(d, 280, 160, 330, 160)
    
    draw_rect_c(d, 330, 140, 100, 40, colors.lightgreen, "3. Rollback", "Restore Root")
    
    # Impact on Storage
    draw_rect_c(d, 30, 40, 400, 40, C_L2, "NBMF State (L1 / L2 / L3)")
    
    draw_arrow(d, 230, 140, 230, 80) # Quarantine locks state
    draw_arrow(d, 380, 140, 380, 80) # Rollback resets state
    
    return d

def fig8_hardware():
    """FIG 8: Hardware Abstraction"""
    d = Drawing(460, 200)
    
    draw_rect_c(d, 20, 80, 120, 60, C_HDW, "Device Manager")
    
    draw_arrow(d, 140, 110, 180, 110)
    draw_rect_c(d, 180, 80, 100, 60, C_PROC, "Tensor Router")
    
    # Targets
    draw_rect_c(d, 340, 150, 80, 30, C_HDW, "CPU")
    draw_rect_c(d, 340, 95, 80, 30, C_HDW, "GPU")
    draw_rect_c(d, 340, 40, 80, 30, C_HDW, "TPU")
    
    draw_arrow(d, 280, 120, 340, 165)
    draw_arrow(d, 280, 110, 340, 110)
    draw_arrow(d, 280, 100, 340, 55)
    
    return d

def fig9_cross_tenant():
    """FIG 9: Cross-Tenant Isolation"""
    d = Drawing(460, 220)
    
    # Tenants
    draw_rect_c(d, 20, 160, 100, 40, colors.mistyrose, "Tenant A", "Raw Data")
    draw_rect_c(d, 20, 100, 100, 40, colors.mistyrose, "Tenant B", "Raw Data")
    
    # Sanitization
    draw_rect_c(d, 160, 80, 100, 140, C_SEC, "Sanitization", "Strip PII")
    
    # Shared
    draw_rect_c(d, 300, 110, 140, 80, C_L2, "Shared Patterns", "Abstract Vectors")
    
    draw_arrow(d, 120, 180, 160, 180)
    draw_arrow(d, 120, 120, 160, 120)
    draw_arrow(d, 260, 150, 300, 150)
    
    return d

# ---------------- DOCUMENT GENERATOR ----------------

def build_pdf():
    doc = SimpleDocTemplate(FILENAME, pagesize=LETTER, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    story = []
    
    # Styles
    title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=16, spaceAfter=12)
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=12, spaceBefore=12, spaceAfter=6, textColor=colors.darkblue)
    body_style = ParagraphStyle('B', parent=styles['BodyText'], fontSize=10, leading=12, alignment=4) # Justify

    # 1. Header
    story.append(Paragraph("<b>PROVISIONAL PATENT APPLICATION</b>", title_style))
    story.append(Paragraph(f"<b>Title:</b> {TITLE}", body_style))
    story.append(Paragraph(f"<b>Filing Date:</b> {FILING_DATE}", body_style))
    story.append(Paragraph(f"<b>Inventor:</b> {INVENTOR_NAME} — {INVENTOR_LOC}", body_style))
    story.append(Spacer(1, 12))
    
    # 2. Abstract
    story.append(Paragraph("<b>Abstract</b>", h1_style))
    story.append(Paragraph(
        "A system and method for a Neural-Backed Memory Fabric (NBMF) integrated with an Enterprise-DNA (eDNA) "
        "governance layer. The system utilizes a hierarchical tiered memory structure comprising hot (L1), warm (L2), "
        "and cold (L3) storage layers, managed via Content-Addressable Storage (CAS) identifiers. The eDNA layer "
        "enforces governance through a Genome (capability schema) and Epigenome (tenant policy), utilizing "
        "Merkle-notarized lineage for immutable audit logs. An immune system component provides threat detection, "
        "quarantine, and state rollback capabilities.", body_style
    ))
    
    # 3. Background & Summary
    story.append(Paragraph("<b>Background & Summary</b>", h1_style))
    story.append(Paragraph(
        "Current multi-agent orchestrations face challenges regarding memory context windows, costs, and governance. "
        "This invention solves these by providing a tiered memory fabric (NBMF) wrapped in a biological governance "
        "layer (eDNA). It ensures data is stored efficiently (L1/L2/L3) and accessed securely (Genome/Epigenome).",
        body_style
    ))
    
    # 4. Brief Description of Drawings
    story.append(Paragraph("<b>Brief Description of the Drawings</b>", h1_style))
    fig_descs = [
        "FIG. 1: System Overview showing eDNA layer and NBMF tiers.",
        "FIG. 2: Promotion and Eviction pipelines with trust validation.",
        "FIG. 3: Trust validation logic including quarantine buffers.",
        "FIG. 4: Data encoding into lossless or semantic formats.",
        "FIG. 5: Merkle Tree Lineage for cryptographic auditing.",
        "FIG. 6: The four components of eDNA governance.",
        "FIG. 7: Immune system detection and rollback workflow.",
        "FIG. 8: Hardware abstraction for CPU/GPU/TPU routing.",
        "FIG. 9: Cross-tenant learning with raw data isolation."
    ]
    for f in fig_descs:
        story.append(Paragraph(f"• {f}", body_style))
        
    story.append(PageBreak())

    # 5. Drawings & Details
    story.append(Paragraph("<b>Detailed Description & Drawings</b>", h1_style))

    # Add all figures with captions
    figures = [
        (fig1_overview, "FIG. 1: NBMF System Overview"),
        (fig2_promotion, "FIG. 2: Promotion & Eviction"),
        (fig3_trust, "FIG. 3: Trust & Quarantine Pipeline"),
        (fig4_encoding, "FIG. 4: Neural Encoding"),
        (fig5_merkle, "FIG. 5: Merkle Lineage Ledger"),
        (fig6_edna, "FIG. 6: eDNA Governance Components"),
        (fig7_immune_workflow, "FIG. 7: Immune System Workflow"),
        (fig8_hardware, "FIG. 8: Hardware Abstraction"),
        (fig9_cross_tenant, "FIG. 9: Cross-Tenant Isolation"),
    ]

    for draw_func, cap in figures:
        d = draw_func()
        # Center the drawing
        t = Table([[d]], colWidths=[460])
        t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        story.append(t)
        story.append(make_caption(cap))
        story.append(Spacer(1, 12))

    # 6. Benchmarks (Realistic Data from Clean File)
    story.append(PageBreak())
    story.append(Paragraph("<b>Examples & Performance Metrics</b>", h1_style))
    story.append(Paragraph("The following metrics demonstrate the efficiency of the NBMF architecture:", body_style))
    
    data = [
        ['Metric', 'Measured Value', 'Note'],
        ['L1 Retrieval Latency', '15 ms', 'High-speed active context'],
        ['Storage Cost Reduction', '42%', 'Compared to All-RAM storage'],
        ['SimHash Deduplication', '12.5%', 'Space saved via fuzzy matching'],
        ['Immune Response Time', '< 200 ms', 'Time to quarantine threat'],
        ['Cold Recall Time', '< 500 ms', 'Retrieval from L3 Object Store']
    ]
    
    t = Table(data, colWidths=[150, 100, 200])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white])
    ]))
    story.append(t)
    
    # 7. Claims
    story.append(Paragraph("<b>Claims</b>", h1_style))
    claims = [
        "1. A distributed computing system comprising: (a) a Neural-Backed Memory Fabric (NBMF) with hierarchical tiers (L1/L2/L3) indexed via Content-Addressable Storage; and (b) an Enterprise-DNA (eDNA) governance layer enforcing access control via Genome and Epigenome policies.",
        "2. The system of Claim 1, further comprising a Merkle-tree based lineage ledger that records all memory promotions and evictions.",
        "3. The system of Claim 1, wherein an Immune System module detects threats and executes a state rollback to a previous valid Merkle root.",
        "4. A method for memory management comprising: ingesting data, generating SimHash identifiers, validating against trust policies, and routing to a storage tier based on access frequency.",
        "5. The system of Claim 1, utilizing hardware abstraction to dynamically route tensor operations to CPU, GPU, or TPU resources."
    ]
    for c in claims:
        story.append(Paragraph(c, body_style))
        story.append(Spacer(1, 6))

    doc.build(story)
    print(f"Success! {FILENAME} generated with colored figures and complete text.")

if __name__ == "__main__":
    build_pdf()