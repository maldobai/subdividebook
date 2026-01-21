#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import pikepdf


SECTION_RE = re.compile(r"^(?P<section>\d+\.\d+)\b")


@dataclass
class Bookmark:
    title: str
    page_index: int
    order: int


@dataclass
class SplitResult:
    pdf_path: str
    sections_created: List[str]
    sections_skipped: List[dict]
    warnings: List[str]


def iter_outline_items(items: Iterable) -> Iterable:
    for item in items:
        yield item
        children = getattr(item, "children", None)
        if children:
            yield from iter_outline_items(children)


def resolve_page_index(pdf: pikepdf.Pdf, item) -> Optional[int]:
    destination = getattr(item, "destination", None)
    if destination is None:
        action = getattr(item, "action", None)
        if action and "/D" in action:
            destination = action["/D"]

    if destination is None:
        return None

    try:
        if isinstance(destination, (list, tuple, pikepdf.Array)):
            target = destination[0]
        else:
            target = destination
        return pdf.pages.index(target)
    except Exception:
        return None


def collect_bookmarks(pdf: pikepdf.Pdf) -> List[Bookmark]:
    outline = pdf.open_outline()
    if outline is None:
        return []

    bookmarks: List[Bookmark] = []
    order = 0
    for item in iter_outline_items(outline.root):
        title = (getattr(item, "title", "") or "").strip()
        page_index = resolve_page_index(pdf, item)
        if page_index is None:
            continue
        bookmarks.append(Bookmark(title=title, page_index=page_index, order=order))
        order += 1
    bookmarks.sort(key=lambda b: (b.page_index, b.order))
    return bookmarks


def split_pdf(
    pdf_path: Path,
    output_dir: Path,
    report: SplitResult,
    dry_run: bool = False,
    overwrite: bool = False,
) -> None:
    with pikepdf.open(pdf_path) as pdf:
        bookmarks = collect_bookmarks(pdf)
        if not bookmarks:
            report.warnings.append(
                "No usable bookmarks found. Fallback: add manual bookmarks or use OCR+TOC parsing."
            )
            return

        last_page_index = len(pdf.pages) - 1

        for idx, bookmark in enumerate(bookmarks):
            match = SECTION_RE.match(bookmark.title)
            if not match:
                continue

            section_id = match.group("section")
            unit_id = section_id.split(".")[0]
            unit_dir = output_dir / f"Unit {unit_id}"
            output_path = unit_dir / f"{section_id}.pdf"

            next_start = None
            for next_bookmark in bookmarks[idx + 1 :]:
                if next_bookmark.page_index > bookmark.page_index:
                    next_start = next_bookmark.page_index
                    break

            end_page = (next_start - 1) if next_start is not None else last_page_index
            if end_page < bookmark.page_index:
                report.sections_skipped.append(
                    {
                        "section": section_id,
                        "reason": "Non-increasing page numbers; ambiguous section range.",
                        "title": bookmark.title,
                    }
                )
                continue

            if output_path.exists() and not overwrite:
                report.sections_skipped.append(
                    {
                        "section": section_id,
                        "reason": "Output already exists. Use --overwrite to replace.",
                        "title": bookmark.title,
                    }
                )
                continue

            report.sections_created.append(str(output_path))
            if dry_run:
                continue

            unit_dir.mkdir(parents=True, exist_ok=True)
            new_pdf = pikepdf.Pdf.new()
            for page in pdf.pages[bookmark.page_index : end_page + 1]:
                new_pdf.pages.append(page)
            new_pdf.save(output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split PDFs into subsection files based on bookmarks."
    )
    parser.add_argument(
        "pdfs",
        nargs="+",
        type=Path,
        help="One or more PDF paths to split.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Base output directory. Defaults to each PDF's parent directory.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("split_report.json"),
        help="Path to write JSON summary report.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be created.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    results: List[SplitResult] = []

    for pdf_path in args.pdfs:
        if not pdf_path.exists():
            print(f"Missing file: {pdf_path}", file=sys.stderr)
            continue

        output_dir = args.output_dir or pdf_path.parent
        report = SplitResult(
            pdf_path=str(pdf_path),
            sections_created=[],
            sections_skipped=[],
            warnings=[],
        )
        try:
            split_pdf(
                pdf_path=pdf_path,
                output_dir=output_dir,
                report=report,
                dry_run=args.dry_run,
                overwrite=args.overwrite,
            )
        except Exception as exc:
            report.warnings.append(f"Failed to process PDF: {exc}")

        results.append(report)

    summary = {"results": [result.__dict__ for result in results]}
    args.report.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    for result in results:
        print(f"PDF: {result.pdf_path}")
        print(f"  Sections created: {len(result.sections_created)}")
        if result.sections_skipped:
            print("  Sections skipped:")
            for item in result.sections_skipped:
                print(f"    - {item['section']}: {item['reason']}")
        if result.warnings:
            print("  Warnings:")
            for warning in result.warnings:
                print(f"    - {warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
