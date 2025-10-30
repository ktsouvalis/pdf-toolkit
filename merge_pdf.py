#!/usr/bin/env python3
"""
Merge multiple PDFs into one using PyMuPDF (fitz).

Examples:
  python merge_pdf.py output.pdf input1.pdf input2.pdf input3.pdf

Install:
  pip install pymupdf
"""
from __future__ import annotations
import os
import argparse
import sys
from typing import Iterable, List


def merge_pdfs(
    inputs: Iterable[str],
    output: str,
    progress_callback=None,
) -> str:
    """
    Merge input PDFs in the given order into 'output'. Returns the output path.
    progress_callback: optional callable taking (current_index: int, total: int)
    """
    import fitz  # delay import so --help works even if fitz has issues

    in_paths: List[str] = [p for p in inputs if p and p.strip()]
    if len(in_paths) < 2:
        raise ValueError("Need at least two input PDFs to merge.")
    for p in in_paths:
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Input not found: {p}")
        try:
            if os.path.getsize(p) <= 0:
                raise ValueError(f"Input is empty: {p}")
        except OSError:
            raise FileNotFoundError(f"Cannot stat input: {p}")

    out_dir = os.path.dirname(os.path.abspath(output)) or os.getcwd()
    os.makedirs(out_dir, exist_ok=True)

    out_doc = fitz.open()
    first_meta_set = False
    try:
        total = len(in_paths)
        for i, path in enumerate(in_paths, 1):
            src = fitz.open(path)
            try:
                if not first_meta_set:
                    try:
                        out_doc.set_metadata(src.metadata or {})
                    except Exception:
                        pass
                    first_meta_set = True
                out_doc.insert_pdf(src)
            finally:
                src.close()

            if progress_callback:
                try:
                    progress_callback(i, total)
                except Exception:
                    pass

        out_doc.save(output, garbage=3, clean=True, deflate=True)
        return output
    finally:
        out_doc.close()


def main():
    ap = argparse.ArgumentParser(description="Merge multiple PDFs into one.")
    ap.add_argument("output", help="Output PDF path")
    ap.add_argument("inputs", nargs='+', help="Input PDF paths (2 or more)")
    args = ap.parse_args()

    out_path = os.path.abspath(args.output)
    try:
        result = merge_pdfs(args.inputs, out_path)
        print(f"Created: {result}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
