#!/usr/bin/env python3
"""
Shrink scanned PDFs by rasterizing each page and re-embedding as JPEG.
Best for PDFs that are essentially one scanned photo per page.
Requires: PyMuPDF and Pillow

Install:
    pip install pymupdf pillow
"""

import os
import sys
import io
import argparse
import fitz  # PyMuPDF
from PIL import Image


def human(n: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024.0:
            return f"{n:,.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def compress_scanned_pdf(
    input_path: str,
    output_path: str,
    dpi: int = 150,
    quality: int = 60,
    grayscale: bool = False,
    optimize: bool = True,
    clean: bool = True,
    progress_callback=None,
):
    """
    Re-rasterize each page to an image and rebuild the PDF with JPEG-compressed pages.
    Intended for scanned PDFs (image per page).

    progress_callback: optional callable taking (current_page: int, total_pages: int)
    """
    src = fitz.open(input_path)
    out = fitz.open()
    try:
        # copy basic metadata (ignore failures)
        try:
            out.set_metadata(src.metadata or {})
        except Exception:
            pass

        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        cs = fitz.csGRAY if grayscale else fitz.csRGB

        total_pages = src.page_count
        for i in range(1, total_pages + 1):
            page = src.load_page(i - 1)
            rect = page.rect
            pix = page.get_pixmap(matrix=mat, colorspace=cs, alpha=False)

            # Convert to PIL Image for JPEG compression
            mode = "L" if grayscale else "RGB"
            img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            img_bytes = buf.getvalue()
            buf.close()

            # Create new page with same physical size and place the JPEG
            new_page = out.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(rect, stream=img_bytes)

            # Progress
            if progress_callback:
                try:
                    progress_callback(i, total_pages)
                except Exception:
                    pass
            print(f"Processed page {i}/{total_pages}", file=sys.stderr)

        save_kwargs = {
            "garbage": 4 if optimize else 1,
            "deflate": True,
            "clean": clean,
            "expand": False,
        }
        out.save(output_path, **save_kwargs)
    finally:
        src.close()
        out.close()


def main():
    ap = argparse.ArgumentParser(description="Shrink scanned PDFs by re-rasterizing pages as JPEG.")
    ap.add_argument("input", help="Input PDF")
    ap.add_argument("output", nargs="?", help="Output PDF (default: <input>.shrink.pdf)")
    ap.add_argument("--dpi", type=int, default=150, help="Render DPI (default: 150)")
    ap.add_argument("--quality", type=int, default=60, help="JPEG quality 1-100 (default: 60)")
    ap.add_argument("--grayscale", action="store_true", help="Convert pages to grayscale")
    ap.add_argument("--light", action="store_true", help="Preset: dpi=200, quality=75 (larger, better)")
    ap.add_argument("--medium", action="store_true", help="Preset: dpi=150, quality=60 (balanced)")
    ap.add_argument("--aggressive", action="store_true", help="Preset: dpi=120, quality=50 (smaller, lossy)")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    # Apply presets
    if args.light:
        args.dpi, args.quality = 200, 75
    if args.medium:
        args.dpi, args.quality = 150, 60
    if args.aggressive:
        args.dpi, args.quality = 120, 50

    output = args.output or os.path.splitext(args.input)[0] + ".shrink.pdf"

    before = os.path.getsize(args.input)
    compress_scanned_pdf(
        input_path=args.input,
        output_path=output,
        dpi=args.dpi,
        quality=args.quality,
        grayscale=args.grayscale,
    )
    after = os.path.getsize(output)
    saved = before - after
    ratio = after / before if before > 0 else 0

    print(f"\nInput : {args.input} ({human(before)})")
    print(f"Output: {output} ({human(after)})")
    print(f"Saved : {human(saved)}  ({(1 - ratio) * 100:.1f}% reduction)")


if __name__ == "__main__":
    main()
