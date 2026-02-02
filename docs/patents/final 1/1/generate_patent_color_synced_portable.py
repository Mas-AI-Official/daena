#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NBMF Provisional Package Builder (Portable)
- No hard-coded /mnt/data paths
- Looks for `generate_patent_color.py` next to this script or in parent
- Optionally accepts: --zip PPA_*.zip  --fig-module path/to/generate_patent_color.py
- Outputs (in current folder):
    NBMF_Patent_Application_COLOR_SYNCED.pdf
    NBMF_eDNA_PPA_COLOR_SYNCED.zip
"""
import argparse, importlib.util, sys, zipfile, io, re, os
from pathlib import Path

# --- Dependency check ---
try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.graphics import renderPDF
except Exception as e:
    print("ReportLab is required. Install with:  pip install reportlab")
    raise

def log(msg): print(f"[sync] {msg}")

def find_fig_module(base: Path, user_arg: str | None) -> Path | None:
    if user_arg:
        p = Path(user_arg).expanduser().resolve()
        return p if p.exists() else None
    candidates = [
        base / "generate_patent_color.py",
        base.parent / "generate_patent_color.py",
        base / "figures" / "generate_patent_color.py",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return None

def load_figs(fig_path: Path):
    spec = importlib.util.spec_from_file_location("nbmf_figs", str(fig_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    # Sanitize captions (strip TODO)
    caps = [c.replace("TODO","").replace("todo","").strip() for c in getattr(mod, "FIG_CAPTIONS", [])]
    funcs = getattr(mod, "FIG_FUNCS", [])
    if not funcs or not caps:
        raise RuntimeError("FIG_FUNCS or FIG_CAPTIONS missing in figure module")
    return funcs, caps

def parse_claims_from_md(md_text: str) -> list[str]:
    # Prefer "### Claim N:" blocks with lettered subparts
    md_text = md_text.replace("\r\n","\n").replace("\r","\n")
    claims = []
    blocks = list(re.finditer(r"^###\s*Claim\s*(\d+)\s*:(.*)$", md_text, flags=re.M))
    if blocks:
        for i, m in enumerate(blocks):
            num = int(m.group(1))
            start = m.end()
            end = blocks[i+1].start() if i+1<len(blocks) else len(md_text)
            body = md_text[start:end].strip()
            # Condense whitespace
            body = re.sub(r"\n{2,}", " ", body)
            body = re.sub(r"\s+", " ", body).strip()
            title = m.group(2).strip()
            claims.append(f"{num}. {title} — {body}")
        return claims
    # Fallback: numbered lines like "1. text"
    numbered = []
    for ln in md_text.splitlines():
        m = re.match(r"^\s*(\d+)\.\s*(.+)", ln.strip())
        if m:
            numbered.append(f"{m.group(1)}. {m.group(2)}")
    return numbered

def extract_claims_from_zip(zip_path: Path) -> list[str]:
    claims = []
    with zipfile.ZipFile(str(zip_path), "r") as z:
        # Try CLAIMS_DRAFT.md first
        md_name = None
        for name in z.namelist():
            if name.lower().endswith("claims_draft.md"):
                md_name = name; break
        if md_name:
            md = z.read(md_name).decode("utf-8", errors="ignore")
            claims = parse_claims_from_md(md)
            if claims: return claims
        # Try any .md
        for name in z.namelist():
            if name.lower().endswith(".md"):
                md = z.read(name).decode("utf-8", errors="ignore")
                claims = parse_claims_from_md(md)
                if claims: return claims
    return claims

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

def find_claims(base: Path, zip_arg: str | None) -> list[str]:
    # Priority: explicit --zip; then any PPA*.zip; then local CLAIMS_DRAFT.md; then baseline
    if zip_arg:
        zp = Path(zip_arg).expanduser().resolve()
        if zp.exists():
            cl = extract_claims_from_zip(zp)
            if cl: return cl
    for cand in sorted(base.glob("*.zip")):
        if "ppa" in cand.name.lower() or "nbmf" in cand.name.lower():
            cl = extract_claims_from_zip(cand)
            if cl: return cl
    md_file = base / "CLAIMS_DRAFT.md"
    if md_file.exists():
        cl = parse_claims_from_md(md_file.read_text(encoding="utf-8", errors="ignore"))
        if cl: return cl
    return BASELINE_20[:]

def build_pdf(out_pdf: Path, fig_funcs, fig_caps, claims: list[str]):
    styles = getSampleStyleSheet()
    S_TITLE = styles['Title']
    S_H1 = ParagraphStyle(name='H1', parent=styles['Heading1'], spaceBefore=12, spaceAfter=8)
    S_H2 = ParagraphStyle(name='H2', parent=styles['Heading2'], spaceBefore=10, spaceAfter=6)
    S_BODY = ParagraphStyle(name='Body', parent=styles['BodyText'], leading=13, spaceAfter=6)
    S_CAP = ParagraphStyle(name='Cap', parent=styles['BodyText'], alignment=1, fontName='Times-Italic', fontSize=9, spaceAfter=12)

    BRIEF_LINES = [
        "FIG. 1 illustrates a three-tier NBMF memory (L1/L2/L3) under an eDNA governance banner with a policy-aware router orchestrating promotion and eviction.",
        "FIG. 2 shows promotion/eviction thresholds and decision signals, including access frequency, recency, and trust, with L2Q intake gatekeeping.",
        "FIG. 3 depicts the L2Q trust pipeline, multi-model consensus, divergence analysis, and final routing to promotion or sanitization.",
        "FIG. 4 shows dual-mode encoding (lossless and semantic) resulting in NBMF bytecode with rich metadata for provenance and policy.",
        "FIG. 5 depicts Merkle-notarized lineage for promotion and eviction events with proof paths to a root for auditability.",
        "FIG. 6 illustrates the eDNA’s Genome, Epigenome (ABAC/retention), Lineage, and Immune components driving NBMF policy.",
        "FIG. 7 shows the Immune workflow (detections, actions, state) and its interactions with NBMF tiers.",
        "FIG. 8 shows device routing and hardware abstraction (CPU/GPU/TPU) via a Tensor Router and DeviceManager.",
        "FIG. 9 shows cross-tenant learning through sanitized artifacts and reusable pattern repositories without raw data sharing.",
    ]

    def center(drawing, width=6.25*inch):
        t = Table([[drawing]], colWidths=[width])
        t.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")]))
        return t

    doc = SimpleDocTemplate(str(out_pdf), pagesize=LETTER,
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

    # Cross-ref index (heuristic)
    XREF = {
        1: [1], 2: [3], 3: [5], 4: [4], 5: [1,3], 6: [7], 7: [6], 8: [8],
        9: [1,2,3,5], 10:[1,2,3,5], 11:[9], 12:[2], 13:[1,2], 14:[1,8],
        15:[5], 16:[6], 17:[3,4], 18:[2], 19:[5], 20:[3]
    }
    story.append(Paragraph("<b>Cross-Reference Index (Claims to Figures)</b>", S_H1))
    for c in claims:
        try:
            claim_no = int(c.split(".",1)[0])
        except Exception:
            claim_no = None
        figs = ", ".join([f"FIG. {i}" for i in XREF.get(claim_no, [])]) if claim_no else "—"
        story.append(Paragraph(f"Claim {claim_no} ↔ {figs}", S_BODY))

    story.append(PageBreak())
    story.append(Paragraph("<b>Detailed Description</b>", S_H1))
    for idx, fn in enumerate(fig_funcs, start=1):
        d = fn()
        story.append(center(d))
        story.append(Paragraph(fig_caps[idx-1], S_CAP))
        story.append(Paragraph(BRIEF_LINES[idx-1], S_BODY))

    story.append(PageBreak())
    story.append(Paragraph("<b>Claims</b>", S_H1))
    for c in claims:
        story.append(Paragraph(c, S_BODY))

    doc.build(story)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", dest="zip_path", default=None, help="Path to PPA zip containing CLAIMS_DRAFT.md (optional)")
    parser.add_argument("--fig-module", dest="fig_module", default=None, help="Path to generate_patent_color.py (optional)")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    out_pdf = base / "NBMF_Patent_Application_COLOR_SYNCED.pdf"
    out_zip = base / "NBMF_eDNA_PPA_COLOR_SYNCED.zip"
    fig_dir = base / "figures_synced"
    fig_dir.mkdir(exist_ok=True)

    # Load figure functions
    fig_path = find_fig_module(base, args.fig_module)
    if not fig_path:
        raise FileNotFoundError("generate_patent_color.py not found. Put it next to this script or pass --fig-module PATH")
    log(f"Using figure module: {fig_path}")
    fig_funcs, fig_caps = load_figs(fig_path)

    # Claims
    claims = find_claims(base, args.zip_path)
    if not claims:
        claims = BASELINE_20[:]
    log(f"Using {len(claims)} claim(s).")

    # Write a claims txt for reference
    (base / "CLAIMS_SYNCED.txt").write_text("\n".join(claims), encoding="utf-8")

    # Render figures to standalone PDFs
    paths = []
    try:
        for idx, fn in enumerate(fig_funcs, start=1):
            d = fn()
            p = fig_dir / f"FIG{idx:02d}.pdf"
            renderPDF.drawToFile(d, str(p), f"FIG {idx}")
            paths.append(p)
    except Exception as e:
        log(f"Warning: figure PDFs not rendered: {e}")

    # Build spec PDF
    build_pdf(out_pdf, fig_funcs, fig_caps, claims)
    log(f"Wrote PDF: {out_pdf}")

    # Build delivery ZIP
    with zipfile.ZipFile(str(out_zip), "w") as z:
        z.write(str(out_pdf), arcname="01_SPECIFICATION_SYNCED.pdf")
        z.write(str(base / "CLAIMS_SYNCED.txt"), arcname="03_CLAIMS/CLAIMS_SYNCED.txt")
        for p in paths:
            z.write(str(p), arcname=f"05_FIGURES/{p.name}")
    log(f"Wrote ZIP: {out_zip}")

if __name__ == "__main__":
    main()
