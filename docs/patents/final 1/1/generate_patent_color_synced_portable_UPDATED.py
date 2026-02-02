#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, importlib.util, zipfile, re
from pathlib import Path
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics import renderPDF

def log(m): print(f"[sync] {m}")

def load_fig_module(p: Path):
    spec = importlib.util.spec_from_file_location("nbmf_figs", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    funcs = getattr(mod, "FIG_FUNCS", [])
    caps = getattr(mod, "FIG_CAPTIONS", [])
    details = getattr(mod, "FIG_DETAILS", [])
    if not funcs or not caps:
        raise RuntimeError("FIG_FUNCS or FIG_CAPTIONS missing in figure module")
    return funcs, caps, details

def parse_claims(md: str):
    md = md.replace("\r\n","\n").replace("\r","\n")
    claims = []
    blocks = list(re.finditer(r"^###\s*Claim\s*(\d+)\s*:(.*)$", md, flags=re.M))
    if blocks:
        for i, m in enumerate(blocks):
            num = int(m.group(1)); start = m.end(); end = blocks[i+1].start() if i+1<len(blocks) else len(md)
            body = re.sub(r"\s+", " ", md[start:end].strip())
            title = m.group(2).strip()
            claims.append(f"{num}. {title} — {body}")
        return claims
    for ln in md.splitlines():
        m = re.match(r"^\s*(\d+)\.\s*(.+)", ln.strip())
        if m: claims.append(f"{m.group(1)}. {m.group(2)}")
    return claims

def claims_from_zip(zp: Path):
    import zipfile
    with zipfile.ZipFile(str(zp), "r") as z:
        for name in z.namelist():
            if name.lower().endswith("claims_draft.md"):
                return parse_claims(z.read(name).decode("utf-8", errors="ignore"))
        for name in z.namelist():
            if name.lower().endswith(".md"):
                c = parse_claims(z.read(name).decode("utf-8", errors="ignore"))
                if c: return c
    return []

BASELINE_20 = [
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fig-module", default="generate_patent_color.py")
    ap.add_argument("--zip", default=None, help="Optional PPA zip containing CLAIMS_DRAFT.md")
    args = ap.parse_args()

    base = Path(__file__).resolve().parent
    fig_path = (base / args.fig_module).resolve()
    if not fig_path.exists():
        raise FileNotFoundError(f"Figure module not found: {fig_path}")
    funcs, caps, details = load_fig_module(fig_path)
    log(f"Using figure module: {fig_path}")

    # Claims
    claims = []
    if args.zip:
        zp = Path(args.zip).expanduser().resolve()
        if zp.exists():
            claims = claims_from_zip(zp)
    if not claims and (base / "CLAIMS_DRAFT.md").exists():
        claims = parse_claims((base / "CLAIMS_DRAFT.md").read_text(encoding="utf-8", errors="ignore"))
    if not claims:
        claims = BASELINE_20[:]
    (base / "CLAIMS_SYNCED.txt").write_text("\n".join(claims), encoding="utf-8")

    # PDF skeleton
    styles = getSampleStyleSheet()
    S_TITLE = styles['Title']
    S_H1 = ParagraphStyle(name='H1', parent=styles['Heading1'], spaceBefore=12, spaceAfter=8)
    S_BODY = ParagraphStyle(name='Body', parent=styles['BodyText'], leading=13, spaceAfter=6)
    S_CAP = ParagraphStyle(name='Cap', parent=styles['BodyText'], alignment=1, fontName='Times-Italic', fontSize=9, spaceAfter=6)

    BRIEF = [
        "FIG. 1 illustrates a three-tier NBMF memory governed by eDNA with promotion/eviction routing.",
        "FIG. 2 shows tier thresholds and validation for safe promotions.",
        "FIG. 3 depicts L2 quarantine with consensus/divergence scoring and outcomes.",
        "FIG. 4 shows dual-mode encoding converging into NBMF bytecode.",
        "FIG. 5 depicts Merkle-notarized lineage for auditable history.",
        "FIG. 6 illustrates Genome, Epigenome, Lineage, and Immune components.",
        "FIG. 7 shows detect–quarantine–rollback defense loop.",
        "FIG. 8 shows dynamic CPU/GPU/TPU routing via a tensor router.",
        "FIG. 9 shows cross-tenant isolation with sanitized artifacts."
    ]

    out_pdf = base / "NBMF_Patent_Application_COLOR_SYNCED.pdf"
    from reportlab.platypus import SimpleDocTemplate, PageBreak, Table, TableStyle
    doc = SimpleDocTemplate(str(out_pdf), pagesize=LETTER,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.8*inch, bottomMargin=0.8*inch)
    story = []
    story.append(Paragraph("<b>PROVISIONAL PATENT APPLICATION</b>", S_TITLE))
    story.append(Paragraph("<b>Title:</b> Neural-Backed Memory Fabric with Enterprise Digital DNA (NBMF-eDNA)", S_H1))
    story.append(Paragraph("<b>Inventor:</b> Masoud Masoori — Richmond Hill, Ontario, Canada", S_BODY))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Brief Description of the Drawings</b>", S_H1))
    for line in BRIEF:
        story.append(Paragraph("• " + line, S_BODY))

    story.append(PageBreak())
    story.append(Paragraph("<b>Detailed Description</b>", S_H1))

    def center(drawing, width=6.25*inch):
        t = Table([[drawing]], colWidths=[width])
        t.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")]))
        return t

    for i, fn in enumerate(funcs, start=1):
        d = fn()
        story.append(center(d))
        story.append(Paragraph(caps[i-1], S_CAP))
        if details and len(details) >= i:
            story.append(Paragraph(details[i-1], S_BODY))
        else:
            story.append(Paragraph(BRIEF[i-1], S_BODY))
        story.append(Spacer(1, 6))

    story.append(PageBreak())
    story.append(Paragraph("<b>Claims</b>", S_H1))
    for c in claims:
        story.append(Paragraph(c, S_BODY))

    doc.build(story)
    log(f"Wrote: {out_pdf}")

if __name__ == "__main__":
    main()
