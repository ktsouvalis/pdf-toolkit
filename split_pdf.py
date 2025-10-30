#!/usr/bin/env python3
"""
Split PDFs using PyMuPDF (fitz).

Two modes:
- Split every N pages
- Split at specific 1-based page numbers (split points), e.g., 5,10 => [1-4], [5-9], [10-end]

Examples:
  python split_pdf.py input.pdf --every 3
  python split_pdf.py input.pdf --split-at 5,10 --outdir out

Install:
  pip install pymupdf
"""
import os
import argparse
from typing import List, Optional, Tuple


def _sanitize_split_points(points: List[int], total_pages: int) -> List[int]:
    # keep unique, sorted, within range 2..total_pages inclusive (1-based)
    uniq = sorted(set(p for p in points if 2 <= p <= total_pages))
    return uniq


def _compute_chunks_every(total_pages: int, every: int) -> List[Tuple[int, int]]:
    # return list of (start, end) page indices, 1-based inclusive
    chunks = []
    start = 1
    while start <= total_pages:
        end = min(total_pages, start + every - 1)
        chunks.append((start, end))
        start = end + 1
    return chunks


def _compute_chunks_split_points(total_pages: int, points: List[int]) -> List[Tuple[int, int]]:
    # points are 1-based split starts, meaning a new chunk starts at each point
    # Always start at 1; ensure points are sanitized and include <= total_pages
    pts = [p for p in _sanitize_split_points(points, total_pages) if p != 1]
    starts = [1] + pts
    chunks = []
    for i, s in enumerate(starts):
        e = (pts[i] - 1) if i < len(pts) else total_pages
        chunks.append((s, e))
    # Filter out any invalid ranges (can happen if a split at last page)
    chunks = [(a, b) for (a, b) in chunks if a <= b]
    return chunks


def split_pdf(
    input_path: str,
    outdir: str,
    every: Optional[int] = None,
    split_at: Optional[List[int]] = None,
    prefix: Optional[str] = None,
    progress_callback=None,
) -> List[str]:
    """
    Split a PDF into multiple parts.
    - If 'every' is provided (>0), split into fixed-size chunks.
    - Else if 'split_at' is provided (list of 1-based page starts), split at those points.
    Returns list of output file paths created.
    progress_callback: optional callable taking (current_part_index, total_parts)
    """
    # Delay import to allow --help to work even if fitz has issues on machine
    import fitz  # PyMuPDF

    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")
    os.makedirs(outdir, exist_ok=True)

    src = fitz.open(input_path)
    try:
        total_pages = src.page_count
        if total_pages == 0:
            return []
        if every is not None:
            if every <= 0:
                raise ValueError("--every must be a positive integer")
            chunks = _compute_chunks_every(total_pages, every)
        elif split_at:
            chunks = _compute_chunks_split_points(total_pages, split_at)
        else:
            raise ValueError("Specify either --every or --split-at")

        base = prefix if prefix else os.path.splitext(os.path.basename(input_path))[0]
        out_paths: List[str] = []

        for idx, (a1, b1) in enumerate(chunks, start=1):
            # convert 1-based inclusive to 0-based inclusive
            a0, b0 = a1 - 1, b1 - 1
            part = fitz.open()
            try:
                part.insert_pdf(src, from_page=a0, to_page=b0)
                out_name = f"{base}_part{idx:02d}.pdf"
                out_path = os.path.join(outdir, out_name)
                part.save(out_path, garbage=3, clean=True, deflate=True)
                out_paths.append(out_path)
            finally:
                part.close()

            if progress_callback:
                try:
                    progress_callback(idx, len(chunks))
                except Exception:
                    pass

        return out_paths
    finally:
        src.close()


def parse_split_points(arg: str) -> List[int]:
    pts: List[int] = []
    for token in arg.split(','):
        token = token.strip()
        if not token:
            continue
        try:
            pts.append(int(token))
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid page number: {token}")
    return pts


def main():
    ap = argparse.ArgumentParser(description="Split a PDF by fixed size or at specific pages.")
    ap.add_argument("input", help="Input PDF")
    ap.add_argument("--outdir", default=None, help="Output directory (default: alongside input)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--every", type=int, help="Split every N pages")
    mode.add_argument("--split-at", dest="split_at", type=parse_split_points, help="Comma-separated 1-based page numbers to start new parts, e.g. 5,10")
    ap.add_argument("--prefix", default=None, help="Output filename prefix (default: input basename)")
    args = ap.parse_args()

    outdir = args.outdir or os.path.dirname(os.path.abspath(args.input))
    created = split_pdf(
        input_path=args.input,
        outdir=outdir,
        every=args.every,
        split_at=args.split_at,
        prefix=args.prefix,
    )
    print(f"Created {len(created)} file(s):")
    for p in created:
        print(f"  {p}")


if __name__ == "__main__":
    main()
