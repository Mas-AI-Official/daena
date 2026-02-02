
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.graphics import renderPDF
import os, zipfile, importlib.util, sys

FIG_MODULE_PATH = "/mnt/data/generate_patent_color.py"

spec = importlib.util.spec_from_file_location("nbmf_figs", FIG_MODULE_PATH)
nbmf_figs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nbmf_figs)

OUT_PDF = "/mnt/data/NBMF_Patent_Application_COLOR_SYNCED.pdf"
ZIP_PATH = "/mnt/data/NBMF_eDNA_PPA_COLOR_SYNCED.zip"
FIG_DIR = "/mnt/data/figures_synced"
os.makedirs(FIG_DIR, exist_ok=True)

styles = getSampleStyleSheet()
S_TITLE = styles['Title']
S_H1 = ParagraphStyle(name='H1', parent=styles['Heading1'], spaceBefore=12, spaceAfter=8)
S_H2 = ParagraphStyle(name='H2', parent=styles['Heading2'], spaceBefore=10, spaceAfter=6)
S_BODY = ParagraphStyle(name='Body', parent=styles['BodyText'], leading=13, spaceAfter=6)
S_CAP = ParagraphStyle(name='Cap', parent=styles['BodyText'], alignment=1, fontName='Times-Italic', fontSize=9, spaceAfter=12)

FIG_FUNCS = nbmf_figs.FIG_FUNCS
FIG_CAPTIONS = [c.replace('TODO','').replace('todo','').strip() for c in nbmf_figs.FIG_CAPTIONS]

FINAL_CLAIMS = ["No claims parsed from CLAIMS_DRAFT.md; using baseline inside script."] or [
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

XREF = {
    1: [1], 2: [3], 3: [5], 4: [4], 5: [1,3], 6: [7], 7: [6], 8: [8],
    9: [1,2,3,5], 10:[1,2,3,5], 11:[9], 12:[2], 13:[1,2], 14:[1,8],
    15:[5], 16:[6], 17:[3,4], 18:[2], 19:[5], 20:[3]
}

BRIEF_LINES = [
    "FIG. 1 illustrates a three-tier NBMF memory (L1/L2/L3) under an eDNA governance banner with a policy-aware router orchestrating promotion and eviction.",
    "FIG. 2 shows promotion/eviction thresholds and decision signals, including access frequency, recency, and trust, with L2Q intake gatekeeping.",
    "FIG. 3 depicts the L2Q trust pipeline, multi-model consensus, divergence analysis, and final routing to promotion or sanitization.",
    "FIG. 4 shows dual-mode encoding (lossless and semantic) resulting in NBMF bytecode with rich metadata for provenance and policy.",
    "FIG. 5 depicts Merkle-notarized lineage for promotion and eviction events with proof paths to a root for auditability.",
    "FIG. 6 illustrates the eDNA’s Genome, Epigenome (ABAC/retention), Lineage, and Immune components driving NBMF policy.",
    "FIG. 7 shows the Immune workflow (detections, actions, state) and its interactions with NBMF tiers.",
    "FIG. 8 shows device routing and hardware abstraction (CPU/GPU/TPU) via a Tensor Router and DeviceManager.",
    "FIG. 9 shows cross-tenant learning through sanitized artifacts and reusable pattern repositories without raw data sharing."
]

def center(drawing, width=6.25*inch):
    t = Table([[drawing]], colWidths=[width])
    t.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")]))
    return t

def render_figures_to_pdfs():
    paths = []
    for idx, fn in enumerate(FIG_FUNCS, start=1):
        d = fn()
        fig_path = os.path.join("/mnt/data", f"figures_synced/FIG{idx:02d}.pdf")
        renderPDF.drawToFile(d, fig_path, f"FIG {idx}")
        paths.append(fig_path)
    return paths

def build_pdf(fig_paths):
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
        "A system and method for a Neural-Backed Memory Fabric (NBMF) integrated with an Enterprise Digital DNA (eDNA) governance layer.", S_BODY))

    story.append(Paragraph("<b>Brief Description of the Drawings</b>", S_H1))
    for line in BRIEF_LINES:
        story.append(Paragraph("• " + line, S_BODY))

    story.append(Paragraph("<b>Cross-Reference Index (Claims to Figures)</b>", S_H1))
    for c in FINAL_CLAIMS:
        try:
            claim_no = int(c.split(".",1)[0])
        except Exception:
            claim_no = None
        figs = ", ".join([f"FIG. {i}" for i in XREF.get(claim_no, [])]) if claim_no else "—"
        story.append(Paragraph(f"Claim {claim_no} ↔ {figs}", S_BODY))

    story.append(PageBreak())
    story.append(Paragraph("<b>Detailed Description</b>", S_H1))
    for idx, fn in enumerate(FIG_FUNCS, start=1):
        d = fn()
        story.append(center(d))
        story.append(Paragraph(FIG_CAPTIONS[idx-1], S_CAP))
        story.append(Paragraph(BRIEF_LINES[idx-1], S_BODY))

    story.append(PageBreak())
    story.append(Paragraph("<b>Claims</b>", S_H1))
    for c in FINAL_CLAIMS:
        story.append(Paragraph(c, S_BODY))

    doc.build(story)

def main():
    paths = render_figures_to_pdfs()
    build_pdf(paths)
    with open("/mnt/data/CLAIMS_SYNCED.txt", "w", encoding="utf-8") as f:
        for c in FINAL_CLAIMS:
            f.write(c + "\n")
    with zipfile.ZipFile(ZIP_PATH, 'w') as z:
        z.write(OUT_PDF, arcname="01_SPECIFICATION_SYNCED.pdf")
        z.write("/mnt/data/CLAIMS_SYNCED.txt", arcname="03_CLAIMS/CLAIMS_SYNCED.txt")
        for p in paths:
            z.write(p, arcname=f"05_FIGURES/{os.path.basename(p)}")

if __name__ == "__main__":
    main()
