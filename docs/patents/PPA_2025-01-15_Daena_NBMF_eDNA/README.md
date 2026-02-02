---
title: "PPA Kit Readme"
date: 2025-01-15
lastmod: 2025-01-15
inventor: "Masoud Masoori"
assignee: "Mas-AI Technology Inc."
status: "Draft – For Provisional Filing"
---

# Provisional Patent Application Kit - Readme

## Overview

This directory contains a complete Provisional Patent Application (PPA) kit for the Neural-Backed Memory Fabric (NBMF) and Enterprise-DNA (eDNA) governance system. All files are dated 2025-01-15 and ready for USPTO filing.

## Directory Structure

```
PPA_2025-01-15_Daena_NBMF_eDNA/
├── ABSTRACT.md
├── SPECIFICATION.md
├── CLAIMS_DRAFT.md
├── FIGURE_LIST.md
├── MICRO_SPEC_ONEPAGER.md
├── FILING_CHECKLIST_USPTO_MICRO.md
├── METADATA.yml
├── README.md (this file)
├── SANITIZATION_LOG.md
├── figures/
│   ├── fig1_system_overview.svg
│   ├── fig2_tier_pipeline.svg
│   ├── fig3_merkle_lineage.svg
│   ├── fig4_genome_epigenome.svg
│   ├── fig5_immune_flow.svg
│   ├── fig6_hardware_abstraction.svg
│   └── fig7_cross_tenant_learning.svg
└── benchmarks/
    ├── methodology.md
    ├── environment.md
    ├── results_2025-01-15.csv
    └── summary.md
```

## Exporting to PDF

### Option 1: Using Pandoc (Recommended)

```bash
# Install pandoc if not already installed
# Windows: choco install pandoc
# Mac: brew install pandoc
# Linux: sudo apt-get install pandoc

# Convert Markdown to PDF
pandoc ABSTRACT.md -o ABSTRACT.pdf
pandoc SPECIFICATION.md -o SPECIFICATION.pdf
pandoc CLAIMS_DRAFT.md -o CLAIMS_DRAFT.pdf
# ... repeat for all .md files
```

### Option 2: Using Markdown to PDF Tools

- **Markdown PDF** (VS Code extension)
- **Typora** (export to PDF)
- **Online converters** (e.g., markdowntopdf.com)

### Option 3: Print to PDF

1. Open each Markdown file in a Markdown viewer
2. Print to PDF (Ctrl+P / Cmd+P)
3. Save with appropriate filename

## Exporting SVG Figures

### Option 1: Using Inkscape (Recommended)

```bash
# Install Inkscape
# Windows: Download from inkscape.org
# Mac: brew install inkscape
# Linux: sudo apt-get install inkscape

# Convert SVG to PDF
inkscape figures/fig1_system_overview.svg --export-filename=FIG.1.pdf
inkscape figures/fig2_tier_pipeline.svg --export-filename=FIG.2.pdf
# ... repeat for all figures
```

### Option 2: Using Online Converters

- Upload SVG to online converter (e.g., cloudconvert.com)
- Convert to PDF
- Download and rename to FIG.1.pdf, FIG.2.pdf, etc.

### Option 3: Using Browser

1. Open SVG file in web browser
2. Print to PDF (Ctrl+P / Cmd+P)
3. Save as FIG.1.pdf, FIG.2.pdf, etc.

### Renaming Figures

After export, rename figures to match USPTO conventions:
- `fig1_system_overview.pdf` → `FIG.1.pdf`
- `fig2_tier_pipeline.pdf` → `FIG.2.pdf`
- `fig3_merkle_lineage.pdf` → `FIG.3.pdf`
- `fig4_genome_epigenome.pdf` → `FIG.4.pdf`
- `fig5_immune_flow.pdf` → `FIG.5.pdf`
- `fig6_hardware_abstraction.pdf` → `FIG.6.pdf`
- `fig7_cross_tenant_learning.pdf` → `FIG.7.pdf`

## Creating Single PDF for Filing

### Option 1: Using PDF Merge Tools

```bash
# Using pdftk (if installed)
pdftk CoverSheet.pdf ABSTRACT.pdf SPECIFICATION.pdf FIG.1.pdf FIG.2.pdf ... CLAIMS_DRAFT.pdf cat output PPA_COMPLETE.pdf

# Using Python (PyPDF2)
python merge_pdfs.py
```

### Option 2: Using Online Tools

- Upload all PDFs to PDF merge tool (e.g., ilovepdf.com)
- Merge in order:
  1. Cover Sheet (Form SB/16)
  2. Abstract
  3. Specification
  4. FIG.1 through FIG.7
  5. Claims (optional)
  6. Benchmarks (optional)

### Option 3: Using Adobe Acrobat

1. Open Adobe Acrobat
2. Tools → Combine Files
3. Add files in order
4. Create PDF

## What to Upload to USPTO

### Required Documents

1. **Cover Sheet (Form SB/16)**: Completed and signed
2. **Specification**: PDF of SPECIFICATION.md
3. **Drawings**: All 7 figures (FIG.1 through FIG.7) as PDFs or images
4. **Abstract**: PDF of ABSTRACT.md (recommended)

### Optional Documents

- **Claims**: PDF of CLAIMS_DRAFT.md (optional in provisional)
- **Benchmarks**: PDFs of benchmark documentation (supporting material)

### File Format Requirements

- **PDF**: Preferred format for all documents
- **Page Size**: 8.5" × 11" (US Letter)
- **Margins**: At least 1 inch on all sides
- **Font**: 12pt, readable font (Times New Roman, Arial, etc.)
- **Figures**: Clear, labeled, with reference numerals matching specification

## What NOT to Upload

### Do NOT Include

1. **Source Code**: No actual code implementations
2. **API Keys or Credentials**: All sanitized (see SANITIZATION_LOG.md)
3. **Customer Data**: No real customer or user data
4. **Internal Documentation**: Only patent-relevant material
5. **Marketing Materials**: Keep technical and functional
6. **Draft Versions**: Only final, dated versions (2025-01-15)

## Filing Process

1. **Prepare Documents**: Export all files to PDF
2. **Complete Cover Sheet**: Fill out Form SB/16
3. **Verify Micro Entity Status**: Complete Form PTO/SB/15A if applicable
4. **Create Single PDF**: Combine all documents (optional, or upload separately)
5. **File via EFS-Web**: Upload to USPTO Electronic Filing System
6. **Pay Filing Fee**: Micro Entity: $75 (verify current fee)
7. **Receive Confirmation**: Save application number and confirmation

## Important Notes

- **12-Month Window**: You have 12 months from filing date to convert to non-provisional
- **Priority Date**: Provisional filing date becomes priority date
- **Confidentiality**: Provisional applications are NOT published
- **Claims**: Optional in provisional but recommended for completeness
- **Dates**: All documents dated 2025-01-15 for consistency

## Verification Checklist

Before filing, verify:

- [ ] All files exported to PDF
- [ ] All figures exported and renamed (FIG.1 through FIG.7)
- [ ] Cover Sheet (Form SB/16) completed
- [ ] Micro Entity Certification (Form PTO/SB/15A) completed if applicable
- [ ] All dates are 2025-01-15
- [ ] No secrets or credentials present (check SANITIZATION_LOG.md)
- [ ] Reference numerals in figures match specification
- [ ] Single PDF created (or files ready for separate upload)
- [ ] Filing fee calculated and payment method ready

## Resources

- **USPTO Forms**: https://www.uspto.gov/forms
- **EFS-Web**: https://www.uspto.gov/patents/apply/efs-web
- **Fee Schedule**: https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule
- **Provisional Patent Guide**: https://www.uspto.gov/patents/basics/types-patent-applications/provisional-application-patent

## Support

For questions about this PPA kit:
- Review FILING_CHECKLIST_USPTO_MICRO.md for detailed filing instructions
- Review SPECIFICATION.md for technical details
- Review METADATA.yml for package information

---

**End of Readme**










