from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, String, Polygon
from reportlab.graphics import renderPDF
from reportlab.lib.units import inch

# --- CONFIGURATION ---
FILENAME = "NBMF_Patent_Application.pdf"
DATE_STR = "2025-01-15"

def create_patent_pdf():
    doc = SimpleDocTemplate(FILENAME, pagesize=LETTER)
    styles = getSampleStyleSheet()
    story = []

    # Custom Styles
    title_style = styles['Title']
    h1_style = ParagraphStyle(name='Heading1_Custom', parent=styles['Heading1'], spaceAfter=12, spaceBefore=20)
    h2_style = ParagraphStyle(name='Heading2_Custom', parent=styles['Heading2'], spaceAfter=10, spaceBefore=15)
    body_style = styles['BodyText']
    code_style = ParagraphStyle(name='Code', parent=styles['Code'], fontSize=8, leading=10)
    
    # --- HELPER: DRAWING FUNCTIONS FOR FIGURES ---
    
    def draw_fig1_overview():
        """Re-creates System Overview: Sunflower-Honeycomb + Blocks"""
        d = Drawing(400, 200)
        # Central VP
        d.add(Circle(200, 100, 30, fillColor=colors.lightgrey, strokeColor=colors.black))
        d.add(String(185, 98, "Daena VP", fontSize=10))
        
        # Honeycomb Agents
        centers = [(140, 140), (260, 140), (140, 60), (260, 60), (200, 160), (200, 40)]
        for cx, cy in centers:
            d.add(Circle(cx, cy, 15, fillColor=colors.whitesmoke, strokeColor=colors.black))
            
        # NBMF & eDNA Blocks
        d.add(Rect(50, 50, 60, 100, fillColor=colors.lightblue, strokeColor=colors.black))
        d.add(String(60, 100, "NBMF", fontSize=12))
        d.add(Rect(290, 50, 60, 100, fillColor=colors.lightgreen, strokeColor=colors.black))
        d.add(String(300, 100, "eDNA", fontSize=12))
        
        # Connection lines
        d.add(Line(110, 100, 170, 100, strokeWidth=2))
        d.add(Line(230, 100, 290, 100, strokeWidth=2))
        return d

    def draw_fig2_flow():
        """Re-creates NBMF Tiered Flow"""
        d = Drawing(400, 250)
        # Nodes
        d.add(Rect(150, 210, 100, 30, fillColor=colors.whitesmoke))
        d.add(String(170, 220, "Ingest Stream"))
        
        d.add(Rect(150, 160, 100, 30, fillColor=colors.whitesmoke))
        d.add(String(160, 170, "Hash (CAS+Sim)"))
        
        d.add(Polygon([200, 150, 250, 125, 200, 100, 150, 125], fillColor=colors.lightyellow, strokeColor=colors.black))
        d.add(String(180, 125, "Decision Logic"))
        
        # Tiers
        d.add(Rect(50, 40, 80, 40, fillColor=colors.mistyrose))
        d.add(String(75, 55, "L1 (Hot)"))
        d.add(Rect(160, 40, 80, 40, fillColor=colors.lightyellow))
        d.add(String(180, 55, "L2 (Warm)"))
        d.add(Rect(270, 40, 80, 40, fillColor=colors.lightcyan))
        d.add(String(290, 55, "L3 (Cold)"))
        
        # Arrows
        d.add(Line(200, 210, 200, 190, strokeWidth=1, arrow=True)) # Ingest -> Hash
        d.add(Line(200, 160, 200, 150, strokeWidth=1, arrow=True)) # Hash -> Decision
        d.add(Line(170, 115, 90, 80, strokeWidth=1)) # -> L1
        d.add(Line(200, 100, 200, 80, strokeWidth=1)) # -> L2
        d.add(Line(230, 115, 310, 80, strokeWidth=1)) # -> L3
        return d

    def draw_fig3_lineage():
        """Re-creates Merkle Tree Lineage"""
        d = Drawing(400, 150)
        # Root
        d.add(Rect(175, 110, 50, 30, fillColor=colors.gold))
        d.add(String(185, 120, "ROOT"))
        # Mid
        d.add(Rect(125, 60, 40, 20, fillColor=colors.lightgrey))
        d.add(Rect(235, 60, 40, 20, fillColor=colors.lightgrey))
        # Leaves
        d.add(Rect(100, 10, 30, 20, fillColor=colors.whitesmoke))
        d.add(Rect(150, 10, 30, 20, fillColor=colors.whitesmoke))
        d.add(Rect(210, 10, 30, 20, fillColor=colors.whitesmoke))
        d.add(Rect(260, 10, 30, 20, fillColor=colors.whitesmoke))
        
        # Lines
        d.add(Line(200, 110, 145, 80))
        d.add(Line(200, 110, 255, 80))
        d.add(Line(145, 60, 115, 30))
        d.add(Line(145, 60, 165, 30))
        return d
    
    def draw_fig4_genome():
        """Genome/Epigenome Gates"""
        d = Drawing(400, 100)
        # Flow
        d.add(String(10, 50, "Request ->"))
        
        d.add(Rect(80, 30, 80, 40, fillColor=colors.thistle))
        d.add(String(90, 45, "Genome (Static)"))
        
        d.add(Line(160, 50, 190, 50))
        
        d.add(Rect(190, 30, 90, 40, fillColor=colors.plum))
        d.add(String(200, 45, "Epigenome (ABAC)"))
        
        d.add(Line(280, 50, 310, 50, arrow=True))
        d.add(String(320, 50, "Execute"))
        return d

    def draw_fig5_immune():
        """Immune System Loop"""
        d = Drawing(400, 150)
        # Circle flow
        d.add(Rect(150, 110, 100, 30, fillColor=colors.whitesmoke))
        d.add(String(160, 120, "1. Monitor"))
        
        d.add(Rect(250, 60, 100, 30, fillColor=colors.mistyrose))
        d.add(String(260, 70, "2. Detect Antigen"))
        
        d.add(Rect(150, 10, 100, 30, fillColor=colors.lightcoral))
        d.add(String(160, 20, "3. Quarantine"))
        
        d.add(Rect(50, 60, 100, 30, fillColor=colors.lightgreen))
        d.add(String(60, 70, "4. Rollback"))
        
        # Arrows approx
        d.add(Line(250, 125, 300, 90, arrow=True))
        d.add(Line(300, 60, 250, 25, arrow=True))
        d.add(Line(150, 25, 100, 60, arrow=True))
        d.add(Line(100, 90, 150, 110, arrow=True))
        return d

    # --- CONTENT GENERATION ---

    # 1. Title
    story.append(Paragraph("<b>PROVISIONAL PATENT APPLICATION</b>", title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Title:</b> NEURAL-BACKED MEMORY FABRIC (NBMF) WITH ENTERPRISE-DNA GOVERNANCE FOR MULTI-AGENT SYSTEMS", h1_style))
    story.append(Paragraph(f"<b>Filing Date:</b> {DATE_STR}", body_style))
    story.append(Paragraph("<b>Inventor(s):</b> [TODO: Insert Name]", body_style))
    story.append(Spacer(1, 24))

    # 2. Abstract
    story.append(Paragraph("<b>Abstract</b>", h1_style))
    story.append(Paragraph("A system and method for a Neural-Backed Memory Fabric (NBMF) integrated with an Enterprise-DNA (eDNA) governance layer to manage multi-agent artificial intelligence architectures. The system utilizes a hierarchical tiered memory structure comprising hot (L1), warm (L2), and cold (L3) storage layers, managed via Content-Addressable Storage (CAS) identifiers and SimHash algorithms. The eDNA layer enforces governance through a Genome (capability schema) and Epigenome (tenant policy), utilizing Merkle-notarized lineage for immutable audit logs. An immune system component provides threat detection, quarantine, and state rollback capabilities.", body_style))

    # 3. Background
    story.append(Paragraph("<b>Background of the Invention</b>", h1_style))
    story.append(Paragraph("The invention relates to AI memory management. Current multi-agent orchestrations face challenges regarding memory context windows, costs, and governance. Autonomous agents often lack rigid access controls, and existing vector databases lack cryptographic lineage.", body_style))

    # 4. Summary
    story.append(Paragraph("<b>Summary of the Invention</b>", h1_style))
    story.append(Paragraph("The invention provides a Neural-Backed Memory Fabric (NBMF) coupled with an Enterprise-DNA (eDNA) governance layer. NBMF creates a unified address space with tiers L1/L2/L3 using CAS and SimHash. eDNA provides Genome (capabilities), Epigenome (policy), Lineage (Merkle proofs), and an Immune System (threat detection/rollback).", body_style))

    # 5. Drawings Description
    story.append(Paragraph("<b>Brief Description of the Drawings</b>", h1_style))
    story.append(Paragraph("FIG. 1 illustrates the System Overview.", body_style))
    story.append(Paragraph("FIG. 2 illustrates the NBMF Tiered Flow.", body_style))
    story.append(Paragraph("FIG. 3 illustrates the Lineage Ledger (Merkle Tree).", body_style))
    story.append(Paragraph("FIG. 4 illustrates the Genome/Epigenome Governance Gates.", body_style))
    story.append(Paragraph("FIG. 5 illustrates the Immune System Logic.", body_style))
    story.append(Paragraph("FIG. 6 illustrates the Hardware Abstraction Layer.", body_style))
    story.append(Paragraph("FIG. 7 illustrates Cross-Tenant Learning Isolation.", body_style))

    # 6. Detailed Description
    story.append(PageBreak())
    story.append(Paragraph("<b>Detailed Description</b>", h1_style))
    
    story.append(Paragraph("<b>A. System Overview</b>", h2_style))
    story.append(Paragraph("The system comprises a 'Sunflower-Honeycomb' organizational structure. A central Virtual Personality (VP) coordinates specialized agents.", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig1_overview())
    story.append(Paragraph("<i>FIG. 1: System Overview showing Daena VP and Agent Hive.</i>", body_style))
    story.append(Spacer(1, 24))

    story.append(Paragraph("<b>B. Neural-Backed Memory Fabric (NBMF)</b>", h2_style))
    story.append(Paragraph("NBMF organizes data into three tiers: L1 (Hot/RAM), L2 (Warm/NVMe), and L3 (Cold/Object Store). It uses CAS IDs (SHA-256) and SimHash for deduplication.", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig2_flow())
    story.append(Paragraph("<i>FIG. 2: NBMF Ingestion and Tiering Flow.</i>", body_style))
    story.append(Spacer(1, 24))

    story.append(Paragraph("<b>C. Enterprise-DNA (eDNA)</b>", h2_style))
    story.append(Paragraph("eDNA wraps NBMF for governance. 1) Genome: Static capabilities. 2) Epigenome: Dynamic ABAC policy. 3) Lineage: Merkle-tree based ledger.", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig3_lineage())
    story.append(Paragraph("<i>FIG. 3: Lineage Ledger using Merkle Tree.</i>", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig4_genome())
    story.append(Paragraph("<i>FIG. 4: Genome and Epigenome Request Gates.</i>", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig5_immune())
    story.append(Paragraph("<i>FIG. 5: Immune System Detection and Rollback Loop.</i>", body_style))
    
    story.append(Paragraph("<b>D. Hardware & Enablement</b>", h2_style))
    story.append(Paragraph("The system uses hardware adapters (FIG. 6, not shown) for CPU/GPU/TPU routing and ensures Cross-Tenant Learning (FIG. 7, not shown) allows abstract vector sharing without raw data leakage.", body_style))

    # 7. Benchmarks
    story.append(Paragraph("<b>Examples & Benchmarks</b>", h1_style))
    data = [
        ['Metric', 'Value (approx)', 'Source'],
        ['L1 Latency', '[TODO: 15ms]', 'docs/benchmarks.md'],
        ['Storage Savings', '[TODO: 40%]', 'docs/costs.md'],
        ['SimHash Dedupe', '[TODO: 12%]', 'docs/benchmarks.md']
    ]
    t = Table(data)
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black),
                           ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    story.append(t)
    story.append(Spacer(1, 12))
    story.append(Paragraph("<i>Note: Values must be verified against source files before filing.</i>", body_style))

    # 8. Claims
    story.append(PageBreak())
    story.append(Paragraph("<b>Claims</b>", h1_style))
    claims = [
        "1. A distributed computing system for managing artificial intelligence agent memory and governance, comprising: (a) a processor and memory; (b) a Neural-Backed Memory Fabric (NBMF) configured to store data in a hierarchical tier structure (L1, L2, L3) indexed via Content-Addressable Storage (CAS); and (c) an Enterprise-DNA (eDNA) governance layer configured to enforce access control via a Genome schema and Epigenome policy.",
        "2. A method for managing multi-agent memory, comprising: ingesting input; generating a CAS ID and SimHash; determining a storage tier; verifying against Epigenome policy; and recording the action in a Merkle tree-based lineage ledger.",
        "3. A non-transitory computer-readable medium storing instructions to perform the method of Claim 2.",
        "4. The system of Claim 1, wherein the NBMF utilizes SimHash for semantic deduplication.",
        "5. The system of Claim 1, wherein the lineage ledger utilizes a Merkle tree structure.",
        "6. The system of Claim 1, further comprising an immune system module for threat detection and rollback.",
        "7. The system of Claim 1, utilizing Attribute-Based Access Control (ABAC)."
    ]
    for claim in claims:
        story.append(Paragraph(claim, body_style))
        story.append(Spacer(1, 6))

    # 9. Checklist
    story.append(PageBreak())
    story.append(Paragraph("<b>Filing Checklist (MICRO Entity)</b>", h1_style))
    story.append(Paragraph("[] Fee: $70 USD", body_style))
    story.append(Paragraph("[] Specification (This Document)", body_style))
    story.append(Paragraph("[] Drawings (Included in this PDF)", body_style))
    story.append(Paragraph("[] Cover Sheet (Fill online at USPTO)", body_style))

    # Build PDF
    doc.build(story)
    print(f"Success! {FILENAME} has been generated.")

if __name__ == "__main__":
    create_patent_pdf()