# PDF Subsection Splitter

This repo includes a script to split full-book PDFs into subsection PDFs (e.g., `1.1.pdf`, `1.2.pdf`) organized under `Unit X/` folders. It uses the PDF's existing bookmarks/outline to determine page ranges.

## Requirements

- Python 3.10+
- `pikepdf` (install with `python -m pip install pikepdf`)

## Usage

Split one or more PDFs:

```
python scripts/split_pdf_by_bookmarks.py \
  "Basic Engineering Circuit Analysis/Basic-Engineering-Circuit-Analysis.pdf" \
  "Java How to Program, Early Objects, 11th Edition/Java How to Program 11th Early Objects.pdf"
```

By default, output folders are created alongside each PDF:

```
Basic Engineering Circuit Analysis/Unit 1/1.1.pdf
Basic Engineering Circuit Analysis/Unit 1/1.2.pdf
...
```

Optional flags:

- `--output-dir /path/to/output` (base output folder)
- `--report split_report.json` (summary report path)
- `--dry-run` (no files written)
- `--overwrite` (replace existing files)

## Naming Rules

- Subsections are recognized by bookmark titles that start with `X.Y` (e.g., `1.1`, `10.2`).
- Output folder: `Unit X`
- Output filename: `X.Y.pdf`

## Missing or Non-Standard Bookmarks

If a PDF has no usable bookmarks or the section titles do not follow `X.Y`, the report will record the gap. Fallback options:

- Add manual bookmarks in a PDF editor
- Use OCR + TOC parsing to generate a synthetic outline

