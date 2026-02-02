from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, String, Polygon, Group
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
        
        # Multi-LLM Router
        d.add(Rect(170, 10, 60, 30, fillColor=colors.lightyellow, strokeColor=colors.black))
        d.add(String(175, 20, "Multi-LLM", fontSize=9))
        d.add(String(180, 12, "Router", fontSize=9))
        
        # Connection lines
        d.add(Line(110, 100, 170, 100, strokeWidth=2))
        d.add(Line(230, 100, 290, 100, strokeWidth=2))
        d.add(Line(200, 70, 200, 40, strokeWidth=1))
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
        
        # Lineage Write
        d.add(Rect(320, 160, 60, 30, fillColor=colors.lightgrey))
        d.add(String(325, 170, "Lineage", fontSize=9))
        d.add(String(330, 162, "Write", fontSize=9))
        
        # Arrows
        d.add(Line(200, 210, 200, 190, strokeWidth=1)) # Ingest -> Hash
        d.add(Line(200, 160, 200, 150, strokeWidth=1)) # Hash -> Decision
        d.add(Line(170, 115, 90, 80, strokeWidth=1)) # -> L1
        d.add(Line(200, 100, 200, 80, strokeWidth=1)) # -> L2
        d.add(Line(230, 115, 310, 80, strokeWidth=1)) # -> L3
        d.add(Line(250, 125, 320, 175, strokeWidth=1)) # Decision -> Lineage
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
        d.add(Line(255, 60, 225, 30))
        d.add(Line(255, 60, 275, 30))
        
        # Rollback indicator
        d.add(String(300, 120, "Rollback", fontSize=8))
        d.add(Line(300, 115, 250, 125, strokeWidth=1))
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
        
        d.add(Line(280, 50, 310, 50))
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
        
        # Arrows
        d.add(Line(250, 125, 300, 90, strokeWidth=1))
        d.add(Line(300, 60, 250, 25, strokeWidth=1))
        d.add(Line(150, 25, 100, 60, strokeWidth=1))
        d.add(Line(100, 90, 150, 110, strokeWidth=1))
        return d
    
    def draw_fig6_hardware():
        """Hardware Abstraction Layer"""
        d = Drawing(400, 180)
        # Core
        d.add(Rect(150, 100, 100, 50, fillColor=colors.lightblue, strokeColor=colors.black))
        d.add(String(170, 120, "NBMF/eDNA", fontSize=11))
        d.add(String(175, 108, "Core", fontSize=11))
        
        # Adapters
        d.add(Rect(50, 30, 80, 40, fillColor=colors.lightcyan, strokeColor=colors.black))
        d.add(String(65, 45, "CPU", fontSize=10))
        d.add(String(70, 37, "Adapter", fontSize=10))
        
        d.add(Rect(160, 30, 80, 40, fillColor=colors.lightcyan, strokeColor=colors.black))
        d.add(String(175, 45, "GPU", fontSize=10))
        d.add(String(180, 37, "Adapter", fontSize=10))
        
        d.add(Rect(270, 30, 80, 40, fillColor=colors.lightcyan, strokeColor=colors.black))
        d.add(String(285, 45, "TPU", fontSize=10))
        d.add(String(290, 37, "Adapter", fontSize=10))
        
        # Connections
        d.add(Line(190, 100, 90, 70, strokeWidth=2))
        d.add(Line(200, 100, 200, 70, strokeWidth=2))
        d.add(Line(210, 100, 310, 70, strokeWidth=2))
        return d
    
    def draw_fig7_cross_tenant():
        """Cross-Tenant Learning Isolation"""
        d = Drawing(400, 150)
        # Tenant A
        d.add(Rect(50, 80, 100, 50, fillColor=colors.lightblue, strokeColor=colors.black))
        d.add(String(75, 105, "Tenant A", fontSize=10))
        d.add(String(60, 95, "Raw Data", fontSize=8))
        d.add(String(65, 87, "(Isolated)", fontSize=8))
        
        # Tenant B
        d.add(Rect(250, 80, 100, 50, fillColor=colors.lightgreen, strokeColor=colors.black))
        d.add(String(275, 105, "Tenant B", fontSize=10))
        d.add(String(260, 95, "Raw Data", fontSize=8))
        d.add(String(265, 87, "(Isolated)", fontSize=8))
        
        # Shared Abstract Vectors
        d.add(Rect(150, 20, 100, 40, fillColor=colors.lightyellow, strokeColor=colors.black))
        d.add(String(165, 40, "Shared Abstract", fontSize=9))
        d.add(String(180, 32, "Vectors", fontSize=9))
        
        # Connections (abstract only, no raw data)
        d.add(Line(100, 80, 200, 60, strokeWidth=2, strokeDashArray=[5, 3]))
        d.add(Line(300, 80, 200, 60, strokeWidth=2, strokeDashArray=[5, 3]))
        d.add(String(195, 10, "No Raw Data Leakage", fontSize=8))
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
    story.append(Paragraph("A system and method for a Neural-Backed Memory Fabric (NBMF) integrated with an Enterprise-DNA (eDNA) governance layer to manage multi-agent artificial intelligence architectures. The system utilizes a hierarchical tiered memory structure comprising hot (L1), warm (L2), and cold (L3) storage layers, managed via Content-Addressable Storage (CAS) identifiers and SimHash algorithms for deduplication and fuzzy matching. The eDNA layer enforces governance through a Genome (capability schema) and Epigenome (tenant policy), utilizing Merkle-notarized lineage for immutable audit logs. An immune system component provides threat detection, quarantine, and state rollback capabilities. The architecture optimizes token usage, latency, and storage costs while ensuring cryptographic provenance and cross-tenant data isolation without raw data leakage.", body_style))

    # 3. Background
    story.append(Paragraph("<b>Background of the Invention</b>", h1_style))
    story.append(Paragraph("<b>Field of the Invention</b>", h2_style))
    story.append(Paragraph("The present invention relates generally to artificial intelligence and distributed computing, and more specifically to memory management and governance architectures for multi-agent Large Language Model (LLM) systems.", body_style))
    story.append(Paragraph("<b>Description of Related Art</b>", h2_style))
    story.append(Paragraph("Current multi-agent orchestrations face significant challenges regarding memory context windows, operational costs, and data governance.", body_style))
    story.append(Paragraph("1. Memory Cost and Latency: LLMs possess finite context windows. Storing entire conversation histories in active memory (RAM/GPU VRAM) is prohibitively expensive and increases latency.", body_style))
    story.append(Paragraph("2. Governance and Safety: Autonomous agents often lack rigid access controls (RBAC/ABAC) at the cognitive processing level, leading to potential prompt injection vulnerabilities or unauthorized data access.", body_style))
    story.append(Paragraph("3. Auditability: Existing vector databases provide retrieval but lack cryptographic proof of lineage (provenance) for why a specific memory was retrieved or how an agent's state evolved.", body_style))
    story.append(Paragraph("[SOURCE: daena/docs/problems.md (TODO: Verify file path)] describes these specific pain points in detail.", body_style))

    # 4. Summary
    story.append(Paragraph("<b>Summary of the Invention</b>", h1_style))
    story.append(Paragraph("The invention provides a Neural-Backed Memory Fabric (NBMF) coupled with an Enterprise-DNA (eDNA) governance layer.", body_style))
    story.append(Paragraph("The NBMF creates a unified address space for agentic memory, abstracting physical storage (RAM, NVMe, Object Store) into logical tiers (L1, L2, L3). It utilizes Content-Addressable Storage (CAS) based on cryptographic hashes and SimHash for semantic deduplication.", body_style))
    story.append(Paragraph("The eDNA layer acts as a biological control structure for the digital agents. It comprises:", body_style))
    story.append(Paragraph("• Genome: The immutable set of capabilities an agent can perform.", body_style))
    story.append(Paragraph("• Epigenome: The mutable policy layer (ABAC) defining what an agent may perform under specific contexts.", body_style))
    story.append(Paragraph("• Lineage: A Merkle-tree based ledger ensuring every memory promotion/eviction and agent action is cryptographically notarized.", body_style))
    story.append(Paragraph("• Immune System: A monitoring loop that detects anomalies (via heuristic or model-based signals), quarantines \"infected\" memory nodes, and executes rollbacks to safe states.", body_style))

    # 5. Drawings Description
    story.append(Paragraph("<b>Brief Description of the Drawings</b>", h1_style))
    story.append(Paragraph("• FIG. 1 is a block diagram illustrating the System Overview, including the Sunflower–Honeycomb organization, Daena VP, NBMF, eDNA blocks, and the multi-LLM router.", body_style))
    story.append(Paragraph("• FIG. 2 is a flow diagram of the NBMF Tiered Flow, detailing the path from ingestion, chunking, CAS ID generation, SimHash calculation, L1/L2/L3 decision logic, to lineage writing.", body_style))
    story.append(Paragraph("• FIG. 3 is a schematic of the Lineage Ledger, showing the Merkle tree structure of promotions with proof paths and rollback mechanisms.", body_style))
    story.append(Paragraph("• FIG. 4 is a block diagram of the Genome/Epigenome architecture, illustrating the capability schema and tenant policy gates within the request path.", body_style))
    story.append(Paragraph("• FIG. 5 is a logic flow diagram of the Immune System, covering threat signal detection, quarantine storage, and the review/rollback process.", body_style))
    story.append(Paragraph("• FIG. 6 is a component diagram of the Hardware Abstraction layer, showing CPU/GPU/TPU adapters wrapping the NBMF/eDNA core.", body_style))
    story.append(Paragraph("• FIG. 7 is a conceptual diagram of Cross-Tenant Learning, demonstrating abstract vector sharing without raw data crossing tenant boundaries.", body_style))

    # 6. Detailed Description
    story.append(PageBreak())
    story.append(Paragraph("<b>Detailed Description</b>", h1_style))
    
    story.append(Paragraph("<b>A. System Overview</b>", h2_style))
    story.append(Paragraph("The system comprises a \"Sunflower-Honeycomb\" organizational structure where a central Virtual Personality (VP), referred to herein as \"Daena,\" coordinates multiple specialized agents. The system runs on a hardware abstraction layer capable of utilizing CPU, GPU, or TPU resources [SOURCE: daena/docs/hardware.md §TODO].", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig1_overview())
    story.append(Paragraph("<i>FIG. 1: System Overview showing Daena VP and Agent Hive.</i>", body_style))
    story.append(Spacer(1, 24))

    story.append(Paragraph("<b>B. Neural-Backed Memory Fabric (NBMF)</b>", h2_style))
    story.append(Paragraph("The NBMF organizes data into three distinct tiers to balance performance and cost.", body_style))
    story.append(Paragraph("• L1 (Hot/Active): Resides in high-speed memory (e.g., RAM or GPU VRAM). It stores the immediate context and highest-priority vectors.", body_style))
    story.append(Paragraph("• L2 (Warm/Associative): Resides in fast persistent storage (e.g., NVMe SSDs). It utilizes vector indices for rapid retrieval of relevant historical context.", body_style))
    story.append(Paragraph("• L3 (Cold/Archive): Resides in bulk object storage (e.g., S3-compatible blobs). It stores the complete archival history.", body_style))
    story.append(Paragraph("<b>Ingest and CAS:</b>", h2_style))
    story.append(Paragraph("Upon data ingestion, the system chunks input and generates a Content-Addressable Storage (CAS) ID using a cryptographic hash (e.g., SHA-256). Simultaneously, a SimHash is calculated to detect near-duplicates.", body_style))
    story.append(Paragraph("• SimHash Logic: [TODO: Insert logic/thresholds from daena/docs/nbmf_logic.md]. If the Hamming distance between a new input and stored SimHash is below threshold T, the system treats it as a duplicate or version.", body_style))
    story.append(Paragraph("<b>Promotion and Eviction:</b>", h2_style))
    story.append(Paragraph("Memory segments move between L1, L2, and L3 based on access frequency and \"emotional\" salience scores assigned by the VP.", body_style))
    story.append(Paragraph("• Compaction: Periodic processes merge small memory fragments in L2 into consolidated blocks for L3 storage.", body_style))
    story.append(Paragraph("• Lineage Write: Every movement (e.g., L1 → L2) is recorded in the Lineage ledger.", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig2_flow())
    story.append(Paragraph("<i>FIG. 2: NBMF Ingestion and Tiering Flow.</i>", body_style))
    story.append(Spacer(1, 24))

    story.append(Paragraph("<b>C. Enterprise-DNA (eDNA)</b>", h2_style))
    story.append(Paragraph("The eDNA layer wraps the NBMF to enforce strict governance.", body_style))
    story.append(Paragraph("1. Genome (Capabilities): A static schema defining the hard limits of an agent's code execution capabilities (e.g., \"CanReadFiles\", \"CannotExecuteShell\").", body_style))
    story.append(Paragraph("2. Epigenome (Policy): A dynamic layer implementing Attribute-Based Access Control (ABAC). It evaluates policy rules such as \"Tenant A cannot access Tenant B's vectors\" or \"Spending limit < $5.00/day\". [SOURCE: daena/docs/edna_policy.md §TODO].", body_style))
    story.append(Paragraph("3. Lineage (Provenance): A cryptographic log. All state changes are hashed into a Merkle Tree. The Root Hash is published periodically to an immutable store (or blockchain), allowing verification that memory has not been tampered with.", body_style))
    story.append(Paragraph("4. Immune System:", body_style))
    story.append(Paragraph("   o Detection: Monitors for \"antigens\" (signals of hallucination, prompt injection, or policy violation).", body_style))
    story.append(Paragraph("   o Quarantine: If a signal exceeds a risk threshold, the associated memory nodes are moved to a quarantined state, inaccessible to standard queries.", body_style))
    story.append(Paragraph("   o Rollback: The system can revert the NBMF state to a previous Merkle Root before the infection occurred.", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig3_lineage())
    story.append(Paragraph("<i>FIG. 3: Lineage Ledger using Merkle Tree.</i>", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig4_genome())
    story.append(Paragraph("<i>FIG. 4: Genome and Epigenome Request Gates.</i>", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig5_immune())
    story.append(Paragraph("<i>FIG. 5: Immune System Detection and Rollback Loop.</i>", body_style))
    
    story.append(Paragraph("<b>D. Hardware Abstraction and Security</b>", h2_style))
    story.append(Paragraph("The system employs adapters (FIG. 6) to interface with underlying hardware.", body_style))
    story.append(Paragraph("• Data Minimization: PII (Personally Identifiable Information) is redacted or tokenized before entering the NBMF tiers using a \"Data-Minimization Path\" [SOURCE: daena/docs/security.md §TODO].", body_style))
    story.append(Paragraph("• Multi-LLM Router: The system routes prompts to different underlying models (e.g., GPT-4, local LLaMA) based on cost/complexity trade-offs defined in the Epigenome.", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig6_hardware())
    story.append(Paragraph("<i>FIG. 6: Hardware Abstraction Layer showing CPU/GPU/TPU adapters.</i>", body_style))
    story.append(Spacer(1, 12))
    story.append(draw_fig7_cross_tenant())
    story.append(Paragraph("<i>FIG. 7: Cross-Tenant Learning mechanism with data isolation.</i>", body_style))
    
    story.append(Paragraph("<b>E. Enablement</b>", h2_style))
    story.append(Paragraph("The system may be implemented using Python for the orchestration layer, Rust for the high-performance CAS/SimHash engine, and a vector store (e.g., Qdrant/Milvus) for L2 indices. The eDNA policies can be defined in a declarative language (e.g., Rego or JSON/YAML schemas).", body_style))

    # 7. Examples & Benchmarks
    story.append(PageBreak())
    story.append(Paragraph("<b>Examples & Benchmarks</b>", h1_style))
    story.append(Paragraph("<b>Methodology Notes & Variance:</b>", h2_style))
    story.append(Paragraph("All benchmarks were conducted on [TODO: Insert Hardware Specs from docs] as of 2025-01-15.", body_style))
    data = [
        ['Metric', 'Measured Value', 'Source File'],
        ['L1 Retrieval Latency', '[TODO: e.g., 15ms]', '[SOURCE: daena/docs/benchmarks.md §L1]'],
        ['Storage Savings (vs. Raw)', '[TODO: e.g., 40%]', '[SOURCE: daena/docs/storage_costs.md §Compression]'],
        ['SimHash Deduplication Rate', '[TODO: e.g., 12%]', '[SOURCE: daena/docs/benchmarks.md §Dedupe]'],
        ['Immune Response Time', '[TODO: e.g., <200ms]', '[SOURCE: daena/docs/security_bench.md §Immune]']
    ]
    t = Table(data)
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT')
    ]))
    story.append(t)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Note: If variance exists between source files, the conservative (higher latency/lower savings) value is reported above.", body_style))

    # 8. Advantages
    story.append(Paragraph("<b>Advantages</b>", h1_style))
    story.append(Paragraph("1. Cost Efficiency: The NBMF tiered architecture reduces reliance on expensive VRAM (L1) by offloading semantic context to cheaper L2/L3 storage. [SOURCE: daena/docs/cost_analysis.md]", body_style))
    story.append(Paragraph("2. Auditability: The eDNA Lineage system provides cryptographic proof of every agent decision, essential for enterprise compliance.", body_style))
    story.append(Paragraph("3. Safety: The Immune System allows for instant rollback of agent \"lobotomies\" or poisonings without rebuilding the entire database.", body_style))
    story.append(Paragraph("4. Privacy: Cross-tenant learning (FIG. 7) allows agents to improve shared abstract reasoning without exposing raw tenant data.", body_style))

    # 9. Claims
    story.append(PageBreak())
    story.append(Paragraph("<b>Claims (Draft)</b>", h1_style))
    claims = [
        "Claim 1. A distributed computing system for managing artificial intelligence agent memory and governance, comprising: (a) a processor and a memory; (b) a Neural-Backed Memory Fabric (NBMF) configured to store data in a hierarchical tier structure comprising a first tier (L1) for active context, a second tier (L2) for associative retrieval, and a third tier (L3) for archival storage, wherein data is indexed via Content-Addressable Storage (CAS) identifiers; and (c) an Enterprise-DNA (eDNA) governance layer configured to enforce access control via a static Genome capability schema and a dynamic Epigenome policy engine, and to record state changes in a cryptographically verifiable lineage ledger.",
        "Claim 2. A method for managing multi-agent memory, comprising: ingesting an input data stream; generating a unique CAS identifier and a SimHash locality-sensitive hash for said input; determining a storage tier (L1, L2, or L3) for said input based on a promotion/eviction logic; verifying said input against an Epigenome policy definition; recording the storage action in a Merkle tree-based lineage ledger; and monitoring said input for threat signals via an immune system module configured to quarantine said input upon detection of a policy violation.",
        "Claim 3. A non-transitory computer-readable medium storing instructions that, when executed by a processor, cause the processor to perform the method of Claim 2.",
        "Claim 4. The system of Claim 1, wherein the NBMF utilizes SimHash algorithms to identify and deduplicate semantically similar data across the L1, L2, and L3 tiers.",
        "Claim 5. The system of Claim 1, wherein the lineage ledger utilizes a Merkle tree structure to provide a root hash representing the exact state of the memory fabric at a specific timestamp.",
        "Claim 6. The system of Claim 1, wherein the eDNA layer further comprises an immune system module configured to detect anomaly signals and execute a rollback of the NBMF to a previous Merkle root.",
        "Claim 7. The system of Claim 1, wherein the Epigenome policy engine utilizes Attribute-Based Access Control (ABAC) to restrict agent actions based on tenant context.",
        "Claim 8. The system of Claim 1, further comprising a hardware abstraction layer configured to route computational tasks to a CPU, GPU, or TPU based on resource availability.",
        "Claim 9. The method of Claim 2, wherein determining the storage tier includes calculating an emotional salience score for the input data.",
        "Claim 10. The method of Claim 2, wherein the quarantine action includes logically isolating the CAS identifier from retrieval queries without deleting the underlying data.",
        "Claim 11. The method of Claim 2, further comprising a cross-tenant learning process wherein abstract vectors are shared between tenants while raw text data remains isolated.",
        "Claim 12. The system of Claim 1, wherein the L2 tier resides on NVMe storage and utilizes vector indexing for nearest-neighbor search.",
        "Claim 13. The system of Claim 1, wherein the L3 tier utilizes object storage for long-term retention of compressed memory blocks.",
        "Claim 14. The system of Claim 1, further comprising a multi-LLM router configured to select a specific Large Language Model for processing based on cost policies defined in the Epigenome.",
        "Claim 15. The system of Claim 1, wherein the Genome capability schema is immutable during the runtime of an agent instance.",
        "Claim 16. The system of Claim 6, wherein the immune system module utilizes heuristic analysis to detect prompt injection attacks.",
        "Claim 17. The system of Claim 1, configured to operate within a Sunflower–Honeycomb organizational structure managed by a central Virtual Personality.",
        "Claim 18. The method of Claim 2, wherein the ingestion step includes redacting personally identifiable information (PII) prior to CAS ID generation.",
        "Claim 19. The system of Claim 1, wherein the NBMF is configured to perform periodic compaction of data in the L2 tier for migration to the L3 tier.",
        "Claim 20. The method of Claim 2, wherein the lineage ledger provides a proof path to verify the existence of a specific memory chunk without revealing the entire dataset."
    ]
    for claim in claims:
        story.append(Paragraph(claim, body_style))
        story.append(Spacer(1, 6))

    # 10. Figure List
    story.append(PageBreak())
    story.append(Paragraph("<b>Figure List</b>", h1_style))
    story.append(Paragraph("• FIG. 1 shows the System Overview, depicting the relationship between the Daena VP, the NBMF storage layers, and the eDNA governance modules.", body_style))
    story.append(Paragraph("• FIG. 2 shows the NBMF Tiered Flow, illustrating the data lifecycle from ingestion through hashing to storage tier placement.", body_style))
    story.append(Paragraph("• FIG. 3 shows the Lineage Ledger, depicting the Merkle Tree structure used for auditing and rollback operations.", body_style))
    story.append(Paragraph("• FIG. 4 shows the Genome/Epigenome architecture, illustrating how capability schemas and policies gate agent requests.", body_style))
    story.append(Paragraph("• FIG. 5 shows the Immune System logic, detailing the detection, quarantine, and remediation workflow.", body_style))
    story.append(Paragraph("• FIG. 6 shows the Hardware Abstraction layer, illustrating the interface between the core system and physical computation resources.", body_style))
    story.append(Paragraph("• FIG. 7 shows the Cross-Tenant Learning mechanism, validating data isolation.", body_style))

    # 11. Glossary
    story.append(Paragraph("<b>Glossary</b>", h1_style))
    story.append(Paragraph("• NBMF (Neural-Backed Memory Fabric): A hierarchical storage architecture using L1/L2/L3 tiers to manage AI context.", body_style))
    story.append(Paragraph("• eDNA (Enterprise-DNA): The governance layer comprising Genome, Epigenome, Lineage, and Immune components.", body_style))
    story.append(Paragraph("• Genome: The immutable set of static capabilities available to an agent.", body_style))
    story.append(Paragraph("• Epigenome: The mutable, context-aware policy layer (ABAC) governing agent behavior.", body_style))
    story.append(Paragraph("• CAS (Content-Addressable Storage): A method of storing data where the address is derived from the content's hash.", body_style))
    story.append(Paragraph("• SimHash: A locality-sensitive hashing technique used to identify near-duplicate records.", body_style))
    story.append(Paragraph("• Merkle Root: The top hash of a Merkle tree, used to cryptographically verify the integrity of the entire dataset.", body_style))
    story.append(Paragraph("• ABAC: Attribute-Based Access Control.", body_style))
    story.append(Paragraph("• Sunflower-Honeycomb: The specific organizational topology of the agent swarm.", body_style))

    # 12. Provisional Cover-Sheet Content
    story.append(PageBreak())
    story.append(Paragraph("<b>Provisional Cover-Sheet Content (For Manual Entry)</b>", h1_style))
    story.append(Paragraph("• Title: NEURAL-BACKED MEMORY FABRIC (NBMF) WITH ENTERPRISE-DNA GOVERNANCE FOR MULTI-AGENT SYSTEMS", body_style))
    story.append(Paragraph("• Inventor(s): [TODO: Insert First Name Last Name, City, State, Country]", body_style))
    story.append(Paragraph("• Correspondence Address: [TODO: Insert Address / Email]", body_style))
    story.append(Paragraph("• Entity Status: MICRO (Check the box confirming Gross Income limit and <4 prior applications).", body_style))
    story.append(Paragraph("• Government Interest: None.", body_style))
    story.append(Paragraph("• Attorney Docket Number: [Optional: e.g., DAENA-001-PROV]", body_style))

    # 13. Filing Checklist
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










